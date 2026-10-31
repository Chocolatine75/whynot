"""`whynot daily`: the agency's day. Read results, decide, make new ads with new ideas, launch, report.

1. RESULTS: yesterday's numbers for every live ad (Meta Insights, or the simulated account), into memory.
2. DECIDE: the autopilot rules (`run/autopilot.review`) mark losers (cost per conversion far above the
   account) and tired ads; every pause goes through `decide()` (autonomy level, cap) and the action log.
3. IDEAS: the free slots (target live ads minus live ads, at most `max_new` a day) get new ideas from the
   planner (`agency/ideas.py`): build on what sells in a new format, explore far from everything tried,
   never an idea twice.
4. MAKE: one video per idea (`trend_video.Studio`), its script told the hooks and lines already used.
5. LAUNCH: each new ad asks `decide()` for its daily budget: executed within the cap and autonomy level,
   or waiting for the owner's approval.
6. REPORT: `<run>/agency/reports/<day>.md` + `.json`, every number from memory or the action log.

A lock makes two runs of the same day impossible (a second one fails): the cap can't be breached by
concurrent runs. Everything about the client lives in `<run>/agency/` (memory, action log, reports).
"""

import fcntl
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Protocol

from whynot.agency.ideas import Idea, plan
from whynot.agency.memory import AdRecord, Memory
from whynot.run.autopilot import (
    AccountState,
    Action,
    ActionLog,
    Kind,
    Outcome,
    Policy,
    Rules,
    decide,
    review,
)


class Producer(Protocol):
    """Makes one video for an idea; returns at least {"brief": {...hook, voice...}, "file": {"path": ...}}."""

    def make(self, p: dict[str, Any], name_prefix: str, *, avoid: list[tuple[str, str]] | None = None
             ) -> dict[str, Any]: ...


class Launcher(Protocol):
    """Starts or pauses an ad on the account. Returns the account's ad id when it launches one."""

    simulated: bool

    def launch(self, rec: AdRecord, budget_eur: float) -> str: ...

    def pause(self, rec: AdRecord) -> None: ...


class SimLauncher:
    """The simulated account: launching marks the ad live; its results come from `SimulatedAccount`."""

    simulated = True

    def launch(self, rec: AdRecord, budget_eur: float) -> str:
        return f"sim-{rec.key}"

    def pause(self, rec: AdRecord) -> None:
        return None


class MetaLauncher:
    """The real account: pauses go through the Marketing API. Publishing a new VIDEO ad is not built yet
    (roadmap E14-10): launching raises, so new ads stay proposed and the report says why."""

    simulated = False

    def __init__(self, client: Any):
        self.client = client

    def launch(self, rec: AdRecord, budget_eur: float) -> str:
        raise NotImplementedError("publishing video ads to Meta is not built yet (E14-10): approve and upload "
                                  f"{rec.file} by hand, or wait for E14-10")

    def pause(self, rec: AdRecord) -> None:
        if rec.meta_ad_id:
            self.client.set_status(rec.meta_ad_id, "PAUSED")


@dataclass
class DailyConfig:
    target_live: int = 4  # ads running at the same time
    max_new: int = 2  # new ads made per day at most
    budget_per_ad_eur: float = 5.0
    rules: Rules = field(default_factory=lambda: Rules(min_spend_eur=10.0))
    formats: list[str] | None = None  # default: the whole library


@dataclass
class DayReport:
    day: str
    simulated: bool
    yesterday: dict[str, float] = field(default_factory=dict)
    live: list[str] = field(default_factory=list)
    paused: list[dict[str, str]] = field(default_factory=list)
    new: list[dict[str, Any]] = field(default_factory=list)
    waiting_approval: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    learnings: dict[str, Any] = field(default_factory=dict)
    committed_eur: float = 0.0
    cap_eur: float = 0.0


BACKUP_IDEAS = 2  # extra ideas planned each day, used only when one fails


class AlreadyRunning(RuntimeError):
    pass


@contextmanager
def day_lock(folder: Path) -> Iterator[None]:
    """One daily run at a time for a client: a second concurrent run fails at once instead of double-spending."""
    folder.mkdir(parents=True, exist_ok=True)
    f = (folder / "daily.lock").open("w")
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AlreadyRunning("a daily run is already in progress for this client") from None
        yield
    finally:
        f.close()


def _pairs(strategy: Any) -> list[tuple[str, str]]:
    return [(a.persona, a.id) for a in strategy.angles]


def run_day(run_dir: Path, day: date, *, source: Any, producer: Producer, launcher: Launcher, policy: Policy,
            strategy: Any, cfg: DailyConfig | None = None, approved_by: str | None = None,
            say: Callable[[str], None] = print) -> DayReport:
    cfg = cfg or DailyConfig()
    folder = Path(run_dir) / "agency"
    with day_lock(folder):
        memory = Memory(folder / "memory.json")
        log = ActionLog(folder / "actions.jsonl")
        rep = DayReport(day.isoformat(), bool(getattr(source, "simulated", False)), cap_eur=policy.daily_cap_eur)

        # 1. results up to yesterday
        running = memory.by_status("live", "paused")
        if running:
            ids = {r.meta_ad_id or r.key: r for r in running}
            launched = {k: date.fromisoformat(r.launched) for k, r in ids.items() if r.launched}
            since = min(launched.values(), default=day - timedelta(days=1))
            kwargs = {"launched": launched} if rep.simulated else {}
            got = source.fetch(list(ids), since, day - timedelta(days=1), **kwargs)
            for k, days in got.items():
                if k in ids:
                    memory.record_metrics(ids[k].key, [d for d in days if d.day < day.isoformat()])
            y = (day - timedelta(days=1)).isoformat()
            rows = [m for r in running for m in r.metrics if m.day == y]
            rep.yesterday = {"spend_eur": round(sum(m.spend_eur for m in rows), 2),
                             "impressions": sum(m.impressions for m in rows),
                             "clicks": sum(m.clicks for m in rows), "conversions": sum(m.conversions for m in rows)}

        # 2. decide: pause losers and tired ads
        live = memory.by_status("live")
        budgets = {r.key: cfg.budget_per_ad_eur for r in live}
        for action in review({r.key: r.metrics for r in live}, cfg.rules):
            d = decide(action, policy, AccountState(dict(budgets)), approved_by=approved_by)
            log.record(action, policy, d, approved_by=approved_by)
            if d.outcome is Outcome.EXECUTE:
                launcher.pause(memory.ads[action.ad_ref])
                memory.set_status(action.ad_ref, "paused", action.reason, day=rep.day)
                memory.save()  # what happened on the account is on disk before anything else can fail
                budgets.pop(action.ad_ref, None)
                rep.paused.append({"ad": action.ad_ref, "why": action.reason})
                say(f"  ⏸ {action.ad_ref}: {action.reason}")
            else:
                rep.failures.append(f"pause of {action.ad_ref} not executed: {d.why}")

        # 3. ideas for the free slots
        from whynot.create.trends import FORMATS

        formats = cfg.formats or [f.id for f in FORMATS]
        slots = max(0, cfg.target_live - len(budgets) - len(memory.by_status("proposed")))
        want = min(slots, cfg.max_new)
        # backups: when an idea fails to become an ad, the next one takes its slot
        ideas: list[Idea] = plan(want + BACKUP_IDEAS if want else 0, formats=formats, pairs=_pairs(strategy),
                                 tried=[(f, p, a) for f, p, a, _ in memory.ideas()], ads=list(memory.ads.values()))
        say(f"day {rep.day}: {len(budgets)} live, {slots} free slot(s), {want} new ad(s) to make")

        # 4. make one video per idea, until the free slots are filled
        avoid = [(r.hook, r.voice) for r in memory.ads.values()]
        made = 0
        for n, idea in enumerate(ideas, 1):
            if made >= want:
                break
            try:
                v = producer.make({"format": idea.format, "persona": idea.persona, "angle": idea.angle,
                                   "why": idea.why}, f"day-{rep.day}-{n}", avoid=avoid)
            except Exception as exc:  # one failed video must not stop the day; the idea is never retried
                why = f"{type(exc).__name__}: {exc}"[:300]
                rep.failures.append(f"{idea.format}/{idea.angle}: {why}")
                memory.add(AdRecord(f"failed-{rep.day}-{n}", rep.day, idea.format, idea.persona, idea.angle, "",
                                    why=idea.why, status="failed", notes=[why]))
                continue
            made += 1
            b = v["brief"]
            key = Path(v["file"]["path"]).stem
            rec = AdRecord(key, rep.day, idea.format, idea.persona, idea.angle, b.get("hook", ""),
                           voice=b.get("voice", ""), file=v["file"]["path"], why=idea.why)
            memory.add(rec)
            avoid.append((rec.hook, rec.voice))
            rep.new.append({"ad": key, "format": idea.format, "persona": idea.persona, "angle": idea.angle,
                            "hook": rec.hook, "why": idea.why})

        # 5. launch what the autonomy level and the cap allow (new ads and earlier ones waiting)
        for rec in sorted(memory.by_status("proposed"), key=lambda r: r.key):
            action = Action(Kind.PUBLISH, rec.key, f"launch {rec.format} / {rec.angle}", cfg.budget_per_ad_eur)
            d = decide(action, policy, AccountState(dict(budgets)), approved_by=approved_by)
            log.record(action, policy, d, approved_by=approved_by)
            if d.outcome is Outcome.EXECUTE:
                try:
                    rec.meta_ad_id = launcher.launch(rec, cfg.budget_per_ad_eur)
                except Exception as exc:  # stays proposed; the owner sees why
                    rep.failures.append(f"launch of {rec.key} failed: {type(exc).__name__}: {exc}"[:300])
                    rep.waiting_approval.append(rec.key)
                    continue
                memory.set_status(rec.key, "live", d.why, day=rep.day)
                memory.save()  # a crash after this point must not make tomorrow launch the same ad again
                budgets[rec.key] = cfg.budget_per_ad_eur
            else:
                rep.waiting_approval.append(rec.key)
                if d.outcome is Outcome.REFUSED:
                    rep.failures.append(f"launch of {rec.key} refused: {d.why}")

        rep.live = sorted(budgets)
        rep.committed_eur = round(sum(budgets.values()), 2)
        rep.learnings = memory.learnings(min_spend=cfg.rules.min_spend_eur)
        memory.save()
        write_report(folder / "reports", rep, memory)
        return rep


def write_report(folder: Path, rep: DayReport, memory: Memory) -> Path:
    """The owner's daily report: what ran, what was paused and why, what's new, what waits for approval."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{rep.day}.json").write_text(json.dumps(asdict(rep), indent=1, ensure_ascii=False, default=str))
    tag = " (SIMULATED account: these numbers are not real results)" if rep.simulated else ""
    y = rep.yesterday
    lines = [f"# Daily report — {rep.day}{tag}", ""]
    if y:
        cpa = f"€{y['spend_eur'] / y['conversions']:.2f}" if y.get("conversions") else "—"
        lines += [f"Yesterday: €{y['spend_eur']:.2f} spent, {y['impressions']} impressions, {y['clicks']} clicks, "
                  f"{y['conversions']} conversions (cost per conversion {cpa}).", ""]
    lines += [f"Running: {len(rep.live)} ads, €{rep.committed_eur:.2f}/day committed (cap €{rep.cap_eur:.2f}).", ""]
    if rep.paused:
        lines += ["## Paused", *[f"- {p['ad']}: {p['why']}" for p in rep.paused], ""]
    if rep.new:
        lines += ["## New ads", *[f"- **{n['ad']}** — {n['format']} · {n['angle']} · \"{n['hook']}\"  \n  {n['why']}"
                                  for n in rep.new], ""]
    if rep.waiting_approval:
        lines += ["## Waiting for your approval", *[f"- {k}" for k in rep.waiting_approval], ""]
    best = sorted((r for r in memory.ads.values() if r.cpa is not None), key=lambda r: r.cpa or 0)[:3]
    if best:
        lines += ["## Best so far", *[f"- {r.key} ({r.format} · {r.angle}): €{r.cpa:.2f} per conversion, "
                                      f"{r.conversions} conversions" for r in best], ""]
    if rep.failures:
        lines += ["## Problems", *[f"- {f}" for f in rep.failures], ""]
    path = folder / f"{rep.day}.md"
    path.write_text("\n".join(lines))
    return path
