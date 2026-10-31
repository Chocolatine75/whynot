"""The daily loop: a week on a simulated account, the cap under random results, the lock, the report."""

import json
from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from strategy_fixture import ADS, APP, COUNTRIES, strategy_json
from whynot.agency.daily import AlreadyRunning, DailyConfig, SimLauncher, day_lock, run_day
from whynot.agency.memory import Memory
from whynot.agents.strategist import Sources
from whynot.agents.strategist import make_validator as strategy_validator
from whynot.run.autopilot import DailyMetrics, Level, Policy, Rules
from whynot.run.insights import SimulatedAccount

STRATEGY = strategy_validator(Sources.build(APP, ADS), COUNTRIES)(strategy_json())
DAY0 = date(2026, 11, 1)


class Producer:
    """A fake studio: a new hook per call, records what it was asked to avoid."""

    def __init__(self, fail_on=()):
        self.calls, self.fail_on = [], set(fail_on)

    def make(self, p, name_prefix, *, avoid=None):
        self.calls.append({**p, "avoid": list(avoid or [])})
        if p["format"] in self.fail_on:
            raise RuntimeError("render failed")
        n = len(self.calls)
        return {"brief": {"hook": f"hook {n} {p['format']}", "voice": f"line {n}"},
                "file": {"path": f"{name_prefix}-{p['format']}.mp4"}}


AUTOPILOT = Policy(Level.AUTOPILOT, 20.0, first_live_approved=True)


def week(tmp_path, *, policy=AUTOPILOT, days=7, producer=None, cfg=None):
    producer = producer or Producer()
    acc = SimulatedAccount(seed=1, daily_budget_eur=5.0)
    reports = [run_day(tmp_path, DAY0 + timedelta(days=i), source=acc, producer=producer, launcher=SimLauncher(),
                       policy=policy, strategy=STRATEGY, cfg=cfg or DailyConfig(target_live=4, max_new=2),
                       say=lambda s: None) for i in range(days)]
    return reports, Memory(tmp_path / "agency" / "memory.json"), producer


def test_a_simulated_week_launches_learns_pauses_and_never_repeats(tmp_path):
    reports, memory, producer = week(tmp_path)
    assert len(reports[0].new) == 2 and reports[0].live  # day 1: new ads made and launched
    ideas = [(r.format, r.persona, r.angle) for r in memory.ads.values()]
    assert len(ideas) == len(set(ideas))  # never the same idea twice
    assert any(r.paused for r in reports)  # the rules paused something during the week
    paused = memory.by_status("paused")
    assert paused and all(p.notes[-1].split(" ", 1)[1].startswith("paused") for p in paused)
    assert all(rep.committed_eur <= rep.cap_eur for rep in reports)
    assert reports[-1].yesterday["spend_eur"] > 0 and reports[-1].simulated
    # each new script was told the hooks of every earlier ad
    assert len(producer.calls[-1]["avoid"]) == len(producer.calls) - 1
    md = (tmp_path / "agency" / "reports" / f"{reports[-1].day}.md").read_text()
    assert "SIMULATED account" in md and "Running:" in md


def test_exploit_appears_once_something_sells(tmp_path):
    reports, memory, _ = week(tmp_path, days=6)
    whys = [n["why"] for rep in reports for n in rep.new]
    assert any(w.startswith("explore") for w in whys)
    if any(r.cpa is not None and r.spend >= 10 for r in memory.ads.values()):
        assert any(w.startswith("exploit") for w in whys)


def test_dry_run_makes_ads_but_launches_nothing(tmp_path):
    reports, memory, _ = week(tmp_path, policy=Policy(), days=2)
    assert not memory.by_status("live") and memory.by_status("proposed")
    assert reports[0].waiting_approval and all(r.committed_eur == 0 for r in reports)


def test_propose_mode_waits_for_the_owner_then_launches_with_approval(tmp_path):
    producer = Producer()
    acc = SimulatedAccount(seed=1)
    kw = dict(source=acc, producer=producer, launcher=SimLauncher(), strategy=STRATEGY, say=lambda s: None,
              policy=Policy(Level.PROPOSE, 20.0, first_live_approved=True))
    r1 = run_day(tmp_path, DAY0, **kw)
    assert r1.waiting_approval and not r1.live
    r2 = run_day(tmp_path, DAY0 + timedelta(days=1), approved_by="Matteo", **kw)
    assert set(r2.live) >= set(r1.waiting_approval)
    log = [json.loads(x) for x in (tmp_path / "agency" / "actions.jsonl").read_text().splitlines()]
    assert any(x["approved_by"] == "Matteo" and x["outcome"] == "execute" for x in log)


def test_a_failed_video_does_not_stop_the_day(tmp_path):
    producer = Producer(fail_on={"pov", "tell_me_without", "expectation_reality", "nobody_me"})
    reports, memory, _ = week(tmp_path, days=1, producer=producer)
    assert len(memory.ads) + len(reports[0].failures) >= 2


class RandomSource:
    simulated = True

    def __init__(self, series):
        self.series = series

    def fetch(self, ad_ids, since, until, launched=None):
        out = {}
        for i, ad in enumerate(ad_ids):
            spend, conv = self.series[i % len(self.series)]
            out[ad] = [DailyMetrics(until.isoformat(), spend, 1000, 10, conv)]
        return out


@settings(max_examples=25, deadline=None)
@given(st.lists(st.tuples(st.floats(0, 60, allow_nan=False), st.integers(0, 10)), min_size=1, max_size=6),
       st.floats(0, 40, allow_nan=False), st.integers(1, 5))
def test_the_cap_is_never_exceeded_whatever_the_results(tmp_path_factory, series, cap, target):
    folder = tmp_path_factory.mktemp("cap")
    for i in range(4):
        rep = run_day(folder, DAY0 + timedelta(days=i), source=RandomSource(series), producer=Producer(),
                      launcher=SimLauncher(), policy=Policy(Level.AUTOPILOT, cap, first_live_approved=True),
                      strategy=STRATEGY, cfg=DailyConfig(target_live=target, max_new=3, budget_per_ad_eur=6.0,
                                                         rules=Rules(min_spend_eur=5.0)), say=lambda s: None)
        assert rep.committed_eur <= cap + 1e-9


def test_two_runs_at_the_same_time_are_impossible(tmp_path):
    with day_lock(tmp_path / "agency"), pytest.raises(AlreadyRunning):
        run_day(tmp_path, DAY0, source=SimulatedAccount(), producer=Producer(), launcher=SimLauncher(),
                policy=AUTOPILOT, strategy=STRATEGY, say=lambda s: None)


def test_on_the_real_account_pauses_go_to_meta_and_unbuilt_video_launches_wait(tmp_path):
    from types import SimpleNamespace as NS

    from whynot.agency.daily import MetaLauncher
    from whynot.agency.memory import AdRecord
    calls = []
    launcher = MetaLauncher(NS(set_status=lambda i, s: calls.append((i, s))))
    launcher.pause(AdRecord("k", "2026-11-01", "pov", "p", "a", "h", meta_ad_id="123"))
    launcher.pause(AdRecord("k2", "2026-11-01", "pov", "p", "a", "h"))  # never published: nothing to pause
    assert calls == [("123", "PAUSED")]
    rep = run_day(tmp_path, DAY0, source=SimulatedAccount(), producer=Producer(), launcher=launcher,
                  policy=AUTOPILOT, strategy=STRATEGY, say=lambda s: None)
    assert not rep.live and rep.waiting_approval and "E14-10" in rep.failures[0]


def test_a_failed_idea_is_replaced_the_same_day_and_never_retried(tmp_path):
    """Regression: an idea that failed was planned again every day, so days produced nothing."""

    class FirstFails(Producer):
        def make(self, p, name_prefix, *, avoid=None):
            if not self.calls:
                self.calls.append({**p, "avoid": []})
                raise RuntimeError("tone rule: 'learn'")
            return super().make(p, name_prefix, avoid=avoid)

    producer = FirstFails()
    reports, memory, _ = week(tmp_path, days=3, producer=producer)
    failed = memory.by_status("failed")
    assert len(failed) == 1 and "learn" in failed[0].notes[0]
    asked = [(c["format"], c["persona"], c["angle"]) for c in producer.calls]
    assert len(asked) == len(set(asked))  # a failed idea is never asked again
    assert len(reports[0].new) == 2  # a backup filled the slot the same day
