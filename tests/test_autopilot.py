import pytest

from whynot.autopilot import (
    AccountState, Action, ActionLog, DailyMetrics, Kind, Level, Outcome, Policy, Rules, decide, review,
)

RUNNING = AccountState({"ad1": 10.0, "ad2": 15.0})  # €25/day committed


def publish(budget=10.0, guards=True, ref="new"):
    return Action(Kind.PUBLISH, ref, "winner in the simulated feed", budget, guards)


def test_default_policy_is_dry_run_with_no_spend():
    p = Policy()
    assert p.level is Level.DRY_RUN and p.daily_cap_eur == 0
    assert decide(publish(), p, AccountState()).outcome is Outcome.REFUSED  # cap 0
    d = decide(Action(Kind.PAUSE, "ad1", "loser"), p, RUNNING)
    assert d.outcome is Outcome.SIMULATED and d.committed_after_eur == 15.0


@pytest.mark.parametrize("level", list(Level))
def test_cap_is_enforced_at_every_level(level):
    p = Policy(level, daily_cap_eur=30.0, first_live_approved=True)
    d = decide(publish(budget=10.0), p, RUNNING, approved_by="owner")
    assert d.outcome is Outcome.REFUSED and "above the cap" in d.why
    assert decide(publish(budget=5.0), p, RUNNING, approved_by="owner").outcome is not Outcome.REFUSED


def test_budget_change_counts_replacement_not_addition():
    p = Policy(Level.AUTOPILOT, 30.0, first_live_approved=True)
    assert decide(Action(Kind.BUDGET, "ad1", "scale", 15.0), p, RUNNING).outcome is Outcome.EXECUTE  # 15+15
    assert decide(Action(Kind.BUDGET, "ad1", "scale", 16.0), p, RUNNING).outcome is Outcome.REFUSED
    # lowering a budget is always allowed, even when already over the cap
    over = Policy(Level.AUTOPILOT, 5.0, first_live_approved=True)
    assert decide(Action(Kind.BUDGET, "ad2", "cut", 1.0), over, RUNNING).outcome is Outcome.EXECUTE
    assert decide(Action(Kind.BUDGET, "ad2", "neg", -1.0), p, RUNNING).outcome is Outcome.REFUSED


def test_guard_failed_ad_is_never_published():
    p = Policy(Level.AUTOPILOT, 100.0, first_live_approved=True)
    d = decide(publish(guards=False), p, RUNNING, approved_by="owner")
    assert d.outcome is Outcome.REFUSED and "guards" in d.why


def test_propose_waits_for_approval():
    p = Policy(Level.PROPOSE, 100.0, first_live_approved=True)
    assert decide(Action(Kind.PAUSE, "ad1", "x"), p, RUNNING).outcome is Outcome.NEEDS_APPROVAL
    d = decide(Action(Kind.PAUSE, "ad1", "x"), p, RUNNING, approved_by="owner")
    assert d.outcome is Outcome.EXECUTE and "owner" in d.why


def test_autopilot_needs_approval_for_first_live_launch_only():
    first = Policy(Level.AUTOPILOT, 100.0, first_live_approved=False)
    d = decide(publish(), first, RUNNING)
    assert d.outcome is Outcome.NEEDS_APPROVAL and "first live launch" in d.why
    assert decide(Action(Kind.PAUSE, "ad1", "x"), first, RUNNING).outcome is Outcome.EXECUTE
    later = Policy(Level.AUTOPILOT, 100.0, first_live_approved=True)
    assert decide(publish(), later, RUNNING).outcome is Outcome.EXECUTE


def test_policy_from_env():
    assert Policy.from_env("Autopilot ", "12.5").level is Level.AUTOPILOT
    with pytest.raises(ValueError, match="AUTONOMY_LEVEL"):
        Policy.from_env("yolo", 10)
    with pytest.raises(ValueError, match="negative"):
        Policy.from_env("dry_run", -1)


def days(spend, conv, ctrs):
    return [DailyMetrics(f"2026-11-0{i + 1}", spend, 1000, int(c * 1000), conv) for i, c in enumerate(ctrs)]


def test_review_pauses_losers_and_fatigued_ads():
    history = {
        "good": days(10, 2, [0.02] * 6),        # CPA 5
        "ok": days(10, 1, [0.02] * 6),          # CPA 10
        "loser": days(10, 0, [0.02] * 6),       # no conversion
        "tired": days(10, 2, [0.03, 0.03, 0.03, 0.015, 0.015, 0.015]),
        "young": days(1, 0, [0.01]),            # spent too little to judge
    }
    actions = {a.ad_ref: a for a in review(history)}
    assert set(actions) == {"loser", "tired"}
    assert "no conversion" in actions["loser"].reason and "fatigue" in actions["tired"].reason
    assert all(a.kind is Kind.PAUSE for a in actions.values())


def test_review_with_custom_rules_and_expensive_ad():
    history = {"a": days(10, 2, [0.02] * 3), "b": days(10, 2, [0.02] * 3), "c": days(30, 1, [0.02] * 3)}
    assert [a.ad_ref for a in review(history)] == ["c"]  # CPA 90 vs median 15
    assert review(history, Rules(loser_cpa_ratio=10)) == []


def test_action_log(tmp_path):
    log = ActionLog(tmp_path / "actions.jsonl")
    p = Policy()
    a = Action(Kind.PAUSE, "ad1", "loser")
    log.record(a, p, decide(a, p, RUNNING))
    rows = log.rows()
    assert rows[0]["kind"] == "pause" and rows[0]["outcome"] == "simulated" and rows[0]["level"] == "dry_run"
