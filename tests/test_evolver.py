"""Evolver: one-element mutations that answer objections, checked like any ad copy."""

import json

import pytest

from director_fixture import director_json
from fakes import ScriptedChat
from strategy_fixture import ADS, APP, COUNTRIES, strategy_json
from whynot.agents import evolver
from whynot.agents.ask import AgentError, Invalid
from whynot.agents.director import Context
from whynot.agents.director import make_validator as director_validator
from whynot.agents.strategist import Sources
from whynot.agents.strategist import make_validator as strategy_validator
from whynot.create.templates import Variant

STRATEGY = strategy_validator(Sources.build(APP, ADS), COUNTRIES)(strategy_json())
CTX = Context(STRATEGY, APP.name, APP.description, ("Rival Lingo",), ("#F5FAFF", "#0B1D33", "#1E6FD9"), "s.png")
TEMPLATE = director_validator(CTX, [a.id for a in STRATEGY.angles])(director_json())[1]  # listen_first
GENOME = next(TEMPLATE.genomes())
PARENT = evolver.Parent("v1", TEMPLATE, GENOME, -0.4, 2.1, ("I don't see the price", "Not for me"))


def mutations(*items):
    return {"mutations": [{"gene": g, "text": t, "why": "answers the price objection"} for g, t in items]}


def test_valid_mutations():
    out = evolver.make_validator(CTX, PARENT, 2)(mutations(("hook", "Free to start, train your ear first"),
                                                           ("proof", "Free to start")))
    assert [(m.gene, m.text) for m in out] == [("hook", "Free to start, train your ear first"),
                                               ("proof", "Free to start")]


@pytest.mark.parametrize("data, msg", [
    (mutations(("format", "reel")), "gene must be one of"),
    (mutations(("cta", "Buy")), "gene must be one of"),
    (mutations(("hook", "Train your ear first")), "already exists"),  # an existing option
    (mutations(("hook", "New one here"), ("hook", "new  one HERE")), "already exists"),  # duplicates
    (mutations(("hook", "Join 2 million learners")), "not in any verified claim"),
    (mutations(("hook", "Better than Rival Lingo")), "competitor"),
    (mutations(("hook", "Are you lonely abroad?")), "personal attribute"),
    (mutations(("proof", "★ Loved by families")), "pictograms"),
    (mutations(("title", "x" * 41)), "max 40"),
    ({"mutations": [{"gene": "hook", "text": "Fine text", "why": ""}]}, "why"),
    (mutations(("hook", "a"), ("hook", "b"), ("hook", "c")), "1 to 2"),
])
def test_bad_mutations_are_refused(data, msg):
    with pytest.raises(Invalid, match=msg):
        evolver.make_validator(CTX, PARENT, 2)(data)


def test_apply_adds_an_option_and_changes_exactly_one_gene():
    m = evolver.Mutation("hook", "Free to start, train your ear first", "price")
    child_t, child_g = evolver.apply(TEMPLATE, GENOME, m, tag="g1_ab_0")
    changed = [k for k in GENOME if GENOME[k] != child_g[k]]
    assert changed == ["hook"] and child_t.text("hook", child_g["hook"]) == m.text
    assert len(child_t.genes["hook"]) == len(TEMPLATE.genes["hook"]) + 1
    assert Variant(child_t.id, child_g).id != Variant(TEMPLATE.id, GENOME).id
    with pytest.raises(ValueError, match="already exists"):
        evolver.apply(child_t, GENOME, m, tag="g1_ab_0")


def test_prompt_carries_the_objections_and_only_verified_claims():
    p = evolver.build_prompt(CTX, PARENT, 2)
    assert "“I don't see the price”" in p and "- Choose a Northern or Southern accent" in p
    assert "exactly ONE element" in p and "SIMULATED" in p


def test_propose_repairs_then_gives_up_on_invented_facts():
    good = json.dumps(mutations(("hook", "Free to start, train your ear first")))
    bad = json.dumps(mutations(("hook", "Rated 4.9 by 1 million users")))
    chat = ScriptedChat([bad, good])
    assert evolver.propose(chat, CTX, PARENT).attempts == 2
    with pytest.raises(AgentError):
        evolver.propose(ScriptedChat([bad] * 3), CTX, PARENT)
