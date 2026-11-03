"""`whynot create`: from an app to a ready-to-launch Meta campaign.

Stages, each writing inspectable files into the run folder (resumable: a stage
whose output exists is loaded, not recomputed or re-billed):

 1. app       App Store page, reviews, real screenshots, brand palette from the icon
 2. market    Scout: competitor advertisers and their ads (Ad Library, EU/UK)
 3. strategy  Strategist (Muse Wonder): personas, objections, angles, verified claims
 4. creative  Creative director: one template per angle, checked copy
 5. produce   Composer: ad images per variant + every guard
 6. simulate  Viewer agents: each variant in fair feeds next to real competitor ads and placebos (SIMULATED)
 7. evolve    Evolver: mutate the best ads to answer viewers' objections, judge each generation in a tournament
              against its parents and the generation-0 champion, keep the strongest, noise floor (SIMULATED)
 8. plan      Campaign plan in Marketing API shape, validated; launch decisions via the autopilot
 9. report    report.md for the owner

All model calls go through one `ModelClient` with a hard budget for the run.
Nothing is sent to Meta here: the plan is created PAUSED and only published
by the autopilot under the owner's autonomy level, cap and approval.
"""

import json
import math
import random
import re
import shutil
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

from whynot.agency.report import spent_usd, write_report
from whynot.agents import director, evolver, scout, strategist
from whynot.agents.ask import AgentError
from whynot.agents.director import Context
from whynot.agents.strategist import Strategy
from whynot.assets.brand import palette_from_icon
from whynot.assets.screens import Screen
from whynot.assets.screens import pick as pick_screens
from whynot.assets.screens import prepare as prepare_screens
from whynot.budget import BudgetExceeded
from whynot.create.composer import LEGACY_LAYOUT, ComposeError, compose, hex_to_rgb, layouts_for, styles_for
from whynot.create.content import verified_content
from whynot.create.guards import publishable, run_guards
from whynot.create.locale import LANGUAGES, language_groups, unmapped
from whynot.create.templates import Template, Variant
from whynot.events import EventLog, file_digest
from whynot.ingest.adlibrary import AdLibraryClient, CompetitorAd, load_jsonl, save_jsonl
from whynot.ingest.appstore import AppProfile, AppStoreClient
from whynot.ingest.creatives import CreativeStore, Renderer, capture, shrink
from whynot.models import SPARK, WONDER, ModelClient, image_data_url
from whynot.run.autopilot import Policy
from whynot.run.campaign import (
    AdChoice,
    AdSetPlan,
    Audience,
    CampaignPlan,
    build_plan,
    launch_decisions,
    to_api,
    validate,
)
from whynot.sim import tournament
from whynot.sim.arena import brand_name, is_placebo, judge, our_item, paired_feeds, placebo_item
from whynot.sim.feed import FeedItem
from whynot.sim.personas import Persona as SimPersona
from whynot.sim.relevance import hard_competitors
from whynot.sim.scores import score_ads
from whynot.sim.viewer import Viewer, run_simulation
from whynot.validate import retest as retest_stats
from whynot.validate.stats import kendall_tau

STAGES = ("app", "market", "strategy", "creative", "produce", "simulate", "evolve", "plan", "report")
# who acts at each stage (the `agent` of its events) and the files it leaves (digested in its "ok" event)
AGENTS = {"app": "appstore", "market": "scout", "strategy": "strategist", "creative": "director",
          "produce": "composer", "simulate": "viewers", "evolve": "evolver", "plan": "planner",
          "report": "account_manager"}
OUTPUTS = {"app": ("app.json", "brand.json"), "market": ("market.json", "market_ads.jsonl"),
           "strategy": ("strategy.json",), "creative": ("templates",), "produce": ("variants.json",),
           "simulate": ("simulation.json",), "evolve": ("evolution.json",), "plan": ("plan.json", "launch.json"),
           "report": ("report.md",)}


@dataclass
class CreateConfig:
    app_ref: str  # App Store URL, app id, or the app's website
    countries: list[str]  # campaign countries
    daily_cap_eur: float  # owner's daily ad-spend cap for the plan
    budget_usd: float = 3.0  # hard cap on model spend for this run
    research_countries: list[str] | None = None  # EU/UK; default: campaign countries in the EU/UK, else GB
    store_country: str = "us"
    language: str | None = None  # language code for every ad; default: per country (create/locale.py)
    competitor_pages: list[str] = field(default_factory=list)  # owner-named Facebook page ids
    max_angles: int = 6
    variants_per_template: int = 4
    feeds_per_variant: int = 3  # feeds each candidate (variant or placebo) appears in
    placebos: int = 3  # real competitor ads dressed as ours, per persona group (bias control; 12 views by default)
    feed_size: int = 4
    viewers_per_feed: int = 2
    viewer_reasoning: str | None = "low"
    generations: int = 2  # evolution rounds after the first simulation; 0 = no evolution
    evolve_parents: int = 2  # ads kept per audience each round (best of different concepts first)
    mutations_per_parent: int = 2
    tournament_rounds: int = 2  # feeds per pair of candidates per generation (1 round: too little power, DECISIONS)
    evolve_audiences: int | None = None  # evolve only the first N simulated audiences (cost); None = all
    strategy_model: str = WONDER
    director_model: str = SPARK
    policy: Policy = field(default_factory=Policy)
    seed: int = 0
    feed_pool: int = 12  # competitor ads per language in the feeds: the most relevant ones (sim/relevance.py)
    static_formats: tuple[str, ...] = ("portrait", "square")  # formats a static variant may take (4:5 feed, 1:1)
    viewer_images: bool = True  # viewers see our composed ads and competitors' real creatives (E2-2); off = text
    image_side: int = 512  # longest side of every picture a viewer sees (images cost tokens)
    capture_creatives: int = 24  # competitor creatives to capture per language when missing (headless browser)

    def research(self) -> list[str]:
        if self.research_countries:
            return scout.check_countries(self.research_countries)
        eu = [c.upper() for c in self.countries if c.upper() in scout.EU_UK]
        return eu or ["GB"]


class StageError(RuntimeError):
    def __init__(self, stage: str, cause: Exception):
        super().__init__(f"stage '{stage}' failed: {type(cause).__name__}: {cause}")
        self.stage = stage
        self.cause = cause


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "app"


class Run:
    """The run folder: stage outputs, an event log, and the run's own cost ledger."""

    def __init__(self, folder: Path, *, parent: str | None = None, secrets: tuple[str | None, ...] = ()):
        self.dir = Path(folder)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.dir / "events.jsonl"
        self.events = EventLog(self.events_path, secrets)
        self.parent = parent  # the orchestrator step this run is part of, if any

    def path(self, *parts: str) -> Path:
        return self.dir.joinpath(*parts)

    def done(self, stage: str) -> bool:
        return self.path(f"{stage}.done").exists()

    def redo_from(self, stage: str) -> list[str]:
        """Forget `stage` and every later stage, so the next run recomputes them (earlier ones are reused)."""
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}; one of {STAGES}")
        cleared = []
        for s in STAGES[STAGES.index(stage):]:
            marker = self.path(f"{s}.done")
            if marker.exists():
                marker.unlink()
                cleared.append(s)
        return cleared

    def mark(self, stage: str) -> None:
        self.path(f"{stage}.done").write_text(datetime.now(UTC).isoformat())

    def log(self, **event: Any) -> dict[str, Any]:
        """One `AgentEvent`-shaped line in events.jsonl (agent and parent filled in, secrets removed)."""
        stage = event.get("stage", "")
        row = {"agent": AGENTS.get(stage, stage), **({"parent": self.parent} if self.parent else {}), **event}
        return self.events.write(row)

    def write_json(self, name: str, data: Any) -> Path:
        p = self.path(name)
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return p

    def read_json(self, name: str) -> Any:
        return json.loads(self.path(name).read_text(encoding="utf-8"))


@dataclass
class Clients:
    model: ModelClient
    appstore: AppStoreClient
    adlibrary: AdLibraryClient
    creatives: CreativeStore | None = None  # competitors' creatives on disk (E2-3); None = viewers read text only
    renderer: Callable[[], Renderer] | None = None  # opens a browser to capture missing creatives; None = no capture


@dataclass
class Result:
    run_dir: Path
    app: AppProfile
    strategy: Strategy
    templates: list[Template]
    choices: list[AdChoice]
    plan: CampaignPlan
    plan_errors: list[str]
    usd: float  # everything ever spent on this run folder (all invocations, redos included)
    usd_now: float = 0.0  # spent by this invocation


def _stage(run: Run, name: str, fn: Callable[[], Any], clients: Clients) -> Any:
    if run.done(name):
        run.log(stage=name, status="cached")
        return None
    start, spent = time.monotonic(), clients.model.spent_usd
    run.log(stage=name, status="start")
    try:
        out = fn()
    except Exception as exc:
        run.log(stage=name, status="error", error=f"{type(exc).__name__}: {str(exc)[:500]}",
                usd=round(clients.model.spent_usd - spent, 4))
        raise StageError(name, exc) from exc
    run.mark(name)
    outputs = {f: d for f in OUTPUTS.get(name, ()) if (d := file_digest(run.path(f)))}
    run.log(stage=name, status="ok", seconds=round(time.monotonic() - start, 2),
            usd=round(clients.model.spent_usd - spent, 4), outputs=outputs, **_guards(run, name))
    return out


def _guards(run: Run, stage: str) -> dict[str, Any]:
    """What the stage's checks said, for its event: ads passing every guard, plan errors."""
    try:
        if stage in ("produce", "evolve") and run.path("variants.json").exists():
            vs = run.read_json("variants.json")
            return {"guards": {"variants": len(vs), "passed": sum(1 for v in vs if v.get("guards_passed"))}}
        if stage == "plan" and run.path("plan.json").exists():
            return {"guards": {"plan_errors": len(run.read_json("plan.json").get("errors", []))}}
    except (ValueError, OSError):  # a summary must never fail the stage it describes
        return {}
    return {}


# --- stage functions ---------------------------------------------------------------------

def stage_app(run: Run, cfg: CreateConfig, c: Clients) -> None:
    app = c.appstore.profile(cfg.app_ref, country=cfg.store_country)
    if not app.screenshot_urls:
        raise ValueError("the App Store page has no screenshots: the ads need real app screens")
    shots = c.appstore.download_screenshots(app, run.path("assets"))
    icon_path = run.path("assets", "icon.png")
    if app.icon_url and not icon_path.exists():
        icon_path.write_bytes(c.appstore._get(app.icon_url).content)
    palette = palette_from_icon(Image.open(icon_path)) if icon_path.exists() else ["#F7F9FC", "#111827", "#2563EB"]
    run.write_json("app.json", app.to_json())
    run.write_json("brand.json", {"palette": palette, "screenshots": [p.name for p in shots]})


def stage_market(run: Run, cfg: CreateConfig, c: Clients, app: AppProfile) -> None:
    result = scout.scan(c.model, c.adlibrary, app, cfg.research(), known_pages=cfg.competitor_pages)
    save_jsonl(result.ads, run.path("market_ads.jsonl"))
    run.write_json("market.json", {**result.summary(), "research_countries": cfg.research(),
                                   "advertisers": [asdict(a) for a in result.advertisers[:60]]})


def stage_strategy(run: Run, cfg: CreateConfig, c: Clients, app: AppProfile, ads: list[CompetitorAd]) -> None:
    answer = strategist.plan_strategy(c.model, app, ads, [x.upper() for x in cfg.countries], model=cfg.strategy_model)
    run.write_json("strategy.json", answer.value.to_json())
    run.write_json("strategy.raw.json", {"attempts": answer.attempts, "errors": answer.errors, "usd": answer.usd,
                                         "answer": answer.raw})


def pick_angles(strategy: Strategy, n: int) -> list[str]:
    """Up to n angles, covering every persona first (round-robin over personas)."""
    by_persona: dict[str, list[str]] = {}
    for a in strategy.angles:
        by_persona.setdefault(a.persona, []).append(a.id)
    out: list[str] = []
    while len(out) < n and any(by_persona.values()):
        for p in list(by_persona):
            if by_persona[p] and len(out) < n:
                out.append(by_persona[p].pop(0))
    return out


def languages(cfg: CreateConfig) -> dict[str, list[str]]:
    return language_groups([c.upper() for c in cfg.countries], override=cfg.language)


def localised(strategy: Strategy, countries: list[str]) -> Strategy:
    """The strategy restricted to personas targeting some of `countries` (and those countries only)."""
    personas = [replace(p, countries=tuple(c for c in p.countries if c in countries)) for p in strategy.personas]
    personas = [p for p in personas if p.countries]
    keep = {p.id for p in personas}
    return replace(strategy, personas=personas, angles=[a for a in strategy.angles if a.persona in keep])


def static_screens(run: Run, c: Clients, app: AppProfile, brand: dict[str, Any], log: dict[str, Any]) -> list[Screen]:
    """Screens cut out and described for the statics; on any failure, the store posters in turn (logged)."""
    try:
        return prepare_screens(c.model, run.path("assets"), app.name, list(brand["screenshots"]),
                               sam_cache=run.path("assets", "sam"))
    except Exception as exc:  # better a poster than no ad: the ads are still made, the report says why
        log["screens"] = f"screens not cut out ({type(exc).__name__}: {str(exc)[:200]}); store posters used in turn"
        return []


def stage_creative(run: Run, cfg: CreateConfig, c: Clients, app: AppProfile, strategy: Strategy,
                   market: dict[str, Any], brand: dict[str, Any]) -> None:
    """One template set per ad language: French ads for France, English ads for the UK."""
    names = tuple(x["page_name"] for x in market.get("advertisers", []) if x.get("page_name"))
    folder = run.path("templates")
    folder.mkdir(exist_ok=True)
    for old in folder.glob("*.yaml"):  # a redo replaces the whole set
        old.unlink()
    # ...and the copy evolution keeps of the previous set: else `evolve` would restore the OLD templates over these
    shutil.rmtree(run.path("templates_gen0"), ignore_errors=True)
    log: dict[str, Any] = {}
    screens = static_screens(run, c, app, brand, log)
    made: list[dict[str, Any]] = []
    for code, countries in languages(cfg).items():
        local = localised(strategy, countries)
        angles = pick_angles(local, cfg.max_angles)
        if not angles:
            continue
        ctx = Context(local, app.name, app.description, names, tuple(brand["palette"]), brand["screenshots"][0],
                      LANGUAGES[code])
        answer = director.write_templates(c.model, ctx, angles, model=cfg.director_model)
        log[code] = {"countries": countries, "attempts": answer.attempts, "errors": answer.errors}
        for i, t in enumerate(answer.value):
            d = t.to_dict()
            d["id"] = t.id.removesuffix("_v1") + f"_{code}_v1"
            d["fixed"]["language"] = code
            d["fixed"]["product"]["asset"] = brand["screenshots"][i % len(brand["screenshots"])]
            made.append(d)
    if screens and made:  # the real screen that shows what each concept talks about, cut out of its store poster
        picks = pick_screens(c.model, app.name, {d["id"]: d["concept"] for d in made}, screens)
        for d in made:
            d["fixed"]["product"]["asset"] = picks[d["id"]].asset
    for d in made:  # how the picture may look (E5-2): layouts its verified facts allow, readable styles, formats
        d["fixed"]["content"] = verified_content(strategy, app, d["evidence"]["angle"], d["fixed"]["language"])
        legacy = [LEGACY_LAYOUT[s] for s in d["genes"].pop("first_shot", []) if s in LEGACY_LAYOUT]
        d["genes"]["layout"] = list(dict.fromkeys(legacy + layouts_for(d["fixed"]["content"])))
        d["genes"]["style"] = styles_for([hex_to_rgb(x) for x in d["fixed"]["brand"]["palette"]])
        d["genes"]["format"] = list(cfg.static_formats)
        log["screens"] = {d["id"]: picks[d["id"]].description for d in made}
    for d in made:
        (folder / f"{d['id']}.yaml").write_text(yaml.safe_dump(d, sort_keys=False, allow_unicode=True),
                                                encoding="utf-8")
    run.write_json("creative.json", log)


def load_templates(run: Run) -> list[Template]:
    return [Template.load(p) for p in sorted(run.path("templates").glob("*.yaml"))]


def produce_row(run: Run, t: Template, genome: dict[str, str], **extra: Any) -> dict[str, Any]:
    """Compose one variant, save its image, run every guard: the row stored in variants.json."""
    v = Variant(t.id, genome)
    row: dict[str, Any] = {"variant_id": v.id, "template_id": t.id, "persona": t.persona, "genome": genome,
                           "language": t.fixed.get("language", "en"), "generation": 0, **extra}
    asset = Image.open(run.path("assets", t.fixed["product"]["asset"]))
    try:
        comp = compose(t, genome, asset)
    except ComposeError as exc:
        return {**row, "error": str(exc), "guards_passed": False}
    comp.image.save(run.path("ads", f"{v.id}.png"))
    results = run_guards(t, comp, asset)
    story = story_version(run, t, genome, asset, v.id)
    return {**row, "image": f"ads/{v.id}.png", "guards": {k: asdict(r) for k, r in results.items()},
            "guards_passed": publishable(results), **story,
            "texts": {g: t.text(g, genome[g]) for g in ("hook", "body", "title", "proof", "cta") if g in genome}}


def story_version(run: Run, t: Template, genome: dict[str, str], asset: Image.Image, vid: str) -> dict[str, Any]:
    """The same ad in 9:16 for Stories and Reels (text kept out of the zones Meta covers), guarded the same way.
    Saved next to the feed picture; the simulated feed judges the feed picture."""
    if genome.get("format") == "story":
        return {}
    d = t.to_dict()
    d["genes"]["format"] = list(dict.fromkeys([*d["genes"]["format"], "story"]))
    tall = Template.from_dict(d)
    try:
        comp = compose(tall, {**genome, "format": "story"}, asset)
    except ComposeError as exc:
        return {"story_error": str(exc)}
    comp.image.save(run.path("ads", f"{vid}.story.png"))
    return {"story_image": f"ads/{vid}.story.png", "story_guards_passed": publishable(run_guards(tall, comp, asset))}


def stage_produce(run: Run, cfg: CreateConfig, templates: list[Template]) -> None:
    out = run.path("ads")
    out.mkdir(exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    rows = [produce_row(run, t, genome) for t in templates for genome in t.sample(cfg.variants_per_template,
                                                                                   seed=cfg.seed)]
    run.write_json("variants.json", rows)


def feed_competitors(ads: list[CompetitorAd], code: str, app: AppProfile, cfg: CreateConfig,
                     images: dict[str, str] | None = None) -> tuple[list[FeedItem], dict[str, Any]]:
    """Hard feeds: the competitor ads most relevant to ads in language `code` (language, longevity, topic).

    Longevity is counted up to the latest date seen in the market data, not today, so a rerun on recorded
    inputs picks the same ads. With `images` (ad id → data URL), the feeds use only competitors whose real
    creative is known, so every ad in a feed is seen the same way; `info["images"]` says whether that was
    possible (enough of them) or the feeds stay text-only."""
    dates = [d for a in ads for d in (a.start_date, a.stop_date) if d]
    as_of = max(dates) if dates else datetime.now(UTC).date()
    need = cfg.placebos + cfg.feed_size - 2
    pictured = [a for a in ads if a.id in images] if images else []
    with_images = len(pictured) >= need
    hard = hard_competitors(pictured if with_images else ads, language=code, topic=f"{app.name} {app.description}",
                            as_of=as_of, k=max(cfg.feed_pool, need))
    if with_images and len(hard.ads) < need:  # the pictured ads are in other languages: text for everyone
        with_images = False
        hard = hard_competitors(ads, language=code, topic=f"{app.name} {app.description}", as_of=as_of,
                                k=max(cfg.feed_pool, need))
    info = {"pool": len(hard.ads), "long_running": sum(r.long_running for r in hard.ranked),
            "wrong_language": hard.wrong_language_used, "images": with_images}
    items = [FeedItem.from_ad(a) for a in hard.ads]
    if with_images and images:
        items = [replace(x, image_url=images[x.ad_id]) for x in items]
    return items, info


def competitor_images(cfg: CreateConfig, c: Clients, ads: list[CompetitorAd], app: AppProfile, *,
                      capture_missing: bool = True) -> tuple[dict[str, str], dict[str, Any]]:
    """Competitors' real creatives for the viewers (E2-2): ad id → data URL, and what happened.

    The creatives come from the snapshot capture (E2-3, `data/cache/creatives`, shared by every run). Missing
    ones among the most relevant ads per language are captured first, when a browser is available; one page
    that fails is skipped. No store, or `viewer_images` off: no image (text-only feeds, said in the info)."""
    if not cfg.viewer_images:
        return {}, {"on": False, "why": "text-only: viewer_images is off"}
    store = c.creatives
    if store is None:
        return {}, {"on": False, "why": "no creative store: viewers read text only"}
    failed: dict[str, str] = {}
    if capture_missing and c.renderer is not None and c.adlibrary.token:
        dates = [d for a in ads for d in (a.start_date, a.stop_date) if d]
        as_of = max(dates) if dates else datetime.now(UTC).date()
        wanted: dict[str, CompetitorAd] = {}
        for code in languages(cfg):
            hard = hard_competitors(ads, language=code, topic=f"{app.name} {app.description}", as_of=as_of,
                                    k=cfg.capture_creatives)
            wanted.update((a.id, a) for a in hard.ads if a.snapshot_url and not store.has(a.id))
        if wanted:
            try:
                r = c.renderer()
            except Exception as exc:  # no browser on this machine: text-only, said in the info
                failed["renderer"] = f"{type(exc).__name__}: {exc}"[:200]
            else:
                try:
                    failed |= capture(list(wanted.values()), store, token=c.adlibrary.token, renderer=r,
                                      max_side=cfg.image_side).failed
                finally:
                    close = getattr(r, "close", None)
                    if close:
                        close()
    images = {}
    for a in ads:
        if store.has(a.id):
            jpeg, _, _ = shrink(store.path(a.id).read_bytes(), cfg.image_side)
            images[a.id] = image_data_url(jpeg, "image/jpeg")
    return images, {"on": True, "competitors_with_image": len(images), "capture_failed": len(failed)}


def ad_picture(run: Run, cfg: CreateConfig) -> Callable[[dict[str, Any]], str | None]:
    """Our variant's composed ad (`ads/<id>.png`) as the viewer sees it: a small JPEG data URL, made once."""
    made: dict[str, str | None] = {}

    def picture(v: dict[str, Any]) -> str | None:
        rel = v.get("image")
        if not rel:
            return None
        if rel not in made:
            path = run.path(rel)
            made[rel] = (image_data_url(shrink(path.read_bytes(), cfg.image_side)[0], "image/jpeg")
                         if path.exists() else None)
        return made[rel]
    return picture


def no_picture(v: dict[str, Any]) -> str | None:
    return None


def viewer_personas(p: strategist.Persona, n: int) -> list[SimPersona]:
    """Viewers for a persona: who they are and what they want. Objections are measured, never given to them."""
    genders = [p.gender] if p.gender != "all" else ["female", "male"]
    traits = (p.description, "wants: " + "; ".join(p.motivations))
    return [SimPersona(f"{p.id}_{i}", p.countries[i % len(p.countries)], f"{p.age_min}-{p.age_max}",
                       genders[i % len(genders)], traits) for i in range(n)]


@dataclass
class Round:
    verdicts: dict[str, dict[str, Any]]  # our variants only
    info: dict[str, Any]  # placebo lift/intent/views, biased, feeds — or an error
    usd: float
    failures: list[dict[str, str]]


def arena_round(viewer: Viewer, persona: strategist.Persona, rows: list[dict[str, Any]],
                competitors: list[FeedItem], brand: str, cfg: CreateConfig, rng: random.Random, *,
                seed: int, picture: Callable[[dict[str, Any]], str | None] = no_picture) -> Round:
    """One fair-feed comparison of `rows` (our variants) with fresh placebos, for one persona's viewers."""
    placebos = [placebo_item(a, brand) for a in rng.sample(competitors, cfg.placebos)]
    candidates = [our_item(v["variant_id"], brand, v["texts"], picture(v)) for v in rows] + placebos
    feeds = paired_feeds(candidates, competitors, feed_size=cfg.feed_size, appearances=cfg.feeds_per_variant,
                         seed=seed)
    sim = run_simulation(viewer, viewer_personas(persona, max(cfg.viewers_per_feed, 2)), feeds,
                         viewers_per_feed=cfg.viewers_per_feed)
    ids = {x.ad_id for x in candidates}
    scored = {k: s for k, s in score_ads(sim.reactions).items() if k in ids}
    try:
        result = judge(scored, ids)
    except ValueError as exc:  # every viewer failed: nothing to judge
        return Round({}, {"error": str(exc), "feeds": len(feeds)}, sim.usd, sim.failures)
    info = {"placebo_lift": result.placebo_lift, "placebo_intent": result.placebo_intent, "biased": result.biased,
            "placebo_views": result.placebo_views, "feeds": len(feeds)}
    verdicts = {k: {**asdict(v), "top_why_not": scored[k].top_why_not, "biased_group": result.biased}
                for k, v in result.verdicts.items()}
    return Round(verdicts, info, sim.usd, sim.failures)


def stage_simulate(run: Run, cfg: CreateConfig, c: Clients, app: AppProfile, strategy: Strategy,
                   ads: list[CompetitorAd], variants: list[dict[str, Any]]) -> None:
    """Fair feeds with placebos (sim/arena.py): our variants head-to-head next to real competitor ads."""
    ok = [v for v in variants if v.get("guards_passed")]
    competitors = [FeedItem.from_ad(a) for a in ads if (a.bodies or [""])[0].strip()]
    needed = cfg.placebos + cfg.feed_size - 2
    if len(competitors) < needed:
        run.write_json("simulation.json", {"simulated": False, "scores": {}, "groups": [],
                                           "reason": f"only {len(competitors)} competitor ads (need {needed})"})
        return
    brand = brand_name(app.name)
    viewer = Viewer(c.model, reasoning_effort=cfg.viewer_reasoning)
    images, images_info = competitor_images(cfg, c, ads, app)
    picture = ad_picture(run, cfg)
    verdicts: dict[str, Any] = {}
    groups_out: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    usd = 0.0
    rng = random.Random(cfg.seed)
    groups = languages(cfg)
    for p_all, code in ((p, code) for p in strategy.personas for code in groups):
        p = replace(p_all, countries=tuple(x for x in p_all.countries if x in groups[code]))
        mine = [v for v in ok if v["persona"] == p.id and v.get("language", "en") == code]
        if not mine or not p.countries:
            continue
        pool, pool_info = feed_competitors(ads, code, app, cfg, images)
        r = arena_round(viewer, p, mine, pool, brand, cfg, rng, seed=cfg.seed + len(groups_out),
                        picture=picture if pool_info["images"] else no_picture)
        usd += r.usd
        failures += r.failures
        groups_out.append({"persona": p.id, "language": code, **r.info, "variants": len(mine),
                           "competitors": pool_info})
        verdicts.update(r.verdicts)
    feeds = sum(int(g.get("feeds", 0)) for g in groups_out)
    images_info["groups_with_images"] = sum(bool(g["competitors"].get("images")) for g in groups_out)
    run.write_json("simulation.json", {"simulated": True, "brand": brand, "usd": usd, "failures": failures,
                                       "feeds": feeds, "usd_per_feed": round(usd / feeds, 5) if feeds else None,
                                       "images": images_info, "groups": groups_out, "scores": verdicts})


def pick_parents(rows: list[dict[str, Any]], rank: dict[str, tuple[float, ...]], k: int) -> list[dict[str, Any]]:
    """Best k ranked rows (highest tuple first), preferring different templates (concept diversity), ties by id."""
    ranked = sorted((r for r in rows if r["variant_id"] in rank),
                    key=lambda r: (tuple(-x for x in rank[r["variant_id"]]), r["variant_id"]))
    chosen: list[dict[str, Any]] = []
    for r in ranked:
        if len(chosen) < k and r["template_id"] not in {c["template_id"] for c in chosen}:
            chosen.append(r)
    for r in ranked:  # fill from the same concepts if there are fewer concepts than k
        if len(chosen) < k and r not in chosen:
            chosen.append(r)
    return chosen


def lift_rank(scores: dict[str, dict[str, Any]]) -> dict[str, tuple[float, ...]]:
    """Generation 0 (arena feeds): lift over placebo, then intent."""
    return {k: (float(s["lift_over_placebo"]), float(s["intent"])) for k, s in scores.items()}


def _num(x: float) -> float | None:
    return round(x, 4) if math.isfinite(x) else None  # JSON has no infinity (a CI without bootstrap)


def standings_json(played: tournament.Played) -> list[dict[str, Any]]:
    assert played.result is not None
    why = score_ads(played.reactions)
    return [{"ad_id": s.ad_id, "strength": _num(s.strength), "ci": [_num(s.ci[0]), _num(s.ci[1])],
             "games": s.games, "wins": s.wins, "placebo": is_placebo(s.ad_id),
             "top_why_not": why[s.ad_id].top_why_not if s.ad_id in why else []}
            for s in played.result.standings]


def tournament_round(viewer: Viewer, persona: strategist.Persona, rows: list[dict[str, Any]],
                     competitors: list[FeedItem], brand: str, cfg: CreateConfig, rng: random.Random, *,
                     seed: int, picture: Callable[[dict[str, Any]], str | None] = no_picture) -> tournament.Played:
    """Our variants head-to-head (round robin) + one placebo as a reference point, next to real competitor ads."""
    source = rng.choice(competitors)
    candidates = [our_item(v["variant_id"], brand, v["texts"], picture(v)) for v in rows] + [placebo_item(source,
                                                                                                         brand)]
    fillers = [c for c in competitors if c.ad_id != source.ad_id]
    return tournament.play(viewer, viewer_personas(persona, max(cfg.viewers_per_feed, 2)), candidates, fillers,
                           feed_size=cfg.feed_size, rounds=cfg.tournament_rounds,
                           viewers_per_feed=cfg.viewers_per_feed, seed=seed)


Children = Callable[[list[dict[str, Any]], int, dict[str, list[str]]],
                    tuple[list[dict[str, Any]], list[dict[str, Any]]]]


EVOLVE_RESERVE_USD = 0.05  # kept for after evolution: a few calls of margin (plan and report are code)


def evolve_group(rows: list[dict[str, Any]], gen0: dict[str, dict[str, Any]], *, generations: int, keep: int,
                 make_children: Children, judge: Callable[[list[dict[str, Any]], int], tournament.Played],
                 replay: Callable[[tournament.Played], tournament.Played],
                 spent: Callable[[], float] | None = None, allowance: float = math.inf) -> dict[str, Any]:
    """One audience's evolution, judged by tournaments (E3-2, E6-1). All numbers SIMULATED.

    - generation 0 is the arena simulation (lift over placebo) and picks the first parents;
    - each generation g ≥ 1: children of the parents → one tournament of parents + children + the generation-0
      champion (the anchor: every generation is measured against the same ad, in the same feeds) + a placebo →
      the `keep` strongest by Bradley-Terry strength (different concepts first) become the next parents;
    - the anchor is the strongest generation-0 ad of the first tournament;
    - the last tournament is played again with a fresh draw (`replay`): its gap is the noise floor (E3-3).
    `make_children(parents, generation, why_not)` → (children that passed the guards, refused proposals);
    `judge(pool, generation)` → the played tournament. Verdicts are added by `add_verdicts` (needs every floor).

    Budget: `spent()` is the model spend so far and `allowance` what this audience may use. A generation starts
    only if it fits with the retest after it (the dearest generation so far × 1.2 + the last tournament again);
    otherwise, or if the budget runs out during a generation, evolution stops there and keeps the previous
    generation, so a run is never lost to its last, unfinished round.
    """
    spend = spent or (lambda: 0.0)
    start, dearest, last_usd = spend(), 0.0, 0.0
    parents = pick_parents(rows, lift_rank(gen0), keep)
    why_not = {k: list(s.get("top_why_not", [])) for k, s in gen0.items()}
    history: list[dict[str, Any]] = [{"generation": 0, "judge": "arena", "scores": gen0,
                                      "kept": [r["variant_id"] for r in parents]}]
    by_id = {r["variant_id"]: r for r in rows}
    anchor: str | None = None
    last: tournament.Played | None = None
    for gen in range(1, generations + 1):
        used, need = spend() - start, 1.2 * dearest + last_usd
        if used + need > allowance:
            history.append({"generation": gen, "stopped": f"budget: this audience may spend ${allowance:.2f}, "
                            f"${used:.2f} used, a generation and its retest need about ${need:.2f}"})
            break
        before = spend()
        try:
            children, refused = make_children(parents, gen, why_not)
            if not children:
                history.append({"generation": gen, "stopped": "no valid child", "refused": refused})
                break
            by_id.update((c["variant_id"], c) for c in children)
            pool = parents + children
            if anchor and anchor not in {r["variant_id"] for r in pool}:
                pool.append(by_id[anchor])
            played = judge(pool, gen)
        except BudgetExceeded as exc:
            history.append({"generation": gen, "stopped": f"budget spent during this generation ({exc}): "
                                                          "the previous generation is kept"})
            break
        if any(str(f.get("error", "")).startswith("BudgetExceeded") for f in played.failures):
            # games missing because the money ran out would bias the standings: not judged
            history.append({"generation": gen, "stopped": "budget spent during the tournament: the previous "
                                                          "generation is kept", "refused": refused})
            break
        dearest, last_usd = max(dearest, spend() - before), played.usd
        if played.result is None:
            history.append({"generation": gen, "stopped": "not judged: no head-to-head game (viewers failed)",
                            "refused": refused, "failures": len(played.failures)})
            break
        strength = {s.ad_id: s.strength for s in played.result.standings}
        if anchor is None:
            anchor = max((r["variant_id"] for r in pool if r.get("generation", 0) == 0),
                         key=lambda k: (strength[k], k))
        table = standings_json(played)
        why_not.update((s["ad_id"], s["top_why_not"]) for s in table)
        parents = pick_parents(pool, {k: (v,) for k, v in strength.items() if not is_placebo(k)}, keep)
        best = max(children, key=lambda c: (strength[c["variant_id"]], c["variant_id"]))
        champion = parents[0]["variant_id"]
        history.append({
            "generation": gen, "judge": "tournament", "refused": refused,
            "children": [c["variant_id"] for c in children], "kept": [r["variant_id"] for r in parents],
            "tournament": {"standings": table, "views": played.result.views, "feeds": len(played.feeds),
                           "failures": len(played.failures), "usd": round(played.usd, 4), "simulated": True},
            "best_child": {"id": best["variant_id"], "parent": best["parent_id"],
                           "difference": _num(strength[best["variant_id"]] - strength[best["parent_id"]])},
            "vs_gen0": {"best": champion, "anchor": anchor, "difference": _num(strength[champion] - strength[anchor])}})
        last = played
    group: dict[str, Any] = {"history": history, "anchor": anchor, "simulated": True}
    judged = [h for h in history if h.get("judge") == "tournament"]
    if not judged or last is None:
        group.update(final={}, champion=parents[0]["variant_id"] if parents else None, retest=None)
        return group
    group.update(final={s["ad_id"]: s for s in judged[-1]["tournament"]["standings"]},
                 champion=judged[-1]["kept"][0] if judged[-1]["kept"] else None)
    try:
        again: tournament.Played | None = replay(last)
    except BudgetExceeded:
        again = None
    if again is None or any(str(f.get("error", "")).startswith("BudgetExceeded") for f in again.failures):
        # no money left for the retest: no noise floor, so no verdict ("not measured"), never a claimed win
        group["retest"] = {"generation": judged[-1]["generation"], "usd": round(again.usd, 4) if again else 0.0,
                           "floor": None, "strengths": {}, "stopped": "budget"}
        return group
    retest: dict[str, Any] = {"generation": judged[-1]["generation"], "usd": round(again.usd, 4),
                              "failures": len(again.failures), "floor": None, "strengths": {}}
    if again.result is not None:
        first = {s.ad_id: s.strength for s in last.result.standings} if last.result else {}
        second = {s.ad_id: s.strength for s in again.result.standings}
        retest["strengths"] = {k: _num(v) for k, v in second.items()}
        common = sorted(set(first) & set(second))
        if len(common) >= 2:
            retest["floor"] = _num(retest_stats.noise_floor(first, second))
            try:
                retest["rank_agreement"] = _num(kendall_tau([first[k] for k in common], [second[k] for k in common]))
            except ValueError:
                retest["rank_agreement"] = None
    group["retest"] = retest
    return group


def pooled_floor(groups: list[dict[str, Any]]) -> float | None:
    """The noise floor from every audience's retest together (more ads, a steadier SD than one audience's 6-8)."""
    first: dict[str, float] = {}
    second: dict[str, float] = {}
    for i, g in enumerate(groups):
        r = g.get("retest") or {}
        last = next((h for h in reversed(g["history"]) if h.get("generation") == r.get("generation")
                     and "tournament" in h), None)
        if not last or not r.get("strengths"):
            continue
        for s in last["tournament"]["standings"]:
            if s["ad_id"] in r["strengths"] and s["strength"] is not None and r["strengths"][s["ad_id"]] is not None:
                first[f"{i}:{s['ad_id']}"] = s["strength"]
                second[f"{i}:{s['ad_id']}"] = r["strengths"][s["ad_id"]]
    return _num(retest_stats.noise_floor(first, second)) if len(first) >= 2 else None


def add_verdicts(group: dict[str, Any], pooled: float | None) -> None:
    """Label every simulated difference: improved / worse beyond the noise floor, else within noise (E3-3).

    The floor used is the larger of the audience's own and the pooled one (conservative: a gap must clear both)."""
    own = (group.get("retest") or {}).get("floor")
    floors = [f for f in (own, pooled) if f is not None]
    floor = max(floors) if floors else None
    retest = (group.get("retest") or {}).get("strengths", {})
    last_gen = (group.get("retest") or {}).get("generation")
    group["noise_floor"] = {"used": floor, "audience": own, "pooled": pooled, "simulated": True}
    progress: list[dict[str, Any]] = []
    for h in group["history"]:
        if h.get("judge") != "tournament":
            continue
        table = {s["ad_id"]: s for s in h["tournament"]["standings"]}

        def again(new: str, old: str, gen: int = h["generation"]) -> float | None:
            if gen != last_gen or retest.get(new) is None or retest.get(old) is None:
                return None
            return retest[new] - retest[old]

        bc = h["best_child"]
        bc["retest_difference"] = _num(d) if (d := again(bc["id"], bc["parent"])) is not None else None
        bc["verdict"] = retest_stats.verdict(bc["difference"], floor, retest_difference=bc["retest_difference"])
        v = h["vs_gen0"]
        v["retest_difference"] = _num(d) if (d := again(v["best"], v["anchor"])) is not None else None
        v["verdict"] = retest_stats.verdict(v["difference"], floor, retest_difference=v["retest_difference"])
        if not progress:  # generation 0 = the anchor, measured in the first tournament
            a = table[v["anchor"]]
            progress.append({"generation": 0, "best": v["anchor"], "strength": a["strength"], "ci": a["ci"],
                             "vs_gen0": 0.0})
        b = table[v["best"]]
        progress.append({"generation": h["generation"], "best": v["best"], "strength": b["strength"], "ci": b["ci"],
                         "vs_gen0": v["difference"], "verdict": v["verdict"],
                         "placebo": next((s["strength"] for s in table.values() if s["placebo"]), None)})
    group["progress"] = progress
    if progress:
        final = next(h for h in reversed(group["history"]) if h.get("judge") == "tournament")
        group["result"] = {"generation": final["generation"], "gen0": final["vs_gen0"]["anchor"],
                           "best": final["vs_gen0"]["best"], "difference": final["vs_gen0"]["difference"],
                           "retest_difference": final["vs_gen0"]["retest_difference"], "noise_floor": floor,
                           "verdict": final["vs_gen0"]["verdict"], "simulated": True}


def stage_evolve(run: Run, cfg: CreateConfig, c: Clients, app: AppProfile, strategy: Strategy,
                 ads: list[CompetitorAd], market: dict[str, Any], brand_info: dict[str, Any]) -> None:
    """Generations per audience: parents → mutations answering their objections → tournament → keep the strongest.

    Children and the options they add to templates are written back (templates/, variants.json); the original
    templates are kept in templates_gen0/ so a redo starts from the same place."""
    gen0, live = run.path("templates_gen0"), run.path("templates")
    if gen0.exists():  # a redo: restore the templates as the creative stage left them
        shutil.rmtree(live)
        shutil.copytree(gen0, live)
    else:
        shutil.copytree(live, gen0)
    variants = [v for v in run.read_json("variants.json") if v.get("generation", 0) == 0]
    sim = run.read_json("simulation.json")
    out: dict[str, Any] = {"generations": cfg.generations, "judge": "tournament", "groups": [], "usd": 0.0,
                           "simulated": True}
    if cfg.generations <= 0 or not sim.get("simulated"):
        out["skipped"] = "no evolution requested" if cfg.generations <= 0 else "nothing was simulated"
        run.write_json("variants.json", variants)
        run.write_json("evolution.json", out)
        return
    registry = {t.id: t for t in load_templates(run)}
    names = tuple(x["page_name"] for x in market.get("advertisers", []) if x.get("page_name"))
    brand = sim["brand"]
    viewer = Viewer(c.model, reasoning_effort=cfg.viewer_reasoning)
    # the same pictures as generation 0 (no new capture: the feeds must stay the same)
    images = competitor_images(cfg, c, ads, app, capture_missing=False)[0] if sim.get("images", {}).get("on") else {}
    picture = ad_picture(run, cfg)
    rng = random.Random(cfg.seed + 7)
    groups = languages(cfg)
    spent_before = c.model.spent_usd
    audiences = [x for x in sim["groups"] if "error" not in x][:cfg.evolve_audiences]
    # what evolution may spend: the command's budget left, minus a little for the stages after it (plan and
    # report are code); shared fairly, each audience gets an even share of what is left when its turn comes
    budget = getattr(c.model, "budget", None)
    left = getattr(budget, "remaining", math.inf)
    pot = max(0.0, left - EVOLVE_RESERVE_USD) if math.isfinite(left) else math.inf

    for gi, g in enumerate(audiences):
        allowance = (pot - (c.model.spent_usd - spent_before)) / (len(audiences) - gi)
        code = g["language"]
        rivals, rivals_info = feed_competitors(ads, code, app, cfg, images)  # the same hard feeds as generation 0
        pic = picture if rivals_info["images"] else no_picture
        p_all = strategy.persona(g["persona"])
        p = replace(p_all, countries=tuple(x for x in p_all.countries if x in groups[code]))
        ctx = Context(localised(strategy, groups[code]), app.name, app.description, names,
                      tuple(brand_info["palette"]), brand_info["screenshots"][0], LANGUAGES[code])
        rows = [v for v in variants if v.get("guards_passed") and v["persona"] == p.id and v["language"] == code]
        scores = {k: s for k, s in sim["scores"].items() if k in {r["variant_id"] for r in rows}}

        def make_children(parents: list[dict[str, Any]], gen: int, why_not: dict[str, list[str]],
                          ctx: Context = ctx) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            children, refused = [], []
            for par in parents:
                t = registry[par["template_id"]]
                parent = evolver.Parent(par["variant_id"], t, par["genome"], 0.0, 0.0,
                                        tuple(why_not.get(par["variant_id"], [])))
                try:
                    answer = evolver.propose(c.model, ctx, parent, n=cfg.mutations_per_parent)
                except AgentError as exc:  # evolution improves ads; one refusal must not stop the run
                    refused.append({"parent": par["variant_id"], "errors": exc.errors})
                    continue
                for j, m in enumerate(answer.value):
                    tag = f"g{gen}_{par['variant_id'].rsplit('-', 1)[-1][:6]}_{j}"
                    new_t, genome = evolver.apply(registry[t.id], par["genome"], m, tag=tag)
                    registry[t.id] = new_t
                    if any(v["variant_id"] == Variant(t.id, genome).id for v in variants):
                        # a new layout or style can land on an ad that already exists: it was already judged
                        refused.append({"parent": par["variant_id"], "errors": [f"{m.gene} {m.text}: ad already made"]})
                        continue
                    row = produce_row(run, new_t, genome, generation=gen, parent_id=par["variant_id"],
                                      mutation={"gene": m.gene, "text": m.text, "why": m.why})
                    variants.append(row)
                    if row.get("guards_passed"):
                        children.append(row)
            return children, refused

        def judge(pool: list[dict[str, Any]], gen: int, p: strategist.Persona = p, rivals: list[FeedItem] = rivals,
                  gi: int = gi, pic: Callable[[dict[str, Any]], str | None] = pic) -> tournament.Played:
            return tournament_round(viewer, p, pool, rivals, brand, cfg, rng, seed=cfg.seed + 100 * gen + gi,
                                    picture=pic)

        group = evolve_group(rows, scores, generations=cfg.generations, keep=cfg.evolve_parents,
                             make_children=make_children, judge=judge,
                             replay=lambda played: tournament.replay(viewer, played),
                             spent=lambda: c.model.spent_usd, allowance=allowance)
        group["history"][0]["info"] = {k: g[k] for k in g if k not in ("persona", "language")}
        out["groups"].append({"persona": p.id, "language": code, **group})

    pooled = pooled_floor(out["groups"])
    for group in out["groups"]:
        add_verdicts(group, pooled)
    verdicts = [g["result"]["verdict"] for g in out["groups"] if "result" in g]
    out["noise_floor_pooled"] = pooled
    out["summary"] = {"audiences": len(out["groups"]), "judged": len(verdicts),
                      **{v: verdicts.count(v) for v in (retest_stats.IMPROVED, retest_stats.WITHIN_NOISE,
                                                         retest_stats.WORSE, retest_stats.NOT_MEASURED)},
                      "simulated": True}
    for t in registry.values():
        (live / f"{t.id}.yaml").write_text(yaml.safe_dump(t.to_dict(), sort_keys=False, allow_unicode=True),
                                           encoding="utf-8")
    out["usd"] = round(c.model.spent_usd - spent_before, 4)
    run.write_json("variants.json", variants)
    run.write_json("evolution.json", out)


def final_scores(sim: dict[str, Any], evolution: dict[str, Any] | None) -> dict[str, float]:
    """Ranking signal per variant for the plan (within an audience; scales are not comparable across simulations).

    Latest evidence first: the final tournament of each audience (100 + strength), then earlier tournaments
    (10 × generation + strength), then the generation-0 arena (1 + lift over placebo)."""
    out = {k: 1.0 + float(s["lift_over_placebo"]) for k, s in sim.get("scores", {}).items()}
    for g in (evolution or {}).get("groups", []):
        for h in g["history"]:
            for s in h.get("tournament", {}).get("standings", []):
                if not s["placebo"] and s["strength"] is not None:
                    out[s["ad_id"]] = 10.0 * h["generation"] + max(-4.9, min(4.9, s["strength"]))
        for k, s in g.get("final", {}).items():
            if not s.get("placebo") and s.get("strength") is not None:
                out[k] = 100.0 + max(-4.9, min(4.9, s["strength"]))
    return out


def stage_plan(run: Run, cfg: CreateConfig, app: AppProfile, strategy: Strategy, variants: list[dict[str, Any]],
               sim: dict[str, Any]) -> None:
    evolution = run.read_json("evolution.json") if run.path("evolution.json").exists() else None
    ranks = final_scores(sim, evolution)
    # one audience per (persona, ad language), targeting only that language's countries
    choices = [AdChoice(v["variant_id"], v["template_id"], f"{v['persona']}.{v.get('language', 'en')}", v["image"],
                        v["texts"]["hook"], v["texts"]["body"], v["texts"]["title"], v["genome"]["cta"], True,
                        ranks.get(v["variant_id"], 1.0))
               for v in variants if v.get("guards_passed")]
    groups = languages(cfg)
    audiences = []
    for p in strategy.personas:
        for code, countries in groups.items():
            local = tuple(c for c in p.countries if c in countries)
            if local:
                label = p.name + (f" ({LANGUAGES[code]})" if len(groups) > 1 else "")
                audiences.append(Audience(f"{p.id}.{code}", label, local, p.age_min, p.age_max, p.gender))
    plan = build_plan(app.name, app.store_url, audiences, choices, daily_cap_eur=cfg.daily_cap_eur)
    missing = unmapped(cfg.countries)
    if missing and not cfg.language:
        plan.notes.append(f"no known ad language for {missing}: English used")
    errors = validate(plan)
    if not sim.get("simulated"):
        plan.notes.append("ads were NOT simulated (not enough competitor ads): ranking is arbitrary")
    biased = [f"{g['persona']}.{g['language']}" for g in sim.get("groups", []) if g.get("biased")]
    if biased:
        plan.notes.append(f"simulator bias: placebos (competitor ads under our name) won in {biased}; "
                          "variants are ranked against each other only, not proven better than competitors")
    run.write_json("plan.json", {**plan.to_json(), "errors": errors})
    run.write_json("meta_api_payloads.json", to_api(plan))
    run.write_json("launch.json", [{"ad_set": name, "outcome": d.outcome.value, "why": d.why}
                                   for name, d in launch_decisions(plan, cfg.policy)])


def plan_from_json(d: dict[str, Any]) -> CampaignPlan:
    sets = []
    for s in d["ad_sets"]:
        a = s["audience"]
        sets.append(AdSetPlan(s["name"], Audience(a["persona"], a["name"], tuple(a["countries"]), a["age_min"],
                                                  a["age_max"], a["gender"]),
                              s["daily_budget_eur"], [AdChoice(**x) for x in s["ads"]]))
    return CampaignPlan(d["name"], d["app_name"], d["store_url"], d["daily_cap_eur"], sets, list(d["notes"]))


# --- orchestration -------------------------------------------------------------------------

def create(cfg: CreateConfig, clients: Clients, run_dir: Path, *, redo_from: str | None = None,
           parent_event: str | None = None) -> Result:
    s = clients.model.settings
    run = Run(run_dir, parent=parent_event, secrets=(s.model_api_key, s.baseten_api_key, s.fb_token, s.meta_token,
                                                     s.meta_sandbox_token, clients.adlibrary.token))
    if redo_from:
        run.log(stage=redo_from, status="redo", cleared=run.redo_from(redo_from))
    run.write_json("config.json", {**asdict(cfg), "policy": {"level": cfg.policy.level.value,
                                                             "daily_cap_eur": cfg.policy.daily_cap_eur}})
    _stage(run, "app", lambda: stage_app(run, cfg, clients), clients)
    app = AppProfile.from_json(run.read_json("app.json"))
    brand = run.read_json("brand.json")
    _stage(run, "market", lambda: stage_market(run, cfg, clients, app), clients)
    ads = load_jsonl(run.path("market_ads.jsonl"))
    market = run.read_json("market.json")
    _stage(run, "strategy", lambda: stage_strategy(run, cfg, clients, app, ads), clients)
    strategy = Strategy.from_json(run.read_json("strategy.json"))
    _stage(run, "creative", lambda: stage_creative(run, cfg, clients, app, strategy, market, brand), clients)
    templates = load_templates(run)
    _stage(run, "produce", lambda: stage_produce(run, cfg, templates), clients)
    variants = run.read_json("variants.json")
    _stage(run, "simulate", lambda: stage_simulate(run, cfg, clients, app, strategy, ads, variants), clients)
    _stage(run, "evolve", lambda: stage_evolve(run, cfg, clients, app, strategy, ads, market, brand), clients)
    variants = run.read_json("variants.json")
    templates = load_templates(run)
    sim = run.read_json("simulation.json")
    _stage(run, "plan", lambda: stage_plan(run, cfg, app, strategy, variants, sim), clients)
    plan_json = run.read_json("plan.json")
    plan = plan_from_json(plan_json)
    _stage(run, "report", lambda: write_report(run.dir), clients)
    choices = [a for s in plan.ad_sets for a in s.ads]
    return Result(run.dir, app, strategy, templates, choices, plan, plan_json["errors"], round(spent_usd(run.dir), 4),
                  round(clients.model.spent_usd, 4))


def default_clients(budget_usd: float, run_dir: Path) -> Clients:
    from whynot.config import load_settings
    from whynot.costs import CostLedger

    settings = replace(load_settings(), cost_log=Path(run_dir) / "costs.jsonl")
    from whynot.config import REPO_ROOT

    def renderer() -> Renderer:  # pragma: no cover - a real browser
        from whynot.ingest.creatives import PlaywrightRenderer
        return PlaywrightRenderer()

    return Clients(ModelClient(settings, CostLedger(settings.cost_log), budget_usd=budget_usd), AppStoreClient(),
                   AdLibraryClient(settings.fb_token or "", version=settings.fb_api_version),
                   CreativeStore(REPO_ROOT / "data" / "cache" / "creatives"), renderer)


def new_run_dir(root: Path, app_ref: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return Path(root) / f"{stamp}-{slug(app_ref.split('/')[-1] or app_ref)}"
