"""Strategist validation: hallucinated evidence, invented ids and out-of-scope targeting are rejected."""

import copy
import json

import pytest

from fakes import ScriptedChat
from strategy_fixture import ADS, APP, COUNTRIES, strategy_json
from whynot.agents.ask import AgentError, Invalid
from whynot.agents.strategist import Sources, Strategy, build_prompt, make_validator, normalise, plan_strategy

VALIDATE = make_validator(Sources.build(APP, ADS), COUNTRIES)


def mutated(path, value):
    d = copy.deepcopy(strategy_json())
    target = d
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return d


def test_valid_strategy_and_json_roundtrip():
    s = VALIDATE(strategy_json())
    assert [p.id for p in s.personas] == ["heritage_learner", "busy_traveller"]
    assert s.objection("too_expensive").evidence[0].ref == "review:101"
    assert Strategy.from_json(json.loads(json.dumps(s.to_json()))) == s


@pytest.mark.parametrize("path, value, msg", [
    # hallucinations
    (["objections", 0, "evidence", 0, "quote"], "The app is perfect for everyone", "not verbatim"),
    (["objections", 0, "evidence", 0, "ref"], "review:999", "does not exist"),
    (["angles", 0, "evidence", 0, "ref"], "storefront", "must be one of"),
    (["claims", 0, "evidence"], {"ref": "ad:900", "quote": "Speak Vietnamese in 10 minutes a day"}, "must be one of"),
    (["claims", 1, "evidence", "quote"], "Free"[:3], "too short"),
    # references between parts
    (["personas", 0, "objections"], ["made_up"], "unknown objection"),
    (["angles", 0, "persona"], "ghost", "is not one of"),
    (["angles", 1, "objection"], "ghost", "is not one of"),
    # targeting
    (["personas", 0, "countries"], ["US"], "not targeted"),
    (["personas", 0, "age_min"], 16, "ages must be"),
    (["personas", 0, "age_max"], 17, "ages must be"),
    (["personas", 0, "gender"], "women", "gender"),
    # shape
    (["personas", 1, "id"], "heritage_learner", "duplicate id"),
    (["angles", 0, "id"], "Bad Id", "snake_case"),
    (["angles", 0, "competitors_use_it"], "no", "true or false"),
    (["objections"], [], "3 to 8"),
])
def test_invalid_strategies_are_rejected_with_a_precise_message(path, value, msg):
    with pytest.raises(Invalid, match=msg):
        VALIDATE(mutated(path, value))


def test_every_persona_needs_an_angle():
    d = strategy_json()
    for a in d["angles"]:
        a["persona"] = "heritage_learner"
    with pytest.raises(Invalid, match="busy_traveller"):
        VALIDATE(d)


def test_quotes_match_despite_typography():
    assert normalise("doesn’t   hear\nyou") == normalise("doesn't hear you")
    d = mutated(["objections", 0, "evidence", 0, "quote"], "The app doesn’t  hear you correctly")
    assert VALIDATE(d).objections[0].evidence[0].quote.startswith("The app")


def test_prompt_lists_sources_with_refs_negatives_first():
    prompt = build_prompt(APP, ADS, COUNTRIES)
    assert prompt.index("[review:101]") < prompt.index("[review:102]")  # 2★ before 5★
    assert "[ad:900] Rival Lingo (running since 2026-05-01, still active)" in prompt
    assert "stopped 2026-09-04" in prompt and "Campaign countries: FR, GB" in prompt


def test_plan_strategy_repairs_a_hallucinated_quote():
    bad = mutated(["claims", 0, "evidence", "quote"], "Twelve accents and offline mode")
    chat = ScriptedChat([json.dumps(bad), json.dumps(strategy_json())])
    answer = plan_strategy(chat, APP, ADS, COUNTRIES)
    assert answer.attempts == 2 and chat.calls[0]["model"] == "muse-wonder-1.0"
    assert "not verbatim in store" in chat.calls[1]["messages"][-1]["content"]


def test_plan_strategy_gives_up_rather_than_accepting_invented_facts():
    bad = mutated(["claims", 0, "evidence", "quote"], "Rated number one by teachers")
    chat = ScriptedChat([json.dumps(bad)] * 4)  # first try + 3 repairs
    with pytest.raises(AgentError):
        plan_strategy(chat, APP, ADS, COUNTRIES)
