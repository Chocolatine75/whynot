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
from concurrent.futures import ThreadPoolExecutor
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
from whynot.audio.captions import (
    MAX_WORD_ERROR_RATE,
    Word,
    audio_seconds,
    join_clips,
    to_wav16k,
    word_error_rate,
    words,
)
from whynot.audio.elevenlabs import DEFAULT_VOICE, SFX_PROMPTS, ElevenLabs
from whynot.audio.voices import LANGUAGE_NAMES, cast
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


NATIVE_FLAG_WER = 0.35  # a native line heard this far from its text is flagged (transcription of it may be weak)


LINE_GAP_S = 0.18  # a breath between two lines


def dialogue_track(voice: ElevenLabs, model: Any, b: trend_brief.TrendBrief, ad_code: str, folder: Path
                   ) -> tuple[Any, list[Word], dict[str, Any]]:
    """The dialogue: each line generated on its own (exact timing), checked, then joined with short gaps.

    One take with several voices (ElevenLabs text-to-dialogue) was tried first: its timing drifted from the
    audio, so captions went out of sync and the guard listened to the wrong piece. Per line, the timing is
    exact and each line is checked on its own clip by Muse Voice Transcribe in its language. The creator's
    lines must match their text (word error rate ≤ 0.2 over all their words), else a line is regenerated
    once with another seed, then the voice is dropped. Native lines are flagged above 0.35, never dropped."""
    casts = [cast(x.speaker, x.language, ad_code, gender=x.gender, accent=x.accent) for x in b.lines]
    checks: list[dict[str, Any]] = []
    takes = []
    for i, (x, c) in enumerate(zip(b.lines, casts, strict=True)):
        best = None
        for seed in (7, 8):
            v = voice.voice(x.text, voice_id=c.voice_id, seed=seed)
            try:
                heard = model.transcribe(to_wav16k(v.mp3), module="voice_guard",
                                         languages=[LANGUAGE_NAMES.get(x.language, x.language)])
                wer = word_error_rate(x.text, heard)
                check: dict[str, Any] = {"line": i, "speaker": x.speaker, "language": x.language, "heard": heard,
                                         "word_error_rate": round(wer, 3), "seed": seed}
            except Exception as exc:  # reported, never hidden
                wer, check = 0.0, {"line": i, "speaker": x.speaker, "checked": False,
                                   "error": f"{type(exc).__name__}: {exc}"[:200]}
            if best is None or wer < best[1]:
                best = (v, wer, check)
            if x.speaker == "them" or wer <= MAX_WORD_ERROR_RATE:
                break
        assert best is not None
        v, wer, check = best
        if x.speaker == "them" and wer > NATIVE_FLAG_WER:
            check["flagged"] = True
        checks.append(check)
        takes.append(v)
    mine = [(float(c.get("word_error_rate", 0.0)), len(x.text.split())) for c, x in zip(checks, b.lines, strict=True)
            if x.speaker == "me"]
    n = sum(k for _, k in mine)
    creator_wer = sum(w * k for w, k in mine) / n if n else 0.0
    guard: dict[str, Any] = {"lines": checks, "creator_word_error_rate": round(creator_wer, 3)}
    if creator_wer > MAX_WORD_ERROR_RATE:
        guard["dropped"] = True
        return None, [], guard
    # join the clips with a breath between lines; every word keeps its exact time, shifted by its line's start
    ws: list[Word] = []
    t = 0.0
    parts: list[tuple[Path, float]] = []
    for i, v in enumerate(takes):
        for w in words(v.characters, v.starts, v.ends):
            # captions set apart by LANGUAGE, not by voice: the creator's own Vietnamese is shown apart too
            other = b.lines[i].language != ad_code
            ws.append(Word(w.text, round(w.start + t, 3), round(w.end + t, 3), b.lines[i].speaker, other))
        dur = audio_seconds(v.mp3)
        parts.append((v.mp3, dur))
        t += dur + LINE_GAP_S
    out = folder / f"dialogue-{b.id}.mp3"
    join_clips(parts, out, gap=LINE_GAP_S)
    return out, ws, guard


def save_report(out: Path, report: dict[str, Any]) -> Path:
    """`trends.json`, without ever losing scripts: a run with no video goes to `trends-failed.json`, and the
    previous good report is archived (`trends-<time>.json`) so its scripts can still be re-rendered."""
    target = out / "trends.json"
    if not report.get("videos") and target.exists():
        target = out / "trends-failed.json"
    elif target.exists():
        target.replace(out / f"trends-{int(target.stat().st_mtime * 1000)}.json")
    target.write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str))
    return target


class Studio:
    """Everything a trend video needs about one app, prepared once: the market and its trending formats,
    the real UI and mascot cut-outs, the screen descriptions, the strategy context and what sells. `make`
    then turns one idea (format, persona, angle) into a finished video. Used by `whynot video` and by the
    daily loop."""

    def __init__(self, run_dir: Path, model: Any, *, cfg: VideoConfig | None = None, voice: ElevenLabs | None = None,
                 voice_id: str | None = None, token: str = "", renderer_factory: Callable[[], Any] | None = None,
                 say: Callable[[str], None] = print):
        self.cfg = cfg = cfg or VideoConfig()
        self.run_dir = run_dir = Path(run_dir)
        self.model, self.voice, self.voice_id, self.say = model, voice, voice_id, say
        self.out = run_dir / "videos"
        self.out.mkdir(exist_ok=True)
        app = self.app = json.loads((run_dir / "app.json").read_text())
        brand = self.brand = json.loads((run_dir / "brand.json").read_text())
        config = json.loads((run_dir / "config.json").read_text())
        strategy = Strategy.from_json(json.loads((run_dir / "strategy.json").read_text()))
        ads = load_jsonl(run_dir / "market_ads.jsonl")
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
        self.signals = trending(dec.done, ads, as_of=_as_of(ads))
        say(f"market: {len(dec.done)} ads deconstructed; trending formats: "
            + (", ".join(f"{s.format} ({s.new_ads} new)" for s in self.signals[:4]) or "none"))

        shots: list[Image.Image] = [Image.open(run_dir / "assets" / s) for s in brand["screenshots"]]
        self.cut = cutouts(model, shots, CACHE / "sam")
        say(f"app cut-outs: {len(self.cut.screens)} interfaces, mascot {'found' if self.cut.mascot else 'none'}")
        screens_path = self.out / "screens.json"
        if screens_path.exists():
            self.screens = json.loads(screens_path.read_text())
        else:
            self.screens = classic_brief.describe_screens(
                model, app["name"], [image_data_url(run_dir / "assets" / s) for s in brand["screenshots"]],
                model=cfg.model).value
            screens_path.write_text(json.dumps(self.screens, indent=1, ensure_ascii=False))

        groups = language_groups([c.upper() for c in config["countries"]], override=config.get("language"))
        code, countries = next(iter(groups.items()))
        self.strategy = localised(strategy, countries)
        self.selling = trend_brief.selling_from_app(app, brand_name(app["name"]))
        names = tuple(sorted({a.page_name for a in ads if a.page_name}))
        self.ctx = Context(self.strategy, app["name"], app["description"], names, tuple(brand["palette"][:3]),
                           brand["screenshots"][0], LANGUAGES[code])
        self.icon = Image.open(run_dir / "assets" / "icon.png")

    def pick(self, n: int) -> list[dict[str, Any]]:
        return list(pick_formats(self.model, self.strategy, self.signals, app=self.app["name"],
                                 description=self.app["description"], has_mascot=self.cut.mascot is not None,
                                 n=n, model=self.cfg.model).value)

    def make(self, p: dict[str, Any], name_prefix: str, *, avoid: list[tuple[str, str]] | None = None
             ) -> dict[str, Any]:
        """One video for `p` (format, persona, angle; or a saved "brief" to render again). `avoid`: (hook, voice)
        of past ads, whose words the new script must not repeat."""
        model, voice, out = self.model, self.voice, self.out
        if "brief" in p:  # re-render a brief as it is (no rewrite)
            b = trend_brief.TrendBrief.from_json(p["brief"])
        else:
            fmt = trend_brief.get_format(p["format"])
            b = trend_brief.write(model, self.ctx, fmt, persona=p["persona"], angle=p["angle"], screens=self.screens,
                                  has_mascot=self.cut.mascot is not None, selling=self.selling, avoid=avoid,
                                  model=self.cfg.model).value
        imgs: dict[int, Image.Image] = {}
        for i, s in enumerate(b.shots):
            if s.visual == "photo":
                imgs[i] = scene_image(model, s.prompt or "", CACHE / "scenes", style=PHOTO_STYLE)
            elif s.visual == "screen" and s.screen:
                imgs[i] = self.cut.screens[s.screen - 1]
            elif s.visual == "mascot" and self.cut.mascot is not None:
                imgs[i] = self.cut.mascot
        audio, guard, sfx = None, {"skipped": "no voice client"}, {}
        if voice is not None:
            ad_code = next((c for c, n in LANGUAGE_NAMES.items() if n == self.ctx.language), "en")
            if b.lines:
                mp3, ws, guard = dialogue_track(voice, model, b, ad_code, out)
                cap = ws or None
            elif b.voice:
                v, guard = voice_track(voice, model, b.voice, self.ctx.language, self.voice_id)
                mp3, cap = (v.mp3 if v else None), (words(v.characters, v.starts, v.ends) if v else None)
            else:
                mp3, cap, guard = None, None, {}
            music = voice.music(b.music, b.seconds + 3)
            audio = remotion.Audio(mp3, cap, music, music_volume=0.28)
            # an effect we no longer offer (an older script) is simply left out
            sfx = {name: voice.sfx(name) for name in {s.sfx for s in b.shots} if name in SFX_PROMPTS}
        name = f"{name_prefix}-{b.id}"
        facts = trend_render.render(b, out / f"{name}.mp4", palette=self.brand["palette"],
                                    app_name=brand_name(self.app["name"]), images=imgs, icon=self.icon,
                                    rating=self.app.get("rating"), rating_count=self.app.get("rating_count"),
                                    audio=audio, sfx=sfx)
        self.say(f"  ✓ {name}: {facts['seconds']} s, {len(b.shots)} shots — \"{b.hook}\"")
        return {"brief": b.to_json(), "file": facts, "poster": f"{name}.poster.jpg", "voice_guard": guard,
                "why": p.get("why", "")}


def make_trend_videos(run_dir: Path, model: Any, *, cfg: VideoConfig | None = None, voice: ElevenLabs | None = None,
                      voice_id: str | None = None, token: str = "", renderer_factory: Callable[[], Any] | None = None,
                      reuse_briefs: bool = False, say: Callable[[str], None] = print) -> dict[str, Any]:
    spent0 = model.spent_usd
    studio = Studio(run_dir, model, cfg=cfg, voice=voice, voice_id=voice_id, token=token,
                    renderer_factory=renderer_factory, say=say)
    report: dict[str, Any] = {"app": studio.app["name"], "failures": {},
                              "trending": [asdict(s) for s in studio.signals]}
    previous = studio.out / "trends.json"
    picks: list[dict[str, Any]]
    if reuse_briefs and previous.exists():  # the same scripts, rendered again (new transitions, sounds...)
        picks = [{"format": v["brief"]["format"], "persona": v["brief"]["persona"], "angle": v["brief"]["angle"],
                  "why": v.get("why", ""), "brief": v["brief"]} for v in json.loads(previous.read_text())["videos"]]
    else:
        picks = studio.pick(studio.cfg.n_videos)
    report["picks"] = [{k: v for k, v in p.items() if k != "brief"} for p in picks]
    say("formats: " + ", ".join(f"{p['format']} → {p['angle']}" for p in picks))

    # the videos are independent: make them at the same time (about 3× faster than one after the other)
    videos = []
    with ThreadPoolExecutor(max_workers=max(1, min(len(picks), 3))) as pool:
        futures = {pool.submit(studio.make, p, f"trend-{n}"): p for n, p in enumerate(picks, 1)}
        for f in futures:
            p = futures[f]
            try:
                videos.append(f.result())
            except Exception as exc:  # one failed video must not lose the others
                report["failures"].setdefault("videos", {})[p["format"]] = f"{type(exc).__name__}: {exc}"[:400]
                say(f"  ✗ {p['format']}: {exc}")
    report["videos"] = videos
    report["usd"] = round(model.spent_usd - spent0, 4)
    save_report(studio.out, report)
    return report
