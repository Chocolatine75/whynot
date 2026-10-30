from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from whynot.ingest.adlibrary import CompetitorAd
from whynot.sim.scores import AdScore
from whynot.validate.longevity import advertiser, evaluate, label, select, select_paired
from whynot.validate.stats import stratified_auc, stratified_auc_ci

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


# --- R3 v1: paired selection and within-advertiser AUC ------------------------------------




def test_paired_selection_drops_one_class_advertisers_and_balances_each():
    """Regression for v0: Ling had 24 long-running ads and no short-lived one, so the pooled AUC partly
    measured the brand."""
    ads = [ad(f"l{i}", page="Ling") for i in range(24)]
    ads += [ad(f"m{i}", page="Monzo", ran_days=3, start_days_ago=40) for i in range(5)]
    ads += [ad(f"r{i}", page="Revolut") for i in range(3)]
    ads += [ad(f"rs{i}", page="Revolut", ran_days=2, start_days_ago=40) for i in range(5)]
    chosen = select_paired(ads, as_of=TODAY, per_advertiser=4)
    assert {advertiser(la.ad) for la in chosen} == {"Revolut"}
    assert sum(la.long_running for la in chosen) == 3 and len(chosen) == 6


@settings(max_examples=60, deadline=None)
@given(st.lists(st.tuples(st.sampled_from("ABCDE"), st.booleans()), min_size=1, max_size=60),
       st.integers(1, 5))
def test_paired_selection_is_balanced_within_every_advertiser(spec, cap):
    ads = [ad(i, page=page) if long else ad(i, page=page, ran_days=2, start_days_ago=40)
           for i, (page, long) in enumerate(spec)]
    chosen = select_paired(ads, as_of=TODAY, per_advertiser=cap)
    for page in "ABCDE":
        mine = [la for la in chosen if la.ad.page_id == page]
        n_long = sum(la.long_running for la in mine)
        assert n_long == len(mine) - n_long <= cap


def test_stratified_auc_gives_no_credit_for_recognising_the_brand():
    # brand A's ads all score high, brand B's low: the pooled AUC would reward that, within-brand it can't
    scores = [0.9, 0.8, 0.2, 0.1]
    labels = [True, False, True, False]
    strata = ["A", "A", "B", "B"]
    assert stratified_auc(scores, labels, strata) == 1.0  # within each brand the long ad scores higher
    assert stratified_auc([0.8, 0.9, 0.1, 0.2], labels, strata) == 0.0
    assert stratified_auc([0.5] * 4, labels, strata) == 0.5  # ties count half
    with pytest.raises(ValueError, match="both"):
        stratified_auc([1, 2], [True, True], ["A", "B"])


def test_stratified_auc_ci_resamples_advertisers():
    strata = [f"adv{i // 4}" for i in range(80)]
    labels = [i % 2 == 0 for i in range(80)]
    perfect = [1.0 if y else 0.0 for y in labels]
    lo, hi = stratified_auc_ci(perfect, labels, strata, iterations=200)
    assert lo == hi == 1.0
    noise = [((i * 7919) % 13) / 13 for i in range(80)]
    lo, hi = stratified_auc_ci(noise, labels, strata, iterations=400)
    assert lo < stratified_auc(noise, labels, strata) < hi
