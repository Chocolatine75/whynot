"""Property-based tests: invariants that must hold for any input (Hypothesis).

Each test states a rule the rest of the system relies on. Hypothesis generates
hundreds of inputs per rule and shrinks any failure to a minimal example.
"""

import contextlib
import math
import random

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from PIL import Image

from whynot.assets.sam import parse
from whynot.create.composer import ComposeError, compose, contrast_ratio, fit_product
from whynot.create.guards import run_guards
from whynot.create.templates import Template, Variant
from whynot.run.autopilot import AccountState, Action, Kind, Level, Outcome, Policy, decide
from whynot.sim.feed import FeedItem, build_market_feeds, order_for
from whynot.sim.personas import allocate
from whynot.sim.viewer import ViewerParseError, parse_reactions
from whynot.validate.stats import (
    auc,
    binomial_two_sided_p,
    bootstrap_ci,
    pairwise_accuracy,
    wilson_interval,
)

floats = st.floats(-1e6, 1e6, allow_nan=False)


# --- statistics ------------------------------------------------------------------

@given(st.lists(st.tuples(floats, st.booleans()), min_size=2, max_size=40))
def test_auc_is_a_probability_and_flips_with_labels(rows):
    scores = [s for s, _ in rows]
    labels = [y for _, y in rows]
    assume(any(labels) and not all(labels))
    a = auc(scores, labels)
    assert 0.0 <= a <= 1.0
    assert math.isclose(a + auc(scores, [not y for y in labels]), 1.0)
    # invariant to any strictly increasing transform of the scores
    assert math.isclose(a, auc([math.atan(s / 1000) for s in scores], labels), abs_tol=1e-12) or \
        len(set(scores)) != len({math.atan(s / 1000) for s in scores})


@given(st.lists(floats, min_size=2, max_size=25, unique=True))
def test_pairwise_accuracy_of_perfect_and_reversed_predictors(actual):
    assert pairwise_accuracy(actual, actual).accuracy == 1.0
    assert pairwise_accuracy([-a for a in actual], actual).accuracy == 0.0
    assert pairwise_accuracy([0.0] * len(actual), actual).accuracy == 0.5
    assert pairwise_accuracy(actual, actual).pairs == len(actual) * (len(actual) - 1) // 2


@given(st.integers(1, 500).flatmap(lambda n: st.tuples(st.integers(0, n), st.just(n))))
def test_wilson_interval_contains_the_estimate(sn):
    k, n = sn
    lo, hi = wilson_interval(k, n)
    assert 0.0 <= lo <= k / n <= hi <= 1.0


@given(st.integers(1, 200).flatmap(lambda n: st.tuples(st.integers(0, n), st.just(n))))
def test_binomial_p_value_is_a_probability_and_symmetric(sn):
    k, n = sn
    p = binomial_two_sided_p(k, n)
    assert 0.0 < p <= 1.0
    assert math.isclose(p, binomial_two_sided_p(n - k, n), rel_tol=1e-9)


@settings(max_examples=30)
@given(st.lists(floats, min_size=3, max_size=30), st.integers(0, 10_000))
def test_bootstrap_ci_is_ordered_and_reproducible(values, seed):
    def mean(idx):
        return sum(values[i] for i in idx) / len(idx)
    lo, hi = bootstrap_ci(mean, len(values), iterations=200, seed=seed)
    assert lo <= hi
    assert (lo, hi) == bootstrap_ci(mean, len(values), iterations=200, seed=seed)
    assert min(values) - 1e-6 <= lo and hi <= max(values) + 1e-6


# --- personas and feeds ----------------------------------------------------------

@given(st.dictionaries(st.text(min_size=1, max_size=5), st.integers(1, 10_000), min_size=1, max_size=30),
       st.integers(1, 300))
def test_allocate_sums_to_n_and_stays_proportional(weights, n):
    counts = allocate(weights, n)
    assert sum(counts.values()) == n
    total = sum(weights.values())
    for k, w in weights.items():
        assert abs(counts.get(k, 0) - n * w / total) < 1.0  # largest remainder: off by < 1
    assert counts == allocate(dict(reversed(list(weights.items()))), n)  # order-independent


@given(st.integers(2, 30).flatmap(lambda n: st.tuples(st.just(n), st.integers(2, n))),
       st.integers(1, 4), st.integers(0, 1000))
def test_market_feeds_are_well_formed_and_fair(n_size, appearances, seed):
    n, size = n_size
    items = [FeedItem(str(i), "a", "", "b") for i in range(n)]
    feeds = build_market_feeds(items, feed_size=size, appearances=appearances, seed=seed)
    counts = {str(i): 0 for i in range(n)}
    for feed in feeds:
        ids = [i.ad_id for i in feed]
        assert len(feed) == size and len(set(ids)) == size  # never twice in one feed
        for i in ids:
            counts[i] += 1
    assert min(counts.values()) >= appearances
    assert max(counts.values()) - min(counts.values()) <= 1  # balanced exposure
    assert sorted(o.ad_id for o in order_for(feeds[0], "k")) == sorted(i.ad_id for i in feeds[0])


# --- templates -------------------------------------------------------------------

gene_options = st.lists(st.text("abcdefgh", min_size=1, max_size=6), min_size=1, max_size=4, unique=True)


@st.composite
def templates(draw):
    genes = {"format": ["static_1080"], "hook": draw(gene_options), "cta": draw(gene_options)}
    for extra in draw(st.lists(st.sampled_from(["proof", "first_shot", "tone"]), unique=True)):
        genes[extra] = draw(gene_options)
    return Template.from_dict({"id": "t", "concept": "c", "persona": "p", "objection": "o", "genes": genes})


@given(templates(), st.integers(1, 50), st.integers(0, 1000))
def test_sample_gives_distinct_valid_genomes(t, n, seed):
    genomes = t.sample(n, seed=seed)
    assert len(genomes) == min(n, t.space_size())
    assert len({Variant("t", g).id for g in genomes}) == len(genomes)
    for g in genomes:
        t.check(g)


@given(templates(), st.data())
def test_mutation_changes_exactly_one_gene(t, data):
    genome = data.draw(st.sampled_from(list(t.genomes())))
    mutable = [g for g, opts in t.genes.items() if len(opts) > 1]
    assume(mutable)
    gene = data.draw(st.sampled_from(mutable))
    new = t.mutate(genome, gene, seed=data.draw(st.integers(0, 1000)))
    changed = [k for k in genome if genome[k] != new[k]]
    assert changed == [gene]
    t.check(new)


# --- autopilot: the cap is never exceeded ----------------------------------------

action_kinds = st.sampled_from(list(Kind))
budgets = st.one_of(st.floats(0, 200, allow_nan=False), st.just(float("nan")), st.just(float("inf")),
                    st.floats(-50, 0, exclude_max=True))


@settings(max_examples=300)
@given(st.sampled_from(list(Level)), st.floats(0, 100, allow_nan=False), st.booleans(),
       st.lists(st.tuples(action_kinds, st.integers(0, 5), budgets, st.booleans(), st.booleans()), max_size=30))
def test_executed_actions_never_push_spend_above_the_cap(level, cap, first_ok, steps):
    """Whatever the sequence of actions and approvals, committed daily spend stays ≤ cap."""
    policy = Policy(level, cap, first_ok)
    running: dict[str, float] = {}
    for kind, ref, budget, guards_ok, approved in steps:
        action = Action(kind, f"ad{ref}", "test", budget, guards_ok)
        before = sum(running.values())
        d = decide(action, policy, AccountState(dict(running)), approved_by="owner" if approved else None)
        if d.outcome is Outcome.EXECUTE:
            if kind is Kind.PAUSE:
                running.pop(action.ad_ref, None)
            else:
                running[action.ad_ref] = budget
            assert level is not Level.DRY_RUN
            assert math.isfinite(budget) or kind is Kind.PAUSE
            if kind is Kind.PUBLISH:
                assert guards_ok
                assert first_ok or approved
            if level is Level.PROPOSE:
                assert approved
        after = sum(running.values())
        assert after <= max(cap, before) + 1e-9


# --- composer + guards -----------------------------------------------------------

colours = st.tuples(st.integers(0, 255), st.integers(0, 255), st.integers(0, 255))


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(colours, min_size=3, max_size=3, unique=True), st.integers(20, 900), st.integers(20, 900),
       st.integers(0, 10_000))
def test_composed_ads_never_alter_product_pixels(palette, w, h, seed):
    """For any palette and asset shape, untampered compositions pass the pixel guard,
    and the legibility guard agrees with the contrast it reports."""
    hexes = ["#{:02X}{:02X}{:02X}".format(*c) for c in palette]
    t = Template.from_dict({
        "id": "t", "concept": "c", "persona": "p", "objection": "o",
        "fixed": {"brand": {"name": "B", "palette": hexes}},
        "genes": {"format": ["static_1080"], "hook": ["h"], "first_shot": ["app_screen", "result_card"],
                  "proof": ["none", "stars"], "cta": ["Go"]},
        "copy": {"hook": {"h": "Learn a language in five minutes"}, "proof": {"none": "", "stars": "Rated 4.8"}},
    })
    rng = random.Random(seed)
    asset = Image.new("RGBA", (w, h))
    asset.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256), 255)] * (w * h))
    genome = t.sample(1, seed=seed)[0]
    try:
        comp = compose(t, genome, asset)
    except ComposeError:
        return
    results = run_guards(t, comp, asset)
    assert results["product_pixels_unchanged"].passed is True
    assert results["brand_palette"].passed is True
    worst = min(contrast_ratio(x.fg, x.bg) for x in comp.texts)
    if worst >= 4.5:
        assert results["text_legible"].passed is True


@given(st.integers(1, 5000), st.integers(1, 5000))
def test_fit_product_keeps_aspect_and_stays_in_the_box(w, h):
    box = (240, 330, 840, 860)
    (nw, nh), placed = fit_product((w, h), box)
    assert box[0] <= placed[0] and placed[2] <= box[2] and box[1] <= placed[1] and placed[3] <= box[3]
    assert abs(nw / nh - w / h) / (w / h) < 0.05 or min(nw, nh) <= 20  # rounding on tiny sides


# --- parsers never crash with an unexpected error -------------------------------

@settings(max_examples=300)
@given(st.text(max_size=300))
def test_viewer_parser_only_raises_parse_errors(text):
    with contextlib.suppress(ViewerParseError):
        parse_reactions(text, {"A1": "x", "A2": "y"}, feed_id="F", persona_id="p")


@given(st.lists(st.tuples(st.integers(0, 100), st.integers(0, 100), st.integers(0, 100), st.integers(0, 100)),
                max_size=5),
       st.text("abc|>~!#", min_size=1, max_size=30))
def test_sam_parser_roundtrips_boxes_and_payloads(boxes, payload):
    payload = "~" + payload
    records = []
    for a, b, c, d in boxes:
        x1, x2 = sorted((a, c))
        y1, y2 = sorted((b, d))
        records.append(f"<|box;x1={x1};y1={y1};x2={x2};y2={y2};w=100;h=100|>")
    records.append(f"<|mask;x=0;y=0;data=8,8,{payload}|>")
    parsed_boxes, masks = parse("".join(records))
    assert len(parsed_boxes) == len(boxes)
    assert masks[0].encoding + masks[0].payload == payload
