"""Render a `TrendBrief` with the Remotion `Trend` composition: hard cuts, caption bubbles, sound effects.

Timing: each shot keeps its length; if the voice-over is longer than the shots, every shot is stretched
evenly so the voice ends before the end card. Sound effects play on the cut that starts their shot.

Rhythm: no picture holds longer than `MAX_SHOT_SECONDS`. A longer shot is cut into several, each framed
differently (a photo: wide, then close on the faces, then a pan; the app: its own motion, then a zoom on the
focus, then a scroll), so the viewer always sees something new, like a creator's edit. The hook title stays
over the whole first shot, across its cuts.
"""

import hashlib
import math
from pathlib import Path
from typing import Any

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


MAX_SHOT_SECONDS = 1.0
THEMES = 3  # visual treatments in the Trend composition (TrendProps.theme)
CTA_CARD_FRAMES = round(0.7 * FPS)
PHOTO_CUTS = ("close", "pan", "punch_in")  # framings after the first one, in turn
SCREEN_CUTS = ("zoom", "scroll", "float")


def split_frames(n: int, max_frames: int) -> list[int]:
    """`n` frames as the fewest pieces of at most `max_frames`, as even as possible (they sum to `n`)."""
    k = max(1, math.ceil(n / max_frames))
    return [n // k + (1 if i < n % k else 0) for i in range(k)]


def open_on_a_picture(shots: list[dict]) -> list[dict]:
    """The first frame decides whether the thumb stops: a script that opens on a text card (a flat colour) opens
    instead on its first picture, with the hook title over it; the card's time goes to that picture, nothing else
    of the story moves."""
    first_picture = next((i for i, s in enumerate(shots) if s["visual"] in ("photo", "screen", "mascot")), None)
    if not shots or shots[0]["visual"] != "text" or first_picture is None:
        return shots
    lead = sum(s["durationInFrames"] for s in shots[:first_picture])
    opening = {**shots[first_picture], "durationInFrames": shots[first_picture]["durationInFrames"] + lead,
               "sfx": shots[0]["sfx"] if shots[0]["sfx"] != "none" else shots[first_picture]["sfx"]}
    return [opening, *shots[first_picture + 1:]]


def recut(shots: list[dict], *, max_frames: int) -> list[dict]:
    """Cut every long shot into short ones, each a new framing of the same picture (see the module doc).
    The mascot gets one beat (at most `max_frames`): the rest of its time goes to the next shot."""
    shots = [dict(s) for s in shots]
    for i, s in enumerate(shots):
        if s["visual"] == "mascot" and s["durationInFrames"] > max_frames and len(shots) > 1:
            spare = s["durationInFrames"] - max_frames
            s["durationInFrames"] = max_frames
            shots[i + 1 if i + 1 < len(shots) else i - 1]["durationInFrames"] += spare
    out: list[dict] = []
    for i, s in enumerate(shots):
        pieces = split_frames(s["durationInFrames"], max_frames)
        if s["visual"] in ("text", "review") or s.get("ui") == "grid":
            pieces = [s["durationInFrames"]]  # read whole / tiles animate across the shot
        for j, n in enumerate(pieces):
            piece = {**s, "durationInFrames": n, **({"hook": True} if i == 0 else {})}
            if j:
                piece["sfx"] = "none"  # the sound marks the story's cut, not every reframe
                if s["visual"] in ("photo", "mascot"):
                    piece["move"] = PHOTO_CUTS[(j - 1) % len(PHOTO_CUTS)]
                elif s["visual"] == "screen":
                    piece["ui"] = SCREEN_CUTS[(j - 1) % len(SCREEN_CUTS)]
                    piece.pop("tap", None)
            out.append(piece)
    return out


def build_props(brief: TrendBrief, *, palette: list[str], app_name: str, images: dict[int, str],
                icon: str | None, rating: float | None, rating_count: int | None, audio: Audio | None,
                sfx: dict[str, str], tiles: dict[int, list[list[float]]] | None = None,
                sizes: dict[int, list[int]] | None = None) -> dict:
    """`images`: shot index -> file name in the public dir (photo, UI crop or mascot)."""
    bg, fg, accent, surface = palette[:4]
    on_accent = best_text_colour(hex_to_rgb(accent), [hex_to_rgb(bg), hex_to_rgb(fg), hex_to_rgb(surface)])
    voice_seconds = max((w.end for w in (audio.words or [])), default=0.0) if audio else 0.0
    frames = shot_frames(brief, voice_seconds)
    shots: list[dict[str, Any]] = []
    for i, (s, n) in enumerate(zip(brief.shots, frames, strict=True)):
        if s.visual not in ("text", "review") and i not in images:
            raise ValueError(f"shot {i + 1} ({s.visual}) has no image")
        shots.append({"visual": s.visual, "durationInFrames": n, "caption": s.caption, "move": s.move,
                      "sfx": s.sfx if s.sfx in sfx else "none", "beat": s.beat,
                      **({"src": images[i]} if i in images else {}), **({"focus": s.focus} if s.focus else {}),
                      **({"text": s.text} if s.text else {}), **({"tap": True} if s.tap else {}),
                      **({"ui": s.ui} if s.ui else {}), **({"grid": list(s.grid)} if s.grid else {}),
                      **({"tiles": (tiles or {})[i]} if i in (tiles or {}) else {}),
                      **({"imageSize": (sizes or {})[i]} if s.visual == "screen" and i in (sizes or {}) else {}),
                      **({"quote": s.quote, "stars": s.stars or 5} if s.visual == "review" else {})})
    shots = open_on_a_picture(shots)
    end_frames = round(END_CARD_SECONDS * FPS)
    # a closing text card right before the end card said the call to action twice: it gets a beat, the end card
    # (which shows the same call to action with the icon and the button) takes the rest
    last = shots[-1] if shots else None
    if last and last["visual"] == "text" and last["beat"] == "cta" and last["durationInFrames"] > CTA_CARD_FRAMES:
        end_frames += last["durationInFrames"] - CTA_CARD_FRAMES
        last["durationInFrames"] = CTA_CARD_FRAMES
    shots = recut(shots, max_frames=round(MAX_SHOT_SECONDS * FPS))
    for i in range(1, len(shots)):  # one phone for a run of app shots: it enters once, then changes what it shows
        if shots[i]["visual"] == "screen" and shots[i - 1]["visual"] == "screen":
            shots[i]["continues"] = True
    voice = None
    if audio and audio.voice_mp3 and audio.words:
        voice = {"src": "voice.mp3", "words": [{"text": w.text, "start": w.start, "end": w.end, "speaker": w.speaker,
                                                 "native": w.native} for w in audio.words]}
    return {
        # each video its own look (background of the app shots, captions, hook title): ads that look alike are
        # grouped by Meta's delivery and compete as one
        "theme": int(hashlib.sha1(brief.id.encode()).hexdigest(), 16) % THEMES,
        "fps": FPS, "durationInFrames": sum(s["durationInFrames"] for s in shots) + end_frames, "hook": brief.hook,
        "shots": shots,
        "endCard": {"durationInFrames": end_frames, "appName": app_name, "icon": icon,
                    "rating": rating_text(rating, rating_count), "cta": brief.cta, "offer": brief.offer},
        "look": {"bg": bg, "fg": fg, "accent": accent, "surface": surface,
                 "onAccent": "#{:02X}{:02X}{:02X}".format(*on_accent)},
        "voice": voice,
        "music": {"src": "music.mp3", "volume": audio.music_volume} if audio and audio.music_mp3 else None,
        "sfx": sfx,
    }


def render(brief: TrendBrief, out: Path, *, palette: list[str], app_name: str, images: dict[int, Image.Image],
           icon: Image.Image | None, rating: float | None, rating_count: int | None, audio: Audio | None = None,
           sfx: dict[str, Path] | None = None, tiles: dict[int, list[tuple[int, int, int, int]]] | None = None) -> dict:
    """`tiles`: for "grid" screens, the call's tiles in the screen's pixels (`cutouts.call_tiles`)."""
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
    rel = {i: [[x0 / images[i].width, y0 / images[i].height, x1 / images[i].width, y1 / images[i].height]
               for x0, y0, x1, y1 in boxes] for i, boxes in (tiles or {}).items() if i in images}
    props = build_props(brief, palette=palette, app_name=app_name, images=names,
                        icon="icon.png" if icon is not None else None, rating=rating, rating_count=rating_count,
                        audio=audio, sfx=sfx_names, tiles=rel,
                        # the screen's real size: tiles and picture share one geometry in the phone
                        sizes={i: [img.width, img.height] for i, img in images.items()})
    return render_composition("Trend", props, files, out, poster_at=0.4)
