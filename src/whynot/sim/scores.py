"""Per-ad scores from viewer reactions.

`preference_lift` is the primary score: how often viewers picked the ad as their
favourite in its feed, divided by chance (1 / feed size). 1.0 = chance, 2.0 =
picked twice as often as chance. It measures "does this ad win its feed".
The other rates are reported alongside, never mixed into one opaque number.
"""

from collections import defaultdict
from dataclasses import dataclass

from whynot.sim.viewer import Reaction


@dataclass
class AdScore:
    ad_id: str
    views: int
    preference_lift: float  # primary
    mean_intent: float  # 1–5
    stop_rate: float
    understood_rate: float
    believed_rate: float
    top_why_not: list[str]


def score_ads(reactions: list[Reaction], *, max_reasons: int = 3) -> dict[str, AdScore]:
    by_ad: dict[str, list[Reaction]] = defaultdict(list)
    feed_sizes: dict[tuple[str, str], int] = defaultdict(int)
    for r in reactions:
        by_ad[r.ad_id].append(r)
        feed_sizes[(r.feed_id, r.persona_id)] += 1

    scores: dict[str, AdScore] = {}
    for ad_id, rs in by_ad.items():
        n = len(rs)
        # expected picks if viewers chose at random within each feed they saw
        chance = sum(1 / feed_sizes[(r.feed_id, r.persona_id)] for r in rs)
        picks = sum(r.preferred for r in rs)
        reasons = [r.why_not for r in rs if r.why_not]
        scores[ad_id] = AdScore(
            ad_id=ad_id, views=n,
            preference_lift=picks / chance if chance else 0.0,
            mean_intent=sum(r.intent_score for r in rs) / n,
            stop_rate=sum(r.stopped for r in rs) / n,
            understood_rate=sum(r.understood for r in rs) / n,
            believed_rate=sum(r.believed for r in rs) / n,
            top_why_not=reasons[:max_reasons],
        )
    return scores
