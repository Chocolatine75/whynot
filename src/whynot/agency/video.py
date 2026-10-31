"""`whynot video RUN`: from a `create` run to finished video ads, the way a creative team works.

1. creatives: capture the competitor ads' images from the Ad Library (cached, free);
2. deconstruct: Muse Spark breaks every competitor ad into parts (cached by ad id);
3. archetypes: group them, score each group on market signals, Muse Spark picks the ones that fit us;
4. screens: Muse Spark describes the app's real screenshots once (so briefs pick the right one);
5. briefs: one storyboard per pick, checked like any ad copy;
6. scenes: Muse Image draws the scene backgrounds (never the product; cached by prompt);
7. render: each brief becomes a 9:16 MP4 by code (`create/video.py`).

Everything lands in `<run>/videos/`: the MP4s and posters, and `videos.json` with the archetypes and their
score components, the picks, the briefs, what failed, and what it cost. Steps already done are reused.
"""

import base64
import hashlib
import io
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from PIL import Image

from whynot.agency.create import localised
from whynot.agents import archetypes, brief
from whynot.agents.deconstruct import DeconstructionStore, deconstruct_all
from whynot.agents.director import Context
from whynot.agents.strategist import Strategy
from whynot.audio.captions import MAX_WORD_ERROR_RATE, to_wav16k, word_error_rate, words
from whynot.audio.elevenlabs import DEFAULT_VOICE, ElevenLabs
from whynot.config import REPO_ROOT
from whynot.create import remotion
from whynot.create.locale import LANGUAGES, language_groups
from whynot.create.video import Assets, Look, render
from whynot.ingest.adlibrary import CompetitorAd, load_jsonl
from whynot.ingest.creatives import CreativeStore, Renderer, capture
from whynot.models import ModelClient, image_data_url
from whynot.sim.arena import brand_name

CACHE = REPO_ROOT / "data" / "cache"
SCENE_STYLE = ("Vertical 9:16 photograph, natural light, shallow depth of field, editorial look. No text, no "
               "letters, no logos, no screens, no phones.")


@dataclass
class VideoConfig:
    n_videos: int = 3
    model: str = "muse-spark-1.3"
    capture: bool = True  # capture missing competitor creatives with a headless browser
    renderer: str = "remotion"  # remotion (voice, captions, music) | builtin (silent, no Node needed)


def soundtrack(voice: ElevenLabs, model: Any, b: brief.VideoBrief, language: str,
               voice_id: str | None) -> tuple[remotion.Audio | None, dict[str, Any]]:
    """Voice-over + music for a brief, and the voice guard's verdict.

    The guard: Muse Voice Transcribe listens to the voice; if what it hears differs from the checked script
    by more than `MAX_WORD_ERROR_RATE`, the voice is generated once more with another seed, then dropped
    (the video keeps its music and on-screen text). If the guard can't run, that is recorded, not hidden."""
    guard: dict[str, Any] = {"script": b.narration}
    chosen = None
    for seed in (7, 8):
        v = voice.voice(b.narration, voice_id=voice_id or DEFAULT_VOICE, seed=seed)
        try:
            heard = model.transcribe(to_wav16k(v.mp3), module="voice_guard", languages=[language])
        except Exception as exc:  # the guard failing is reported; the voice is kept, flagged unchecked
            guard.update(checked=False, error=f"{type(exc).__name__}: {exc}"[:200])
            chosen = v
            break
        wer = word_error_rate(b.narration, heard)
        guard.update(checked=True, heard=heard, word_error_rate=round(wer, 3), seed=seed)
        if wer <= MAX_WORD_ERROR_RATE:
            chosen = v
            break
    if chosen is None:
        guard["dropped"] = True
    seconds = sum(s.seconds for s in b.scenes) + brief.END_CARD_SECONDS + 3
    music = voice.music(b.music, seconds)
    if chosen is None:
        return remotion.Audio(music_mp3=music), guard
    return remotion.Audio(chosen.mp3, words(chosen.characters, chosen.starts, chosen.ends), music), guard


def scene_image(model: ModelClient, prompt: str, folder: Path, *, style: str = SCENE_STYLE) -> Image.Image:
    """A generated background for a scene, cached by prompt and style."""
    key = hashlib.sha256(f"{style}|{prompt}".encode()).hexdigest()[:24]
    path = folder / f"{key}.png"
    if not path.exists():
        result = model.image(f"{prompt}. {style}", module="scenes", size="1024x1536")
        folder.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(base64.b64decode(result.images_b64[0]))) as im:
            im.convert("RGB").save(path)
    return Image.open(path).convert("RGB")


def _as_of(ads: list[CompetitorAd]) -> date:
    dates = [d for a in ads for d in (a.start_date, a.stop_date) if d]
    return max(dates) if dates else date.today()


def make_videos(run_dir: Path, model: ModelClient, *, token: str = "", cfg: VideoConfig | None = None,
                renderer_factory: Callable[[], Renderer] | None = None, voice: ElevenLabs | None = None,
                voice_id: str | None = None, say: Callable[[str], None] = print) -> dict[str, Any]:
    """`voice`: an ElevenLabs client for voice-over + music (None: silent videos)."""
    cfg = cfg or VideoConfig()
    run_dir = Path(run_dir)
    out = run_dir / "videos"
    out.mkdir(exist_ok=True)
    app = json.loads((run_dir / "app.json").read_text())
    brand = json.loads((run_dir / "brand.json").read_text())
    config = json.loads((run_dir / "config.json").read_text())
    strategy = Strategy.from_json(json.loads((run_dir / "strategy.json").read_text()))
    ads = load_jsonl(run_dir / "market_ads.jsonl")
    spent0 = model.spent_usd
    report: dict[str, Any] = {"app": app["name"], "failures": {}}

    # 1. creatives
    store = CreativeStore(CACHE / "creatives")
    missing = [a for a in ads if a.snapshot_url and not store.has(a.id)]
    if missing and cfg.capture and renderer_factory is not None:
        say(f"capturing {len(missing)} competitor creatives...")
        r = renderer_factory()
        try:
            cap = capture(missing, store, token=token, renderer=r)
        finally:
            close = getattr(r, "close", None)
            if close:
                close()
        report["failures"]["capture"] = cap.failed
    # capture says image/video; a deconstruction says static/video
    images = {a.id: (store.path(a.id), "video" if info.kind == "video" else "static")
              for a in ads if (info := store.info(a.id))}
    say(f"{len(images)} of {len(ads)} competitor ads have a creative")

    # 2. deconstruct
    dec = deconstruct_all(model, ads, images, DeconstructionStore(CACHE / "deconstruct"), model=cfg.model)
    report["failures"]["deconstruct"] = dec.failed
    say(f"deconstructed {len(dec.done)} ads ({dec.cached} from cache, {len(dec.failed)} failed)")

    # 3. archetypes + fit
    arch = archetypes.build(dec.done, ads, as_of=_as_of(ads))
    if not arch:
        report["usd"] = round(model.spent_usd - spent0, 4)
        report["videos"] = []
        report["failures"]["archetypes"] = "no archetype with at least 2 ads: capture or deconstruction failed"
        (out / "videos.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str))
        say("✗ " + report["failures"]["archetypes"])
        return report
    groups = language_groups([c.upper() for c in config["countries"]], override=config.get("language"))
    code, countries = next(iter(groups.items()))
    local = localised(strategy, countries)
    picks = archetypes.pick(model, arch, local, app_name=app["name"], description=app["description"],
                            n=min(cfg.n_videos, len(arch)), model=cfg.model)
    report["archetypes"] = [asdict(a) for a in arch[:8]]
    report["picks"] = [asdict(p) for p in picks.value]
    say("archetypes: " + ", ".join(f"{p.archetype} → {p.angle}" for p in picks.value))

    # 4. screens
    screens_path = out / "screens.json"
    shots = [run_dir / "assets" / s for s in brand["screenshots"]]
    if screens_path.exists():
        screens = json.loads(screens_path.read_text())
    else:
        screens = brief.describe_screens(model, app["name"], [image_data_url(p) for p in shots],
                                         model=cfg.model).value
        screens_path.write_text(json.dumps(screens, indent=1, ensure_ascii=False))

    # 5-7. briefs, scenes, render
    names = tuple(sorted({a.page_name for a in ads if a.page_name}))
    ctx = Context(local, app["name"], app["description"], names, tuple(brand["palette"][:3]),
                  brand["screenshots"][0], LANGUAGES[code])
    by_key = {a.key: a for a in arch}
    look = Look.from_palette(brand["palette"], brand_name(app["name"]),
                             icon=Image.open(run_dir / "assets" / "icon.png"), rating=app.get("rating"),
                             rating_count=app.get("rating_count"))
    screen_images: list[Image.Image] = [Image.open(p) for p in shots]
    videos = []
    use_remotion = cfg.renderer == "remotion" and remotion.available()
    if cfg.renderer == "remotion" and not use_remotion:
        say("  (Remotion not installed: `cd video && npm install`; rendering with the built-in renderer)")
    icon = Image.open(run_dir / "assets" / "icon.png")
    for n, p in enumerate(picks.value, 1):
        try:
            b = brief.write_brief(model, ctx, p, by_key[p.archetype], screens, model=cfg.model).value
            scenes = {i: scene_image(model, s.prompt or "", CACHE / "scenes")
                      for i, s in enumerate(b.scenes) if s.kind == "scene"}
            name = f"{n}-{b.id}"  # two briefs may pick the same id: never overwrite a video
            sound, guard = (soundtrack(voice, model, b, ctx.language, voice_id) if voice and use_remotion
                            else (None, {"skipped": "no voice client" if not voice else "built-in renderer"}))
            if use_remotion:
                facts = remotion.render(b, out / f"{name}.mp4", palette=brand["palette"], app_name=look.app_name,
                                        screens=screen_images, scenes=scenes, icon=icon, rating=app.get("rating"),
                                        rating_count=app.get("rating_count"), audio=sound)
            else:
                facts = render(b, look, Assets(screen_images, scenes), out / f"{name}.mp4")
            videos.append({"brief": b.to_json(), "file": facts, "poster": f"{name}.poster.jpg",
                           "voice_guard": guard})
            say(f"  ✓ {name}: {facts['seconds']} s — \"{b.hook}\"" + (" · voice + captions + music"
                                                                     if facts.get("voice") else ""))
        except Exception as exc:  # one failed brief must not lose the others
            report["failures"].setdefault("videos", {})[p.archetype] = f"{type(exc).__name__}: {exc}"[:400]
            say(f"  ✗ {p.archetype}: {exc}")
    report["videos"] = videos
    report["usd"] = round(model.spent_usd - spent0, 4)
    (out / "videos.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str))
    return report
