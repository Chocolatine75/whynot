"""`whynot create`: from an app to a ready-to-launch Meta campaign.

Stages, each writing inspectable files into the run folder (resumable: a stage
whose output exists is loaded, not recomputed or re-billed):

 1. app       App Store page, reviews, real screenshots, brand palette from the icon
 2. market    Scout: competitor advertisers and their ads (Ad Library, EU/UK)
 3. strategy  Strategist (Muse Wonder): personas, objections, angles, verified claims
 4. creative  Creative director: one template per angle, checked copy
 5. produce   Composer: ad images per variant + every guard
 6. simulate  Viewer agents: each variant in fair feeds next to real competitor ads and placebos (SIMULATED)
 7. evolve    Evolver: mutate the best ads to answer viewers' objections, re-test, keep the best (SIMULATED)
 8. plan      Campaign plan in Marketing API shape, validated; launch decisions via the autopilot
 9. report    report.md for the owner

All model calls go through one `ModelClient` with a hard budget for the run.
Nothing is sent to Meta here: the plan is created PAUSED and only published
by the autopilot under the owner's autonomy level, cap and approval.
"""

import json
import random
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
from whynot.agents import director, evolver, scout, strategist
from whynot.agents.ask import AgentError
from whynot.agents.director import Context
from whynot.agents.strategist import Strategy
from whynot.assets.brand import palette_from_icon
from whynot.create.composer import ComposeError, compose
from whynot.create.guards import publishable, run_guards
from whynot.create.locale import LANGUAGES, language_groups, unmapped
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
from whynot.sim.arena import brand_name, judge, our_item, paired_feeds, placebo_item
from whynot.sim.feed import FeedItem
from whynot.sim.personas import Persona as SimPersona
from whynot.sim.relevance import hard_competitors
from whynot.sim.scores import score_ads
from whynot.sim.viewer import Viewer, run_simulation

STAGES = ("app", "market", "strategy", "creative", "produce", "simulate", "evolve", "plan", "report")


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
    strategy_model: str = WONDER
    director_model: str = SPARK
    policy: Policy = field(default_factory=Policy)
    seed: int = 0
    feed_pool: int = 12  # competitor ads per language in the feeds: the most relevant ones (sim/relevance.py)

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


def stage_creative(run: Run, cfg: CreateConfig, c: Clients, app: AppProfile, strategy: Strategy,
                   market: dict[str, Any], brand: dict[str, Any]) -> None:
    """One template set per ad language: French ads for France, English ads for the UK."""
    names = tuple(x["page_name"] for x in market.get("advertisers", []) if x.get("page_name"))
    folder = run.path("templates")
    folder.mkdir(exist_ok=True)
    for old in folder.glob("*.yaml"):  # a redo replaces the whole set
        old.unlink()
    log = {}
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
            d["fixed"]["product"]["asset"] = brand["screenshots"][i % len(brand["screenshots"])]  # rotate real screens
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
    return {**row, "image": f"ads/{v.id}.png", "guards": {k: asdict(r) for k, r in results.items()},
            "guards_passed": publishable(results),
            "texts": {g: t.text(g, genome[g]) for g in ("hook", "body", "title", "proof", "cta") if g in genome}}


def stage_produce(run: Run, cfg: CreateConfig, templates: list[Template]) -> None:
    out = run.path("ads")
    out.mkdir(exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    rows = [produce_row(run, t, genome) for t in templates for genome in t.sample(cfg.variants_per_template,
                                                                                   seed=cfg.seed)]
    run.write_json("variants.json", rows)


def feed_competitors(ads: list[CompetitorAd], code: str, app: AppProfile, cfg: CreateConfig
                     ) -> tuple[list[FeedItem], dict[str, Any]]:
    """Hard feeds: the competitor ads most relevant to ads in language `code` (language, longevity, topic).

    Longevity is counted up to the latest date seen in the market data, not today, so a rerun on recorded
    inputs picks the same ads."""
    dates = [d for a in ads for d in (a.start_date, a.stop_date) if d]
    as_of = max(dates) if dates else datetime.now(UTC).date()
    hard = hard_competitors(ads, language=code, topic=f"{app.name} {app.description}", as_of=as_of,
                            k=max(cfg.feed_pool, cfg.placebos + cfg.feed_size - 2))
    info = {"pool": len(hard.ads), "long_running": sum(r.long_running for r in hard.ranked),
            "wrong_language": hard.wrong_language_used}
    return [FeedItem.from_ad(a) for a in hard.ads], info


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
                seed: int) -> Round:
    """One fair-feed comparison of `rows` (our variants) with fresh placebos, for one persona's viewers."""
    placebos = [placebo_item(a, brand) for a in rng.sample(competitors, cfg.placebos)]
    candidates = [our_item(v["variant_id"], brand, v["texts"]) for v in rows] + placebos
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
        pool, pool_info = feed_competitors(ads, code, app, cfg)
        r = arena_round(viewer, p, mine, pool, brand, cfg, rng, seed=cfg.seed + len(groups_out))
        usd += r.usd
        failures += r.failures
        groups_out.append({"persona": p.id, "language": code, **r.info, "variants": len(mine),
                           "competitors": pool_info})
        verdicts.update(r.verdicts)
    run.write_json("simulation.json", {"simulated": True, "brand": brand, "usd": usd, "failures": failures,
                                       "groups": groups_out, "scores": verdicts})


def pick_parents(rows: list[dict[str, Any]], scores: dict[str, dict[str, Any]], k: int) -> list[dict[str, Any]]:
    """Best k scored rows, preferring different templates (concept diversity), ties broken by intent then id."""
    ranked = sorted((r for r in rows if r["variant_id"] in scores),
                    key=lambda r: (-scores[r["variant_id"]]["lift_over_placebo"], -scores[r["variant_id"]]["intent"],
                                   r["variant_id"]))
    chosen: list[dict[str, Any]] = []
    for r in ranked:
        if len(chosen) < k and r["template_id"] not in {c["template_id"] for c in chosen}:
            chosen.append(r)
    for r in ranked:  # fill from the same concepts if there are fewer concepts than k
        if len(chosen) < k and r not in chosen:
            chosen.append(r)
    return chosen


def stage_evolve(run: Run, cfg: CreateConfig, c: Clients, app: AppProfile, strategy: Strategy,
                 ads: list[CompetitorAd], market: dict[str, Any], brand_info: dict[str, Any]) -> None:
    """Generations per audience: parents → mutations answering their objections → fair re-test → keep the best.

    Children and the options they add to templates are written back (templates/, variants.json); the original
    templates are kept in templates_gen0/ so a redo starts from the same place."""
    import shutil

    gen0, live = run.path("templates_gen0"), run.path("templates")
    if gen0.exists():  # a redo: restore the templates as the creative stage left them
        shutil.rmtree(live)
        shutil.copytree(gen0, live)
    else:
        shutil.copytree(live, gen0)
    variants = [v for v in run.read_json("variants.json") if v.get("generation", 0) == 0]
    sim = run.read_json("simulation.json")
    out: dict[str, Any] = {"generations": cfg.generations, "groups": [], "usd": 0.0}
    if cfg.generations <= 0 or not sim.get("simulated"):
        out["skipped"] = "no evolution requested" if cfg.generations <= 0 else "nothing was simulated"
        run.write_json("variants.json", variants)
        run.write_json("evolution.json", out)
        return
    registry = {t.id: t for t in load_templates(run)}
    names = tuple(x["page_name"] for x in market.get("advertisers", []) if x.get("page_name"))
    brand = sim["brand"]
    viewer = Viewer(c.model, reasoning_effort=cfg.viewer_reasoning)
    rng = random.Random(cfg.seed + 7)
    groups = languages(cfg)
    spent_before = c.model.spent_usd

    for gi, g in enumerate(x for x in sim["groups"] if "error" not in x):
        code = g["language"]
        rivals, _ = feed_competitors(ads, code, app, cfg)  # the same hard feeds as generation 0
        p_all = strategy.persona(g["persona"])
        p = replace(p_all, countries=tuple(x for x in p_all.countries if x in groups[code]))
        ctx = Context(localised(strategy, groups[code]), app.name, app.description, names,
                      tuple(brand_info["palette"]), brand_info["screenshots"][0], LANGUAGES[code])
        rows = [v for v in variants if v.get("guards_passed") and v["persona"] == p.id and v["language"] == code]
        scores = {k: s for k, s in sim["scores"].items() if k in {r["variant_id"] for r in rows}}
        parents = pick_parents(rows, scores, cfg.evolve_parents)
        history: list[dict[str, Any]] = [{"generation": 0, "scores": scores, "info": {k: g[k] for k in g
                                          if k not in ("persona", "language")},
                                          "kept": [r["variant_id"] for r in parents]}]
        for gen in range(1, cfg.generations + 1):
            children, refused = [], []
            for par in parents:
                t = registry[par["template_id"]]
                s = scores[par["variant_id"]]
                parent = evolver.Parent(par["variant_id"], t, par["genome"], s["lift_over_placebo"], s["intent"],
                                        tuple(s.get("top_why_not", [])))
                try:
                    answer = evolver.propose(c.model, ctx, parent, n=cfg.mutations_per_parent)
                except AgentError as exc:  # evolution improves ads; one refusal must not stop the run
                    refused.append({"parent": par["variant_id"], "errors": exc.errors})
                    continue
                for j, m in enumerate(answer.value):
                    tag = f"g{gen}_{par['variant_id'].rsplit('-', 1)[-1][:6]}_{j}"
                    new_t, genome = evolver.apply(registry[t.id], par["genome"], m, tag=tag)
                    registry[t.id] = new_t
                    row = produce_row(run, new_t, genome, generation=gen, parent_id=par["variant_id"],
                                      mutation={"gene": m.gene, "text": m.text, "why": m.why})
                    variants.append(row)
                    if row.get("guards_passed"):
                        children.append(row)
            if not children:
                history.append({"generation": gen, "stopped": "no valid child", "refused": refused})
                break
            pool = parents + children
            r = arena_round(viewer, p, pool, rivals, brand, cfg, rng, seed=cfg.seed + 100 * gen + gi)
            if not r.verdicts:
                history.append({"generation": gen, "stopped": r.info.get("error", "not judged"), "refused": refused})
                break
            scores = r.verdicts
            parents = pick_parents(pool, scores, cfg.evolve_parents)
            history.append({"generation": gen, "scores": scores, "info": r.info, "refused": refused,
                            "children": [ch["variant_id"] for ch in children],
                            "kept": [x["variant_id"] for x in parents]})
        final = next(h for h in reversed(history) if "scores" in h)
        out["groups"].append({"persona": p.id, "language": code, "history": history,
                              "final": final["scores"], "champion": final["kept"][0] if final["kept"] else None})

    for t in registry.values():
        (live / f"{t.id}.yaml").write_text(yaml.safe_dump(t.to_dict(), sort_keys=False, allow_unicode=True),
                                           encoding="utf-8")
    out["usd"] = round(c.model.spent_usd - spent_before, 4)
    run.write_json("variants.json", variants)
    run.write_json("evolution.json", out)


def final_scores(sim: dict[str, Any], evolution: dict[str, Any] | None) -> dict[str, float]:
    """Ranking signal per variant for the plan.

    Scores from different simulations are not on the same scale, so: the final evolution round of each audience
    ranks first (10 + lift over placebo); every other variant keeps its latest score (1 + lift over placebo)."""
    out = {k: 1.0 + float(s["lift_over_placebo"]) for k, s in sim.get("scores", {}).items()}
    for g in (evolution or {}).get("groups", []):
        for h in g["history"]:
            for k, s in h.get("scores", {}).items():
                out[k] = 1.0 + float(s["lift_over_placebo"])
        for k, s in g["final"].items():
            out[k] = 10.0 + float(s["lift_over_placebo"])
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

def create(cfg: CreateConfig, clients: Clients, run_dir: Path, *, redo_from: str | None = None) -> Result:
    run = Run(run_dir)
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
    return Clients(ModelClient(settings, CostLedger(settings.cost_log), budget_usd=budget_usd), AppStoreClient(),
                   AdLibraryClient(settings.fb_token or "", version=settings.fb_api_version))


def new_run_dir(root: Path, app_ref: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return Path(root) / f"{stamp}-{slug(app_ref.split('/')[-1] or app_ref)}"
