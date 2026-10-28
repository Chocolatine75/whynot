import pytest

from whynot.costs import (
    CostEvent,
    CostLedger,
    UnknownModelPrice,
    image_cost,
    segment_cost,
    token_cost,
    transcribe_cost,
)


def test_token_cost_spark():
    # 1M fresh input + 1M output on Spark = $1.25 + $4.25
    assert token_cost("muse-spark-1.3", 1_000_000, 0, 1_000_000) == pytest.approx(5.50)


def test_cached_tokens_are_a_subset_of_input():
    # 1M input of which 800k cached on Wonder: 200k * $4 + 800k * $0.20 per 1M
    assert token_cost("muse-wonder-1.0", 1_000_000, 800_000, 0) == pytest.approx(0.80 + 0.16)


def test_cached_never_exceeds_input():
    assert token_cost("muse-spark-1.3", 100, 500, 0) == token_cost("muse-spark-1.3", 100, 100, 0)


def test_unknown_model_raises():
    with pytest.raises(UnknownModelPrice):
        token_cost("gpt-unknown", 1, 0, 1)


def test_unit_prices():
    assert image_cost("muse-image-1.0", 3) == pytest.approx(0.03)
    assert segment_cost("sam-3.1", images=1000) == pytest.approx(2.50)
    # video requests are billed at least 50 frames
    assert segment_cost("sam-3.1", video_frames=10) == pytest.approx(50 * 0.20 / 1000)
    assert transcribe_cost("muse-voice-transcribe-1.0", 3600.0) == pytest.approx(0.18)
    assert transcribe_cost("muse-voice-transcribe-1.0", 0.2) == pytest.approx(0.18 / 3600)  # rounded up


def test_ledger_appends_and_totals(tmp_path):
    ledger = CostLedger(tmp_path / "costs.jsonl")
    ledger.record(CostEvent(module="strategy", model="muse-wonder-1.0", usd=0.5))
    ledger.record(CostEvent(module="viewers", model="meta-models/muse-spark-open", usd=0.25))
    ledger.record(CostEvent(module="viewers", model="meta-models/muse-spark-open", usd=0.25))
    assert ledger.total() == pytest.approx(1.0)
    assert ledger.total("viewers") == pytest.approx(0.5)
    assert ledger.by_module() == {"strategy": pytest.approx(0.5), "viewers": pytest.approx(0.5)}


def test_empty_ledger(tmp_path):
    assert CostLedger(tmp_path / "missing.jsonl").total() == 0
