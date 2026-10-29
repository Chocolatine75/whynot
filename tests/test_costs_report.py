"""`whynot costs`: spend by day, module, model and run, from the ledgers on disk."""

import calendar
import json
import time

import pytest

from whynot.cli import main
from whynot.costs import CostEvent, CostLedger, collect_ledgers, format_report, spend_report


def ts(day: str) -> float:
    """Noon UTC on that day."""
    return calendar.timegm(time.strptime(day + " 12:00", "%Y-%m-%d %H:%M"))


@pytest.fixture
def outputs(tmp_path):
    scripts = CostLedger(tmp_path / "costs.jsonl")
    scripts.record(CostEvent("viewers", "muse-spark-1.3", 0.50, ts=ts("2026-10-28")))
    run = CostLedger(tmp_path / "runs" / "20261029-vietbuddy" / "costs.jsonl")
    run.record(CostEvent("strategy", "muse-wonder-1.0", 1.00, ts=ts("2026-10-29")))
    run.record(CostEvent("viewers", "muse-spark-1.3", 0.25, ok=False, ts=ts("2026-10-29")))  # billed though failed
    run.record(CostEvent("viewers", "muse-spark-1.3", 0.0, source="cache", ts=ts("2026-10-29")))
    run.record(CostEvent("strategy", "muse-wonder-1.0", 0.0, source="cassette", ts=ts("2026-10-30")))
    return tmp_path


def test_totals_by_every_axis(outputs):
    r = spend_report(collect_ledgers(outputs))
    assert r.usd == pytest.approx(1.75) and r.calls == 3 and r.free_calls == 2
    assert r.by_day == {"2026-10-28": 0.5, "2026-10-29": 1.25}
    assert r.by_module == {"viewers": 0.75, "strategy": 1.0}
    assert r.by_model == {"muse-spark-1.3": 0.75, "muse-wonder-1.0": 1.0}
    assert r.by_run == {"scripts": 0.5, "20261029-vietbuddy": 1.25}
    assert r.remaining_usd == pytest.approx(60 - 1.75)


def test_since_is_inclusive(outputs):
    r = spend_report(collect_ledgers(outputs), since="2026-10-29")
    assert r.usd == pytest.approx(1.25) and "2026-10-28" not in r.by_day


def test_the_report_warns_above_two_thirds_of_the_budget(outputs):
    assert "only critical-path" not in format_report(spend_report(collect_ledgers(outputs)))
    assert "only critical-path" in format_report(spend_report(collect_ledgers(outputs), budget_usd=2.0))


def test_empty_outputs_folder(tmp_path):
    r = spend_report(collect_ledgers(tmp_path))
    assert r.usd == 0 and r.calls == 0 and "$60 budget" in format_report(r)


def test_cli(outputs, capsys):
    assert main(["costs", "--outputs", str(outputs), "--since", "2026-10-29", "--budget", "10"]) == 0
    out = capsys.readouterr().out
    assert "model spend $1.25 of $10 budget" in out and "20261029-vietbuddy" in out
    with pytest.raises(SystemExit):
        main(["costs", "--since", "yesterday"])


def test_old_ledgers_without_a_source_are_billed_calls(tmp_path):
    (tmp_path / "costs.jsonl").write_text(json.dumps({"module": "m", "model": "x", "usd": 0.1, "ts": ts("2026-10-27")})
                                          + "\n")
    assert spend_report(collect_ledgers(tmp_path)).calls == 1
