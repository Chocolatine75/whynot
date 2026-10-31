"""The agency's memory of a client: every ad, its idea, its status, its results; saved atomically."""

import json

import pytest

from whynot.agency.memory import AdRecord, Memory
from whynot.run.autopilot import DailyMetrics


def rec(key, fmt="pov", angle="a1", persona="p1", hook="h", status="proposed"):
    return AdRecord(key, "2026-11-01", fmt, persona, angle, hook, status=status)


def test_memory_roundtrips_and_refuses_duplicates(tmp_path):
    m = Memory(tmp_path / "memory.json")
    m.add(rec("x"))
    m.record_metrics("x", [DailyMetrics("2026-11-02", 5.0, 700, 8, 1)])
    m.set_status("x", "live", "approved by Matteo", day="2026-11-02")
    m.save()
    again = Memory(tmp_path / "memory.json")
    assert again.ads["x"].metrics[0].conversions == 1 and again.ads["x"].launched == "2026-11-02"
    assert again.ads["x"].notes == ["2026-11-02 live: approved by Matteo"]
    with pytest.raises(ValueError, match="already"):
        again.add(rec("x"))
    with pytest.raises(ValueError, match="status"):
        again.set_status("x", "deleted", "?")
    assert not list(tmp_path.glob(".memory-*"))  # no temp file left behind


def test_a_day_seen_again_replaces_the_old_numbers():
    m = Memory.__new__(Memory)
    m.ads = {"x": rec("x")}
    m.record_metrics("x", [DailyMetrics("2026-11-02", 5.0, 700, 8, 1), DailyMetrics("2026-11-01", 4.0, 500, 5, 0)])
    m.record_metrics("x", [DailyMetrics("2026-11-02", 5.2, 720, 9, 2)])  # Meta attributed one more install
    r = m.ads["x"]
    assert [d.day for d in r.metrics] == ["2026-11-01", "2026-11-02"] and r.conversions == 2
    assert r.spend == 9.2 and r.cpa == pytest.approx(4.6) and r.ctr == pytest.approx(14 / 1220)


def test_learnings_group_judged_ads_by_format_angle_and_persona(tmp_path):
    m = Memory(tmp_path / "m.json")
    for key, fmt, spend, conv in (("a", "pov", 12, 3), ("b", "pov", 12, 1), ("c", "rating", 12, 0), ("d", "pov", 2, 9)):
        m.add(rec(key, fmt=fmt))
        m.record_metrics(key, [DailyMetrics("2026-11-02", spend, 1000, 10, conv)])
    learn = m.learnings(min_spend=10)
    assert learn["format"]["pov"] == {"ads": 2, "spend": 24.0, "conversions": 4, "cpa": 6.0}  # "d" spent too little
    assert learn["format"]["rating"]["cpa"] == float("inf")
    assert ("pov", "p1", "a1", "h") in m.ideas()


def test_memory_holds_no_secret(tmp_path):
    m = Memory(tmp_path / "m.json")
    m.add(rec("x"))
    m.save()
    blob = (tmp_path / "m.json").read_text()
    assert "access_token" not in blob and "EAA" not in blob and json.loads(blob)["ads"]["x"]["format"] == "pov"
