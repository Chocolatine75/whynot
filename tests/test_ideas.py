"""The idea planner: exploit what sells with a new format, explore far away, never repeat."""

from hypothesis import given, settings
from hypothesis import strategies as st

from whynot.agency.ideas import distance, overlap, plan, too_similar, winners
from whynot.agency.memory import AdRecord
from whynot.run.autopilot import DailyMetrics

FORMATS = ["pov", "rating", "this_or_that", "wait_for_it", "starter_pack"]
PAIRS = [("heritage", "southern_accent"), ("heritage", "listen_first"), ("traveller", "coffee_order"),
         ("traveller", "five_minutes")]


def ad(key, fmt, persona, angle, spend=0.0, conv=0, hook="", voice=""):
    r = AdRecord(key, "2026-11-01", fmt, persona, angle, hook or key, voice=voice, status="live")
    if spend:
        r.metrics = [DailyMetrics("2026-11-02", spend, 1000, 10, conv)]
    return r


def test_distance():
    assert distance(("pov", "p", "a"), ("pov", "p", "a")) == 0
    assert distance(("pov", "p", "a"), ("rating", "q", "b")) == 1.0
    assert distance(("pov", "p", "a"), ("rating", "p", "a")) > distance(("pov", "p", "a"), ("pov", "q", "a"))


def test_winners_are_judged_ads_by_cost_per_conversion():
    ads = [ad("a", "pov", *PAIRS[0], spend=20, conv=4), ad("b", "pov", *PAIRS[1], spend=20, conv=1),
           ad("c", "pov", *PAIRS[2], spend=20, conv=0), ad("d", "pov", *PAIRS[3], spend=3, conv=3)]
    assert [w.key for w in winners(ads)] == ["a", "b"]  # no conversion and too little spend are not winners


def test_exploit_keeps_the_winning_message_in_a_new_format():
    ads = [ad("w", "pov", "heritage", "southern_accent", spend=30, conv=10),
           ad("l", "rating", "traveller", "coffee_order", spend=30, conv=0)]
    ideas = plan(3, formats=FORMATS, pairs=PAIRS, tried=[(a.format, a.persona, a.angle) for a in ads], ads=ads)
    first = ideas[0]
    assert first.why.startswith("exploit") and (first.persona, first.angle) == ("heritage", "southern_accent")
    assert first.format != "pov"
    assert all(i.why.startswith("explore") for i in ideas[1:])


def test_explore_goes_far_first():
    tried = [("pov", "heritage", "southern_accent")]
    first = plan(1, formats=FORMATS, pairs=PAIRS, tried=tried)[0]
    assert distance(first.key, tried[0]) == 1.0  # another format, persona and angle


@settings(max_examples=80, deadline=None)
@given(st.lists(st.tuples(st.sampled_from(FORMATS), st.sampled_from(PAIRS), st.integers(0, 40), st.integers(0, 8)),
                max_size=25), st.integers(1, 6))
def test_never_repeat_an_idea_and_never_twice_the_same_day(history, n):
    ads = [ad(f"k{i}", f, p, a, spend=s, conv=c) for i, (f, (p, a), s, c) in enumerate(history)]
    tried = [(a.format, a.persona, a.angle) for a in ads]
    ideas = plan(n, formats=FORMATS, pairs=PAIRS, tried=tried, ads=ads)
    keys = [i.key for i in ideas]
    assert len(keys) == len(set(keys))  # all different today
    assert not set(keys) & set(tried)  # nothing already made
    free = len({(f, p, a) for f in FORMATS for p, a in PAIRS} - set(tried))
    assert len(ideas) == min(n, free)  # as many as asked, unless the space is exhausted


def test_no_idea_when_none_is_asked_or_all_were_tried():
    assert plan(0, formats=FORMATS, pairs=PAIRS, tried=[]) == []
    everything = [(f, p, a) for f in FORMATS for p, a in PAIRS]
    assert plan(3, formats=FORMATS, pairs=PAIRS, tried=everything) == []


def test_new_words_must_differ_from_past_ads():
    past = [ad("a", "pov", *PAIRS[0], hook="pov his mom only speaks vietnamese",
               voice="so i'm meeting his mom and i lowkey wanna cry")]
    assert too_similar("pov: his mom only speaks vietnamese fr", "", past).key == "a"
    assert too_similar("rating every way to order coffee", "bro i was cooked", past) is None
    assert too_similar("totally new hook", "so i'm meeting his mom and i lowkey wanna cry again", past).key == "a"
    assert overlap("", "x") == 0.0


def test_one_free_slot_still_builds_on_a_winner():
    """Regression: with one slot a day, 34 % rounded down to 0 and the winner was never built on."""
    ads = [ad("w", "pov", "heritage", "southern_accent", spend=30, conv=10)]
    idea = plan(1, formats=FORMATS, pairs=PAIRS, tried=[("pov", "heritage", "southern_accent")], ads=ads)[0]
    assert idea.why.startswith("exploit")
    assert plan(1, formats=FORMATS, pairs=PAIRS, tried=[], ads=ads, exploit_share=0)[0].why.startswith("explore")
