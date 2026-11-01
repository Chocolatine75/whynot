"""Frozen predictions (E8-4): ranked per ad set, hashed, never rewritten, compared on real CTR within ad sets."""

import json
from datetime import UTC, datetime

import pytest

from whynot.cli import main
from whynot.run.autopilot import DailyMetrics
from whynot.validate.backtest import PastAd
from whynot.validate.predictions import (
    PredictionError,
    build,
    compare,
    digest,
    freeze,
    results_by_variant,
    totals,
    verify,
)

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def plan(tmp_path):
    (tmp_path / "ads").mkdir(exist_ok=True)
    sets = []
    for s, scores in (("heritage.en", {"a1": 11.2, "a2": 10.4, "a3": 1.5}), ("traveller.en", {"b1": 2.0, "b2": 3.0})):
        ads = []
        for vid, score in scores.items():
            (tmp_path / "ads" / f"{vid}.png").write_bytes(vid.encode())
            ads.append({"variant_id": vid, "image_path": f"ads/{vid}.png", "sim_score": score,
                        "body": f"secret copy {vid}", "title": "Talk to grandma"})
        sets.append({"audience": {"persona": s}, "ads": ads})
    return {"ad_sets": sets}


def result(ad_id, impressions, clicks):
    return PastAd(ad_id, "", "", "", None, 10.0, impressions, clicks, 0)


def test_ads_are_ranked_within_each_ad_set_without_their_copy(tmp_path):
    doc = build(plan(tmp_path), tmp_path, name="pilot", now=NOW)
    assert [[a["id"] for a in s["ads"]] for s in doc["ad_sets"]] == [["a1", "a2", "a3"], ["b2", "b1"]]
    assert doc["ad_sets"][0]["ads"][0]["image_sha256"] and doc["simulated"] and doc["created_at"].startswith("2026")
    assert "secret copy" not in json.dumps(doc) and "grandma" not in json.dumps(doc)
    with pytest.raises(PredictionError):
        build({"ad_sets": []}, tmp_path, name="x")


def test_frozen_once_and_verifiable(tmp_path):
    doc = build(plan(tmp_path), tmp_path, name="pilot", now=NOW)
    path, sha = freeze(doc, tmp_path / "pred")
    assert verify(path, sha) and verify(path, sha.upper() + "\n")
    assert digest(json.loads(json.dumps(doc, sort_keys=False))) == sha  # key order never changes the hash
    with pytest.raises(PredictionError, match="never rewritten"):
        freeze(doc, tmp_path / "pred")
    tampered = json.loads(path.read_text())
    tampered["ad_sets"][0]["ads"][0]["rank"], tampered["ad_sets"][0]["ads"][1]["rank"] = 2, 1
    path.write_text(json.dumps(tampered))
    assert not verify(path, sha)


def test_comparison_uses_pairs_within_an_ad_set_outside_the_noise(tmp_path):
    doc = build(plan(tmp_path), tmp_path, name="pilot", now=NOW)
    right = {"a1": result("a1", 20_000, 600), "a2": result("a2", 20_000, 300), "a3": result("a3", 20_000, 100),
             "b2": result("b2", 20_000, 400), "b1": result("b1", 20_000, 200)}
    r = compare(doc, right)
    assert r.accuracy == 1.0 and r.pairs == 4 and r.ads == 5  # 3 + 1 pairs; never a1 vs b1 (other audience)
    wrong = {k: result(k, 20_000, 700 - v.link_clicks) for k, v in right.items()}
    assert compare(doc, wrong).accuracy == 0.0


def test_small_or_noisy_results_are_not_judged(tmp_path):
    doc = build(plan(tmp_path), tmp_path, name="pilot", now=NOW)
    few = {"a1": result("a1", 500, 50), "a2": result("a2", 20_000, 300), "a3": result("a3", 20_000, 301)}
    with pytest.raises(PredictionError, match="clearly different"):
        compare(doc, few)  # a1 under the impression minimum, a2/a3 inside the noise


def test_equal_simulated_scores_predicted_nothing(tmp_path):
    p = plan(tmp_path)
    p["ad_sets"][1]["ads"][0]["sim_score"] = p["ad_sets"][1]["ads"][1]["sim_score"]
    doc = build(p, tmp_path, name="pilot", now=NOW)
    assert compare(doc, {"b1": result("b1", 20_000, 600), "b2": result("b2", 20_000, 100)}).accuracy == 0.5


def test_results_map_back_to_our_variants():
    daily = {"777": [DailyMetrics("2026-11-02", 5.0, 1000, 10, 1), DailyMetrics("2026-11-03", 5.5, 1200, 14, 0)]}
    by_variant = results_by_variant({"campaign": "1", "ad_a1": "777", "ad_a2": "778", "creative_a1": "9"},
                                    totals(daily))
    a1 = by_variant["a1"]
    assert list(by_variant) == ["a1"] and (a1.spend, a1.impressions, a1.link_clicks) == (10.5, 2200, 24)


def test_cli_freezes_then_verifies(tmp_path, capsys):
    (tmp_path / "plan.json").write_text(json.dumps(plan(tmp_path)))
    assert main(["predict", str(tmp_path), "--name", "pilot", "--out", str(tmp_path / "pred")]) == 0
    sha = capsys.readouterr().out.split("sha256 ")[1].split()[0]
    assert main(["predict", "--verify", str(tmp_path / "pred" / "pilot.json"), "--sha", sha]) == 0
    assert main(["predict", "--verify", str(tmp_path / "pred" / "pilot.json"), "--sha", "0" * 64]) == 1
    assert main(["predict", str(tmp_path), "--name", "pilot", "--out", str(tmp_path / "pred")]) == 1  # immutable
    assert main(["predict"]) == 1
