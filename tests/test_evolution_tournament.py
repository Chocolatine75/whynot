"""Evolution judged by tournaments (E3-2, E6-1) and gated by the noise floor (E3-3), on a noisy fake world.

The world: viewers prefer the ad with the highest quality + Gumbel noise (a fresh draw per request, like a real
model). Ads that talk about family have a higher quality. The evolver proposes neutral body rewrites, and once,
at generation 1, one hook that names the family: the known better mutation. Evolution must find it (the strongest
ad descends from it, called better than generation 0 beyond the noise) in ≥ 80 % of seeds, and must rarely claim
an improvement when that mutation is neutral.
"""

import hashlib
import json
import math
import random
import re
import threading
from collections import Counter
from types import SimpleNamespace as NS

import pytest

from whynot.agency.create import add_verdicts, evolve_group, pick_parents, pooled_floor
from whynot.budget import BudgetExceeded
from whynot.sim import tournament
from whynot.sim.arena import our_item, placebo_item
from whynot.sim.feed import FeedItem
from whynot.sim.personas import Persona
from whynot.sim.viewer import Viewer
from whynot.validate.retest import IMPROVED, NOT_MEASURED, WITHIN_NOISE, WORSE, verdict

BRAND = "LinguaApp"
PERSONAS = [Persona(f"p{i}", "FR", "25-34", "female") for i in range(2)]
ROUNDS = 2  # feeds per pair: `CreateConfig.tournament_rounds`, the default design
COMPETITORS = [FeedItem(f"c{i}", f"Rival {i}", "", f"Learn a language, offer {i}.") for i in range(8)]


class NoisyWorld:
    """Viewer client: preferred ad = argmax(quality + Gumbel noise). Same request asked again = a fresh draw
    (counted per request, so the answers don't depend on thread order)."""

    def __init__(self, seed: int, good: float, noise: float = 1.0):
        self.seed, self.good, self.noise = seed, good, noise
        self.seen: Counter[str] = Counter()
        self.lock = threading.Lock()
        self.calls = 0

    def quality(self, block: str) -> float:
        return self.good if "famil" in block.lower() else 0.0

    def viewer_chat(self, messages, **kwargs):
        text = messages[1]["content"]
        request = json.dumps(messages)  # who watches (system) + what they see
        with self.lock:
            self.calls += 1
            self.seen[request] += 1
            n = self.seen[request]
        rng = random.Random(hashlib.sha256(f"{self.seed}|{n}|{request}".encode()).hexdigest())
        blocks = re.findall(r"\[(A\d+)\] Sponsored · (.*?)(?=\n\n\[A\d+\]|\Z)", text, re.S)
        u = {lab: self.quality(body) - self.noise * math.log(-math.log(rng.random())) for lab, body in blocks}
        best = max(u, key=lambda k: u[k])
        return NS(text=json.dumps({"reactions": [{"ad": lab, "stopped": lab == best, "understood": True,
                                                  "believed": True, "why_not": "" if lab == best else "Not for me",
                                                  "intent": "", "intent_score": 4 if lab == best else 2}
                                                 for lab in u], "preferred": best}), cost=NS(usd=0.001))


def row(vid: str, template: str, hook: str, body: str, generation: int = 0, parent: str | None = None):
    return {"variant_id": vid, "template_id": template, "generation": generation, "parent_id": parent,
            "texts": {"hook": hook, "body": body, "title": "Try it"}}


GEN0 = [row(f"t{t}-v{i}", f"t{t}", f"Speak with confidence {t}{i}", f"Short lessons, version {t}{i}.")
        for t in range(2) for i in range(3)]


def run_evolution(seed: int, *, good: float, better_exists: bool = True, generations: int = 2,
                  noise: float = 1.0) -> tuple[dict, NoisyWorld]:
    world = NoisyWorld(seed, good, noise)
    viewer = Viewer(world)
    rng = random.Random(seed)
    gen0 = {r["variant_id"]: {"lift_over_placebo": rng.choice([3.0, 3.5, 4.0]), "intent": 3.0, "top_why_not": []}
            for r in GEN0}  # the arena's ceiling: generation 0 can't tell them apart
    better_hook = "Finally talk with your family" if better_exists else "Finally talk with your friends"

    def make_children(parents, gen, why_not):
        kids = []
        for pi, p in enumerate(parents):
            for j in range(2):
                hook, body = p["texts"]["hook"], f"{p['texts']['body']} Rewrite g{gen}p{pi}m{j}."
                if gen == 1 and pi == 0 and j == 0:  # the known better mutation, offered once
                    hook, body = better_hook, p["texts"]["body"]
                kids.append(row(f"{p['variant_id']}-g{gen}m{j}", p["template_id"], hook, body, gen, p["variant_id"]))
        return kids, []

    def judge(pool, gen):
        source = rng.choice(COMPETITORS)
        candidates = [our_item(r["variant_id"], BRAND, r["texts"]) for r in pool] + [placebo_item(source, BRAND)]
        fillers = [c for c in COMPETITORS if c.ad_id != source.ad_id]
        return tournament.play(viewer, PERSONAS, candidates, fillers, feed_size=4, rounds=ROUNDS, viewers_per_feed=2,
                               seed=seed * 100 + gen, bootstrap=100)

    group = evolve_group(GEN0, gen0, generations=generations, keep=2, make_children=make_children, judge=judge,
                         replay=lambda p: tournament.replay(viewer, p, bootstrap=100))
    add_verdicts(group, pooled_floor([group]))
    return group, world


def found(group: dict) -> bool:
    """The strongest ad descends from the better mutation, and is called better than generation 0."""
    vid, chain = group["champion"], []
    while vid:
        chain.append(vid)
        vid = vid.rsplit("-g", 1)[0] if "-g" in vid else None
    return f"{group['history'][0]['kept'][0]}-g1m0" in chain and group["result"]["verdict"] == IMPROVED


SEEDS = range(40)
# The family hook's quality edge, in logits (a family ad beats a neutral one head-to-head 92 % of the time).
# Measured on 60 seeds with this design (2 rounds per pair): found 92 %, false alarms 7 %. A smaller edge is
# still selected (2.0: 100 %, 1.5: 98 %) but called an improvement less often (75 %, 50 %): by design, the floor
# (1.96·√2·SD of a retest, worst case) refuses gaps it cannot tell from noise. Table in docs/DECISIONS.md.
GOOD = 2.5


@pytest.fixture(scope="module")
def better_world():
    return [run_evolution(s, good=GOOD)[0] for s in SEEDS]


@pytest.fixture(scope="module")
def null_world():
    return [run_evolution(s, good=GOOD, better_exists=False)[0] for s in SEEDS]


def test_evolution_finds_the_known_better_mutation_in_most_seeds(better_world):
    hits = sum(found(g) for g in better_world)
    assert hits / len(better_world) >= 0.8, hits


def test_evolution_rarely_claims_an_improvement_that_is_not_there(null_world):
    # every child is as good as its parent: any "improved" is a false alarm of the noise floor gate
    false_alarms = sum(g["result"]["verdict"] == IMPROVED for g in null_world)
    assert false_alarms / len(null_world) <= 0.15, false_alarms


def test_each_generation_meets_its_parents_and_the_generation_0_champion(better_world):
    for g in better_world:
        anchor = g["anchor"]
        for h in (h for h in g["history"] if h.get("judge") == "tournament"):
            ids = {s["ad_id"] for s in h["tournament"]["standings"]}
            assert anchor in ids
            assert all(c.rsplit("-g", 1)[0] in ids for c in h["children"])  # each child meets its parent
            assert h["tournament"]["simulated"]
        assert [p["generation"] for p in g["progress"]] == [0, 1, 2]
        assert g["progress"][0]["vs_gen0"] == 0.0
        assert g["noise_floor"]["used"] is not None and g["noise_floor"]["used"] > 0  # a noisy world has noise


def test_a_gap_below_the_floor_is_never_called_an_improvement(better_world, null_world):
    for g in better_world + null_world:
        floor = g["noise_floor"]["used"]
        for h in (h for h in g["history"] if h.get("judge") == "tournament"):
            for claim in (h["best_child"], h["vs_gen0"]):
                if claim["verdict"] in (IMPROVED, WORSE):
                    assert abs(claim["difference"]) > floor
                if claim["difference"] is not None and abs(claim["difference"]) <= floor:
                    assert claim["verdict"] == WITHIN_NOISE


def test_the_retest_is_a_fresh_draw_on_the_same_feeds():
    group, world = run_evolution(0, good=GOOD)
    assert group["retest"]["generation"] == 2 and group["retest"]["strengths"]
    feeds = [h["tournament"]["feeds"] for h in group["history"] if "tournament" in h]
    assert world.calls == 2 * (sum(feeds) + feeds[-1])  # 2 viewers per feed; the last tournament played twice
    last = {s["ad_id"]: s["strength"] for s in group["history"][-1]["tournament"]["standings"]}
    assert set(last) == set(group["retest"]["strengths"])
    assert last != group["retest"]["strengths"]  # a fresh draw, not the first answers again


# --- the verdict rule -----------------------------------------------------------------------------

@pytest.mark.parametrize("difference, floor, retest, expected", [
    (0.9, 0.5, None, IMPROVED),
    (0.9, 0.5, 0.2, IMPROVED),
    (0.9, 0.5, -0.1, WITHIN_NOISE),  # the retest points the other way: the first gap was luck
    (0.9, 0.5, 0.0, WITHIN_NOISE),
    (0.5, 0.5, None, WITHIN_NOISE),  # equal to the floor is not beyond it
    (-0.9, 0.5, -0.3, WORSE),
    (-0.2, 0.5, None, WITHIN_NOISE),
    (0.9, None, None, NOT_MEASURED),
    (None, 0.5, None, NOT_MEASURED),
    (0.9, math.inf, None, NOT_MEASURED),
])
def test_verdict(difference, floor, retest, expected):
    assert verdict(difference, floor, retest_difference=retest) == expected


def test_the_larger_floor_wins_and_no_floor_is_not_measured():
    g = {"history": [], "retest": {"floor": 0.3, "strengths": {}, "generation": 1}}
    add_verdicts(g, 0.8)
    assert g["noise_floor"]["used"] == 0.8
    g = {"history": [], "retest": None}
    add_verdicts(g, None)
    assert g["noise_floor"]["used"] is None and g["progress"] == [] and "result" not in g


def test_pick_parents_prefers_different_concepts_then_strength():
    rows = [row("a1", "a", "h", "b"), row("a2", "a", "h", "b"), row("b1", "b", "h", "b")]
    assert [r["variant_id"] for r in pick_parents(rows, {"a1": (2.0,), "a2": (1.5,), "b1": (0.1,)}, 2)] == ["a1", "b1"]
    assert [r["variant_id"] for r in pick_parents(rows, {"a1": (2.0,), "a2": (1.5,)}, 3)] == ["a1", "a2"]


# --- failure paths ------------------------------------------------------------------------------

class Broken:
    def viewer_chat(self, messages, **kwargs):
        return NS(text="not json", cost=NS(usd=0.0))


def test_a_generation_no_viewer_could_judge_stops_cleanly():
    viewer = Viewer(Broken(), retries=0)

    def judge(pool, gen):
        candidates = [our_item(r["variant_id"], BRAND, r["texts"]) for r in pool]
        return tournament.play(viewer, PERSONAS, candidates, COMPETITORS, feed_size=4, rounds=1, viewers_per_feed=2)

    gen0 = {r["variant_id"]: {"lift_over_placebo": 1.0, "intent": 3.0} for r in GEN0}
    kids = lambda parents, gen, why: ([row(f"{p['variant_id']}-g{gen}m0", p["template_id"], "x", "y", gen,  # noqa: E731
                                          p["variant_id"]) for p in parents], [])
    group = evolve_group(GEN0, gen0, generations=2, keep=2, make_children=kids, judge=judge,
                         replay=lambda p: pytest.fail("nothing to retest"))
    assert group["history"][-1]["stopped"].startswith("not judged") and group["retest"] is None
    add_verdicts(group, None)
    assert "result" not in group and group["champion"] == group["history"][0]["kept"][0]


def test_no_child_stops_before_any_tournament():
    gen0 = {r["variant_id"]: {"lift_over_placebo": 1.0, "intent": 3.0} for r in GEN0}
    group = evolve_group(GEN0, gen0, generations=2, keep=2, make_children=lambda *a: ([], [{"parent": "x"}]),
                         judge=lambda *a: pytest.fail("no tournament without children"), replay=lambda p: p)
    assert group["history"][-1] == {"generation": 1, "stopped": "no valid child", "refused": [{"parent": "x"}]}
    assert group["final"] == {} and group["anchor"] is None


# --- the budget: evolution stops where its money ends and keeps what it has -------------------------------------

def budget_run(*, allowance=math.inf, fail_children_at=None, fail_replay=False):
    world = NoisyWorld(3, GOOD)
    viewer = Viewer(world)
    gen0 = {r["variant_id"]: {"lift_over_placebo": 3.0, "intent": 3.0, "top_why_not": []} for r in GEN0}

    def make_children(parents, gen, why_not):
        if gen == fail_children_at:
            raise BudgetExceeded("model budget of $4.00 spent ($4.01)")
        return [row(f"{p['variant_id']}-g{gen}m0", p["template_id"], p["texts"]["hook"], f"Rewrite {gen}", gen,
                    p["variant_id"]) for p in parents], []

    def judge(pool, gen):
        candidates = [our_item(r["variant_id"], BRAND, r["texts"]) for r in pool]
        candidates.append(placebo_item(COMPETITORS[0], BRAND))
        return tournament.play(viewer, PERSONAS, candidates, COMPETITORS[1:], feed_size=4, rounds=ROUNDS,
                               viewers_per_feed=2, seed=gen, bootstrap=50)

    def replay(played):
        if fail_replay:
            raise BudgetExceeded("model budget spent")
        return tournament.replay(viewer, played, bootstrap=50)

    group = evolve_group(GEN0, gen0, generations=3, keep=2, make_children=make_children, judge=judge, replay=replay,
                         spent=lambda: world.calls * 0.001, allowance=allowance)
    add_verdicts(group, pooled_floor([group]))
    return group, world


def test_a_generation_that_would_not_fit_the_budget_is_not_started():
    full, _ = budget_run()
    g1 = full["history"][1]["tournament"]["usd"]  # one generation (all its cost is viewers here)
    # room for generation 1 and its retest (≈ 2 × g1), not for generation 2 on top (needs ≈ 1.2 × g1 + g1 more)
    group, world = budget_run(allowance=3.0 * g1)
    judged = [h for h in group["history"] if h.get("judge") == "tournament"]
    assert len(judged) == 1 and group["history"][-1]["stopped"].startswith("budget: this audience may spend")
    assert world.calls * 0.001 <= 3.0 * g1 + 1e-9  # never past what this audience was given
    assert group["retest"]["floor"] is not None and "result" in group  # the kept generation is still measured
    assert len([h for h in full["history"] if h.get("judge") == "tournament"]) == 3


def test_money_running_out_during_a_generation_keeps_the_previous_one():
    group, _ = budget_run(fail_children_at=2)
    assert group["history"][-1]["stopped"].startswith("budget spent during this generation")
    assert group["champion"] == group["history"][1]["kept"][0]  # generation 1's best, measured
    assert group["retest"]["generation"] == 1 and "result" in group


def test_no_money_for_the_retest_means_no_verdict_never_a_claimed_win():
    group, _ = budget_run(fail_replay=True)
    assert group["retest"]["floor"] is None and group["retest"]["stopped"] == "budget"
    assert group["result"]["verdict"] == NOT_MEASURED
