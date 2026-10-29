"""Bias suite: planted biases are caught (>= 90 %), a fair simulator stays quiet (<= 5 % false alarms)."""

import json
import math
import random
import re
from types import SimpleNamespace as NS

import pytest

from whynot.sim.feed import FeedItem
from whynot.sim.personas import Persona
from whynot.sim.viewer import Reaction, Viewer
from whynot.validate.bias import (
    CONTROL,
    EMOJIS,
    FILLER_SENTENCE,
    LEAK,
    TREATED,
    Check,
    estimated_calls,
    position_effect,
    run_suite,
    standard_checks,
    translated,
    twin_effect,
    twin_feeds,
)

BRAND = "LinguaApp"
ITEMS = [FeedItem(f"ad{i}", f"Rival {i}", "Q=1", f"Speak with your family, lesson {i}.") for i in range(12)]
FILLERS = [FeedItem(f"f{i}", f"Filler {i}", "Q=-1", f"Something else entirely {i}.") for i in range(10)]
PERSONAS = [Persona(f"p{i}", "FR", "25-34", "female") for i in range(4)]

BIASES = {  # what a biased simulator rewards, read from one ad block of the prompt
    "brand_name": lambda adv, body: adv == BRAND,
    "copy_length": lambda adv, body: FILLER_SENTENCE.strip() in body,
    "emoji": lambda adv, body: EMOJIS.strip() in body,
    "label_leak": lambda adv, body: LEAK.strip() in body,
}


class Simulated:
    """Prefers the highest Q + Gumbel noise; `bias` adds a bonus for one attribute, or for the first slot."""

    def __init__(self, seed: int, bias: str | None = None, bonus: float = 1.0):
        self.seed, self.bias, self.bonus = seed, bias, bonus

    def viewer_chat(self, messages, **kwargs):
        rng = random.Random(f"{self.seed}|{json.dumps(messages)}")
        blocks = re.findall(r"\[(A\d+)\] Sponsored · (.*?)\nTitle: Q=(-?[\d.]+)\nText: (.*?)(?:\n\n|$)",
                            messages[1]["content"], re.S)
        u = {}
        for lab, adv, q, body in blocks:
            bonus = self.bonus if (self.bias == "position" and lab == "A1") or (
                self.bias in BIASES and BIASES[self.bias](adv, body)) else 0.0
            u[lab] = float(q) + bonus - math.log(-math.log(rng.random()))
        best = max(u, key=lambda k: u[k])
        return NS(text=json.dumps({"reactions": [{"ad": lab, "stopped": True, "understood": True, "believed": True,
                                                  "why_not": "", "intent": "", "intent_score": 3} for lab in u],
                                   "preferred": best}), cost=NS(usd=0.001))


def suite(client):
    return run_suite(Viewer(client), PERSONAS, ITEMS, FILLERS, standard_checks(BRAND))  # default size


SEEDS = range(20)


@pytest.mark.parametrize("bias", [*BIASES, "position"])
def test_a_planted_bias_is_caught(bias):
    caught = sum(bias in suite(Simulated(seed, bias)).flagged for seed in SEEDS)
    assert caught / len(SEEDS) >= 0.9, caught


def test_a_fair_simulator_is_rarely_flagged():
    checks = [c for seed in SEEDS for c in suite(Simulated(seed)).checks]
    assert len(checks) == len(SEEDS) * 5
    assert sum(c.flagged for c in checks) / len(checks) <= 0.05


def test_a_planted_bias_does_not_spill_into_other_checks():
    result = suite(Simulated(0, "emoji"))
    assert result.flagged == ["emoji"]
    assert result.usd == pytest.approx(estimated_calls(12, 4, feeds_per_item=3, viewers_per_feed=2) * 0.001)


# --- pieces ----------------------------------------------------------------------------------

def test_twins_differ_in_one_attribute_and_share_every_feed():
    feeds = twin_feeds(ITEMS[:2], FILLERS, standard_checks(BRAND)[0].treatment, feed_size=4, feeds_per_item=3)
    assert len(feeds) == 6
    for f in feeds:
        control, treated = f[0], f[1]
        assert control.ad_id.endswith(CONTROL) and treated.ad_id.endswith(TREATED)
        assert (control.body, control.title) == (treated.body, treated.title)
        assert control.advertiser != treated.advertiser == BRAND
        assert len({x.ad_id for x in f}) == 4


def test_twin_feed_errors():
    with pytest.raises(ValueError, match="feed_size"):
        twin_feeds(ITEMS, FILLERS, translated({}), feed_size=2, feeds_per_item=1)
    with pytest.raises(ValueError, match="filler"):
        twin_feeds(ITEMS, FILLERS[:1], translated({}), feed_size=4, feeds_per_item=1)


def test_translated_twin():
    treated = translated({"ad0": "Parlez avec votre famille."})(ITEMS[0])
    assert treated.body == "Parlez avec votre famille." and treated.advertiser == ITEMS[0].advertiser
    check = Check("language", translated({}))
    assert check.threshold == 0.10


def r(feed, ad_id, preferred, position=1, persona="p"):
    return Reaction(feed, persona, ad_id, position, False, True, True, "", "", 3, preferred)


def test_effect_and_flag_rules():
    rs = [r(f"F{i}", "x" + TREATED, True) for i in range(30)] + [r(f"G{i}", "x" + CONTROL, True) for i in range(10)]
    result = twin_effect("t", rs, threshold=0.1, alpha=0.05)
    assert result.effect == pytest.approx(0.25) and result.flagged and result.twin_picks == 40
    small = twin_effect("t", rs[:3] + rs[-1:], threshold=0.1, alpha=0.05)  # 3 vs 1: large but could be luck
    assert small.effect == pytest.approx(0.25) and not small.flagged
    nothing = twin_effect("t", [r("F0", "filler", True)], threshold=0.1, alpha=0.05)
    assert nothing.twin_picks == 0 and not nothing.flagged


def test_position_ignores_feeds_of_another_size():
    four = [r("F0", f"a{i}", i == 0, position=i) for i in range(4)]
    three = [r("F1", f"b{i}", i == 0, position=i) for i in range(3)]
    result = position_effect(four + three, 4)
    assert result.twin_picks == 1 and result.effect == pytest.approx(0.75)
    assert position_effect([], 4).twin_picks == 0
