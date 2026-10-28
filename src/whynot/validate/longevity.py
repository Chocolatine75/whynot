"""R3: does the simulator tell long-running competitor ads from short-lived ones?

Long-running ads (still active after N days) are a practitioner proxy for "this
ad pays"; ads stopped within a few days are the opposite. A noisy proxy: we
report it as one validation signal among others, never alone.

Design choices, fixed before looking at results:
- positives: still running and started at least `long_days` ago;
  negatives: stopped after at most `short_days` of delivery;
- one ad per (advertiser, copy): advertisers often run the same copy as several
  ads (e.g. one per gender), which would count the same creative twice;
- classes balanced per advertiser where possible, so the test isn't "which brand";
- primary metric: AUC of `preference_lift`; `mean_intent` reported as secondary;
- baselines: copy length, and chance (0.5).
"""

import random
from dataclasses import dataclass
from datetime import date

from whynot.ingest.adlibrary import CompetitorAd
from whynot.sim.scores import AdScore
from whynot.validate.stats import auc, auc_ci


@dataclass
class LabelledAd:
    ad: CompetitorAd
    long_running: bool


def label(ad: CompetitorAd, *, as_of: date, long_days: int = 60, short_days: int = 14) -> bool | None:
    """True = long-running, False = short-lived, None = neither (excluded)."""
    days = ad.longevity_days(as_of)
    if days is None:
        return None
    if ad.stop_date is None and days >= long_days:
        return True
    if ad.stop_date is not None and days <= short_days:
        return False
    return None


def _copy_key(ad: CompetitorAd) -> tuple[str, str]:
    return (ad.page_id or ad.page_name or "", " ".join((ad.bodies or [""])[0].split()).lower())


def select(ads: list[CompetitorAd], *, as_of: date, per_class: int, long_days: int = 60,
           short_days: int = 14, seed: int = 0) -> list[LabelledAd]:
    """Deduplicated, text-bearing, balanced set of labelled ads."""
    seen: set[tuple[str, str]] = set()
    pos: dict[str, list[CompetitorAd]] = {}
    neg: dict[str, list[CompetitorAd]] = {}
    for ad in ads:
        if not (ad.bodies and ad.bodies[0].strip()):
            continue
        key = _copy_key(ad)
        if key in seen:
            continue
        lab = label(ad, as_of=as_of, long_days=long_days, short_days=short_days)
        if lab is None:
            continue
        seen.add(key)
        (pos if lab else neg).setdefault(key[0], []).append(ad)

    rng = random.Random(seed)

    def take(groups: dict[str, list[CompetitorAd]], n: int) -> list[CompetitorAd]:
        # round-robin across advertisers so no single brand dominates
        pools = {k: rng.sample(v, len(v)) for k, v in sorted(groups.items())}
        out: list[CompetitorAd] = []
        while len(out) < n and any(pools.values()):
            for k in list(pools):
                if pools[k] and len(out) < n:
                    out.append(pools[k].pop())
        return out

    n = min(per_class, sum(map(len, pos.values())), sum(map(len, neg.values())))
    chosen = [LabelledAd(a, True) for a in take(pos, n)] + [LabelledAd(a, False) for a in take(neg, n)]
    rng.shuffle(chosen)
    return chosen


@dataclass
class LongevityResult:
    n_long: int
    n_short: int
    auc_preference: float
    ci_preference: tuple[float, float]
    auc_intent: float
    ci_intent: tuple[float, float]
    auc_copy_length: float  # baseline
    scored_ads: int


def evaluate(labelled: list[LabelledAd], scores: dict[str, AdScore], *, seed: int = 0) -> LongevityResult:
    rows = [(scores[la.ad.id], la) for la in labelled if la.ad.id in scores]
    labels = [la.long_running for _, la in rows]
    pref = [s.preference_lift for s, _ in rows]
    intent = [s.mean_intent for s, _ in rows]
    length = [float(len((la.ad.bodies or [""])[0])) for _, la in rows]
    return LongevityResult(
        n_long=sum(labels), n_short=len(labels) - sum(labels),
        auc_preference=auc(pref, labels), ci_preference=auc_ci(pref, labels, seed=seed),
        auc_intent=auc(intent, labels), ci_intent=auc_ci(intent, labels, seed=seed),
        auc_copy_length=auc(length, labels), scored_ads=len(rows),
    )
