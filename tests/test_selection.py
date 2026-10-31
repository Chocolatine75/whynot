"""The natural-selection demo: a structured simulated world, lineage, the random baseline, selection.json."""

import json
from datetime import date

from strategy_fixture import ADS, APP, COUNTRIES, strategy_json
from whynot.agency.ideas import format_scores, plan, plan_random
from whynot.agency.memory import AdRecord
from whynot.agency.selection import LABEL, run_selection
from whynot.agents.strategist import Sources
from whynot.agents.strategist import make_validator as strategy_validator
from whynot.run.autopilot import DailyMetrics
from whynot.run.insights import SimulatedWorld

STRATEGY = strategy_validator(Sources.build(APP, ADS), COUNTRIES)(strategy_json())


def test_the_world_has_hidden_structure_and_is_deterministic():
    w = SimulatedWorld(seed=4)
    w.register("a", ("pov", "p1", "x"))
    w.register("b", ("pov", "p1", "x"))
    d = date(2026, 11, 1)
    assert w.day("a", d, 0) == w.day("a", d, 0)
    # same idea, different ads: the same hidden effects, only each ad's luck differs
    ratio = w.quality("a") / w.quality("b")
    assert 0.5 < ratio < 2.0
    best = w.best(["pov", "rating"], [("p1", "x"), ("p2", "y")])
    score = lambda f, p, a: w.effect("format", f) + w.effect("persona", p) + w.effect("angle", a)  # noqa: E731
    assert score(*best) == max(score(f, p, a) for f in ("pov", "rating") for p, a in (("p1", "x"), ("p2", "y")))


def test_better_ads_get_more_views_per_euro_and_ads_tire():
    w = SimulatedWorld(seed=1)
    for i in range(40):
        w.register(f"ad{i}", (f"f{i}", "p", "a"))
    ranked = sorted((f"ad{i}" for i in range(40)), key=w.quality)
    d = date(2026, 11, 1)
    low, high = w.day(ranked[0], d, 0), w.day(ranked[-1], d, 0)
    assert high.impressions / high.spend_eur > low.impressions / low.spend_eur  # Meta delivers good ads cheaper
    fresh = sum(w.day(ranked[-1], d, 0).conversions for _ in range(1))
    tired = w.day(ranked[-1], d, 40).conversions
    assert tired <= fresh
    assert w.fetch(["unknown"], d, d) == {}  # an ad never launched has no results


def test_the_random_baseline_never_repeats_and_is_seeded():
    formats, pairs = ["pov", "rating", "x"], [("p", "a"), ("q", "b")]
    a = plan_random(4, formats=formats, pairs=pairs, tried=[("pov", "p", "a")], seed="d1")
    assert a == plan_random(4, formats=formats, pairs=pairs, tried=[("pov", "p", "a")], seed="d1")
    assert ("pov", "p", "a") not in [i.key for i in a] and len({i.key for i in a}) == 4
    assert all(i.why.startswith("random") and i.parent is None for i in a)


def ad(key, fmt, spend, conv, persona="p", angle="a"):
    r = AdRecord(key, "2026-11-01", fmt, persona, angle, key, status="live")
    r.metrics = [DailyMetrics("2026-11-02", spend, 1000, 10, conv)]
    return r


def test_exploit_builds_on_the_winner_with_the_format_that_sells_and_records_its_parent():
    ads = [ad("win", "pov", 30, 15), ad("good", "rating", 30, 12, persona="q", angle="b"),
           ad("bad", "x", 30, 1, persona="q", angle="b")]
    scores = format_scores(ads)
    assert scores["rating"] > scores["x"]
    idea = plan(1, formats=["pov", "rating", "x"], pairs=[("p", "a"), ("q", "b")],
                tried=[(a.format, a.persona, a.angle) for a in ads], ads=ads)[0]
    assert idea.parent == "win" and idea.format == "rating" and (idea.persona, idea.angle) == ("p", "a")


def test_selection_json_follows_the_contract_and_is_reproducible(tmp_path):
    out = run_selection(tmp_path, STRATEGY, days=8, seed=2, say=lambda s: None, app={"name": "X"})
    saved = json.loads((tmp_path / "agency-sim" / "selection.json").read_text())
    assert saved == out and out["simulated"] is True and out["label"] == LABEL
    assert set(out["policies"]) == {"whynot", "random"}
    for name, p in out["policies"].items():
        ids = {n["id"] for n in p["nodes"]}
        assert all(n["parent"] in ids for n in p["nodes"] if n["parent"])  # every edge points to a real node
        assert len(p["timeline"]) == 8 and {"views_per_eur", "conversions_per_100_eur"} <= set(p["timeline"][0])
        if name == "random":
            assert all(n["parent"] is None for n in p["nodes"])
    assert set(out["truth"]) == {"best_format", "best_persona", "best_angle"}
    again = run_selection(tmp_path, STRATEGY, days=8, seed=2, say=lambda s: None, app={"name": "X"})
    assert again == out  # the same seed gives the same campaign


def test_whynot_beats_random_in_most_worlds(tmp_path):
    """The claim the demo makes, measured: over 12 simulated worlds, the learning loop wins most of them."""
    wins = 0
    for seed in range(12):
        s = run_selection(tmp_path / str(seed), STRATEGY, days=21, seed=seed, say=lambda s: None)["summary"]
        wins += s["whynot_conversions_per_100_eur_last_week"] > s["random_conversions_per_100_eur_last_week"]
    assert wins >= 8
