"""Archetypes: market signals scored transparently, then a validated pick that fits the app."""

import json
from datetime import date, timedelta

import pytest

from fakes import ScriptedChat
from strategy_fixture import ADS, APP, COUNTRIES, strategy_json
from whynot.agents.archetypes import WEIGHTS, build, pick
from whynot.agents.ask import AgentError
from whynot.agents.deconstruct import Deconstruction
from whynot.agents.strategist import Sources
from whynot.agents.strategist import make_validator as strategy_validator
from whynot.ingest.adlibrary import CompetitorAd

STRATEGY = strategy_validator(Sources.build(APP, ADS), COUNTRIES)(strategy_json())
TODAY = date(2026, 10, 30)


def ad(i, page, *, days=100, stopped=False, reach=1000, body=None):
    start = TODAY - timedelta(days=days)
    return CompetitorAd(id=str(i), page_id=page, page_name=page, bodies=[body or f"copy {i}"], titles=[],
                        start_date=start, stop_date=TODAY - timedelta(days=1) if stopped else None, platforms=[],
                        eu_total_reach=reach, target_ages=[], target_gender=None)


def dec(i, pitch, style):
    return Deconstruction(str(i), "x", "static", f"hook {i}", "phone", [], None, pitch, style, "promise", "people")


def market():
    ads = [ad(1, "A", days=200), ad(2, "B", days=150), ad(3, "C", days=120),  # lasting, 3 advertisers
           ad(4, "A", days=5, stopped=True), ad(5, "A", days=8, stopped=True),  # stopped fast, 1 advertiser
           ad(6, "D", days=30), ad(7, "D", days=30, body="copy 6"), ad(8, "D", days=30, body="copy 6"),  # reused
           ad(9, "E", days=400)]  # alone in its group
    decons = {"1": dec(1, "transformation", "app_screen"), "2": dec(2, "transformation", "app_screen"),
              "3": dec(3, "transformation", "app_screen"), "4": dec(4, "humor", "illustration"),
              "5": dec(5, "humor", "illustration"), "6": dec(6, "offer", "text_card"),
              "7": dec(7, "offer", "text_card"), "8": dec(8, "offer", "text_card"),
              "9": dec(9, "curiosity", "mixed")}
    return ads, decons


def test_archetypes_are_scored_on_visible_market_signals():
    ads, decons = market()
    arch = build(decons, ads, as_of=TODAY)
    assert arch[0].key == "transformation:app_screen"  # lasting, broad
    assert "curiosity:mixed" not in [a.key for a in arch]  # a single ad is not a pattern
    by = {a.key: a for a in arch}
    assert by["humor:illustration"].signals["staying"] == 0  # every ad was stopped
    assert by["offer:text_card"].components["reuse"] == 1.0  # the same copy run three times
    assert by["transformation:app_screen"].signals["breadth"] == 3
    for a in arch:
        assert a.score == pytest.approx(sum(WEIGHTS[s] * a.components[s] for s in WEIGHTS), abs=1e-3)
    assert by["transformation:app_screen"].examples[0]["ad_id"] == "1"  # longest-running first


def _answer(picks):
    return json.dumps({"picks": picks})


P = {"archetype": "transformation:app_screen", "persona": "heritage_learner", "angle": "southern_accent",
     "audience_fit": 8, "message_fit": 7, "production_fit": 9, "why": "Shows the real app."}


def test_pick_repairs_bad_answers_and_returns_valid_pairs():
    ads, decons = market()
    arch = build(decons, ads, as_of=TODAY)
    bad_angle = {**P, "archetype": "humor:illustration", "angle": "five_minutes"}  # angle of another persona
    good = [P, {**P, "archetype": "humor:illustration", "angle": "listen_first"},
            {**P, "archetype": "offer:text_card", "persona": "busy_traveller", "angle": "free_start"}]
    model = ScriptedChat([_answer([P, bad_angle, good[2]]), _answer(good)])
    answer = pick(model, arch, STRATEGY, app_name=APP.name, description=APP.description)
    assert [p.archetype for p in answer.value] == [g["archetype"] for g in good]
    assert answer.attempts == 2 and "five_minutes" in answer.errors[0]
    assert answer.value[0].fit == pytest.approx(24 / 30)


@pytest.mark.parametrize("picks, error", [
    ([P, P, {**P, "archetype": "offer:text_card"}], "different archetype"),
    ([P, {**P, "archetype": "made:up"}, {**P, "archetype": "offer:text_card"}], "not one of"),
    ([P, {**P, "archetype": "humor:illustration", "production_fit": 11},
      {**P, "archetype": "offer:text_card"}], "production_fit"),
    ([P], "exactly 3"),
])
def test_pick_refuses_invalid_answers(picks, error):
    ads, decons = market()
    model = ScriptedChat(lambda m, mod: _answer(picks))
    with pytest.raises(AgentError, match=error):
        pick(model, build(decons, ads, as_of=TODAY), STRATEGY, app_name=APP.name, description=APP.description)


def test_pick_needs_enough_archetypes():
    ads, decons = market()
    with pytest.raises(ValueError, match="at least 4"):
        pick(ScriptedChat([]), build(decons, ads, as_of=TODAY), STRATEGY, app_name="x", description="y", n=4)
