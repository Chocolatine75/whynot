"""Autopilot safety rules: what the agency may do on a real ad account.

Every live action (publish, pause, budget change) goes through `decide`, which
applies, in order:
1. hard caps: daily budget never above the owner's cap; nothing that spends
   when the cap is 0; a guard-failed ad is never published;
2. the autonomy level:
   - dry_run (default): nothing is executed, the decision is "simulated";
   - propose: every action waits for the owner's approval;
   - autopilot: acts within caps, except the first live publish, which always
     needs the owner's explicit approval.
Pausing never adds spend, so it is allowed under any cap.

`review` turns daily metrics into proposed actions (pause losers and fatigued
ads); those still go through `decide`. Every decision is appended to a JSONL
log (`LiveAction` in ARCHITECTURE.md). This module never calls Meta itself.
"""

import json
import math
import statistics
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path


class Level(StrEnum):
    DRY_RUN = "dry_run"
    PROPOSE = "propose"
    AUTOPILOT = "autopilot"


class Kind(StrEnum):
    PUBLISH = "publish"
    PAUSE = "pause"
    BUDGET = "budget"  # change an ad set's daily budget


class Outcome(StrEnum):
    SIMULATED = "simulated"  # dry run: shown, not executed
    NEEDS_APPROVAL = "needs_approval"
    EXECUTE = "execute"
    REFUSED = "refused"


@dataclass(frozen=True)
class Policy:
    level: Level = Level.DRY_RUN
    daily_cap_eur: float = 0.0  # owner's hard cap over all running ads
    first_live_approved: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.daily_cap_eur) or self.daily_cap_eur < 0:
            raise ValueError("daily cap must be a finite number ≥ 0")

    @classmethod
    def from_env(cls, level: str, daily_cap_eur: str | float, first_live_approved: bool = False) -> "Policy":
        try:
            lvl = Level(level.strip().lower())
        except ValueError:
            raise ValueError(f"AUTONOMY_LEVEL must be one of {[x.value for x in Level]}, got {level!r}") from None
        try:
            cap = float(daily_cap_eur)
        except (TypeError, ValueError):
            raise ValueError(f"MAX_DAILY_AD_SPEND_EUR must be a number, got {daily_cap_eur!r}") from None
        if not math.isfinite(cap) or cap < 0:
            raise ValueError("MAX_DAILY_AD_SPEND_EUR must be a finite number ≥ 0")
        return cls(lvl, cap, first_live_approved)


@dataclass(frozen=True)
class Action:
    kind: Kind
    ad_ref: str
    reason: str
    daily_budget_eur: float = 0.0  # publish/budget: the ad's new daily budget
    guards_passed: bool = True  # publish: all guards of the variant passed


@dataclass(frozen=True)
class AccountState:
    daily_budgets_eur: dict[str, float] = field(default_factory=dict)  # running ads → daily budget

    @property
    def committed_eur(self) -> float:
        return sum(self.daily_budgets_eur.values())


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    why: str
    committed_after_eur: float


def decide(action: Action, policy: Policy, state: AccountState, *, approved_by: str | None = None) -> Decision:
    current = state.committed_eur
    if not math.isfinite(current) or any(b < 0 for b in state.daily_budgets_eur.values()):
        return Decision(Outcome.REFUSED, "account state has an invalid budget", current)
    after = current
    if action.kind in (Kind.PUBLISH, Kind.BUDGET):
        b = action.daily_budget_eur
        if not math.isfinite(b) or b < 0:
            return Decision(Outcome.REFUSED, f"invalid budget {b!r}", current)
        after = current - state.daily_budgets_eur.get(action.ad_ref, 0.0) + action.daily_budget_eur
    elif action.kind is Kind.PAUSE:
        after = current - state.daily_budgets_eur.get(action.ad_ref, 0.0)

    if action.kind is Kind.PUBLISH and not action.guards_passed:
        return Decision(Outcome.REFUSED, "guards did not all pass", current)
    if after > current and after > policy.daily_cap_eur + 1e-9:
        return Decision(Outcome.REFUSED,
                        f"would commit €{after:.2f}/day, above the cap of €{policy.daily_cap_eur:.2f}", current)

    if policy.level is Level.DRY_RUN:
        return Decision(Outcome.SIMULATED, "dry run: nothing is sent to Meta", after)
    first_live = action.kind is Kind.PUBLISH and not policy.first_live_approved
    if policy.level is Level.PROPOSE or first_live:
        if approved_by:
            return Decision(Outcome.EXECUTE, f"approved by {approved_by}", after)
        why = ("first live launch needs the owner's approval" if first_live
               else "propose mode: owner approves each action")
        return Decision(Outcome.NEEDS_APPROVAL, why, after)
    return Decision(Outcome.EXECUTE, "autopilot, within caps", after)


# --- daily review ----------------------------------------------------------------

@dataclass(frozen=True)
class DailyMetrics:
    day: str  # ISO date
    spend_eur: float
    impressions: int
    clicks: int
    conversions: int  # installs / purchases


@dataclass(frozen=True)
class Rules:
    min_spend_eur: float = 20.0  # don't judge an ad before it spent this much
    loser_cpa_ratio: float = 2.0  # CPA above ratio × median CPA of the account → pause
    fatigue_window_days: int = 3
    fatigue_ctr_drop: float = 0.3  # CTR of the last window ≥30 % below the first → pause


def _ctr(days: list[DailyMetrics]) -> float | None:
    imp = sum(d.impressions for d in days)
    return sum(d.clicks for d in days) / imp if imp else None


def review(history: dict[str, list[DailyMetrics]], rules: Rules | None = None) -> list[Action]:
    """Pause actions for losers (CPA far above the account median) and fatigued ads."""
    rules = rules or Rules()
    cpas: dict[str, float] = {}
    for ad, days in history.items():
        spend = sum(d.spend_eur for d in days)
        conv = sum(d.conversions for d in days)
        if spend >= rules.min_spend_eur:
            cpas[ad] = spend / conv if conv else float("inf")
    finite = [c for c in cpas.values() if c != float("inf")]
    median = statistics.median(finite) if finite else None

    actions: list[Action] = []
    for ad, days in sorted(history.items()):
        if ad not in cpas:
            continue
        cpa = cpas[ad]
        if median is not None and cpa > rules.loser_cpa_ratio * median:
            shown = "no conversion" if cpa == float("inf") else f"CPA €{cpa:.2f}"
            actions.append(Action(Kind.PAUSE, ad, f"loser: {shown} vs account median €{median:.2f}"))
            continue
        w = rules.fatigue_window_days
        ordered = sorted(days, key=lambda d: d.day)
        if len(ordered) >= 2 * w:
            first, last = _ctr(ordered[:w]), _ctr(ordered[-w:])
            if first and last is not None and last < (1 - rules.fatigue_ctr_drop) * first:
                actions.append(Action(Kind.PAUSE, ad,
                                      f"fatigue: CTR {last:.2%} over the last {w} days vs {first:.2%} at start"))
    return actions


# --- log -------------------------------------------------------------------------

class ActionLog:
    """Append-only JSONL of every decision, executed or not."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def record(self, action: Action, policy: Policy, decision: Decision, *, approved_by: str | None = None) -> dict:
        row = {"ts": datetime.now(UTC).isoformat(), **asdict(action), "level": policy.level.value,
               "cap_eur": policy.daily_cap_eur, "outcome": decision.outcome.value, "why": decision.why,
               "committed_after_eur": decision.committed_after_eur, "approved_by": approved_by}
        row["kind"] = action.kind.value
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]
