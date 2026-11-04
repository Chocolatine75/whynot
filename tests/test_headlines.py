"""E5-1: headline rules, tested on weak headlines from our runs and on headlines of ads that lasted on Meta."""

import json
from pathlib import Path

import pytest

from whynot.create.headlines import MAX_WORDS, has_action, problems

DATA = json.loads((Path(__file__).parent / "data" / "headlines.json").read_text())


def test_every_weak_headline_from_our_runs_is_refused():
    passed = [h for h in DATA["bad"] if not problems(h)]
    assert len(DATA["bad"]) == 30 and not passed, passed


def test_headlines_of_ads_that_lasted_pass_at_least_90_percent():
    failed = [h for h in DATA["good"] if problems(h)]
    assert len(DATA["good"]) == 30 and len(failed) <= 3, failed  # ≥ 90 %


@pytest.mark.parametrize("text, reason", [
    ("Less memorizing, more lived moments", "Less X, more Y"), ("From first moves to full matches", "From X to Y"),
    ("A seamless language journey", "filler"), ("Quiet reps between busy days", "no action"),
    ("Speak useful phrases out loud at your own pace", f"max {MAX_WORDS}"),
])
def test_each_rule_says_what_is_wrong(text, reason):
    assert any(reason in p for p in problems(text))


def test_an_action_is_a_verb_a_question_or_a_number():
    assert has_action("Order coffee by ear") and has_action("Busy day?") and has_action("4.8 stars, 300 ratings")
    assert not has_action("A Saigon counter, one real request")
    assert problems("Nur zehn Minuten am Tag", language="de") == []  # other languages: the length rule only
