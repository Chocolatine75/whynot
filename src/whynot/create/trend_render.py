"""Render a `TrendBrief` with the Remotion `Trend` composition: hard cuts, caption bubbles, sound effects.

Timing: each shot keeps its length; if the voice-over is longer than the shots, every shot is stretched
evenly so the voice ends before the end card. Sound effects play on the cut that starts their shot.
"""

from pathlib import Path

from PIL import Image

from whynot.agents.trend_brief import END_CARD_SECONDS, TrendBrief
from whynot.create.composer import best_text_colour, hex_to_rgb
from whynot.create.remotion import FPS, VOICE_TAIL_SECONDS, Audio, rating_text, render_composition


def shot_frames(brief: TrendBrief, voice_seconds: float = 0.0) -> list[int]:
    frames = [max(1, round(s.seconds * FPS)) for s in brief.shots]
    need = round((voice_seconds + VOICE_TAIL_SECONDS) * FPS)
    if voice_seconds and need > sum(frames):
        k = need / sum(frames)
        frames = [round(f * k) + 1 for f in frames]
    return frames


def build_props(brief: TrendBrief, *, palette: list[str], app_name: str, images: dict[int, str],
                icon: str | None, rating: float | None, rating_count: int | None, audio: Audio | None,
                sfx: dict[str, str]) -> dict:
    """`images`: shot index -> file name in the public dir (photo, UI crop or mascot)."""
    bg, fg, accent, surface = palette[:4]
    on_accent = best_text_colour(hex_to_rgb(accent), [hex_to_rgb(bg), hex_to_rgb(fg), hex_to_rgb(surface)])
    voice_seconds = max((w.end for w in (audio.words or [])), default=0.0) if audio else 0.0
    frames = shot_frames(brief, voice_seconds)
    shots = []
    for i, (s, n) in enumerate(zip(brief.shots, frames, strict=True)):
        if s.visual != "text" and i not in images:
            raise ValueError(f"shot {i + 1} ({s.visual}) has no image")
        shots.append({"visual": s.visual, "durationInFrames": n, "caption": s.caption, "move": s.move,
                      "sfx": s.sfx if s.sfx in sfx else "none", "beat": s.beat,
                      **({"src": images[i]} if i in images else {}), **({"focus": s.focus} if s.focus else {}),
                      **({"text": s.text} if s.text else {})})
    end_frames = round(END_CARD_SECONDS * FPS)
    voice = None
    if audio and audio.voice_mp3 and audio.words:
        voice = {"src": "voice.mp3", "words": [{"text": w.text, "start": w.start, "end": w.end, "speaker": w.speaker,
                                                 "native": w.native} for w in audio.words]}
    return {
        "fps": FPS, "durationInFrames": sum(frames) + end_frames, "hook": brief.hook, "shots": shots,
        "endCard": {"durationInFrames": end_frames, "appName": app_name, "icon": icon,
                    "rating": rating_text(rating, rating_count), "cta": brief.cta},
        "look": {"bg": bg, "fg": fg, "accent": accent, "surface": surface,
                 "onAccent": "#{:02X}{:02X}{:02X}".format(*on_accent)},
        "voice": voice,
        "music": {"src": "music.mp3", "volume": audio.music_volume} if audio and audio.music_mp3 else None,
        "sfx": sfx,
    }


def render(brief: TrendBrief, out: Path, *, palette: list[str], app_name: str, images: dict[int, Image.Image],
           icon: Image.Image | None, rating: float | None, rating_count: int | None, audio: Audio | None = None,
           sfx: dict[str, Path] | None = None) -> dict:
    files: dict[str, Path | Image.Image] = {}
    names: dict[int, str] = {}
    for i, img in images.items():
        names[i] = f"shot_{i}.png" if brief.shots[i].visual in ("screen", "mascot") else f"shot_{i}.jpg"
        files[names[i]] = img  # real UI and mascot as PNG: their pixels stay exact
    if icon is not None:
        files["icon.png"] = icon
    if audio and audio.voice_mp3:
        files["voice.mp3"] = audio.voice_mp3
    if audio and audio.music_mp3:
        files["music.mp3"] = audio.music_mp3
    sfx_names = {}
    for name, path in (sfx or {}).items():
        sfx_names[name] = f"sfx_{name}.mp3"
        files[sfx_names[name]] = path
    props = build_props(brief, palette=palette, app_name=app_name, images=names,
                        icon="icon.png" if icon is not None else None, rating=rating, rating_count=rating_count,
                        audio=audio, sfx=sfx_names)
    return render_composition("Trend", props, files, out, poster_at=0.4)
