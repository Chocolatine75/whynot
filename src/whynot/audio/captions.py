"""Word-by-word captions from the voice's timing, and the voice guard.

Most Reels are watched muted, so the narration is also shown as captions, each word lit when it is said.
ElevenLabs gives the start and end of every character; `words` groups them into timed words.

The guard: Muse Voice Transcribe listens to the generated voice, and the transcript is compared with the
script our agents wrote and checked (`word_error_rate`). A voice that says something else (a dropped
word, a misread name or number) is refused: what is heard must be what was validated.
"""

import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg

MAX_WORD_ERROR_RATE = 0.2


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    speaker: str = "me"  # who says it: "me" (the creator) or "them"
    native: bool = False  # said by a native voice in another language (shown apart in the captions)


TAG = re.compile(r"\[[^\]]*\]")


def spoken(script: str) -> str:
    """The script without emotion tags ([laughs]...): what the voice actually says."""
    return " ".join(TAG.sub(" ", script).split())


def words(characters: list[str], starts: list[float], ends: list[float]) -> list[Word]:
    """Characters with times → words with times (spaces split words; punctuation stays on its word).
    Emotion tags ([laughs]) are performed, not said: they are left out of the captions."""
    if not len(characters) == len(starts) == len(ends):
        raise ValueError("characters, starts and ends must have the same length")
    out: list[Word] = []
    buf, t0, t1 = "", 0.0, 0.0
    for ch, s, e in zip(characters, starts, ends, strict=True):
        if ch.isspace():
            if buf:
                out.append(Word(buf, round(t0, 3), round(t1, 3)))
            buf = ""
            continue
        if not buf:
            t0 = s
        buf += ch
        t1 = e
    if buf:
        out.append(Word(buf, round(t0, 3), round(t1, 3)))
    return [w for w in out if not TAG.fullmatch(w.text) and not (w.text.startswith("[") or w.text.endswith("]"))]


def _tokens(text: str, apostrophe: str = " ") -> list[str]:
    t = re.sub(r"['’]", apostrophe, text.lower())
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.findall(r"[a-z0-9]+", t)


def word_error_rate(reference: str, heard: str) -> float:
    """(substitutions + deletions + insertions) / words in the reference, case and accents ignored."""
    # "i've"/"ive" and "l'accent"/"l accent" are the same words to a listener: read apostrophes both ways
    return min(_wer(_tokens(spoken(reference), a), _tokens(heard, a)) for a in (" ", ""))


def _wer(ref: list[str], hyp: list[str]) -> float:
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)


def to_wav16k(mp3: Path, start: float | None = None, end: float | None = None) -> bytes:
    """MP3 (or the `start`-`end` seconds of it) → mono 16 kHz PCM WAV, what Muse Voice Transcribe takes."""
    cut = ([] if start is None else ["-ss", f"{start:.3f}"]) + ([] if end is None else ["-to", f"{end:.3f}"])
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(mp3), *cut, "-ac", "1", "-ar",
                        "16000", "-acodec", "pcm_s16le", "-f", "wav", "-"], capture_output=True, check=True)
    return r.stdout


def audio_seconds(path: Path) -> float:
    """Length of an audio file, read by ffmpeg."""
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if not m:
        raise ValueError(f"cannot read the length of {path}")
    h, mi, se = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(se)


def join_clips(parts: list[tuple[Path, float]], out: Path, *, gap: float) -> Path:
    """Clips one after the other with `gap` seconds of silence between them (exact: each clip is padded to
    its measured length plus the gap), as one MP3."""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    inputs: list[str] = []
    chains = []
    for i, (p, dur) in enumerate(parts):
        inputs += ["-i", str(p)]
        pad = dur + (gap if i < len(parts) - 1 else 0.0)
        chains.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=mono,apad,atrim=0:{pad:.3f}[a{i}]")
    graph = ";".join(chains) + ";" + "".join(f"[a{i}]" for i in range(len(parts))) + \
        f"concat=n={len(parts)}:v=0:a=1[out]"
    subprocess.run([ff, "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[out]", "-q:a", "3",
                    str(out)], check=True)
    return out
