"""ElevenLabs: the voice-over (with per-character timing, for word-by-word captions) and the music bed.

Meta's hackathon models have no text-to-speech, so audio comes from ElevenLabs; every word it says was
written and checked by our agents (the brief's narration), and Muse Voice Transcribe listens back to
check it (`audio/captions.py`).

Both calls are cached on disk by a hash of the request: a voice or a track is generated once, then reused
across reruns. The API key travels only in the `xi-api-key` header and is redacted from every error.
"""

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

API = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE = "TX3LPaxmHKxFdv7VOQHJ"  # premade "Liam - Energetic, Social Media Creator" (young male)
YOUNG_VOICES = {"male": "TX3LPaxmHKxFdv7VOQHJ", "female": "cgSgspJ2msm6clMCkdW9"}  # Liam, Jessica (premade)
VOICE_MODEL = "eleven_v3"  # the most expressive: plays [laughs], [sighs]...; multilingual
MUSIC_PROMPTS = {
    "upbeat": "Upbeat modern pop instrumental for a mobile app ad, bright synths, light drums, feel-good",
    "calm": "Calm warm acoustic instrumental, soft piano and guitar, gentle, for a mobile app ad",
    "playful": "Playful quirky instrumental, pizzicato and marimba, light percussion, for a mobile app ad",
    "inspiring": "Inspiring cinematic instrumental, building piano and strings, hopeful, for a mobile app ad",
    "dramatic": "Dramatic tense instrumental, pulsing bass and drums, cinematic hits, for a mobile app ad",
}

SFX_PROMPTS = {  # one short, clean effect per cut type, generated once and reused by every video
    "whoosh": "Soft airy whoosh for a video transition, smooth and subtle, clean studio sound, no distortion, "
              "no crackle, no vinyl noise",
    "pop": "Soft bubbly pop, gentle and satisfying, clean, no distortion, no crackle",
    "ding": "Light pleasant chime, single soft bell tone, clean, no distortion",
}


class ElevenLabsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Voice:
    mp3: Path
    characters: list[str]
    starts: list[float]
    ends: list[float]

    @property
    def seconds(self) -> float:
        return self.ends[-1] if self.ends else 0.0


class ElevenLabs:
    def __init__(self, api_key: str, cache: Path, *, http: httpx.Client | None = None, base_url: str = API):
        if not api_key:
            raise ElevenLabsError("no ElevenLabs key: set ELEVENLABS_API_KEY in .env")
        self.key = api_key
        self.cache = Path(cache)
        self.http = http or httpx.Client(timeout=180)
        self.base = base_url

    def _post(self, path: str, body: dict[str, Any], **params: Any) -> httpx.Response:
        try:
            r = self.http.post(f"{self.base}{path}", json=body, params=params or None,
                               headers={"xi-api-key": self.key, "Content-Type": "application/json"})
        except httpx.HTTPError as exc:
            raise ElevenLabsError(f"request failed: {exc}".replace(self.key, "[REDACTED]")) from None
        if r.status_code >= 400:
            raise ElevenLabsError(f"HTTP {r.status_code}: {r.text[:300]}".replace(self.key, "[REDACTED]"))
        return r

    @staticmethod
    def _key(kind: str, body: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps({"kind": kind, **body}, sort_keys=True).encode()).hexdigest()[:24]

    def voice(self, text: str, *, voice_id: str = DEFAULT_VOICE, model_id: str = VOICE_MODEL,
              seed: int = 7) -> Voice:
        """The narration as an MP3 plus the start/end time of every character."""
        settings: dict[str, Any] = ({"stability": 0.5} if model_id == "eleven_v3"  # v3: 0 creative, 0.5 natural
                                    else {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25, "speed": 1.05})
        body = {"text": text, "model_id": model_id, "seed": seed, "voice_settings": settings}
        key = self._key(f"voice:{voice_id}", body)
        mp3, meta = self.cache / f"voice-{key}.mp3", self.cache / f"voice-{key}.json"
        if not (mp3.exists() and meta.exists()):
            data = self._post(f"/text-to-speech/{voice_id}/with-timestamps", body).json()
            al = data.get("alignment") or data.get("normalized_alignment")
            if not data.get("audio_base64") or not al:
                raise ElevenLabsError("no audio or no alignment in the answer")
            self.cache.mkdir(parents=True, exist_ok=True)
            mp3.write_bytes(base64.b64decode(data["audio_base64"]))
            meta.write_text(json.dumps({"characters": al["characters"],
                                        "starts": al["character_start_times_seconds"],
                                        "ends": al["character_end_times_seconds"]}))
        m = json.loads(meta.read_text())
        return Voice(mp3, m["characters"], m["starts"], m["ends"])

    def music(self, mood: str, seconds: float) -> Path:
        """An instrumental bed for the mood, `seconds` long (rounded up to the second, min 3 s)."""
        if mood not in MUSIC_PROMPTS:
            raise ValueError(f"unknown mood {mood!r}")
        body = {"prompt": MUSIC_PROMPTS[mood], "music_length_ms": max(3000, int(seconds + 0.999) * 1000),
                "force_instrumental": True}
        path = self.cache / f"music-{self._key('music', body)}.mp3"
        if not path.exists():
            r = self._post("/music", body)
            if not r.content:
                raise ElevenLabsError("empty music answer")
            self.cache.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
        return path

    def sfx(self, name: str) -> Path:
        """A short sound effect for a cut (`SFX_PROMPTS`), generated once."""
        if name not in SFX_PROMPTS:
            raise ValueError(f"unknown sound effect {name!r}")
        body = {"text": SFX_PROMPTS[name], "duration_seconds": 0.6, "prompt_influence": 0.7}
        path = self.cache / f"sfx-{name}-{self._key('sfx', body)}.mp3"
        if not path.exists():
            r = self._post("/sound-generation", body)
            if not r.content:
                raise ElevenLabsError("empty sound effect answer")
            self.cache.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
        return path

    def dialogue(self, lines: list[tuple[str, str]], *, model_id: str = VOICE_MODEL, seed: int = 7) -> "Dialogue":
        """Several voices in one take (`lines`: (text, voice id) in order), with per-character timing and
        when each line starts and ends."""
        if not lines:
            raise ValueError("a dialogue needs at least one line")
        body = {"inputs": [{"text": t, "voice_id": v} for t, v in lines], "model_id": model_id, "seed": seed}
        key = self._key("dialogue", body)
        mp3, meta = self.cache / f"dialogue-{key}.mp3", self.cache / f"dialogue-{key}.json"
        if not (mp3.exists() and meta.exists()):
            data = self._post("/text-to-dialogue/with-timestamps", body).json()
            al = data.get("alignment") or data.get("normalized_alignment")
            if not data.get("audio_base64") or not al or not data.get("voice_segments"):
                raise ElevenLabsError("no audio, alignment or segments in the dialogue answer")
            self.cache.mkdir(parents=True, exist_ok=True)
            mp3.write_bytes(base64.b64decode(data["audio_base64"]))
            meta.write_text(json.dumps({
                "characters": al["characters"], "starts": al["character_start_times_seconds"],
                "ends": al["character_end_times_seconds"],
                "segments": [[s["dialogue_input_index"], s["start_time_seconds"], s["end_time_seconds"]]
                             for s in data["voice_segments"]]}))
        m = json.loads(meta.read_text())
        return Dialogue(mp3, m["characters"], m["starts"], m["ends"], [tuple(x) for x in m["segments"]])


@dataclass(frozen=True)
class Dialogue(Voice):
    segments: list[tuple[int, float, float]] = ()  # type: ignore[assignment]  # (line index, start s, end s)

    def line_at(self, t: float) -> int | None:
        """The line being spoken at time `t` (seconds)."""
        for i, a, b in self.segments:
            if a <= t < b:
                return int(i)
        return None
