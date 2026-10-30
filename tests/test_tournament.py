"""Tournament: round-robin feeds, head-to-head games, Bradley-Terry ranking that recovers a known order."""

import hashlib
import json
import math
import random
import re
from itertools import combinations
from types import SimpleNamespace as NS

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from test_viewer import PERSONAS
from whynot.sim.feed import FeedItem
from whynot.sim.personas import Persona
from whynot.sim.tournament import head_to_head, rank, round_robin_feeds
from whynot.sim.viewer import Reaction, Viewer, run_simulation
from whynot.validate.stats import bradley_terry, kendall_tau

# --- statistics ---------------------------------------------------------------


def test_kendall_tau_known_values():
    assert kendall_tau([1, 2, 3, 4], [10, 20, 30, 40]) == 1
    assert kendall_tau([1, 2, 3, 4], [4, 3, 2, 1]) == -1
    assert kendall_tau([1, 2, 3], [1, 1, 2]) == pytest.approx(0.8165, abs=1e-4)  # tau-b, as scipy computes it
    with pytest.raises(ValueError):
        kendall_tau([1, 1], [1, 2])
    with pytest.raises(ValueError):
        kendall_tau([1], [1, 2])


def sample_games(true: dict[str, float], per_pair: int, rng: random.Random):
    games = []
    for a, b in combinations(sorted(true), 2):
        p = 1 / (1 + math.exp(true[b] - true[a]))
        games += [(a, b, 1.0 if rng.random() < p else 0.0) for _ in range(per_pair)]
    return games


@pytest.mark.parametrize("seed", range(20))
def test_bradley_terry_recovers_a_known_ranking(seed):
    true = {f"v{i}": s for i, s in enumerate([-1.5, -0.75, 0.0, 0.75, 1.5, 2.25])}
    fit = bradley_terry(sample_games(true, 12, random.Random(seed)))
    assert kendall_tau([true[k] for k in true], [fit[k] for k in true]) >= 0.8
    assert sum(fit.values()) == pytest.approx(0, abs=1e-9)


def test_an_unbeaten_variant_stays_finite_and_the_prior_shrinks_small_samples():
    lucky = bradley_terry([("a", "b", 1.0), ("a", "b", 1.0)])
    steady = bradley_terry([("a", "b", 1.0)] * 40)
    assert math.isfinite(lucky["a"]) and 0 < lucky["a"] < steady["a"]


def test_bradley_terry_refuses_bad_input():
    for bad in ([("a", "a", 1.0)], [("a", "b", 1.5)]):
        with pytest.raises(ValueError):
            bradley_terry(bad)
    with pytest.raises(ValueError):
        bradley_terry([])
    with pytest.raises(ValueError):
        bradley_terry([("a", "b", 1.0)], prior=0)


outcomes = st.lists(st.tuples(st.sampled_from("abcd"), st.sampled_from("abcd"), st.sampled_from([0.0, 0.5, 1.0]))
                    .filter(lambda g: g[0] != g[1]), min_size=1, max_size=40)


@settings(max_examples=150, deadline=None)
@given(outcomes)
def test_bradley_terry_ignores_order_and_orientation(games):
    fit = bradley_terry(games)
    flipped = bradley_terry([(b, a, 1 - s) for a, b, s in reversed(games)])
    assert all(fit[k] == pytest.approx(flipped[k], abs=1e-6) for k in fit)


# --- feeds and games ------------------------------------------------------------

def ad(i, body="", advertiser="Ours"):
    return FeedItem(i, advertiser, "", body)


COMPETITORS = [ad(f"c{i}", "Q=0", f"Rival {i}") for i in range(8)]


def test_every_pair_meets_in_rounds_feeds_without_duplicates():
    ours = [ad(f"v{i}") for i in range(5)]
    feeds = round_robin_feeds(ours, COMPETITORS, feed_size=4, rounds=2, seed=3)
    assert len(feeds) == 10 * 2
    meetings = {}
    for f in feeds:
        ids = [x.ad_id for x in f]
        assert len(f) == 4 and len(set(ids)) == 4
        pair = tuple(sorted(i for i in ids if i.startswith("v")))
        meetings[pair] = meetings.get(pair, 0) + 1
    assert set(meetings.values()) == {2} and len(meetings) == 10
    assert feeds == round_robin_feeds(ours, COMPETITORS, feed_size=4, rounds=2, seed=3)  # deterministic


def test_feed_errors_say_what_is_wrong():
    ours = [ad("v0"), ad("v1")]
    with pytest.raises(ValueError, match="feed_size"):
        round_robin_feeds(ours, COMPETITORS, feed_size=2)
    with pytest.raises(ValueError, match="rounds"):
        round_robin_feeds(ours, COMPETITORS, feed_size=4, rounds=0)
    with pytest.raises(ValueError, match="unique"):
        round_robin_feeds([ad("v0"), ad("v0")], COMPETITORS, feed_size=4)
    with pytest.raises(ValueError, match="competitor"):
        round_robin_feeds(ours, COMPETITORS[:1], feed_size=4)


def reaction(feed, persona, ad_id, preferred=False, intent=3):
    return Reaction(feed, persona, ad_id, 0, False, True, True, "", "", intent, preferred)


def test_head_to_head_rules():
    rs = [reaction("F0", "p", "a", preferred=True), reaction("F0", "p", "b"), reaction("F0", "p", "c0"),
          reaction("F1", "p", "a", intent=2), reaction("F1", "p", "b", intent=4), reaction("F1", "p", "c", True),
          reaction("F2", "p", "a"), reaction("F2", "p", "b")]
    games = head_to_head(rs, {"a", "b"})
    assert games == [[("a", "b", 1.0)], [("a", "b", 0.0)], [("a", "b", 0.5)]]  # pick, intent, tie


def test_rank_without_games_is_refused():
    with pytest.raises(ValueError, match="nothing to rank"):
        rank([reaction("F0", "p", "a")], {"a", "b"})


# --- end to end: viewers with a known taste --------------------------------------

class TasteViewer:
    """Prefers the ad with the highest hidden quality Q plus noise (Gumbel: a Bradley-Terry world)."""

    def viewer_chat(self, messages, **kwargs):
        user = messages[1]["content"]
        rng = random.Random(hashlib.sha256(json.dumps(messages).encode()).hexdigest())  # per viewer and feed
        blocks = re.findall(r"\[(A\d+)\] Sponsored · .*?Text: Q=(-?[\d.]+)", user, re.S)
        utility = {lab: float(q) - math.log(-math.log(rng.random())) for lab, q in blocks}
        best = max(utility, key=lambda k: utility[k])
        answer = {"reactions": [{"ad": lab, "stopped": lab == best, "understood": True, "believed": True,
                                 "why_not": "", "intent": "", "intent_score": min(5, max(1, round(3 + u)))}
                                for lab, u in utility.items()],
                  "preferred": best}
        return NS(text=json.dumps(answer), cost=NS(usd=0.001))


QUALITY = {"v0": 1.6, "v1": 0.9, "v2": 0.3, "v3": -0.3, "v4": -0.9, "v5": -1.6}


def tournament(seed: int):
    ours = [ad(k, f"Q={q}") for k, q in QUALITY.items()]
    feeds = round_robin_feeds(ours, COMPETITORS, feed_size=4, rounds=3, seed=seed)
    personas = [Persona(f"p{i}", "FR", "25-34", "female") for i in range(6)]
    sim = run_simulation(Viewer(TasteViewer()), personas, feeds, viewers_per_feed=3)
    return rank(sim.reactions, set(QUALITY), seed=seed), len(feeds)


def test_a_simulated_tournament_recovers_the_true_ranking():
    # 6 variants, 3 rounds x 3 viewers = 9 games per pair. Sampling noise swaps close neighbours now and then,
    # so the bar is over many seeds (ROADMAP E3-2: tau >= 0.8), with no seed far off.
    taus = []
    for seed in range(20):
        result, n_feeds = tournament(seed)
        taus.append(kendall_tau(list(QUALITY.values()), [result.strength(k) for k in QUALITY]))
        assert result.clearly_ahead("v0", "v5") and not result.clearly_ahead("v5", "v0")
        assert all(s.ci[0] <= s.strength <= s.ci[1] for s in result.standings)
        assert result.simulated and result.views == n_feeds * 3
    assert sum(t >= 0.8 for t in taus) >= 16 and min(taus) >= 0.6, taus


def test_without_bootstrap_nothing_is_clearly_ahead():
    rs = [reaction("F0", "p", "a", preferred=True), reaction("F0", "p", "b")]
    result = rank(rs, {"a", "b"}, bootstrap=0)
    assert result.standings[0].ad_id == "a" and not result.clearly_ahead("a", "b")
    assert PERSONAS  # shared fixtures stay importable
