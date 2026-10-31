"""Render a `VideoBrief` with Remotion (`video/`, our own React compositions), with voice, captions and music.

The brief stays the contract between the agents and the renderer: this module only turns a brief, its
assets (real screenshots, generated scenes, icon) and its audio into Remotion props, copies the files into
a private public dir, and calls `npx remotion render`. When Node or the `video/` packages are missing (CI,
a fresh clone), `available()` says so and the caller falls back to the Pillow renderer (`create/video.py`).

Timing: scenes keep the brief's lengths, stretched when the voice needs longer, so the narration always
ends before the end card. Transitions overlap neighbouring scenes by `TRANSITION_FRAMES`.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
from PIL import Image

from whynot.agents.brief import END_CARD_SECONDS, VideoBrief
from whynot.audio.captions import Word
from whynot.config import REPO_ROOT
from whynot.create.composer import best_text_colour, hex_to_rgb

PROJECT = REPO_ROOT / "video"
FPS = 30
TRANSITION_FRAMES = 10
VOICE_TAIL_SECONDS = 0.6  # silence after the last word before the end card
MIN_RATING_SHOWN = 4.3


def available() -> bool:
    return shutil.which("npx") is not None and (PROJECT / "node_modules" / "@remotion" / "cli").exists()


@dataclass
class Audio:
    voice_mp3: Path | None = None
    words: list[Word] | None = None
    music_mp3: Path | None = None
    music_volume: float = 0.22


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def rating_text(rating: float | None, count: int | None) -> str:
    """The end card's line: the rating only when it helps (≥ 4.3 with ≥ 20 ratings), never rounded up."""
    if rating is not None and rating >= MIN_RATING_SHOWN and (count or 0) >= 20:
        return f"Rated {rating:.1f} on the App Store"
    return "On the App Store"


def scene_frames(brief: VideoBrief, voice_seconds: float = 0.0) -> list[int]:
    """Frames per scene: the brief's lengths, stretched evenly if the voice needs more time."""
    frames = [round(s.seconds * FPS) for s in brief.scenes]
    usable = sum(frames) - TRANSITION_FRAMES * len(frames)  # the end card starts after the last transition
    need = round((voice_seconds + VOICE_TAIL_SECONDS) * FPS)
    if voice_seconds and need > usable:
        k = need / usable
        frames = [round(f * k) + 1 for f in frames]
    return frames


def build_props(brief: VideoBrief, *, palette: list[str], app_name: str, screens: list[str], scenes: dict[int, str],
                icon: str | None, rating: float | None, rating_count: int | None, audio: Audio | None) -> dict:
    """Remotion props. `screens` / `scenes` / `icon` / audio are file names inside the public dir."""
    bg, fg, accent, surface = palette[:4]
    on_accent = best_text_colour(hex_to_rgb(accent), [hex_to_rgb(bg), hex_to_rgb(fg), hex_to_rgb(surface)])
    voice_seconds = max((w.end for w in (audio.words or [])), default=0.0) if audio else 0.0
    frames = scene_frames(brief, voice_seconds)
    end_frames = round(END_CARD_SECONDS * FPS)
    out_scenes = []
    for i, (s, n) in enumerate(zip(brief.scenes, frames, strict=True)):
        src = screens[s.screen - 1] if s.kind == "screen" and s.screen else scenes.get(i)
        if s.kind != "text" and not src:
            raise ValueError(f"scene {i + 1} ({s.kind}) has no image")
        out_scenes.append({"kind": s.kind, "durationInFrames": n, "overlay": s.overlay, "motion": s.motion,
                           **({"src": src} if src else {}), **({"text": s.text} if s.text else {})})
    voice = None
    if audio and audio.voice_mp3 and audio.words:
        voice = {"src": "voice.mp3", "words": [{"text": w.text, "start": w.start, "end": w.end} for w in audio.words]}
    music = {"src": "music.mp3", "volume": audio.music_volume} if audio and audio.music_mp3 else None
    return {
        "fps": FPS, "durationInFrames": sum(frames) + end_frames - TRANSITION_FRAMES * len(frames),
        "transitionFrames": TRANSITION_FRAMES, "hook": brief.hook, "scenes": out_scenes,
        "endCard": {"durationInFrames": end_frames, "appName": app_name, "icon": icon,
                    "rating": rating_text(rating, rating_count), "cta": brief.cta},
        "look": {"bg": bg, "fg": fg, "accent": accent, "surface": surface, "onAccent": _hex(on_accent)},
        "voice": voice, "music": music,
    }


def render_composition(composition: str, props: dict, files: dict[str, Path | Image.Image], out: Path, *,
                       poster_at: float = 1.2) -> dict:
    """Render `composition` with `props`; `files` (public name -> path or image) are copied to a private public
    dir removed afterwards. Writes `out` (.mp4) and `<out>.poster.jpg`; returns facts about the file."""
    out = Path(out)
    public = out.parent / f".public-{out.stem}"
    if public.exists():
        shutil.rmtree(public)
    public.mkdir(parents=True)
    try:
        for name, src in files.items():
            if isinstance(src, Image.Image):
                if name.endswith(".png"):
                    src.convert("RGBA").save(public / name)
                else:
                    src.convert("RGB").save(public / name, quality=92)
            else:
                shutil.copy(src, public / name)
        props_path = public / "props.json"
        props_path.write_text(json.dumps(props, ensure_ascii=False))
        r = subprocess.run(["npx", "remotion", "render", "src/index.ts", composition, str(out.resolve()),
                            f"--props={props_path.resolve()}", f"--public-dir={public.resolve()}", "--log=error"],
                           cwd=PROJECT, capture_output=True, text=True, timeout=900)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f"remotion render failed: {(r.stderr or r.stdout)[-800:]}")
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-y", "-ss", str(poster_at), "-i", str(out),
                        "-frames:v", "1", "-q:v", "3", str(out.with_suffix(".poster.jpg"))], check=True)
    finally:
        shutil.rmtree(public, ignore_errors=True)
    frames, secs = imageio_ffmpeg.count_frames_and_secs(str(out))
    return {"path": out.name, "frames": frames, "seconds": round(secs, 2), "width": 1080, "height": 1920,
            "fps": FPS, "bytes": out.stat().st_size, "renderer": "remotion", "composition": composition,
            "voice": bool(props.get("voice")), "music": bool(props.get("music"))}


def render(brief: VideoBrief, out: Path, *, palette: list[str], app_name: str, screens: list[Image.Image],
           scenes: dict[int, Image.Image], icon: Image.Image | None, rating: float | None,
           rating_count: int | None, audio: Audio | None = None, poster_at: float = 1.2) -> dict:
    """Render a classic brief (`Ad` composition)."""
    files: dict[str, Path | Image.Image] = {f"screen_{i}.png": img for i, img in enumerate(screens, 1)}
    files |= {f"scene_{i}.jpg": img for i, img in scenes.items()}
    if icon is not None:
        files["icon.png"] = icon
    if audio and audio.voice_mp3:
        files["voice.mp3"] = audio.voice_mp3
    if audio and audio.music_mp3:
        files["music.mp3"] = audio.music_mp3
    props = build_props(brief, palette=palette, app_name=app_name,
                        screens=[f"screen_{i}.png" for i in range(1, len(screens) + 1)],
                        scenes={i: f"scene_{i}.jpg" for i in scenes}, icon="icon.png" if icon is not None else None,
                        rating=rating, rating_count=rating_count, audio=audio)
    return render_composition("Ad", props, files, out, poster_at=poster_at)
