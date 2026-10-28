"""Fake SDK clients and settings shared by tests: no network, no keys."""

from pathlib import Path
from types import SimpleNamespace as NS

from whynot.config import Settings


def make_settings(tmp_path: Path, key: str | None = "test") -> Settings:
    return Settings(model_api_key=key, model_base_url="https://example.invalid/v1",
                    baseten_api_key=key, baseten_base_url="https://example.invalid/v1",
                    baseten_model="meta-models/muse-spark-open",
                    cost_log=tmp_path / "costs.jsonl")


class FakeChat:
    def __init__(self, text="OK", prompt=1000, cached=400, completion=50, reasoning=30, finish="stop"):
        self.completions = self
        self._resp = NS(
            choices=[NS(message=NS(content=text), finish_reason=finish)],
            usage=NS(prompt_tokens=prompt, completion_tokens=completion,
                     prompt_tokens_details=NS(cached_tokens=cached),
                     completion_tokens_details=NS(reasoning_tokens=reasoning)),
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
