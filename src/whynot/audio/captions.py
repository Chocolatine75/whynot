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


# Spoken forms a transcriber writes differently, all said the same way.
_SPOKEN = {"wanna": "want to", "gonna": "going to", "gotta": "got to", "kinda": "kind of", "sorta": "sort of",
           "tryna": "trying to", "lemme": "let me", "gimme": "give me", "dunno": "don't know", "ok": "okay",
           "til": "until", "till": "until", "u": "you", "ur": "your", "cuz": "because", "bc": "because"}
_UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
          "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}


def _canonical(tokens: list[str]) -> list[str]:
    """Spoken forms expanded ("wanna" → "want to"), number words as digits ("fifty" → "50")."""
    out: list[str] = []
    for t in tokens:
        out += _SPOKEN.get(t, t).split()
    merged: list[str] = []
    i = 0
    while i < len(out):
        t = out[i]
        if t in _TENS:
            n = _TENS[t]
            if i + 1 < len(out) and out[i + 1] in _UNITS[1:10]:
                n += _UNITS.index(out[i + 1])
                i += 1
            merged.append(str(n))
        elif t in _UNITS:
            merged.append(str(_UNITS.index(t)))
        else:
            merged.append(t)
        i += 1
    return merged


def _merge_compounds(a: list[str], b: list[str]) -> list[str]:
    """Join neighbours of `a` that form one word of `b` ("low key" → "lowkey", "viet buddy" → "vietbuddy")."""
    vocab = set(b)
    out: list[str] = []
    i = 0
    while i < len(a):
        if i + 1 < len(a) and a[i] + a[i + 1] in vocab and a[i] not in vocab:
            out.append(a[i] + a[i + 1])
            i += 2
        else:
            out.append(a[i])
            i += 1
    return out


def word_error_rate(reference: str, heard: str) -> float:
    """(substitutions + deletions + insertions) / words in the reference, case and accents ignored."""
    # what a listener hears as the same: apostrophes read both ways ("i've"/"ive", "l'accent"/"l accent"),
    # spoken forms and numbers ("wanna"/"want to", "fifty"/"50"), compounds ("lowkey"/"low key")
    best = 1e9
    for a in (" ", ""):
        ref, hyp = _canonical(_tokens(spoken(reference), a)), _canonical(_tokens(heard, a))
        ref, hyp = _merge_compounds(ref, hyp), _merge_compounds(hyp, ref)
        best = min(best, _wer(ref, hyp))
    return best


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
