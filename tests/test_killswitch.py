"""Kill switch: everything whynot created is paused, campaigns first, even from a half-finished publish."""

import json

import httpx
import pytest

from test_publish import TOKEN, FakeGraph
from whynot.agency.memory import AdRecord, Memory
from whynot.run.autopilot import Policy
from whynot.run.killswitch import stop, targets
from whynot.run.meta import Account, MarketingClient
from whynot.run.publish import PublishState

ACT = "act_42"


def make_client(graph: FakeGraph) -> MarketingClient:
    return MarketingClient(Account("42", TOKEN), http=httpx.Client(transport=httpx.MockTransport(graph)),
                           sleep=lambda s: None, retries=0)


def published(graph: FakeGraph, run, refs: list[str], account: str = ACT) -> dict[str, str]:
    """A publish.json as `whynot publish` leaves it, with real objects in the fake account."""
    objects = {}
    for ref in refs:
        kind = "campaigns" if ref == "campaign" else ref.split("_")[0] + "s"
        objects[ref] = graph._new(kind, {"status": "ACTIVE"})
    run.mkdir(parents=True, exist_ok=True)
    PublishState("live", account, "traffic", objects=objects, status="active").save(run / "publish.json")
    return objects


def status_posts(graph: FakeGraph) -> list[str]:
    return [path for method, path, fields in graph.calls if method == "POST" and fields.get("status") == "PAUSED"]


def test_everything_is_paused_campaign_first(tmp_path):
    graph = FakeGraph()
    objects = published(graph, tmp_path / "run", ["campaign", "adset_fr", "adset_gb", "creative_1", "ad_1", "ad_2"])
    report = stop([tmp_path / "run"], make_client(graph), by="Tom")
    assert report.ok and len(report.paused) == 5  # the creative has no status
    assert all(graph.objects[objects[r]]["status"] == "PAUSED" for r in objects if not r.startswith("creative"))
    assert status_posts(graph)[0] == objects["campaign"]
    assert report.seconds < 10


def test_a_half_finished_publish_is_stopped_too(tmp_path):
    graph = FakeGraph()
    objects = published(graph, tmp_path / "run", ["campaign", "adset_fr"])  # crashed before the ads
    report = stop([tmp_path / "run"], make_client(graph), by="Tom")
    assert {t.meta_id for t in report.paused} == set(objects.values())


def test_daily_loop_ads_are_paused_and_marked_in_memory(tmp_path):
    graph = FakeGraph()
    run = tmp_path / "run"
    real = graph._new("ads", {"status": "ACTIVE"})
    memory = Memory(run / "agency" / "memory.json")
    memory.add(AdRecord("day-1-pov", "2026-11-02", "pov", "p", "a", "hook", status="live", meta_ad_id=real))
    memory.add(AdRecord("day-1-sim", "2026-11-02", "pov", "p", "b", "hook", status="live", meta_ad_id="sim-x"))
    memory.save()
    report = stop([run], make_client(graph), by="Tom")
    assert [t.meta_id for t in report.paused] == [real] and graph.objects[real]["status"] == "PAUSED"
    after = Memory(run / "agency" / "memory.json")
    assert after.ads["day-1-pov"].status == "paused" and "kill switch by Tom" in after.ads["day-1-pov"].notes[-1]
    assert after.ads["day-1-sim"].status == "live"  # a simulated ad has nothing to pause on Meta


def test_one_failure_does_not_stop_the_rest_and_is_reported(tmp_path):
    graph = FakeGraph()
    objects = published(graph, tmp_path / "run", ["campaign", "adset_fr", "ad_1"])
    graph.objects.pop(objects["adset_fr"])  # Meta no longer knows it: the status call fails
    report = stop([tmp_path / "run"], make_client(graph), by="Tom")
    assert not report.ok and list(report.failed) == [objects["adset_fr"]]
    assert graph.objects[objects["campaign"]]["status"] == graph.objects[objects["ad_1"]]["status"] == "PAUSED"
    rows = [json.loads(x) for x in (tmp_path / "run" / "actions.jsonl").read_text().splitlines()]
    assert sorted(r["outcome"] for r in rows) == ["execute", "execute", "refused"]


def test_it_works_whatever_the_autonomy_level_and_logs_who(tmp_path):
    graph = FakeGraph()
    published(graph, tmp_path / "run", ["campaign"])
    report = stop([tmp_path / "run"], make_client(graph), by="Tom", policy=Policy())  # dry_run
    assert report.ok and len(report.paused) == 1
    log = (tmp_path / "run" / "actions.jsonl").read_text()
    assert "kill switch by Tom" in log and TOKEN not in log


def test_runs_on_another_account_are_left_alone(tmp_path):
    graph = FakeGraph()
    published(graph, tmp_path / "sandbox-run", ["campaign"], account="act_7")
    report = stop([tmp_path / "sandbox-run"], make_client(graph), by="Tom")
    assert report.skipped == [str(tmp_path / "sandbox-run")] and not status_posts(graph)
    assert targets(tmp_path / "sandbox-run", ACT) == ([], True)


def test_nothing_to_stop_and_anonymous_switch(tmp_path):
    graph = FakeGraph()
    assert stop([tmp_path / "empty"], make_client(graph), by="Tom").paused == []
    with pytest.raises(ValueError, match="who"):
        stop([tmp_path], make_client(graph), by=" ")


def test_cli_without_a_token_says_what_to_set(tmp_path, monkeypatch, capsys):
    from whynot.cli import main

    for var in ("META_SANDBOX_TOKEN", "META_SANDBOX_AD_ACCOUNT_ID"):  # never a real account from a test
        monkeypatch.setenv(var, "")
    assert main(["stop", str(tmp_path), "--by", "Tom"]) == 1
    assert "META_SANDBOX_TOKEN" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["stop", str(tmp_path)])  # --by is required
