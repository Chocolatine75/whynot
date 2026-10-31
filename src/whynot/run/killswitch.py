"""Kill switch: pause everything whynot created on an ad account, now (E8-6).

The owner's emergency stop. It reads what whynot created from each run folder, whatever state it is in:
- `publish.json` (campaigns, ad sets and ads from `whynot publish`, even a half-finished publish);
- `agency/memory.json` (ads the daily loop launched).
Campaigns are paused first: that alone stops delivery of everything under them. Ad sets and ads follow,
in parallel, so nothing keeps running if a campaign call fails. Creatives have no status and are skipped.

It never asks the autopilot: pausing adds no spend, and the owner must be able to stop everything whatever
the autonomy level. Every pause is logged in the run's `actions.jsonl` (outcome execute or failed) and the
daily loop's memory marks the ads paused, so tomorrow's run does not count them as live.
Objects published to another account (sandbox vs live) are left alone and reported.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from whynot.agency.memory import Memory
from whynot.run.autopilot import Action, ActionLog, Decision, Kind, Outcome, Policy
from whynot.run.meta import MarketingClient, MetaError
from whynot.run.publish import PublishState

ORDER = ("campaign", "adset", "ad")  # parents first: a paused campaign stops all its ads at once


@dataclass(frozen=True)
class Target:
    run: Path
    ref: str  # whynot's name for it: campaign, adset_<x>, ad_<x>, or a daily-loop ad key
    meta_id: str
    level: str  # campaign | adset | ad


@dataclass
class StopReport:
    paused: list[Target] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)  # meta id -> error
    skipped: list[str] = field(default_factory=list)  # runs published to another account
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.failed


def _level(ref: str) -> str | None:
    if ref == "campaign" or ref.startswith("campaign_"):
        return "campaign"
    if ref.startswith("adset_"):
        return "adset"
    if ref.startswith("ad_"):
        return "ad"
    return None  # creatives, images: no status to change


def targets(run: Path, account_act: str) -> tuple[list[Target], bool]:
    """(what whynot created in this run on this account, whether the run belongs to another account)."""
    run = Path(run)
    found: dict[str, Target] = {}
    state = PublishState.load(run / "publish.json") if (run / "publish.json").exists() else None
    if state is not None and state.account and state.account != account_act:
        return [], True
    if state is not None:
        for ref, meta_id in state.objects.items():
            level = _level(ref)
            if level and meta_id:
                found[meta_id] = Target(run, ref, meta_id, level)
    memory_path = run / "agency" / "memory.json"
    if memory_path.exists():
        for rec in Memory(memory_path).by_status("live"):
            if rec.meta_ad_id and not rec.meta_ad_id.startswith("sim-"):
                found.setdefault(rec.meta_ad_id, Target(run, rec.key, rec.meta_ad_id, "ad"))
    return sorted(found.values(), key=lambda t: (ORDER.index(t.level), t.meta_id)), False


def stop(runs: list[Path], client: MarketingClient, *, by: str, policy: Policy | None = None,
         workers: int = 8) -> StopReport:
    """Pause every campaign, ad set and ad these runs created on the client's account. Returns what happened."""
    if not by.strip():
        raise ValueError("say who pulls the kill switch (it is logged)")
    start = time.monotonic()
    report = StopReport()
    policy = policy or Policy()
    todo: list[Target] = []
    for run in runs:
        found, other_account = targets(run, client.account.act)
        if other_account:
            report.skipped.append(str(run))
        todo += found

    def pause(t: Target) -> tuple[Target, str | None]:
        try:
            client.set_status(t.meta_id, "PAUSED")
            return t, None
        except MetaError as exc:
            return t, str(exc)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        first = [t for t in todo if t.level == "campaign"]
        rest = [t for t in todo if t.level != "campaign"]
        results = list(pool.map(pause, first)) + list(pool.map(pause, rest))

    for t, error in results:
        log = ActionLog(t.run / "actions.jsonl")
        outcome = Outcome.EXECUTE if error is None else Outcome.REFUSED
        log.record(Action(Kind.PAUSE, t.ref, f"kill switch: pause {t.level} {t.meta_id}"), policy,
                   Decision(outcome, f"kill switch by {by}" + (f"; failed: {error}" if error else ""), 0.0),
                   approved_by=by)
        if error is None:
            report.paused.append(t)
        else:
            report.failed[t.meta_id] = error

    for run in {t.run for t, error in results if error is None}:  # the daily loop must not count them as live
        memory_path = run / "agency" / "memory.json"
        if memory_path.exists():
            memory = Memory(memory_path)
            paused_ids = {t.meta_id for t in report.paused}
            for rec in memory.by_status("live"):
                if rec.meta_ad_id in paused_ids:
                    memory.set_status(rec.key, "paused", f"kill switch by {by}")
            memory.save()
    report.seconds = round(time.monotonic() - start, 2)
    return report
