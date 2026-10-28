"""ModelClient records a cost for every call. Uses fake SDK clients: no network."""


import pytest

from fakes import FakeChat, FakeOpenAI, make_settings
from whynot.costs import CostLedger
from whynot.models import MissingKey, ModelClient, TruncatedOutput, image_data_url


def test_chat_records_cost(tmp_path):
    fake = FakeOpenAI()
    client = ModelClient(make_settings(tmp_path), meta=fake)
    result = client.chat([{"role": "user", "content": "hi"}], module="test")
    assert result.text == "OK"
    # 600 fresh * 1.25 + 400 cached * 0.15 + 50 out * 4.25, per 1M
    assert result.cost.usd == pytest.approx((600 * 1.25 + 400 * 0.15 + 50 * 4.25) / 1e6)
    assert client.ledger.total("test") == pytest.approx(result.cost.usd)


def test_reasoning_tokens_recorded(tmp_path):
    client = ModelClient(make_settings(tmp_path), meta=FakeOpenAI())
    result = client.chat([{"role": "user", "content": "hi"}], module="test")
    assert result.cost.reasoning_tokens == 30
    assert result.finish_reason == "stop"


def test_truncated_empty_answer_raises_but_is_billed(tmp_path):
    # Seen on real calls: reasoning used all of max_tokens, empty content, still billed.
    fake = FakeOpenAI()
    fake.chat = FakeChat(text="", completion=20, reasoning=18, finish="length")
    client = ModelClient(make_settings(tmp_path), meta=fake)
    with pytest.raises(TruncatedOutput):
        client.chat([{"role": "user", "content": "hi"}], module="test", max_tokens=20)
    assert client.ledger.total("test") > 0


def test_truncated_partial_answer_is_returned(tmp_path):
    fake = FakeOpenAI()
    fake.chat = FakeChat(text="Partial ans", finish="length")
    client = ModelClient(make_settings(tmp_path), meta=fake)
    assert client.chat([{"role": "user", "content": "hi"}], module="test").finish_reason == "length"


def test_image_data_url(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"\x89PNG fake")
    assert image_data_url(path).startswith("data:image/png;base64,")
    assert image_data_url(b"abc", "image/webp") == "data:image/webp;base64,YWJj"


def test_viewer_backend_switch(tmp_path):
    from dataclasses import replace
    meta, baseten = FakeOpenAI(), FakeOpenAI()
    on_meta = ModelClient(make_settings(tmp_path), meta=meta, baseten=baseten)
    on_meta.viewer_chat([{"role": "user", "content": "hi"}])
    assert meta.chat.calls[0]["model"] == "muse-spark-1.3" and not baseten.chat.calls
    on_baseten = ModelClient(replace(make_settings(tmp_path), viewer_backend="baseten"), meta=meta, baseten=baseten)
    on_baseten.viewer_chat([{"role": "user", "content": "hi"}])
    assert baseten.chat.calls[0]["model"] == "meta-models/muse-spark-open"


def test_viewers_refuse_contributor_tier(tmp_path):
    from dataclasses import replace
    client = ModelClient(replace(make_settings(tmp_path), viewer_model="muse-spark-1.3-contributor"), meta=FakeOpenAI())
    with pytest.raises(ValueError):
        client.viewer_chat([{"role": "user", "content": "hi"}])


def test_open_chat_uses_baseten_model(tmp_path):
    fake = FakeOpenAI()
    client = ModelClient(make_settings(tmp_path), baseten=fake)
    client.open_chat([{"role": "user", "content": "hi"}], module="viewers")
    assert fake.chat.calls[0]["model"] == "meta-models/muse-spark-open"


def test_image_billed_per_image_returned(tmp_path):
    client = ModelClient(make_settings(tmp_path), meta=FakeOpenAI())
    result = client.image("a red fox", module="scenes", n=2)
    assert len(result.images_b64) == 2
    assert result.cost.usd == pytest.approx(0.02)


def test_segment_collects_stream(tmp_path):
    client = ModelClient(make_settings(tmp_path), meta=FakeOpenAI())
    result = client.segment("https://example.invalid/cat.jpg", "cat", module="cutout")
    assert result.text.startswith("<|box;")
    assert result.cost.usd == pytest.approx(0.0025)


def test_missing_key(tmp_path):
    client = ModelClient(make_settings(tmp_path, key=None))
    with pytest.raises(MissingKey):
        client.chat([{"role": "user", "content": "hi"}], module="test")
    assert CostLedger(tmp_path / "costs.jsonl").total() == 0
