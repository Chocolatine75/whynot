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


def words(characters: list[str], starts: list[float], ends: list[float]) -> list[Word]:
    """Characters with times → words with times (spaces split words; punctuation stays on its word)."""
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
    return out


def _tokens(text: str) -> list[str]:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.findall(r"[a-z0-9]+", t)


def word_error_rate(reference: str, heard: str) -> float:
    """(substitutions + deletions + insertions) / words in the reference, case and accents ignored."""
    ref, hyp = _tokens(reference), _tokens(heard)
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)


def to_wav16k(mp3: Path) -> bytes:
    """MP3 → mono 16 kHz PCM WAV (what Muse Voice Transcribe takes)."""
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(mp3), "-ac", "1", "-ar", "16000",
                        "-acodec", "pcm_s16le", "-f", "wav", "-"], capture_output=True, check=True)
    return r.stdout
