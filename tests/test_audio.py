"""Voice-over, captions, music and the voice guard — on fake ElevenLabs and Muse servers."""

import base64
import json
import wave
from types import SimpleNamespace as NS

import httpx
import pytest

from whynot.agency.video import soundtrack
from whynot.agents.brief import Scene, VideoBrief
from whynot.audio.captions import Word, to_wav16k, word_error_rate, words
from whynot.audio.elevenlabs import ElevenLabs, ElevenLabsError
from whynot.models import ModelClient

KEY = "sk_eleven_SECRET_123"


def silent_mp3(tmp_path, seconds=1.0):
    """A real (silent) MP3 made with ffmpeg, so decoding paths are exercised."""
    import subprocess

    import imageio_ffmpeg
    out = tmp_path / "silence.mp3"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=44100:cl=mono", "-t", str(seconds), "-q:a", "9", str(out)], check=True)
    return out.read_bytes()


def test_words_group_characters_with_their_times():
    chars = list("Hi, grandma!")
    starts = [i * 0.1 for i in range(len(chars))]
    ends = [s + 0.08 for s in starts]
    assert words(chars, starts, ends) == [Word("Hi,", 0.0, 0.28), Word("grandma!", 0.4, 1.18)]
    with pytest.raises(ValueError):
        words(["a"], [0.0], [])


@pytest.mark.parametrize("ref, heard, wer", [
    ("She speaks Southern.", "she speaks southern", 0.0),
    ("Choisis l'accent du Sud", "choisis l accent du sud", 0.0),  # accents and apostrophes ignored
    ("She speaks Southern", "she speaks", 1 / 3),
    ("Order coffee in Vietnam", "order a coffee in vietnam", 1 / 4),
    ("", "", 0.0),
])
def test_word_error_rate(ref, heard, wer):
    assert word_error_rate(ref, heard) == pytest.approx(wer)


def eleven(tmp_path, handler):
    return ElevenLabs(KEY, tmp_path / "audio", http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_voice_and_music_are_generated_once_then_cached(tmp_path):
    calls = []
    mp3 = silent_mp3(tmp_path)

    def handler(request):
        calls.append(request)
        assert request.headers["xi-api-key"] == KEY
        if request.url.path.endswith("/with-timestamps"):
            body = json.loads(request.content)
            text = body["text"]
            return httpx.Response(200, json={"audio_base64": base64.b64encode(mp3).decode(), "alignment": {
                "characters": list(text), "character_start_times_seconds": [i * 0.05 for i in range(len(text))],
                "character_end_times_seconds": [i * 0.05 + 0.04 for i in range(len(text))]}})
        assert request.url.path == "/v1/music"
        assert json.loads(request.content)["force_instrumental"] is True
        return httpx.Response(200, content=mp3)

    el = eleven(tmp_path, handler)
    v = el.voice("Hear it first.", voice_id="v1")
    assert v.mp3.read_bytes() == mp3 and v.characters[0] == "H" and v.seconds == pytest.approx(13 * 0.05 + 0.04)
    assert el.voice("Hear it first.", voice_id="v1").mp3 == v.mp3
    assert el.music("calm", 17.2).read_bytes() == mp3 and el.music("calm", 17.2).exists()
    assert len(calls) == 2  # one voice, one track: the rest from the cache
    assert el.voice("Hear it first.", voice_id="v1", seed=8).mp3 != v.mp3  # another seed is another take
    assert len(calls) == 3


def test_errors_never_show_the_key(tmp_path):
    el = eleven(tmp_path, lambda r: httpx.Response(401, text=f"invalid key {KEY}"))
    with pytest.raises(ElevenLabsError) as exc:
        el.voice("x")
    assert KEY not in str(exc.value) and "401" in str(exc.value)
    with pytest.raises(ElevenLabsError, match="ELEVENLABS_API_KEY"):
        ElevenLabs("", tmp_path)
    with pytest.raises(ValueError, match="mood"):
        eleven(tmp_path, lambda r: httpx.Response(200)).music("techno", 10)


def test_mp3_is_converted_to_the_wav_muse_transcribes(tmp_path):
    p = tmp_path / "v.mp3"
    p.write_bytes(silent_mp3(tmp_path, 0.5))
    wav = to_wav16k(p)
    with wave.open(__import__("io").BytesIO(wav)) as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1 and w.getsampwidth() == 2


def test_transcribe_sends_a_multipart_request_and_bills_the_seconds(tmp_path):
    from fakes import make_settings
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"sessionId": "s", "transcript": "hear it first", "audioDurationMs": 2500,
                                         "turns": []})

    model = ModelClient(make_settings(tmp_path))
    text = model.transcribe(b"RIFF....", module="voice_guard", languages=["English"],
                            http=httpx.Client(transport=httpx.MockTransport(handler)))
    assert text == "hear it first"
    body = seen[0].content.decode(errors="ignore")
    assert '"model": "muse-voice-transcribe-1.0"' in body and '"languageBias": ["English"]' in body
    assert seen[0].url.path.endswith("/asr/transcribe")
    assert model.spent_usd == pytest.approx(3 / 3600 * 0.18)  # 2.5 s, rounded up to whole seconds


BRIEF = VideoBrief("t", "a:b", "p", "a", "English", "Hook", (Scene("screen", "x", "still", 3.0, screen=1),),
                   "Start", "Hear it first, then say it.", "calm", "why")


class FakeVoice:
    def __init__(self, tmp_path):
        self.tmp, self.seeds = tmp_path, []

    def voice(self, text, *, voice_id, seed):
        self.seeds.append(seed)
        p = self.tmp / f"v{seed}.mp3"
        p.write_bytes(silent_mp3(self.tmp, 0.3))
        chars = list(text)
        return NS(mp3=p, characters=chars, starts=[i * 0.05 for i in range(len(chars))],
                  ends=[i * 0.05 + 0.04 for i in range(len(chars))])

    def music(self, mood, seconds):
        p = self.tmp / "m.mp3"
        p.write_bytes(b"ID3")
        return p


def test_the_guard_keeps_a_voice_that_says_the_script(tmp_path):
    fv = FakeVoice(tmp_path)
    audio, guard = soundtrack(fv, NS(transcribe=lambda wav, **k: "hear it first then say it"), BRIEF, "English", None)
    assert audio.voice_mp3 is not None and audio.words[0].text == "Hear" and guard["word_error_rate"] == 0
    assert fv.seeds == [7]


def test_the_guard_retries_then_drops_a_voice_that_says_something_else(tmp_path):
    fv = FakeVoice(tmp_path)
    audio, guard = soundtrack(fv, NS(transcribe=lambda wav, **k: "here it is first then pay it"), BRIEF, "English",
                              None)
    assert fv.seeds == [7, 8] and guard["dropped"] is True
    assert audio.voice_mp3 is None and audio.music_mp3 is not None  # music and on-screen text stay


def test_a_guard_that_cannot_run_is_reported_not_hidden(tmp_path):
    def broken(wav, **k):
        raise RuntimeError("503")
    audio, guard = soundtrack(FakeVoice(tmp_path), NS(transcribe=broken), BRIEF, "English", None)
    assert audio.voice_mp3 is not None and guard["checked"] is False and "503" in guard["error"]


def test_sound_effects_are_generated_once_per_kind(tmp_path):
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        assert request.url.path == "/v1/sound-generation"
        return httpx.Response(200, content=b"ID3fx")

    el = eleven(tmp_path, handler)
    assert el.sfx("whoosh").read_bytes() == b"ID3fx" and el.sfx("whoosh").exists()
    el.sfx("pop")
    assert len(calls) == 2 and calls[0]["duration_seconds"] == 1.0
    with pytest.raises(ValueError, match="sound effect"):
        el.sfx("explosion")


def test_emotion_tags_are_performed_not_captioned_nor_counted_by_the_guard():
    from whynot.audio.captions import spoken
    text = "so i said ca phe [laughs] and she kept going"
    chars = list(text)
    t = [i * 0.05 for i in range(len(chars))]
    assert [w.text for w in words(chars, t, [x + 0.04 for x in t])] == ["so", "i", "said", "ca", "phe", "and", "she",
                                                                      "kept", "going"]
    assert spoken(text) == "so i said ca phe and she kept going"
    assert word_error_rate(text, "so i said ca phe and she kept going") == 0.0
