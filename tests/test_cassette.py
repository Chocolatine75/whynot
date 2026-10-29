"""Cassettes: record model answers once, replay them for free, never touch the network in replay."""

import json

import pytest

from fakes import FakeChat, FakeOpenAI, make_settings
from whynot.agency.create import CreateConfig, create
from whynot.cassette import REDACTED, Cassette, CassetteMissing, Recording, request_key, scrub
from whynot.costs import CostLedger
from whynot.models import ModelClient, TruncatedOutput
from world import FakeMeta, clients

MSGS = [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"}]


class Exploding:
    """An SDK client that fails the test if anything touches it (= the network)."""

    def __getattr__(self, name):
        raise AssertionError(f"network touched in replay mode ({name})")


def client(tmp_path, mode, meta=None, **kw):
    return ModelClient(make_settings(tmp_path), meta=meta or Exploding(), baseten=Exploding(),
                       cassette=Cassette(tmp_path / "cassettes", mode), **kw)


def test_key_ignores_dict_order_but_not_content():
    a = request_key("m", [{"role": "user", "content": "x"}], {"max_tokens": 10, "reasoning_effort": "low"})
    b = request_key("m", [{"content": "x", "role": "user"}], {"reasoning_effort": "low", "max_tokens": 10})
    assert a == b
    assert a != request_key("m", [{"role": "user", "content": "y"}], {"max_tokens": 10, "reasoning_effort": "low"})
    assert a != request_key("m", [{"role": "user", "content": "x"}], {"max_tokens": 10, "reasoning_effort": "high"})
    assert a != request_key("other", [{"role": "user", "content": "x"}], {"max_tokens": 10, "reasoning_effort": "low"})


def test_scrub_removes_known_secrets_and_token_shapes():
    text = "key sk-live-123 and EAAB" + "x" * 30 + " and https://x.com/?a=1&access_token=abc123&b=2"
    out = scrub(text, ("sk-live-123", None, ""))
    assert "sk-live-123" not in out and "EAAB" not in out and "abc123" not in out
    assert out.count(REDACTED) == 3 and "&b=2" in out


def test_unknown_mode_is_refused(tmp_path):
    with pytest.raises(ValueError, match="cassette mode"):
        Cassette(tmp_path, "replya")


def test_record_then_replay_gives_the_same_answer_for_free(tmp_path):
    rec = client(tmp_path, "record", meta=FakeOpenAI())
    first = rec.chat(MSGS, module="strategy", max_tokens=100)
    assert first.cost.usd > 0
    stored = list((tmp_path / "cassettes").glob("*.json"))
    assert len(stored) == 1
    assert "be brief" not in stored[0].read_text()  # the request (possibly partner data) is never stored

    play = client(tmp_path, "replay", budget_usd=0.0)  # replay costs nothing, so even a $0 budget works
    again = play.chat(MSGS, module="strategy", max_tokens=100)
    assert again.text == first.text and again.finish_reason == first.finish_reason
    assert again.cost.usd == 0 and again.cost.source == "cassette" and again.raw is None
    assert play.spent_usd == 0


def test_replay_without_a_recording_fails_loudly_and_offline(tmp_path):
    play = client(tmp_path, "replay")
    with pytest.raises(CassetteMissing, match="WHYNOT_CASSETTE=record"):
        play.chat(MSGS, module="strategy", max_tokens=100)
    with pytest.raises(CassetteMissing):  # a different parameter is a different request
        client(tmp_path, "record", meta=FakeOpenAI()).chat(MSGS, module="s", max_tokens=100)
        play.chat(MSGS, module="s", max_tokens=101)


def test_replay_reproduces_a_truncated_answer(tmp_path):
    fake = FakeOpenAI()
    fake.chat = FakeChat(text="", finish="length")
    with pytest.raises(TruncatedOutput):
        client(tmp_path, "record", meta=fake).chat(MSGS, module="s")
    with pytest.raises(TruncatedOutput):
        client(tmp_path, "replay").chat(MSGS, module="s")


def test_images_and_segmentation_are_refused_in_replay(tmp_path):
    play = client(tmp_path, "replay")
    with pytest.raises(CassetteMissing):
        play.image("a cat", module="scenes")
    with pytest.raises(CassetteMissing):
        play.segment("data:image/png;base64,AA==", "phone screen", module="cutout")


def test_secrets_never_reach_a_recording(tmp_path):
    settings = make_settings(tmp_path, key="sk-model-SECRET")
    fake = FakeOpenAI()
    fake.chat = FakeChat(text="echo sk-model-SECRET and EAA" + "Z" * 25)
    cassette = Cassette(tmp_path / "c", "record", secrets=(settings.model_api_key,))
    ModelClient(settings, meta=fake, cassette=cassette).chat(MSGS, module="s")
    body = next((tmp_path / "c").glob("*.json")).read_text()
    assert "SECRET" not in body and "ZZZZ" not in body


def test_off_mode_neither_reads_nor_writes(tmp_path):
    c = Cassette(tmp_path / "c", "off")
    c.put("k", Recording("m", "s", "stale", "stop"))  # even with a recording on disk...
    fake = FakeOpenAI()
    result = ModelClient(make_settings(tmp_path), meta=fake, cassette=c).chat(MSGS, module="s")
    assert result.text == "OK" and len(fake.chat.calls) == 1  # ...off mode calls the API
    assert [p.name for p in (tmp_path / "c").glob("*.json")] == ["k.json"]


OUTPUTS = ("strategy.json", "variants.json", "simulation.json", "evolution.json", "plan.json")


def without_cost(data):
    """The output minus what it cost: a replay is free by design, everything else must match."""
    if isinstance(data, dict):
        return {k: without_cost(v) for k, v in data.items() if k != "usd"}
    if isinstance(data, list):
        return [without_cost(v) for v in data]
    return data


def test_a_whole_create_run_replays_identically_without_network(tmp_path):
    cfg = CreateConfig(app_ref="https://apps.apple.com/us/app/linguaapp/id1234567890", countries=["FR", "GB"],
                       daily_cap_eur=20.0)
    cassettes = tmp_path / "cassettes"

    c, meta, _ = clients(tmp_path / "a")
    c.model = ModelClient(make_settings(tmp_path / "a"), CostLedger(tmp_path / "a" / "costs.jsonl"), meta=meta,
                          cassette=Cassette(cassettes, "record"))
    create(cfg, c, tmp_path / "a" / "run")
    assert meta.requests and len(list(cassettes.glob("*.json"))) <= len(meta.requests)

    c2, _, _ = clients(tmp_path / "b", meta=FakeMeta(reply=lambda *a: pytest.fail("model called in replay")))
    c2.model = ModelClient(make_settings(tmp_path / "b"), CostLedger(tmp_path / "b" / "costs.jsonl"),
                           meta=Exploding(), cassette=Cassette(cassettes, "replay"))
    create(cfg, c2, tmp_path / "b" / "run")
    for name in OUTPUTS:
        a, b = ((tmp_path / x / "run" / name).read_text() for x in "ab")
        assert without_cost(json.loads(a)) == without_cost(json.loads(b)), name
    for image in (tmp_path / "a" / "run" / "ads").glob("*.png"):
        assert image.read_bytes() == (tmp_path / "b" / "run" / "ads" / image.name).read_bytes()
    replayed = [json.loads(line) for line in (tmp_path / "b" / "costs.jsonl").read_text().splitlines()]
    assert replayed and all(e["usd"] == 0 and e["source"] == "cassette" for e in replayed)
