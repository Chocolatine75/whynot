"""Campaign plan: budgets never exceed the cap, Meta rules hold, the launch goes through the autopilot."""

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from whynot.run.autopilot import Level, Outcome, Policy
from whynot.run.campaign import (
    MIN_ADSET_DAILY_EUR,
    AdChoice,
    Audience,
    build_plan,
    launch_decisions,
    select_ads,
    to_api,
    validate,
)

STORE = "https://apps.apple.com/us/app/x/id1"
AUDIENCES = [Audience("heritage", "Heritage learner", ("FR", "GB"), 18, 34, "all"),
             Audience("traveller", "Busy traveller", ("GB",), 25, 54, "female")]


def ad(i, persona="heritage", template="t1", score=1.0, ok=True):
    return AdChoice(f"{template}-{i}", template, persona, f"ads/{template}-{i}.png", "Hook", "Body text", "Title",
                    "INSTALL_MOBILE_APP", ok, score)


CANDIDATES = ([ad(i, "heritage", f"t{i % 3}", score=2.0 - i / 10) for i in range(6)]
              + [ad(i, "traveller", f"u{i % 2}", score=1.0 + i / 10) for i in range(4)])


def test_select_ads_best_first_with_template_diversity_and_guards():
    chosen = select_ads([*CANDIDATES, ad(99, "heritage", "t0", score=9.0, ok=False)], "heritage", k=4)
    assert [c.variant_id for c in chosen] == ["t0-0", "t1-1", "t2-2", "t0-3"]
    assert all(c.guards_passed for c in chosen)
    many = [ad(i, "heritage", "same", score=i) for i in range(5)]
    assert len(select_ads(many, "heritage", k=4)) == 2  # ≤ 2 variants per template


def test_plan_splits_the_cap_and_validates():
    plan = build_plan("App", STORE, AUDIENCES, CANDIDATES, daily_cap_eur=20)
    assert validate(plan) == []
    assert [s.daily_budget_eur for s in plan.ad_sets] == [10.0, 10.0] and plan.daily_total_eur == 20.0
    assert {s.audience.persona for s in plan.ad_sets} == {"heritage", "traveller"}


def test_small_cap_funds_fewer_ad_sets_and_says_so():
    plan = build_plan("App", STORE, AUDIENCES, CANDIDATES, daily_cap_eur=7)
    assert len(plan.ad_sets) == 1 and plan.ad_sets[0].daily_budget_eur == 7.0
    assert any("dropped" in n for n in plan.notes)
    with pytest.raises(ValueError, match="minimum"):
        build_plan("App", STORE, AUDIENCES, CANDIDATES, daily_cap_eur=4.99)


def test_personas_without_enough_publishable_ads_get_no_ad_set():
    plan = build_plan("App", STORE, AUDIENCES, [*CANDIDATES[:6], ad(1, "traveller", ok=False)], daily_cap_eur=20)
    assert [s.audience.persona for s in plan.ad_sets] == ["heritage"]
    assert any("traveller" in n for n in plan.notes)
    with pytest.raises(ValueError, match="nothing to launch"):
        build_plan("App", STORE, AUDIENCES, [ad(1)], daily_cap_eur=20)


@given(st.floats(MIN_ADSET_DAILY_EUR, 10_000, allow_nan=False), st.integers(1, 2))
def test_plan_total_never_exceeds_the_cap(cap, n):
    plan = build_plan("App", STORE, AUDIENCES[:n], CANDIDATES, daily_cap_eur=cap)
    assert plan.daily_total_eur <= cap and validate(plan) == []


def test_validate_catches_every_broken_rule():
    plan = build_plan("App", STORE, AUDIENCES, CANDIDATES, daily_cap_eur=20)
    s0, s1 = plan.ad_sets
    s0.daily_budget_eur = 15  # total 25 > cap
    s1.audience = Audience("traveller", "x", ("gb",), 17, 54, "women")
    s1.ads = [*s1.ads[:1], ad(7, "heritage", "u0", ok=False)]
    s0.ads = [*s0.ads, s0.ads[0]]
    plan.store_url = "https://play.google.com/x"
    errors = " | ".join(validate(plan))
    for expected in ["exceeds the cap", "App Store link", "outside 18-65", "ISO codes", "gender 'women'",
                     "did not pass its guards", "made for persona", "appears in two ad sets"]:
        assert expected in errors, expected


def test_api_payload_shape():
    plan = build_plan("App", STORE, AUDIENCES, CANDIDATES, daily_cap_eur=20)
    api = to_api(plan)
    assert api["campaign"]["objective"] == "OUTCOME_APP_PROMOTION"
    statuses = [api["campaign"]["status"]] + [x["status"] for x in api["ad_sets"] + api["ads"]]
    assert set(statuses) == {"PAUSED"}
    s = api["ad_sets"][1]
    assert s["daily_budget"] == 1000 and s["optimization_goal"] == "APP_INSTALLS"
    assert s["targeting"]["genders"] == [2] and s["targeting"]["user_os"] == ["iOS"]
    assert s["targeting"]["targeting_automation"] == {"advantage_audience": 0}  # required explicitly since v26
    assert "genders" not in api["ad_sets"][0]["targeting"]
    assert s["promoted_object"]["object_store_url"] == STORE
    link = api["creatives"][0]["object_story_spec"]["link_data"]
    assert link["call_to_action"]["type"] == "INSTALL_MOBILE_APP" and link["link"] == STORE
    assert len(api["ads"]) == len(api["creatives"]) == sum(len(x.ads) for x in plan.ad_sets)
    json.dumps(api)  # serialisable


def test_launch_goes_through_the_autopilot():
    plan = build_plan("App", STORE, AUDIENCES, CANDIDATES, daily_cap_eur=20)
    dry = launch_decisions(plan, Policy())  # default: dry run, cap 0
    assert {d.outcome for _, d in dry} == {Outcome.REFUSED}  # owner set no live budget
    simulated = launch_decisions(plan, Policy(Level.DRY_RUN, 20))
    assert {d.outcome for _, d in simulated} == {Outcome.SIMULATED}
    first = launch_decisions(plan, Policy(Level.AUTOPILOT, 20, first_live_approved=False))
    assert {d.outcome for _, d in first} == {Outcome.NEEDS_APPROVAL}
    approved = launch_decisions(plan, Policy(Level.AUTOPILOT, 20), approved_by="owner")
    assert {d.outcome for _, d in approved} == {Outcome.EXECUTE}
    tight = launch_decisions(plan, Policy(Level.AUTOPILOT, 15, first_live_approved=True))
    assert [d.outcome for _, d in tight] == [Outcome.EXECUTE, Outcome.REFUSED]  # second set would pass the cap


def test_ad_set_names_never_carry_persona_labels():
    sensitive = [Audience("adhd", "Overwhelmed ADHD adults", ("US",), 18, 34, "all")]
    plan = build_plan("App", STORE, sensitive, [ad(i, "adhd", f"t{i}") for i in range(3)], daily_cap_eur=10)
    api = json.dumps(to_api(plan))
    assert "ADHD" not in api and plan.ad_sets[0].name == "Profile 1 · US · 18-34"
