"""Test-retest noise floor: identical runs have no noise, noisy viewers set a floor, real gaps clear it."""

import hashlib
import json
import math
import random
import re
from types import SimpleNamespace as NS

import pytest

from test_tournament import COMPETITORS, ad
from whynot.sim.feed import build_market_feeds
from whynot.sim.personas import Persona
from whynot.sim.scores import score_ads
from whynot.sim.viewer import Reaction, Viewer, ViewerCache, run_simulation
from whynot.validate.retest import compare, noise_floor, pick_agreement, retest

PERSONAS = [Persona(f"p{i}", "FR", "25-34", "female") for i in range(6)]


class NoisyViewer:
    """Prefers the highest Q + Gumbel noise; the noise depends on the draw (the full request), like a real model."""

    def __init__(self, noise: float = 1.0):
        self.noise = noise
        self.calls = 0

    def viewer_chat(self, messages, **kwargs):
        self.calls += 1
        rng = random.Random(hashlib.sha256((json.dumps(messages) + str(self.calls)).encode()).hexdigest())
        blocks = re.findall(r"\[(A\d+)\] Sponsored · .*?Text: Q=(-?[\d.]+)", messages[1]["content"], re.S)
        u = {lab: float(q) - self.noise * math.log(-math.log(rng.random())) for lab, q in blocks}
        best = max(u, key=lambda k: u[k])
        return NS(text=json.dumps({"reactions": [{"ad": lab, "stopped": True, "understood": True, "believed": True,
                                                  "why_not": "", "intent": "", "intent_score": 3} for lab in u],
                                   "preferred": best}), cost=NS(usd=0.001))


def feeds(qualities):
    items = [ad(f"v{i}", f"Q={q}") for i, q in enumerate(qualities)] + COMPETITORS
    return build_market_feeds(items, feed_size=4, appearances=6, seed=0)


def test_noise_floor_math():
    assert noise_floor({"a": 1.0, "b": 2.0}, {"a": 1.0, "b": 2.0}) == 0
    # diffs 1 and -1: sample SD sqrt(2), floor 1.96 * sqrt(2) * sqrt(2)
    assert noise_floor({"a": 1.0, "b": 0.0}, {"a": 0.0, "b": 1.0}) == pytest.approx(1.959964 * 2)
    with pytest.raises(ValueError):
        noise_floor({"a": 1.0}, {"a": 1.0, "b": 2.0})


def test_pick_agreement_matches_views():
    def r(feed, ad_id, preferred):
        return Reaction(feed, "p", ad_id, 0, False, True, True, "", "", 3, preferred)
    first = [r("F0", "a", True), r("F0", "b", False), r("F1", "a", True)]
    second = [r("F0", "a", False), r("F0", "b", True), r("F1", "a", True), r("F2", "a", True)]
    assert pick_agreement(first, second) == (0.5, 2)
    assert pick_agreement(first, []) == (None, 0)


def test_a_deterministic_simulator_has_no_noise():
    fs = feeds([1, 0, -1])
    run = run_simulation(Viewer(NoisyViewer(noise=0.0)), PERSONAS, fs, viewers_per_feed=2)
    result = compare(run.reactions, run.reactions)
    assert result.floor == 0 and result.pick_agreement == 1 and result.rank_agreement == 1
    assert result.is_real(0.01) and not result.is_real(0.0)


def test_retest_takes_a_fresh_draw_even_with_a_cache(tmp_path):
    client = NoisyViewer()
    viewer = Viewer(client, cache=ViewerCache(tmp_path / "cache"))
    fs = feeds([1, 0, -1])
    result = retest(viewer, PERSONAS, fs, viewers_per_feed=2)
    assert client.calls == 2 * len(fs) * 2  # the second run was not served from the cache
    assert result.usd == pytest.approx(client.calls * 0.001)
    assert result.views == len(fs) * 2 and result.simulated


def test_noise_sets_a_floor_that_real_gaps_clear_and_equal_ads_do_not():
    # 8 variants: v0-v3 equally strong, v4-v7 equally weak. Floor from a retest, gaps from a third run.
    ours = {f"v{i}" for i in range(8)}
    cleared = false_alarms = 0
    seeds = 60
    for seed in range(seeds):
        client = NoisyViewer()
        client.calls = seed * 10_000  # another stream of noise per seed
        fs = feeds([2.0] * 4 + [-2.0] * 4)
        result = retest(Viewer(client), PERSONAS, fs, viewers_per_feed=3, ads=ours)
        third = run_simulation(Viewer(client, draw=2), PERSONAS, fs, viewers_per_feed=3).reactions
        s = {k: v.preference_lift for k, v in score_ads(third).items()}
        cleared += result.is_real(s["v0"] - s["v7"])
        false_alarms += result.is_real(s["v0"] - s["v1"])
    assert cleared / seeds >= 0.8 and false_alarms / seeds <= 0.15, (cleared, false_alarms)
