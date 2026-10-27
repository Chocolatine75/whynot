"""Statistics behind every reliability number we show (TARGETS.md R1–R3, R6).

Pure Python, no dependencies, deterministic given a seed.

- `pairwise_accuracy`: of all pairs of ads whose real metric differs, how often
  does the simulator order them the same way? 0.5 = random. (R1)
- `auc`: probability that a random positive (e.g. long-running ad) scores higher
  than a random negative. 0.5 = random. (R3)
- `bootstrap_ci`: confidence interval by resampling ads, for any metric above.
- `wilson_interval`, `binomial_two_sided_p`: for agreement and preference rates
  out of n paired judgements (R2, R6).
"""

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PairwiseResult:
    accuracy: float  # agreeing pairs / compared pairs (simulator ties count half)
    pairs: int  # pairs compared (pairs tied on the real metric are skipped)


def pairwise_accuracy(predicted: Sequence[float], actual: Sequence[float]) -> PairwiseResult:
    if len(predicted) != len(actual):
        raise ValueError("predicted and actual must have the same length")
    score = 0.0
    pairs = 0
    n = len(actual)
    for i in range(n):
        for j in range(i + 1, n):
            real = actual[i] - actual[j]
            if real == 0:
                continue
            pred = predicted[i] - predicted[j]
            pairs += 1
            if pred == 0:
                score += 0.5
            elif (pred > 0) == (real > 0):
                score += 1.0
    if pairs == 0:
        raise ValueError("no comparable pairs: all actual values are equal")
    return PairwiseResult(accuracy=score / pairs, pairs=pairs)


def auc(scores: Sequence[float], labels: Sequence[bool]) -> float:
    """Area under the ROC curve (Mann–Whitney form, ties count half)."""
    if len(scores) != len(labels):
        raise ValueError("scores and labels must have the same length")
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        raise ValueError("need at least one positive and one negative")
    wins = 0.0
    for p in pos:
        for q in neg:
            wins += 1.0 if p > q else 0.5 if p == q else 0.0
    return wins / (len(pos) * len(neg))


def bootstrap_ci(metric: Callable[[list[int]], float], n_items: int, *, iterations: int = 2000,
                 level: float = 0.95, seed: int = 0) -> tuple[float, float]:
    """Percentile CI of `metric(indices)` over resamples of item indices.

    `metric` receives a list of indices (with repeats) and returns a number;
    resamples where the metric is undefined (raises ValueError) are skipped.
    """
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(iterations):
        sample = [rng.randrange(n_items) for _ in range(n_items)]
        try:
            values.append(metric(sample))
        except ValueError:
            continue
    if not values:
        raise ValueError("metric undefined on every resample")
    values.sort()
    alpha = (1 - level) / 2
    lo = values[int(alpha * (len(values) - 1))]
    hi = values[int(math.ceil((1 - alpha) * (len(values) - 1)))]
    return lo, hi


def pairwise_accuracy_ci(predicted: Sequence[float], actual: Sequence[float], **kwargs) -> tuple[float, float]:
    return bootstrap_ci(lambda idx: pairwise_accuracy([predicted[i] for i in idx],
                                                      [actual[i] for i in idx]).accuracy,
                        len(actual), **kwargs)


def auc_ci(scores: Sequence[float], labels: Sequence[bool], **kwargs) -> tuple[float, float]:
    return bootstrap_ci(lambda idx: auc([scores[i] for i in idx], [labels[i] for i in idx]),
                        len(scores), **kwargs)


def wilson_interval(successes: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """95 % Wilson score interval for a proportion."""
    if n <= 0:
        raise ValueError("n must be positive")
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def binomial_two_sided_p(successes: int, n: int, p: float = 0.5) -> float:
    """Exact two-sided binomial test: probability of a result at least this extreme."""
    if n <= 0 or not 0 <= successes <= n:
        raise ValueError("need 0 <= successes <= n and n > 0")
    probs = [math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(n + 1)]
    observed = probs[successes]
    return min(1.0, sum(q for q in probs if q <= observed * (1 + 1e-9)))
