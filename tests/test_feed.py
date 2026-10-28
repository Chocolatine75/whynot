from collections import Counter

import pytest

from whynot.sim.feed import FeedItem, build_candidate_feeds, build_market_feeds, order_for


def items(n):
    return [FeedItem(str(i), f"Brand {i}", f"Title {i}", f"Body {i}") for i in range(n)]


def test_market_feeds_cover_every_item_evenly():
    feeds = build_market_feeds(items(20), feed_size=5, appearances=3, seed=1)
    assert len(feeds) == 12 and all(len(f) == 5 for f in feeds)
    counts = Counter(i.ad_id for f in feeds for i in f)
    assert set(counts.values()) == {3}


def test_no_duplicates_within_a_feed_even_with_topup():
    feeds = build_market_feeds(items(7), feed_size=5, appearances=4, seed=2)
    for f in feeds:
        assert len({i.ad_id for i in f}) == len(f) == 5
    counts = Counter(i.ad_id for f in feeds for i in f)
    assert min(counts.values()) >= 4


def test_market_feeds_deterministic():
    assert build_market_feeds(items(10), feed_size=4, appearances=2, seed=3) == \
        build_market_feeds(items(10), feed_size=4, appearances=2, seed=3)


def test_market_feeds_errors():
    with pytest.raises(ValueError):
        build_market_feeds(items(3), feed_size=5, appearances=1)
    with pytest.raises(ValueError):
        build_market_feeds(items(3), feed_size=1, appearances=1)


def test_candidate_feeds():
    cand = FeedItem("me", "Us", "Ours", "Our ad")
    feeds = build_candidate_feeds(cand, items(10), feed_size=4, n_feeds=6, seed=4)
    assert len(feeds) == 6
    for f in feeds:
        assert f[0] == cand and len({i.ad_id for i in f}) == 4


def test_order_for_is_a_stable_permutation():
    feed = items(6)
    a, b = order_for(feed, "viewer-1"), order_for(feed, "viewer-1")
    assert a == b and sorted(i.ad_id for i in a) == sorted(i.ad_id for i in feed)
    assert any(order_for(feed, f"v{k}") != feed for k in range(5))
