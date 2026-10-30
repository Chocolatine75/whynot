"""`whynot video RUN --style trend`: trend-jacking ads that hold a thumb, from a `create` run.

1. market: the competitor ads, deconstructed (cached), now with the viral format each one follows;
2. trending: which formats competitors started using in the last two weeks (Ad Library dates);
3. formats: Muse Spark picks the formats that fit this app, each with a persona and an angle;
4. app cut-outs: SAM 3.1 finds the bare interface and the mascot in the store screenshots (cached);
5. briefs: a fast shot list per format (trend → twist with the real app → CTA), checked like any copy;
6. photos: Muse Image, candid phone-camera style (never the product), cached;
7. sound: voice-over checked by Muse Voice Transcribe, sound effects on the cuts, music (ElevenLabs);
8. render: the Remotion `Trend` composition.

Outputs land in `<run>/videos/` (`trend-<n>-<id>.mp4` + poster) with `trends.json`: the trending
signals, the picks, the briefs, the voice guard verdicts, failures and cost.
"""

import json
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PIL import Image

from whynot.agency.create import localised
from whynot.agency.video import CACHE, VideoConfig, _as_of, scene_image
from whynot.agents import brief as classic_brief
from whynot.agents import trend_brief
from whynot.agents.ask import Answer, ChatClient, Invalid, ask_json
from whynot.agents.deconstruct import DeconstructionStore, deconstruct_all
from whynot.agents.director import Context
from whynot.agents.strategist import Strategy
from whynot.assets.cutouts import cutouts
from whynot.audio.captions import MAX_WORD_ERROR_RATE, to_wav16k, word_error_rate, words
from whynot.audio.elevenlabs import DEFAULT_VOICE, ElevenLabs
from whynot.create import remotion, trend_render
from whynot.create.locale import LANGUAGES, language_groups
from whynot.create.trends import FORMATS, TrendSignal, trending
from whynot.ingest.adlibrary import load_jsonl
from whynot.ingest.creatives import CreativeStore, capture
from whynot.models import image_data_url
from whynot.sim.arena import brand_name

PHOTO_STYLE = ("Candid vertical photo taken on a phone, natural light, real and unpolished, like a frame from a "
               "creator's video. No text, no letters, no logos, no screens, no phones.")

PICK_PROMPT = """You are the head of creative at a short-form ad agency. Pick the {n} viral formats this app should
use now, each with one persona and one angle of our strategy. Prefer formats competitors are starting to use
(they are working now) when they fit; never force a format that doesn't fit the app.

App: {app} — {description}
Has a mascot: {mascot}
Personas: {personas}
Angles: {angles}

Formats (id: name — why it works; what it needs):
{formats}

What competitors started in the last 2 weeks (format: new ads / all ads / advertisers):
{trending}

Return JSON only: {{"picks": [{{"format": "<id>", "persona": "<id>", "angle": "<id>", "why": "<one sentence>"}}]}}
Rules: {n} different formats; the angle must belong to the persona; skip formats that need a mascot if there is none."""


def pick_formats(client: ChatClient, strategy: Strategy, signals: list[TrendSignal], *, app: str, description: str,
                 has_mascot: bool, n: int, model: str) -> Answer[list[dict[str, str]]]:
    ids = {f.id for f in FORMATS}
    personas = {p.id for p in strategy.personas}
    angle_persona = {a.id: a.persona for a in strategy.angles}

    def validate(data: Any) -> list[dict[str, str]]:
        picks = data.get("picks") if isinstance(data, dict) else None
        if not isinstance(picks, list) or len(picks) != n:
            raise Invalid(f"'picks' must be a list of exactly {n}")
        out = []
        for i, p in enumerate(picks, 1):
            if not isinstance(p, dict) or p.get("format") not in ids:
                raise Invalid(f"pick {i}: 'format' must be one of {sorted(ids)}")
            if p.get("persona") not in personas or angle_persona.get(str(p.get("angle"))) != p["persona"]:
                raise Invalid(f"pick {i}: persona must be one of {sorted(personas)} and the angle one of its angles")
            if not has_mascot and "mascot" in trend_brief.get_format(p["format"]).needs and \
                    "screen" not in trend_brief.get_format(p["format"]).needs:
                raise Invalid(f"pick {i}: {p['format']} needs a mascot; this app has none")
            out.append({"format": p["format"], "persona": p["persona"], "angle": p["angle"],
                        "why": " ".join(str(p.get("why", "")).split())[:300]})
        if len({p["format"] for p in out}) != n:
            raise Invalid("each pick must use a different format")
        return out

    prompt = PICK_PROMPT.format(
        n=n, app=app, description=" ".join(description.split())[:500], mascot="yes" if has_mascot else "no",
        personas="; ".join(f"{p.id} = {p.description}" for p in strategy.personas),
        angles="; ".join(f"{a.id} (persona {a.persona}) = {a.idea}" for a in strategy.angles),
        formats="\n".join(f"- {f.id}: {f.name} — {f.why}; needs {', '.join(f.needs)}" for f in FORMATS),
        trending="\n".join(f"- {s.format}: {s.new_ads} / {s.ads} / {s.advertisers}" for s in signals[:8])
        or "(no competitor ad follows a known format)")
    return ask_json(client, [{"role": "user", "content": prompt}], validate, module="trend_formats", model=model,
                    repairs=2, max_tokens=3000, reasoning_effort="low")


def voice_track(voice: ElevenLabs, model: Any, text: str, language: str, voice_id: str | None
                ) -> tuple[Any, dict[str, Any]]:
    """The voice-over, checked by Muse Voice Transcribe (one retry with another seed, then dropped)."""
    guard: dict[str, Any] = {"script": text}
    for seed in (7, 8):
        v = voice.voice(text, voice_id=voice_id or DEFAULT_VOICE, seed=seed)
        try:
            heard = model.transcribe(to_wav16k(v.mp3), module="voice_guard", languages=[language])
        except Exception as exc:  # reported, never hidden
            guard.update(checked=False, error=f"{type(exc).__name__}: {exc}"[:200])
            return v, guard
        wer = word_error_rate(text, heard)
        guard.update(checked=True, heard=heard, word_error_rate=round(wer, 3), seed=seed)
        if wer <= MAX_WORD_ERROR_RATE:
            return v, guard
    guard["dropped"] = True
    return None, guard


def make_trend_videos(run_dir: Path, model: Any, *, cfg: VideoConfig | None = None, voice: ElevenLabs | None = None,
                      voice_id: str | None = None, token: str = "", renderer_factory: Callable[[], Any] | None = None,
                      say: Callable[[str], None] = print) -> dict[str, Any]:
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
    if not remotion.available():
        raise RuntimeError("trend videos need Remotion: run `cd video && npm install`")

    store = CreativeStore(CACHE / "creatives")
    missing = [a for a in ads if a.snapshot_url and not store.has(a.id)]
    if missing and cfg.capture and renderer_factory is not None:
        say(f"capturing {len(missing)} competitor creatives...")
        r = renderer_factory()
        try:
            capture(missing, store, token=token, renderer=r)
        finally:
            getattr(r, "close", lambda: None)()
    images = {a.id: (store.path(a.id), "video" if info.kind == "video" else "static")
              for a in ads if (info := store.info(a.id))}
    dec = deconstruct_all(model, ads, images, DeconstructionStore(CACHE / "deconstruct"), model=cfg.model)
    signals = trending(dec.done, ads, as_of=_as_of(ads))
    report["trending"] = [asdict(s) for s in signals]
    say(f"market: {len(dec.done)} ads deconstructed; trending formats: "
        + (", ".join(f"{s.format} ({s.new_ads} new)" for s in signals[:4]) or "none"))

    shots: list[Image.Image] = [Image.open(run_dir / "assets" / s) for s in brand["screenshots"]]
    cut = cutouts(model, shots, CACHE / "sam")
    say(f"app cut-outs: {len(cut.screens)} interfaces, mascot {'found' if cut.mascot else 'none'}")
    screens_path = out / "screens.json"
    if screens_path.exists():
        screens = json.loads(screens_path.read_text())
    else:
        screens = classic_brief.describe_screens(model, app["name"], [image_data_url(run_dir / "assets" / s)
                                                                     for s in brand["screenshots"]],
                                                 model=cfg.model).value
        screens_path.write_text(json.dumps(screens, indent=1, ensure_ascii=False))

    groups = language_groups([c.upper() for c in config["countries"]], override=config.get("language"))
    code, countries = next(iter(groups.items()))
    local = localised(strategy, countries)
    picks = pick_formats(model, local, signals, app=app["name"], description=app["description"],
                         has_mascot=cut.mascot is not None, n=cfg.n_videos, model=cfg.model).value
    report["picks"] = picks
    say("formats: " + ", ".join(f"{p['format']} → {p['angle']}" for p in picks))

    names = tuple(sorted({a.page_name for a in ads if a.page_name}))
    ctx = Context(local, app["name"], app["description"], names, tuple(brand["palette"][:3]),
                  brand["screenshots"][0], LANGUAGES[code])
    icon = Image.open(run_dir / "assets" / "icon.png")
    videos = []
    for n, p in enumerate(picks, 1):
        try:
            fmt = trend_brief.get_format(p["format"])
            b = trend_brief.write(model, ctx, fmt, persona=p["persona"], angle=p["angle"], screens=screens,
                                  has_mascot=cut.mascot is not None, model=cfg.model).value
            imgs: dict[int, Image.Image] = {}
            for i, s in enumerate(b.shots):
                if s.visual == "photo":
                    imgs[i] = scene_image(model, s.prompt or "", CACHE / "scenes", style=PHOTO_STYLE)
                elif s.visual == "screen" and s.screen:
                    imgs[i] = cut.screens[s.screen - 1]
                elif s.visual == "mascot" and cut.mascot is not None:
                    imgs[i] = cut.mascot
            audio, guard, sfx = None, {"skipped": "no voice client"}, {}
            if voice is not None:
                v, guard = voice_track(voice, model, b.voice, ctx.language, voice_id) if b.voice else (None, {})
                music = voice.music(b.music, b.seconds + 3)
                audio = remotion.Audio(v.mp3 if v else None, words(v.characters, v.starts, v.ends) if v else None,
                                       music, music_volume=0.28)
                sfx = {name: voice.sfx(name) for name in {s.sfx for s in b.shots} if name != "none"}
            name = f"trend-{n}-{b.id}"
            facts = trend_render.render(b, out / f"{name}.mp4", palette=brand["palette"],
                                        app_name=brand_name(app["name"]), images=imgs, icon=icon,
                                        rating=app.get("rating"), rating_count=app.get("rating_count"),
                                        audio=audio, sfx=sfx)
            videos.append({"brief": b.to_json(), "file": facts, "poster": f"{name}.poster.jpg",
                           "voice_guard": guard, "why": p["why"]})
            say(f"  ✓ {name}: {facts['seconds']} s, {len(b.shots)} shots — \"{b.hook}\"")
        except Exception as exc:  # one failed video must not lose the others
            report["failures"].setdefault("videos", {})[p["format"]] = f"{type(exc).__name__}: {exc}"[:400]
            say(f"  ✗ {p['format']}: {exc}")
    report["videos"] = videos
    report["usd"] = round(model.spent_usd - spent0, 4)
    (out / "trends.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str))
    return report
