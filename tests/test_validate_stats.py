import random

import pytest

from whynot.validate.stats import (
    auc, auc_ci, binomial_two_sided_p, bootstrap_ci, pairwise_accuracy, pairwise_accuracy_ci,
    wilson_interval,
)


# --- pairwise accuracy (R1) ---------------------------------------------------

def test_perfect_and_reversed_order():
    actual = [0.01, 0.02, 0.03, 0.04]
    assert pairwise_accuracy([1, 2, 3, 4], actual).accuracy == 1.0
    assert pairwise_accuracy([4, 3, 2, 1], actual).accuracy == 0.0
    assert pairwise_accuracy([1, 2, 3, 4], actual).pairs == 6


def test_ties_in_actual_are_skipped():
    result = pairwise_accuracy([1, 2, 3], [5, 5, 9])
    assert result.pairs == 2
    assert result.accuracy == 1.0


def test_simulator_ties_count_half():
    assert pairwise_accuracy([1, 1], [0, 1]).accuracy == 0.5


def test_pairwise_errors():
    with pytest.raises(ValueError):
        pairwise_accuracy([1, 2], [1])
    with pytest.raises(ValueError):
        pairwise_accuracy([1, 2], [3, 3])


# --- AUC (R3) -----------------------------------------------------------------

def test_auc_known_example():
    # Classic example: sklearn.roc_auc_score gives 0.75 here.
    assert auc([0.1, 0.4, 0.35, 0.8], [False, False, True, True]) == pytest.approx(0.75)


def test_auc_bounds_and_ties():
    assert auc([1, 2, 3, 4], [False, False, True, True]) == 1.0
    assert auc([4, 3, 2, 1], [False, False, True, True]) == 0.0
    assert auc([1, 1, 1, 1], [False, True, False, True]) == 0.5


def test_auc_equals_pairwise_accuracy_on_binary_labels():
    rng = random.Random(1)
    scores = [rng.random() for _ in range(30)]
    labels = [rng.random() < 0.4 for _ in range(30)]
    expected = pairwise_accuracy(scores, [1 if y else 0 for y in labels]).accuracy
    assert auc(scores, labels) == pytest.approx(expected)


def test_auc_needs_both_classes():
    with pytest.raises(ValueError):
        auc([1, 2], [True, True])


# --- bootstrap CIs ------------------------------------------------------------

def test_bootstrap_perfect_predictions_give_degenerate_ci():
    actual = [1, 2, 3, 4, 5, 6, 7, 8]
    assert pairwise_accuracy_ci(actual, actual, iterations=300) == (1.0, 1.0)


def test_bootstrap_is_deterministic_with_seed():
    rng = random.Random(2)
    pred = [rng.random() for _ in range(25)]
    actual = [rng.random() for _ in range(25)]
    assert pairwise_accuracy_ci(pred, actual, seed=7) == pairwise_accuracy_ci(pred, actual, seed=7)


def test_random_predictions_ci_contains_chance():
    rng = random.Random(3)
    pred = [rng.random() for _ in range(40)]
    actual = [rng.random() for _ in range(40)]
    lo, hi = pairwise_accuracy_ci(pred, actual, iterations=500)
    assert lo < 0.5 < hi


def test_auc_ci_contains_point_estimate():
    rng = random.Random(4)
    labels = [i % 2 == 0 for i in range(40)]
    scores = [rng.random() + (0.5 if y else 0) for y in labels]
    lo, hi = auc_ci(scores, labels, iterations=500)
    assert lo <= auc(scores, labels) <= hi


def test_bootstrap_undefined_everywhere():
    with pytest.raises(ValueError):
        bootstrap_ci(lambda idx: auc([1.0] * len(idx), [True] * len(idx)), 5, iterations=20)


# --- proportions (R2, R6) -----------------------------------------------------

def test_wilson_known_value():
    lo, hi = wilson_interval(8, 10)
    assert lo == pytest.approx(0.4902, abs=1e-3)
    assert hi == pytest.approx(0.9433, abs=1e-3)


def test_wilson_edges():
    assert wilson_interval(0, 10)[0] == pytest.approx(0.0)
    assert wilson_interval(10, 10)[1] == pytest.approx(1.0)


def test_binomial_p_values():
    assert binomial_two_sided_p(9, 10) == pytest.approx(22 / 1024)
    assert binomial_two_sided_p(5, 10) == pytest.approx(1.0)
    assert binomial_two_sided_p(60, 80) < 0.001


def test_binomial_errors():
    with pytest.raises(ValueError):
        binomial_two_sided_p(3, 0)
    with pytest.raises(ValueError):
        binomial_two_sided_p(11, 10)
