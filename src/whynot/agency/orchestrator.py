"""The agency end to end (E4-5): from a Meta login and an App Store link to a running, reported campaign.

    whynot connect   (once: the owner's Meta login → ad account + Page, checked, saved privately)
    whynot agency https://apps.apple.com/... --countries FR --daily-cap 20 --connection <file>

Steps, in order, each one an agent step in the shared event log (`events.jsonl`, see `events.py`):

 1. connect   the Meta login is still valid and the ad account usable (skipped on the simulated account)
 2. create    research, strategy, ads, simulated test, evolution, campaign plan (`agency/create.py`)
 3. publish   the plan's static ads on Meta, within the autonomy level and the owner's cap (`run/publish.py`)
 4. daily     today's agency day: results, pauses, new video ads with new ideas, launches, report
              (`agency/daily.py`); run again tomorrow (`whynot agency --resume RUN`) for the next day

State lives in `<run>/agency/state.json`: a finished step is never redone or re-billed; a failed one is retried
on resume; a step waiting for the owner's approval does not block the next ones and runs again once approved.
`daily` runs once per calendar day.

Money rules, enforced here and below:
- model spend: one budget for the whole command, and one per step (a step never gets more than what is left);
- ad spend: one cap for the account. The static campaign gets `static_share` of it, the daily loop's video ads
  the rest minus what the static campaign really committed, so the two together never pass the cap;
- autonomy: `dry_run` sends nothing to Meta; `propose` needs the owner's approval for each action; `autopilot`
  acts within the cap, and its first live launch still needs the owner's approval (recorded, then remembered).
"""

import json
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from whynot.agency.create import Clients, CreateConfig, StageError, create, new_run_dir, plan_from_json
from whynot.config import Settings
from whynot.events import AgentEvent, EventLog, digest
from whynot.models import ModelClient
from whynot.run.autopilot import Level, Policy
from whynot.run.connect import MetaConnection

STEPS = ("connect", "create", "publish", "daily")
AGENTS = {"connect": "connector", "create": "agency", "publish": "publisher", "daily": "media_buyer"}


@dataclass
class AgencyConfig:
    app_ref: str  # App Store URL or app id
    countries: list[str]  # campaign countries
    daily_cap_eur: float  # the owner's hard cap on ad spend per day, for everything whynot runs
    level: str = "dry_run"  # dry_run | propose | autopilot
    simulated_account: bool = False  # results invented by a known model (labelled), nothing sent to Meta
    connection: str | None = None  # the saved Meta connection (`whynot connect`)
    objective: str = "traffic"
    budget_usd: float = 8.0  # model spend for one invocation, all steps together
    step_budgets_usd: dict[str, float] = field(default_factory=lambda: {"create": 4.0, "daily": 3.0})
    publish_static: bool = True  # publish the static image campaign from the plan (else: video ads only)
    static_share: float = 0.5  # share of the cap planned for the static campaign
    target_live: int = 4  # video ads running at the same time
    max_new: int = 2  # new video ads per day
    budget_per_ad_eur: float = 5.0
    create: dict[str, Any] = field(default_factory=dict)  # extra CreateConfig fields (angles, generations, ...)
    seed: int = 0

    def __post_init__(self) -> None:
        Level(self.level)  # raises on a typo
        if not 0 <= self.static_share <= 1:
            raise ValueError("static_share must be between 0 and 1")
        if self.daily_cap_eur < 0 or self.budget_usd < 0:
            raise ValueError("caps must be ≥ 0")
        if not self.simulated_account and not self.connection:
            raise ValueError("a real account needs a Meta connection (`whynot connect`), or use the simulated one")

    @property
    def static_cap_eur(self) -> float:
        """The static campaign's share of the cap. On the simulated account it is never published, so its plan
        gets the whole cap (halving it there only dropped audiences from a proposal nobody runs)."""
        if self.publish_static and not self.simulated_account:
            return round(self.daily_cap_eur * self.static_share, 2)
        return self.daily_cap_eur

    @property
    def effective_level(self) -> str:
        """What actually decides launches: the simulated account always runs on autopilot within the cap."""
        return Level.AUTOPILOT.value if self.simulated_account else self.level


class Waiting(Exception):
    """The step needs the owner's approval; the next steps still run."""


class AgencyError(RuntimeError):
    def __init__(self, step: str, cause: BaseException):
        super().__init__(f"step '{step}' failed: {type(cause).__name__}: {cause}")
        self.step = step
        self.cause = cause


@dataclass
class Services:
    """Everything that talks to the outside world, so tests run the whole agency on fakes."""

    settings: Settings
    create_clients: Callable[[float, Path], Clients]  # (model budget, run folder) → clients for `create`
    model: Callable[[float, Path], ModelClient]  # (model budget, run folder) → a model client
    marketing: Callable[[MetaConnection], Any]  # → MarketingClient on the connected account
    producer: Callable[[Path, Any], Any]  # (run folder, model) → the video studio (daily.Producer)
    check_connection: Callable[[MetaConnection], list[str]]  # → problems with the login (empty = fine)
    launcher: Callable[..., Any] | None = None  # (client, run folder, objective=, say=) → daily.Launcher


@dataclass
class StepContext:
    run_dir: Path
    cfg: AgencyConfig
    services: Services
    state: dict[str, Any]
    budget_usd: float  # what this step may spend on models
    parent: str  # this step's event id
    today: date
    approved_by: str | None
    say: Callable[[str], None]
    connection: MetaConnection | None = None
    spent_usd: float = 0.0  # set by the step


# --- state file ----------------------------------------------------------------------------------

def _write_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".state-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def state_path(run_dir: Path) -> Path:
    return Path(run_dir) / "agency" / "state.json"


def load_state(run_dir: Path) -> dict[str, Any]:
    p = state_path(run_dir)
    if not p.exists():
        raise FileNotFoundError(f"{run_dir} is not an agency run (no agency/state.json)")
    return dict(json.loads(p.read_text(encoding="utf-8")))


def config_from_state(state: dict[str, Any]) -> AgencyConfig:
    return AgencyConfig(**state["config"])


# --- steps ---------------------------------------------------------------------------------------

def owner_policy(cfg: AgencyConfig, state: dict[str, Any], cap_eur: float) -> Policy:
    """The owner's policy for an action on the real account; the first live launch is approved once, then
    remembered in the state (with who approved it)."""
    return Policy(Level(cfg.level), max(0.0, cap_eur), first_live_approved=bool(state.get("first_live_approved_by")))


def step_connect(ctx: StepContext) -> dict[str, Any]:
    if ctx.cfg.simulated_account:
        raise _Skip("simulated account: no Meta login needed, nothing is sent to Meta")
    assert ctx.connection is not None
    problems = ctx.services.check_connection(ctx.connection)
    if problems:
        raise RuntimeError("; ".join(problems) + " — reconnect with `whynot connect`")
    c = ctx.connection
    if not c.can_publish:
        ctx.say("  ! this connection cannot publish yet: " + ("; ".join(c.warnings) or "missing Page or permission"))
    return {"account": c.act, "page": c.page_id, "can_publish": c.can_publish, "can_read": c.can_read,
            "warnings": c.warnings}


def step_create(ctx: StepContext) -> dict[str, Any]:
    cfg = ctx.cfg
    extra = dict(cfg.create)
    ccfg = CreateConfig(app_ref=cfg.app_ref, countries=cfg.countries, daily_cap_eur=cfg.static_cap_eur,
                        budget_usd=ctx.budget_usd, seed=cfg.seed,
                        policy=owner_policy(cfg, ctx.state, cfg.static_cap_eur), **extra)
    clients = ctx.services.create_clients(ctx.budget_usd, ctx.run_dir)
    try:
        result = create(ccfg, clients, ctx.run_dir, parent_event=ctx.parent)
    finally:
        ctx.spent_usd = clients.model.spent_usd
    return {"app": result.app.name, "ad_sets": len(result.plan.ad_sets), "ads": len(result.choices),
            "planned_eur_per_day": result.plan.daily_total_eur, "plan_errors": result.plan_errors}


class _Skip(Exception):
    """Nothing to do for this step in this configuration (recorded as skipped, re-evaluated next time)."""


def step_publish(ctx: StepContext) -> dict[str, Any]:
    from whynot.run.publish import activate_published, publish

    cfg = ctx.cfg
    if cfg.simulated_account:
        raise _Skip("simulated account: the static campaign stays a proposal (plan.json)")
    if not cfg.publish_static:
        raise _Skip("static campaign not published (video ads only)")
    if Level(cfg.level) is Level.DRY_RUN:
        raise _Skip("dry run: nothing is sent to Meta; the plan stays a PAUSED proposal (plan.json)")
    assert ctx.connection is not None
    if not ctx.connection.can_publish:
        raise RuntimeError("the Meta connection cannot publish: " + "; ".join(ctx.connection.warnings))
    plan_json = json.loads((ctx.run_dir / "plan.json").read_text())
    if plan_json.get("errors"):
        raise RuntimeError("the plan has errors: " + "; ".join(plan_json["errors"]))
    plan = plan_from_json(plan_json)
    client = ctx.services.marketing(ctx.connection)
    policy = owner_policy(cfg, ctx.state, cfg.static_cap_eur)
    state = publish(plan, ctx.run_dir, client, policy, objective=cfg.objective, approved_by=ctx.approved_by)
    out = {"status": state.status, "decisions": state.decisions, "campaign": state.objects.get("campaign"),
           "objects": len(state.objects)}
    if state.status == "refused":
        waiting = [d for d in state.decisions if d["outcome"] == "needs_approval"]
        if waiting:
            raise Waiting(f"{waiting[0]['why']}: run again with --approve <your name>")
        raise RuntimeError("every ad set was refused: " + "; ".join(d["why"] for d in state.decisions))
    if not ctx.connection.sandbox and ctx.approved_by:
        ctx.state.setdefault("first_live_approved_by", ctx.approved_by)
    if state.status == "published":
        state = activate_published(state, client, ctx.run_dir)
    committed = sum(s.daily_budget_eur for i, s in enumerate(plan.ad_sets) if f"adset_{i}" in state.objects)
    ctx.state["static_committed_eur"] = round(committed, 2)
    return {**out, "status": state.status, "committed_eur": round(committed, 2), "url": state.campaign_url}


def video_launcher(client: Any, run_dir: Path, *, objective: str, say: Callable[[str], None] = print) -> Any:
    """The real account's launcher for the daily loop: video ads with the plan's audiences, or (no page id or
    plan) a launcher that leaves new ads waiting, with the reason in the report."""
    from whynot.agency.daily import MetaLauncher
    from whynot.run.meta import MetaError
    from whynot.run.video_ads import VideoPublisher

    if not (run_dir / "plan.json").exists():
        say("! no plan.json: new video ads will wait (no audiences to target)")
        return MetaLauncher(client)
    plan = plan_from_json(json.loads((run_dir / "plan.json").read_text()))
    try:
        publisher = VideoPublisher(client, run_dir, store_url=plan.store_url, objective=objective,
                                   campaign_name=f"whynot daily · {plan.app_name}")
    except MetaError as exc:
        say(f"! {exc}: new video ads will wait")
        return MetaLauncher(client)
    return MetaLauncher(client, publisher, audiences={a.audience.persona: a.audience for a in plan.ad_sets},
                        videos=run_dir / "videos", title=plan.app_name)


def step_daily(ctx: StepContext) -> dict[str, Any]:
    from whynot.agency.daily import DailyConfig, SimLauncher, run_day
    from whynot.agents.strategist import Strategy
    from whynot.run.insights import MetaInsights, SimulatedAccount

    cfg = ctx.cfg
    dcfg = DailyConfig(target_live=cfg.target_live, max_new=cfg.max_new, budget_per_ad_eur=cfg.budget_per_ad_eur)
    source: Any
    launcher: Any
    if cfg.simulated_account:
        source = SimulatedAccount(seed=cfg.seed, daily_budget_eur=cfg.budget_per_ad_eur)
        launcher = SimLauncher()
        # a simulated account has nothing to protect: autopilot within the cap, labelled SIMULATED everywhere
        policy = Policy(Level.AUTOPILOT, cfg.daily_cap_eur, first_live_approved=True)
    else:
        assert ctx.connection is not None
        client = ctx.services.marketing(ctx.connection)
        source = MetaInsights(client, objective=cfg.objective)
        launcher = (ctx.services.launcher or video_launcher)(client, ctx.run_dir, objective=cfg.objective,
                                                             say=ctx.say)
        left = cfg.daily_cap_eur - float(ctx.state.get("static_committed_eur", 0.0))
        policy = owner_policy(cfg, ctx.state, left)
    model = ctx.services.model(ctx.budget_usd, ctx.run_dir)
    try:
        producer = ctx.services.producer(ctx.run_dir, model)
        strategy = Strategy.from_json(json.loads((ctx.run_dir / "strategy.json").read_text()))
        rep = run_day(ctx.run_dir, ctx.today, source=source, producer=producer, launcher=launcher, policy=policy,
                      strategy=strategy, cfg=dcfg, approved_by=ctx.approved_by, say=ctx.say)
    finally:
        ctx.spent_usd = model.spent_usd
    launched_live = not cfg.simulated_account and rep.live and ctx.approved_by
    if launched_live and ctx.connection is not None and not ctx.connection.sandbox:
        ctx.state.setdefault("first_live_approved_by", ctx.approved_by)
    return {"day": rep.day, "simulated": rep.simulated, "live": len(rep.live), "paused": len(rep.paused),
            "new": len(rep.new), "waiting_approval": len(rep.waiting_approval), "failures": rep.failures,
            "committed_eur": rep.committed_eur, "cap_eur": rep.cap_eur,
            "report": f"agency/reports/{rep.day}.md"}


STEP_FUNCS: dict[str, Callable[[StepContext], dict[str, Any]]] = {
    "connect": step_connect, "create": step_create, "publish": step_publish, "daily": step_daily}


# --- the orchestrator ----------------------------------------------------------------------------

@dataclass
class AgencyResult:
    run_dir: Path
    status: str  # done | waiting | error
    steps: dict[str, dict[str, Any]]
    usd: float  # model spend of this invocation
    error: str | None = None


class Orchestrator:
    def __init__(self, run_dir: Path, cfg: AgencyConfig, services: Services, *,
                 steps: dict[str, Callable[[StepContext], dict[str, Any]]] | None = None):
        self.run_dir = Path(run_dir)
        self.cfg = cfg
        self.services = services
        self.funcs = {**STEP_FUNCS, **(steps or {})}
        self.last_spent = 0.0
        p = state_path(self.run_dir)
        self.state: dict[str, Any] = (load_state(self.run_dir) if p.exists()
                                      else {"created": datetime.now(UTC).isoformat(), "steps": {}, "days": {}})
        self.state["config"] = asdict(cfg)
        self.connection = MetaConnection.load(Path(cfg.connection)) if cfg.connection else None
        s = services.settings
        self.events = EventLog(self.run_dir / "events.jsonl", (
            s.model_api_key, s.baseten_api_key, s.fb_token, s.meta_token, s.meta_sandbox_token,
            self.connection.token if self.connection else None))
        if self.connection is not None:
            self.state["account"] = self.connection.public()

    @classmethod
    def start(cls, root: Path, cfg: AgencyConfig, services: Services, **kw: Any) -> "Orchestrator":
        return cls(new_run_dir(Path(root), cfg.app_ref), cfg, services, **kw)

    @classmethod
    def resume(cls, run_dir: Path, services: Services, *, level: str | None = None, **kw: Any) -> "Orchestrator":
        cfg = config_from_state(load_state(run_dir))
        if level and level != cfg.level:
            cfg.level = Level(level).value
        return cls(run_dir, cfg, services, **kw)

    def save(self) -> None:
        _write_atomic(state_path(self.run_dir), self.state)

    def _record(self, step: str, key: str | None) -> dict[str, Any]:
        return dict(self.state["days"].get(key, {}) if key else self.state["steps"].get(step, {}))

    def _store(self, step: str, key: str | None, rec: dict[str, Any]) -> None:
        (self.state["days"].__setitem__(key, rec) if key else self.state["steps"].__setitem__(step, rec))

    def run_step(self, step: str, *, today: date, approved_by: str | None, spent: float,
                 say: Callable[[str], None]) -> dict[str, Any]:
        """One step, with its event pair and state record. Returns the record."""
        key = today.isoformat() if step == "daily" else None
        prev = self._record(step, key)
        if prev.get("status") == "ok" and step != "connect":  # connect re-checks the login every time
            self.events.write(AgentEvent(AGENTS[step], step, "cached", detail=key or ""))
            self.last_spent = 0.0
            return {**prev, "status": "cached", "usd": 0.0}
        left = max(0.0, self.cfg.budget_usd - spent)
        budget = min(self.cfg.step_budgets_usd.get(step, left), left)
        start = AgentEvent(AGENTS[step], step, "start", inputs={"config": digest(asdict(self.cfg)),
                                                                **({"day": key} if key else {})})
        self.events.write(start)
        ctx = StepContext(self.run_dir, self.cfg, self.services, self.state, budget, start.id, today, approved_by,
                          say, self.connection)
        t0 = time.monotonic()
        rec: dict[str, Any] = {"at": datetime.now(UTC).isoformat(), "event": start.id}
        try:
            outputs = self.funcs[step](ctx)
            rec |= {"status": "ok", "outputs": outputs}
        except _Skip as why:
            rec |= {"status": "skipped", "detail": str(why)}
        except Waiting as why:
            rec |= {"status": "waiting", "detail": str(why)}
        except Exception as exc:
            cause = exc.cause if isinstance(exc, StageError) else exc
            rec |= {"status": "error", "error": f"{type(cause).__name__}: {cause}"[:500],
                    **({"stage": exc.stage} if isinstance(exc, StageError) else {})}
        self.last_spent = ctx.spent_usd  # exact, for the command's budget (the record keeps it rounded)
        rec |= {"seconds": round(time.monotonic() - t0, 2), "usd": round(ctx.spent_usd, 4),
                "budget_usd": round(budget, 4)}
        self._store(step, key, rec)
        self.save()
        self.events.write(AgentEvent(
            AGENTS[step], step, rec["status"], parent=None, seconds=rec["seconds"], usd=rec["usd"],
            outputs={"summary": digest(rec.get("outputs"))} if "outputs" in rec else {},
            detail=rec.get("detail", key or ""), error=rec.get("error"),
            rollup=step == "create"))  # create's own stage events already carry its cost
        return rec

    def run(self, *, approved_by: str | None = None, today: date | None = None, days: int = 1,
            say: Callable[[str], None] = print) -> AgencyResult:
        if days < 1:
            raise ValueError("days must be ≥ 1")
        if days > 1 and not self.cfg.simulated_account:
            # a real account runs one day: today (several would launch tomorrow's ads today)
            raise ValueError("several days in one go are for the simulated account only")
        today = today or date.today()
        self.save()
        spent = 0.0
        steps: dict[str, dict[str, Any]] = {}
        status = "done"
        plan = [(s, today) for s in STEPS if s != "daily"] + [("daily", today + timedelta(days=i))
                                                             for i in range(days)]
        for step, day in plan:
            name = f"daily {day.isoformat()}" if step == "daily" else step
            say(f"→ {name}")
            rec = self.run_step(step, today=day, approved_by=approved_by, spent=spent, say=say)
            spent += self.last_spent  # cached steps: 0, nothing was spent this time
            steps[name] = rec
            say(f"  {_icon(rec['status'])} {name}: {rec['status']}"
                + (f" — {rec.get('detail') or rec.get('error')}" if rec.get("detail") or rec.get("error") else "")
                + (f" · ${rec['usd']:.2f}" if rec.get("usd") else ""))
            if rec["status"] == "error":
                return AgencyResult(self.run_dir, "error", steps, round(spent, 4),
                                    f"{name}: {rec['error']}")
            if rec["status"] == "waiting":
                status = "waiting"
        return AgencyResult(self.run_dir, status, steps, round(spent, 4))


def _icon(status: str) -> str:
    return {"ok": "✓", "skipped": "•", "waiting": "⏳", "error": "✗", "cached": "✓"}.get(status, "•")


# --- real services -------------------------------------------------------------------------------

def default_services(settings: Settings, *, silent: bool = False) -> Services:  # pragma: no cover - real network
    from dataclasses import replace

    from whynot.agency.create import default_clients
    from whynot.costs import CostLedger

    def model(budget: float, run_dir: Path) -> ModelClient:
        s = replace(settings, cost_log=Path(run_dir) / "costs.jsonl")
        return ModelClient(s, CostLedger(s.cost_log), budget_usd=budget)

    def marketing(conn: MetaConnection) -> Any:
        from whynot.run.meta import MarketingClient

        return MarketingClient(conn.account(), version=settings.fb_api_version)

    def producer(run_dir: Path, m: Any) -> Any:
        from whynot.agency.trend_video import Studio
        from whynot.agency.video import CACHE, VideoConfig

        voice = None
        if settings.elevenlabs_api_key and not silent:
            from whynot.audio.elevenlabs import ElevenLabs
            voice = ElevenLabs(settings.elevenlabs_api_key, CACHE / "audio")
        return Studio(run_dir, m, cfg=VideoConfig(capture=False), voice=voice, voice_id=settings.elevenlabs_voice_id)

    def check_connection(conn: MetaConnection) -> list[str]:
        from whynot.run.connect import check

        return check(conn, version=settings.fb_api_version)

    return Services(settings, default_clients, model, marketing, producer, check_connection)
