from datetime import date, timedelta

import pytest

from whynot.ingest.adlibrary import CompetitorAd
from whynot.sim.scores import AdScore
from whynot.validate.longevity import evaluate, label, select

TODAY = date(2026, 10, 28)


def ad(i, page="P", body=None, start_days_ago=100, ran_days=None):
    start = TODAY - timedelta(days=start_days_ago)
    stop = start + timedelta(days=ran_days) if ran_days is not None else None
    return CompetitorAd(id=str(i), page_id=page, page_name=page, bodies=[body if body is not None else f"copy {i}"],
                        titles=[], start_date=start, stop_date=stop, platforms=[], eu_total_reach=None,
                        target_ages=[], target_gender=None)


def test_label_rules():
    assert label(ad(1, start_days_ago=90), as_of=TODAY) is True
    assert label(ad(2, start_days_ago=30), as_of=TODAY) is None  # running but too young
    assert label(ad(3, start_days_ago=200, ran_days=5), as_of=TODAY) is False
    assert label(ad(4, start_days_ago=200, ran_days=40), as_of=TODAY) is None  # in between


def test_select_dedupes_same_copy_and_skips_empty_text():
    ads = [ad(1, body="Same copy"), ad(2, body="same   COPY"), ad(3, body=""),
           ad(4, ran_days=3, start_days_ago=50), ad(5, ran_days=2, start_days_ago=60)]
    chosen = select(ads, as_of=TODAY, per_class=5)
    ids = {la.ad.id for la in chosen}
    assert len([la for la in chosen if la.long_running]) == 1  # 1 and 2 are the same copy
    assert "3" not in ids
    assert len(chosen) == 2  # balanced: 1 long, 1 short


def test_select_balances_across_advertisers():
    ads = [ad(f"a{i}", page="A") for i in range(10)] + [ad(f"b{i}", page="B") for i in range(10)]
    ads += [ad(f"s{i}", page="A" if i % 2 else "B", ran_days=1, start_days_ago=30) for i in range(10)]
    chosen = select(ads, as_of=TODAY, per_class=4, seed=1)
    longs = [la.ad.page_id for la in chosen if la.long_running]
    assert sorted(longs) == ["A", "A", "B", "B"]


def score(i, pref, intent=3.0):
    return AdScore(str(i), 5, pref, intent, 0.5, 0.5, 0.5, [])


def test_evaluate_perfect_separation():
    labelled = select([ad(i) for i in range(5)] + [ad(10 + i, ran_days=1) for i in range(5)],
                      as_of=TODAY, per_class=5)
    scores = {la.ad.id: score(la.ad.id, 2.0 if la.long_running else 0.5) for la in labelled}
    result = evaluate(labelled, scores)
    assert result.auc_preference == 1.0
    assert (result.n_long, result.n_short, result.scored_ads) == (5, 5, 10)
    assert result.auc_intent == pytest.approx(0.5)  # all intents equal
    assert 0.0 <= result.auc_copy_length <= 1.0
