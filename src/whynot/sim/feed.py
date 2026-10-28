"""Simulated feeds: a few ads in a row, like a stretch of an Instagram feed.

Two uses:
- market feeds (`build_market_feeds`): every ad of a set appears the same number
  of times, never twice in one feed. Used to score a whole corpus (e.g. R3).
- candidate feeds (`build_candidate_feeds`): our ad + real competitor ads.

Viewers see each feed in their own random order (`order_for`), so position in
the feed doesn't bias the scores.

v0 items are text only (advertiser, title, body). Creatives come with capture.
"""

import random
from dataclasses import dataclass

from whynot.ingest.adlibrary import CompetitorAd


@dataclass(frozen=True)
class FeedItem:
    ad_id: str
    advertiser: str
    title: str
    body: str
    image_url: str | None = None  # data URL or None (text-only v0)

    @classmethod
    def from_ad(cls, ad: CompetitorAd) -> "FeedItem":
        return cls(ad_id=ad.id, advertiser=ad.page_name or "Unknown advertiser",
                   title=(ad.titles or [""])[0], body=(ad.bodies or [""])[0])


Feed = list[FeedItem]


def build_market_feeds(items: list[FeedItem], *, feed_size: int, appearances: int, seed: int = 0) -> list[Feed]:
    """Feeds where each item appears at least `appearances` times, never twice in a feed.

    Each feed takes the `feed_size` items shown least so far, ties broken at
    random. Invariant: shown counts never differ by more than one, so every ad
    gets the same exposure (±1) and meets varied competitors.
    """
    if feed_size < 2:
        raise ValueError("feed_size must be at least 2")
    if appearances < 1:
        raise ValueError("appearances must be at least 1")
    if len({i.ad_id for i in items}) != len(items):
        raise ValueError("ad ids must be unique")
    if len(items) < feed_size:
        raise ValueError("need at least feed_size items")
    rng = random.Random(seed)
    shown = {i.ad_id: 0 for i in items}
    feeds: list[Feed] = []
    while min(shown.values()) < appearances:
        pool = items[:]
        rng.shuffle(pool)
        pool.sort(key=lambda i: shown[i.ad_id])  # stable: random among equals
        feed = pool[:feed_size]
        rng.shuffle(feed)
        for i in feed:
            shown[i.ad_id] += 1
        feeds.append(feed)
    return feeds


def build_candidate_feeds(candidate: FeedItem, competitors: list[FeedItem], *, feed_size: int,
                          n_feeds: int, seed: int = 0) -> list[Feed]:
    """`n_feeds` feeds, each = the candidate + (feed_size - 1) different competitors."""
    if feed_size < 2 or n_feeds < 1:
        raise ValueError("feed_size must be at least 2 and n_feeds at least 1")
    others = list({c.ad_id: c for c in competitors if c.ad_id != candidate.ad_id}.values())
    if len(others) < feed_size - 1:
        raise ValueError("not enough competitor ads for this feed size")
    rng = random.Random(seed)
    return [[candidate, *rng.sample(others, feed_size - 1)] for _ in range(n_feeds)]


def order_for(feed: Feed, key: str) -> Feed:
    """The order one viewer sees this feed in (deterministic per key)."""
    shuffled = feed[:]
    random.Random(key).shuffle(shuffled)
    return shuffled
