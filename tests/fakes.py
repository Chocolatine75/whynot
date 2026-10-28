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


class ScriptedChat:
    """Fake model for agent tests: `reply(messages, module) -> str`, or a list of answers in order.

    Records every call; each call costs `usd` so budget and cost paths are exercised.
    """

    def __init__(self, reply, usd: float = 0.01):
        self._reply = reply
        self._queue = list(reply) if isinstance(reply, list) else None
        self.calls: list[dict] = []
        self.usd = usd

    def chat(self, messages, *, module, model="muse-spark-1.3", **kwargs):
        self.calls.append({"messages": messages, "module": module, "model": model, **kwargs})
        text = self._queue.pop(0) if self._queue is not None else self._reply(messages, module)
        return NS(text=text, cost=NS(usd=self.usd))

    viewer_chat = chat

    def prompts(self, module=None):
        return [c["messages"][-1]["content"] for c in self.calls if module in (None, c["module"])]
