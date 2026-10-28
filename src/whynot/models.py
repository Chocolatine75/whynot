"""The only way whynot calls a model.

`ModelClient` wraps the Meta Model API (OpenAI-compatible) and Muse Spark Open on
Baseten. Every call records a `CostEvent` with the module that made it, so the
cost counter is real and every run can be audited.

Rule: never call the OpenAI SDK directly elsewhere in the code base.
"""

import base64
import mimetypes
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

from whynot.config import Settings, load_settings
from whynot.costs import CostEvent, CostLedger, check_priced, image_cost, segment_cost, token_cost

SPARK = "muse-spark-1.3"
SPARK_CONTRIBUTOR = "muse-spark-1.3-contributor"  # Meta trains on this data: synthetic content only
WONDER = "muse-wonder-1.0"
IMAGE = "muse-image-1.0"
SAM = "sam-3.1"


class MissingKey(RuntimeError):
    """Raised when a call needs an API key that is not set in .env."""


class BudgetExceeded(RuntimeError):
    """The run's model budget is spent: no further call is made."""


class TruncatedOutput(RuntimeError):
    """The model hit max_tokens before writing any answer (reasoning used it all).

    Muse Spark reasons before answering, even at reasoning_effort="minimal", and
    reasoning tokens count against max_tokens. The call is still billed (and
    logged). Raise max_tokens.
    """


def image_data_url(source: str | Path | bytes, mime: str | None = None) -> str:
    """Base64 data URL for an image, so the model never has to download it."""
    if isinstance(source, bytes):
        data = source
        mime = mime or "image/jpeg"
    else:
        path = Path(source)
        data = path.read_bytes()
        mime = mime or mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


@dataclass
class ChatResult:
    text: str
    cost: CostEvent
    raw: Any
    finish_reason: str | None = None


@dataclass
class ImageResult:
    images_b64: list[str]
    cost: CostEvent


@dataclass
class SegmentResult:
    text: str  # SAM 3.1 special-token output; parse with whynot.assets.sam
    cost: CostEvent


def _usage_tokens(usage: Any) -> tuple[int, int, int, int]:
    """(input, cached, output, reasoning) from a Chat Completions usage object."""
    if usage is None:
        return 0, 0, 0, 0
    cached = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0
    reasoning = getattr(getattr(usage, "completion_tokens_details", None), "reasoning_tokens", 0) or 0
    return usage.prompt_tokens or 0, cached, usage.completion_tokens or 0, reasoning


class ModelClient:
    def __init__(self, settings: Settings | None = None, ledger: CostLedger | None = None,
                 meta: OpenAI | None = None, baseten: OpenAI | None = None, *, budget_usd: float | None = None):
        """`budget_usd`: hard cap on what this client may spend; calls stop once it is reached
        (a call already in flight can overshoot by its own cost)."""
        self.settings = settings or load_settings()
        self.ledger = ledger or CostLedger(self.settings.cost_log)
        self._meta = meta
        self._baseten = baseten
        self.budget_usd = budget_usd
        self.spent_usd = 0.0
        self._spent_lock = threading.Lock()

    def _check_budget(self) -> None:
        if self.budget_usd is not None and self.spent_usd >= self.budget_usd:
            raise BudgetExceeded(f"model budget of ${self.budget_usd:.2f} spent (${self.spent_usd:.3f})")

    def _record(self, event: CostEvent) -> CostEvent:
        with self._spent_lock:
            self.spent_usd += event.usd
        return self.ledger.record(event)

    # --- clients -----------------------------------------------------------

    @property
    def meta(self) -> OpenAI:
        if self._meta is None:
            if not self.settings.model_api_key:
                raise MissingKey("MODEL_API_KEY is not set in .env")
            self._meta = OpenAI(api_key=self.settings.model_api_key,
                                base_url=self.settings.model_base_url)
        return self._meta

    @property
    def baseten(self) -> OpenAI:
        if self._baseten is None:
            if not self.settings.baseten_api_key:
                raise MissingKey("BASETEN_API_KEY is not set in .env")
            self._baseten = OpenAI(api_key=self.settings.baseten_api_key,
                                   base_url=self.settings.baseten_base_url)
        return self._baseten

    # --- text --------------------------------------------------------------

    def chat(self, messages: list[dict], *, module: str, model: str = SPARK, **kwargs) -> ChatResult:
        """Chat completion on the Meta Model API (Spark, Spark Contributor, Wonder)."""
        return self._chat(self.meta, model, messages, module, **kwargs)

    def open_chat(self, messages: list[dict], *, module: str, **kwargs) -> ChatResult:
        """Chat completion on Muse Spark Open (open weights, served by Baseten)."""
        return self._chat(self.baseten, self.settings.baseten_model, messages, module, **kwargs)

    def viewer_chat(self, messages: list[dict], *, module: str = "viewers", **kwargs) -> ChatResult:
        """Chat for viewer agents, on the backend chosen by VIEWER_BACKEND.

        "meta": Muse Spark on the Meta API (works today). "baseten": Muse Spark Open.
        Never the Contributor tier: feeds can contain partner ads.
        """
        backend = self.settings.viewer_backend
        if backend == "baseten":
            return self.open_chat(messages, module=module, **kwargs)
        if backend == "meta":
            if "contributor" in self.settings.viewer_model:
                raise ValueError("viewers must not use the Contributor tier (partner data)")
            return self.chat(messages, module=module, model=self.settings.viewer_model, **kwargs)
        raise ValueError(f"unknown VIEWER_BACKEND: {backend!r}")

    def _chat(self, client: OpenAI, model: str, messages: list[dict], module: str, **kwargs) -> ChatResult:
        check_priced(model)
        self._check_budget()
        response = client.chat.completions.create(model=model, messages=messages, **kwargs)  # type: ignore[arg-type]
        input_tokens, cached, output_tokens, reasoning = _usage_tokens(response.usage)
        event = self._record(CostEvent(
            module=module, model=model,
            usd=token_cost(model, input_tokens, cached, output_tokens),
            input_tokens=input_tokens, cached_tokens=cached, output_tokens=output_tokens,
            reasoning_tokens=reasoning,
        ))
        if not response.choices:
            raise RuntimeError(f"{model} returned no choices")
        choice = response.choices[0]
        text = choice.message.content or ""
        finish = getattr(choice, "finish_reason", None)
        if finish == "length" and not text.strip():
            raise TruncatedOutput(
                f"{model} used all {output_tokens} output tokens ({reasoning} reasoning) before answering; "
                "raise max_tokens")
        return ChatResult(text=text, cost=event, raw=response, finish_reason=finish)

    # --- images ------------------------------------------------------------

    def image(self, prompt: str, *, module: str, n: int = 1, size: str = "auto", **kwargs) -> ImageResult:
        """Generate images with Muse Image. Billed per image returned."""
        self._check_budget()
        response = self.meta.images.generate(model=IMAGE, prompt=prompt, n=n, size=size,
                                             response_format="b64_json", **kwargs)
        images = [d.b64_json for d in response.data if getattr(d, "b64_json", None)]
        event = self._record(CostEvent(
            module=module, model=IMAGE, usd=image_cost(IMAGE, len(images)), images=len(images),
        ))
        return ImageResult(images_b64=images, cost=event)

    # --- segmentation ------------------------------------------------------

    def segment(self, image_url: str, concept: str, *, module: str,
                include_confidence: bool = False) -> SegmentResult:
        """Segment `concept` in one image with SAM 3.1 (Responses API, streamed text)."""
        request: dict[str, Any] = {
            "model": SAM,
            "input": [{"role": "user", "content": [
                {"type": "input_text", "text": concept},
                {"type": "input_image", "image_url": image_url},
            ]}],
            "stream": True,
        }
        if include_confidence:
            request["extra_body"] = {"include_confidence": "true"}
        self._check_budget()
        chunks: list[str] = []
        ok = False
        try:
            for event in self.meta.responses.create(**request):
                if getattr(event, "type", "") == "response.output_text.delta":
                    chunks.append(event.delta)
            ok = True
        finally:  # the request is billed even if the stream breaks
            cost = self._record(CostEvent(
                module=module, model=SAM, usd=segment_cost(SAM, images=1), images=1, ok=ok,
            ))
        return SegmentResult(text="".join(chunks), cost=cost)

    # --- discovery ---------------------------------------------------------

    def list_meta_models(self) -> list[str]:
        return sorted(m.id for m in self.meta.models.list())
