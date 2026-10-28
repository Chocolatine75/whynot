"""`whynot create`: from an app to a ready-to-launch Meta campaign.

Stages, each writing inspectable files into the run folder (resumable: a stage
whose output exists is loaded, not recomputed or re-billed):

 1. app       App Store page, reviews, real screenshots, brand palette from the icon
 2. market    Scout: competitor advertisers and their ads (Ad Library, EU/UK)
 3. strategy  Strategist (Muse Wonder): personas, objections, angles, verified claims
 4. creative  Creative director: one template per angle, checked copy
 5. produce   Composer: ad images per variant + every guard
 6. simulate  Viewer agents: each variant in feeds next to real competitor ads (SIMULATED)
 7. plan      Campaign plan in Marketing API shape, validated; launch decisions via the autopilot
 8. report    report.md for the owner

All model calls go through one `ModelClient` with a hard budget for the run.
Nothing is sent to Meta here: the plan is created PAUSED and only published
by the autopilot under the owner's autonomy level, cap and approval.
"""

import json
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

from whynot.agency.report import spent_usd, write_report
from whynot.agents import director, scout, strategist
from whynot.agents.director import Context
from whynot.agents.strategist import Strategy
from whynot.assets.brand import palette_from_icon
from whynot.create.composer import ComposeError, compose
from whynot.create.guards import publishable, run_guards
from whynot.create.templates import Template, Variant
from whynot.ingest.adlibrary import AdLibraryClient, CompetitorAd, load_jsonl, save_jsonl
from whynot.ingest.appstore import AppProfile, AppStoreClient
from whynot.models import SPARK, WONDER, ModelClient
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
from whynot.sim.feed import FeedItem, build_candidate_feeds
from whynot.sim.personas import Persona as SimPersona
from whynot.sim.scores import AdScore, score_ads
from whynot.sim.viewer import Viewer, run_simulation

STAGES = ("app", "market", "strategy", "creative", "produce", "simulate", "plan", "report")


@dataclass
class CreateConfig:
    app_ref: str  # App Store URL, app id, or the app's website
    countries: list[str]  # campaign countries
    daily_cap_eur: float  # owner's daily ad-spend cap for the plan
    budget_usd: float = 3.0  # hard cap on model spend for this run
    research_countries: list[str] | None = None  # EU/UK; default: campaign countries in the EU/UK, else GB
    store_country: str = "us"
    language: str = "English"
    competitor_pages: list[str] = field(default_factory=list)  # owner-named Facebook page ids
    max_angles: int = 6
    variants_per_template: int = 4
    feeds_per_variant: int = 2
    feed_size: int = 4
    viewers_per_feed: int = 2
    viewer_reasoning: str | None = "low"
    strategy_model: str = WONDER
    director_model: str = SPARK
    policy: Policy = field(default_factory=Policy)
    seed: int = 0

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

    def __init__(self, folder: Path):
        self.dir = Path(folder)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.dir / "events.jsonl"

    def path(self, *parts: str) -> Path:
        return self.dir.joinpath(*parts)

    def done(self, stage: str) -> bool:
        return self.path(f"{stage}.done").exists()

    def mark(self, stage: str) -> None:
        self.path(f"{stage}.done").write_text(datetime.now(UTC).isoformat())

    def log(self, **event: Any) -> None:
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now(UTC).isoformat(), **event}, ensure_ascii=False) + "\n")

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


@dataclass
class Result:
    run_dir: Path
    app: AppProfile
    strategy: Strategy
    templates: list[Template]
    choices: list[AdChoice]
    plan: CampaignPlan
    plan_errors: list[str]
    usd: float


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
    run.log(stage=name, status="ok", seconds=round(time.monotonic() - start, 2),
            usd=round(clients.model.spent_usd - spent, 4))
    return out


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
    run.write_json("strategy.raw.json", {"attempts": answer.attempts, "usd": answer.usd, "answer": answer.raw})


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


def stage_creative(run: Run, cfg: CreateConfig, c: Clients, app: AppProfile, strategy: Strategy,
                   market: dict[str, Any], brand: dict[str, Any]) -> None:
    names = tuple(x["page_name"] for x in market.get("advertisers", []) if x.get("page_name"))
    angles = pick_angles(strategy, cfg.max_angles)
    ctx = Context(strategy, app.name, app.description, names, tuple(brand["palette"]), brand["screenshots"][0],
                  cfg.language)
    answer = director.write_templates(c.model, ctx, angles, model=cfg.director_model)
    folder = run.path("templates")
    folder.mkdir(exist_ok=True)
    for i, t in enumerate(answer.value):
        d = t.to_dict()  # rotate real screenshots across templates
        d["fixed"]["product"]["asset"] = brand["screenshots"][i % len(brand["screenshots"])]
        (folder / f"{t.id}.yaml").write_text(yaml.safe_dump(d, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_templates(run: Run) -> list[Template]:
    return [Template.load(p) for p in sorted(run.path("templates").glob("*.yaml"))]


def stage_produce(run: Run, cfg: CreateConfig, templates: list[Template]) -> None:
    out = run.path("ads")
    out.mkdir(exist_ok=True)
    rows = []
    for t in templates:
        asset = Image.open(run.path("assets", t.fixed["product"]["asset"]))
        for genome in t.sample(cfg.variants_per_template, seed=cfg.seed):
            v = Variant(t.id, genome)
            row: dict[str, Any] = {"variant_id": v.id, "template_id": t.id, "persona": t.persona, "genome": genome}
            try:
                comp = compose(t, genome, asset)
            except ComposeError as exc:
                rows.append({**row, "error": str(exc), "guards_passed": False})
                continue
            comp.image.save(out / f"{v.id}.png")
            results = run_guards(t, comp, asset)
            rows.append({**row, "image": f"ads/{v.id}.png", "guards": {k: asdict(r) for k, r in results.items()},
                         "guards_passed": publishable(results),
                         "texts": {g: t.text(g, genome[g]) for g in ("hook", "body", "title", "proof", "cta")
                                   if g in genome}})
    run.write_json("variants.json", rows)


def viewer_personas(p: strategist.Persona, objections: dict[str, str], n: int) -> list[SimPersona]:
    genders = [p.gender] if p.gender != "all" else ["female", "male"]
    traits = (p.description, "wants: " + "; ".join(p.motivations),
              "hesitates because: " + "; ".join(objections[o] for o in p.objections if o in objections))
    return [SimPersona(f"{p.id}_{i}", p.countries[i % len(p.countries)], f"{p.age_min}-{p.age_max}",
                       genders[i % len(genders)], traits) for i in range(n)]


def stage_simulate(run: Run, cfg: CreateConfig, c: Clients, app: AppProfile, strategy: Strategy,
                   ads: list[CompetitorAd], variants: list[dict[str, Any]]) -> None:
    ok = [v for v in variants if v.get("guards_passed")]
    competitors = [FeedItem.from_ad(a) for a in ads if (a.bodies or [""])[0].strip()]
    if len(competitors) < cfg.feed_size - 1:
        run.write_json("simulation.json", {"simulated": False, "reason": f"only {len(competitors)} competitor ads",
                                           "scores": {}})
        return
    objections = {o.id: o.text for o in strategy.objections}
    viewer = Viewer(c.model, reasoning_effort=cfg.viewer_reasoning)
    scores: dict[str, AdScore] = {}
    failures, usd = [], 0.0
    for p in strategy.personas:
        mine = [v for v in ok if v["persona"] == p.id]
        if not mine:
            continue
        feeds = []
        for i, v in enumerate(mine):
            ours = FeedItem(v["variant_id"], app.name, v["texts"]["title"],
                            f"{v['texts']['body']}\n[image text: {v['texts']['hook']}"
                            + (f" — {v['texts']['proof']}" if v["texts"].get("proof") else "") + "]")
            feeds += build_candidate_feeds(ours, competitors, feed_size=cfg.feed_size, n_feeds=cfg.feeds_per_variant,
                                           seed=cfg.seed * 1000 + i)
        personas = viewer_personas(p, objections, max(cfg.viewers_per_feed, 2))
        sim = run_simulation(viewer, personas, feeds, viewers_per_feed=cfg.viewers_per_feed)
        usd += sim.usd
        failures += sim.failures
        ours_ids = {v["variant_id"] for v in mine}
        scores.update({k: s for k, s in score_ads(sim.reactions).items() if k in ours_ids})
    run.write_json("simulation.json", {"simulated": True, "usd": usd, "failures": failures,
                                       "scores": {k: asdict(s) for k, s in scores.items()}})


def stage_plan(run: Run, cfg: CreateConfig, app: AppProfile, strategy: Strategy, variants: list[dict[str, Any]],
               sim: dict[str, Any]) -> None:
    scores = sim.get("scores", {})
    choices = [AdChoice(v["variant_id"], v["template_id"], v["persona"], v["image"], v["texts"]["hook"],
                        v["texts"]["body"], v["texts"]["title"], v["genome"]["cta"], True,
                        float(scores.get(v["variant_id"], {}).get("preference_lift", 1.0)))
               for v in variants if v.get("guards_passed")]
    audiences = [Audience(p.id, p.name, p.countries, p.age_min, p.age_max, p.gender) for p in strategy.personas]
    plan = build_plan(app.name, app.store_url, audiences, choices, daily_cap_eur=cfg.daily_cap_eur)
    errors = validate(plan)
    if not sim.get("simulated"):
        plan.notes.append("ads were NOT simulated (not enough competitor ads): ranking is arbitrary")
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

def create(cfg: CreateConfig, clients: Clients, run_dir: Path) -> Result:
    run = Run(run_dir)
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
    sim = run.read_json("simulation.json")
    _stage(run, "plan", lambda: stage_plan(run, cfg, app, strategy, variants, sim), clients)
    plan_json = run.read_json("plan.json")
    plan = plan_from_json(plan_json)
    _stage(run, "report", lambda: write_report(run.dir), clients)
    choices = [a for s in plan.ad_sets for a in s.ads]
    return Result(run.dir, app, strategy, templates, choices, plan, plan_json["errors"], round(spent_usd(run.dir), 4))


def default_clients(budget_usd: float, run_dir: Path) -> Clients:
    from whynot.config import load_settings
    from whynot.costs import CostLedger

    settings = replace(load_settings(), cost_log=Path(run_dir) / "costs.jsonl")
    return Clients(ModelClient(settings, CostLedger(settings.cost_log), budget_usd=budget_usd), AppStoreClient(),
                   AdLibraryClient(settings.fb_token or "", version=settings.fb_api_version))


def new_run_dir(root: Path, app_ref: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return Path(root) / f"{stamp}-{slug(app_ref.split('/')[-1] or app_ref)}"
