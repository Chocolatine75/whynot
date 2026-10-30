"""Statistics behind every reliability number we show (TARGETS.md R1–R3, R6).

Pure Python, no dependencies, deterministic given a seed.

- `pairwise_accuracy`: of all pairs of ads whose real metric differs, how often
  does the simulator order them the same way? 0.5 = random. (R1)
- `auc`: probability that a random positive (e.g. long-running ad) scores higher
  than a random negative. 0.5 = random. (R3)
- `bootstrap_ci`: confidence interval by resampling ads, for any metric above.
- `wilson_interval`, `binomial_two_sided_p`: for agreement and preference rates
  out of n paired judgements (R2, R6).
- `bradley_terry`: strengths from head-to-head outcomes (tournaments between our
  variants, E3-2); `kendall_tau`: agreement of two rankings.
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
    pos = [s for s, y in zip(scores, labels, strict=True) if y]
    neg = [s for s, y in zip(scores, labels, strict=True) if not y]
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
    if n_items < 1:
        raise ValueError("need at least one item")
    if not 0 < level < 1:
        raise ValueError("level must be between 0 and 1")
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
    hi = values[math.ceil((1 - alpha) * (len(values) - 1))]
    return lo, hi


def pairwise_accuracy_ci(predicted: Sequence[float], actual: Sequence[float], **kwargs) -> tuple[float, float]:
    return bootstrap_ci(lambda idx: pairwise_accuracy([predicted[i] for i in idx],
                                                      [actual[i] for i in idx]).accuracy,
                        len(actual), **kwargs)


def auc_ci(scores: Sequence[float], labels: Sequence[bool], **kwargs) -> tuple[float, float]:
    return bootstrap_ci(lambda idx: auc([scores[i] for i in idx], [labels[i] for i in idx]),
                        len(scores), **kwargs)


def stratified_auc(scores: Sequence[float], labels: Sequence[bool], strata: Sequence[str]) -> float:
    """AUC counting only pairs (positive, negative) from the same stratum (e.g. the same advertiser).

    Answers "within one advertiser, does the score rank its lasting ads above its short-lived ones?",
    so a score that only recognises the brand gets no credit. Ties count half. Strata with one class
    only contribute nothing."""
    if not len(scores) == len(labels) == len(strata):
        raise ValueError("scores, labels and strata must have the same length")
    by: dict[str, tuple[list[float], list[float]]] = {}
    for s, y, g in zip(scores, labels, strata, strict=True):
        by.setdefault(g, ([], []))[0 if y else 1].append(s)
    wins = pairs = 0.0
    for pos, neg in by.values():
        for p in pos:
            for q in neg:
                pairs += 1
                wins += 1.0 if p > q else 0.5 if p == q else 0.0
    if not pairs:
        raise ValueError("no stratum has both a positive and a negative")
    return wins / pairs


def stratified_auc_ci(scores: Sequence[float], labels: Sequence[bool], strata: Sequence[str],
                      **kwargs) -> tuple[float, float]:
    """Bootstrap CI resampling whole strata (advertisers), since items of one stratum are not independent."""
    groups: dict[str, list[int]] = {}
    for i, g in enumerate(strata):
        groups.setdefault(g, []).append(i)
    keys = sorted(groups)

    def metric(idx: list[int]) -> float:
        s, y, g = [], [], []
        for copy, k in enumerate(idx):
            for i in groups[keys[k]]:
                s.append(scores[i])
                y.append(labels[i])
                g.append(f"{copy}")  # a stratum drawn twice counts as two strata
        return stratified_auc(s, y, g)

    return bootstrap_ci(metric, len(keys), **kwargs)


def wilson_interval(successes: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """95 % Wilson score interval for a proportion."""
    if n <= 0 or not 0 <= successes <= n:
        raise ValueError("need 0 <= successes <= n and n > 0")
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lo = 0.0 if successes == 0 else max(0.0, centre - half)
    hi = 1.0 if successes == n else min(1.0, centre + half)  # exact bounds, no float drift
    return lo, hi


def binomial_two_sided_p(successes: int, n: int, p: float = 0.5) -> float:
    """Exact two-sided binomial test: probability of a result at least this extreme."""
    if n <= 0 or not 0 <= successes <= n:
        raise ValueError("need 0 <= successes <= n and n > 0")
    probs = [math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(n + 1)]
    observed = probs[successes]
    return min(1.0, sum(q for q in probs if q <= observed * (1 + 1e-9)))


def kendall_tau(a: Sequence[float], b: Sequence[float]) -> float:
    """Kendall's tau-b between two score lists: 1 = same order, -1 = reversed, 0 = unrelated."""
    if len(a) != len(b):
        raise ValueError("a and b must have the same length")
    concordant = discordant = ties_a = ties_b = 0
    for i in range(len(a)):
        for j in range(i + 1, len(a)):
            da, db = a[i] - a[j], b[i] - b[j]
            if da == 0 and db == 0:
                continue
            if da == 0:
                ties_a += 1
            elif db == 0:
                ties_b += 1
            elif (da > 0) == (db > 0):
                concordant += 1
            else:
                discordant += 1
    denom = math.sqrt((concordant + discordant + ties_a) * (concordant + discordant + ties_b))
    if denom == 0:
        raise ValueError("tau undefined: one of the lists is constant")
    return (concordant - discordant) / denom


Outcome = tuple[str, str, float]  # (a, b, score of a): 1 = a won, 0 = b won, 0.5 = tie


def bradley_terry(outcomes: Sequence[Outcome], items: Sequence[str] | None = None, *, prior: float = 1.0,
                  iterations: int = 500, tol: float = 1e-10) -> dict[str, float]:
    """Log-strengths (mean 0) fitted by the MM algorithm (Hunter 2004); P(a beats b) = 1 / (1 + e^(sb - sa)).

    `prior`: each item also plays `prior` virtual games (half won) against a reference of strength 0.
    It keeps strengths finite when an item wins or loses every game, and pulls items seen in few
    games towards average: a variant with 2 wins out of 2 is not declared infinitely good.
    """
    names = sorted(set(items or []) | {x for a, b, _ in outcomes for x in (a, b)})
    if not names:
        raise ValueError("no items")
    if prior <= 0:
        raise ValueError("prior must be > 0 (strengths are infinite without it for unbeaten items)")
    for a, b, score in outcomes:
        if a == b or not 0 <= score <= 1:
            raise ValueError(f"bad outcome: {(a, b, score)!r}")
    wins = {n: prior / 2 for n in names}
    games: dict[tuple[str, str], float] = {}
    for a, b, score in outcomes:
        wins[a] += score
        wins[b] += 1 - score
        key = (a, b) if a < b else (b, a)
        games[key] = games.get(key, 0.0) + 1
    strength = dict.fromkeys(names, 1.0)  # exp(log-strength); the reference stays at 1
    for _ in range(iterations):
        denom = {n: prior / (strength[n] + 1.0) for n in names}
        for (a, b), n_ab in games.items():
            d = n_ab / (strength[a] + strength[b])
            denom[a] += d
            denom[b] += d
        new = {n: wins[n] / denom[n] for n in names}
        done = max(abs(math.log(new[n] / strength[n])) for n in names) < tol
        strength = new
        if done:
            break
    logs = {n: math.log(v) for n, v in strength.items()}
    mean = sum(logs.values()) / len(logs)
    return {n: v - mean for n, v in logs.items()}
