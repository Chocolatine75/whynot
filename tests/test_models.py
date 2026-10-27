"""ModelClient records a cost for every call. Uses fake SDK clients: no network."""

from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from whynot.config import Settings
from whynot.costs import CostLedger
from whynot.models import ModelClient, MissingKey


def _settings(tmp_path: Path, key: str | None = "test") -> Settings:
    return Settings(model_api_key=key, model_base_url="https://example.invalid/v1",
                    baseten_api_key=key, baseten_base_url="https://example.invalid/v1",
                    baseten_model="meta-models/muse-spark-open",
                    cost_log=tmp_path / "costs.jsonl")


class FakeChat:
    def __init__(self, text="OK", prompt=1000, cached=400, completion=50):
        self.completions = self
        self._resp = NS(
            choices=[NS(message=NS(content=text))],
            usage=NS(prompt_tokens=prompt, completion_tokens=completion,
                     prompt_tokens_details=NS(cached_tokens=cached)),
        )
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._resp


class FakeOpenAI:
    def __init__(self):
        self.chat = FakeChat()
        self.images = NS(generate=lambda **kw: NS(data=[NS(b64_json="aGk="), NS(b64_json="aGk=")]))
        events = [NS(type="response.output_text.delta", delta="<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>"),
                  NS(type="response.completed")]
        self.responses = NS(create=lambda **kw: iter(events))


def test_chat_records_cost(tmp_path):
    fake = FakeOpenAI()
    client = ModelClient(_settings(tmp_path), meta=fake)
    result = client.chat([{"role": "user", "content": "hi"}], module="test")
    assert result.text == "OK"
    # 600 fresh * 1.25 + 400 cached * 0.15 + 50 out * 4.25, per 1M
    assert result.cost.usd == pytest.approx((600 * 1.25 + 400 * 0.15 + 50 * 4.25) / 1e6)
    assert client.ledger.total("test") == pytest.approx(result.cost.usd)


def test_open_chat_uses_baseten_model(tmp_path):
    fake = FakeOpenAI()
    client = ModelClient(_settings(tmp_path), baseten=fake)
    client.open_chat([{"role": "user", "content": "hi"}], module="viewers")
    assert fake.chat.calls[0]["model"] == "meta-models/muse-spark-open"


def test_image_billed_per_image_returned(tmp_path):
    client = ModelClient(_settings(tmp_path), meta=FakeOpenAI())
    result = client.image("a red fox", module="scenes", n=2)
    assert len(result.images_b64) == 2
    assert result.cost.usd == pytest.approx(0.02)


def test_segment_collects_stream(tmp_path):
    client = ModelClient(_settings(tmp_path), meta=FakeOpenAI())
    result = client.segment("https://example.invalid/cat.jpg", "cat", module="cutout")
    assert result.text.startswith("<|box;")
    assert result.cost.usd == pytest.approx(0.0025)


def test_missing_key(tmp_path):
    client = ModelClient(_settings(tmp_path, key=None))
    with pytest.raises(MissingKey):
        client.chat([{"role": "user", "content": "hi"}], module="test")
    assert CostLedger(tmp_path / "costs.jsonl").total() == 0
