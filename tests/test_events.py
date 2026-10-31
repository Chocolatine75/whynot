"""The agents' shared event log: shape, secrets never written, totals never counted twice."""

import json
import threading

import pytest
from hypothesis import given
from hypothesis import strategies as st

from whynot.events import AgentEvent, EventLog, digest, file_digest, total_usd

SECRET = "EAAsecretTOKEN123456"


def test_an_event_has_an_id_a_time_and_only_its_filled_fields(tmp_path):
    log = EventLog(tmp_path / "events.jsonl")
    row = log.write(AgentEvent("scout", "market", "ok", usd=0.12, outputs={"market.json": "abc"}))
    assert set(row) == {"agent", "stage", "status", "id", "ts", "usd", "outputs"}
    assert log.rows() == [row]


def test_unknown_status_is_refused():
    with pytest.raises(ValueError, match="unknown event status"):
        AgentEvent("scout", "market", "done")


def test_secrets_and_tokens_in_urls_never_reach_the_file(tmp_path):
    log = EventLog(tmp_path / "events.jsonl", secrets=[SECRET, None, "short"])
    log.write({"stage": "x", "status": "error", "error": f"failed with {SECRET}",
               "url": "https://graph.facebook.com/v26.0/ads_archive?q=a&access_token=OTHERTOKEN99&limit=2"})
    text = (tmp_path / "events.jsonl").read_text()
    assert SECRET not in text and "OTHERTOKEN99" not in text
    assert "access_token=[REDACTED]&limit=2" in text and "short" not in log._secrets


def test_a_secret_added_later_is_scrubbed_too(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    log.add_secret(SECRET)
    log.write({"detail": SECRET})
    assert SECRET not in (tmp_path / "e.jsonl").read_text()


def test_rollups_and_unfinished_steps_are_not_counted():
    rows = [{"status": "start", "usd": 9}, {"status": "ok", "usd": 0.5}, {"status": "error", "usd": 0.25},
            {"status": "ok", "usd": 0.75, "rollup": True}, {"status": "cached"}]
    assert total_usd(rows) == pytest.approx(0.75)


def test_digests_are_stable_and_order_free(tmp_path):
    assert digest({"a": 1, "b": [1, 2]}) == digest({"b": [1, 2], "a": 1}) != digest({"a": 2, "b": [1, 2]})
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "x.txt").write_text("1")
    first = file_digest(tmp_path / "d")
    (tmp_path / "d" / "x.txt").write_text("2")
    assert first != file_digest(tmp_path / "d") and file_digest(tmp_path / "missing") is None


def test_concurrent_writers_never_mix_lines(tmp_path):
    log = EventLog(tmp_path / "e.jsonl")
    threads = [threading.Thread(target=lambda i=i: [log.write({"n": i, "detail": "x" * 2000}) for _ in range(20)])
               for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    rows = [json.loads(line) for line in (tmp_path / "e.jsonl").read_text().splitlines()]
    assert len(rows) == 160 and len({r["id"] for r in rows}) == 160


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-.", min_size=8, max_size=40))
def test_property_a_registered_secret_never_survives(tmp_path_factory, secret):
    tmp = tmp_path_factory.mktemp("prop")
    log = EventLog(tmp / "e.jsonl", [secret])
    log.write({"detail": f"before {secret} after", "nested": {"k": [secret]}})
    assert secret not in (tmp / "e.jsonl").read_text(encoding="utf-8")
