"""The only way whynot calls a model.

`ModelClient` wraps the Meta Model API (OpenAI-compatible) and Muse Spark Open on
Baseten. Every call records a `CostEvent` with the module that made it, so the
cost counter is real and every run can be audited.

Rule: never call the OpenAI SDK directly elsewhere in the code base.
"""

from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from whynot.config import Settings, load_settings
from whynot.costs import CostEvent, CostLedger, image_cost, segment_cost, token_cost

SPARK = "muse-spark-1.3"
SPARK_CONTRIBUTOR = "muse-spark-1.3-contributor"  # Meta trains on this data: synthetic content only
WONDER = "muse-wonder-1.0"
IMAGE = "muse-image-1.0"
SAM = "sam-3.1"


class MissingKey(RuntimeError):
    """Raised when a call needs an API key that is not set in .env."""


@dataclass
class ChatResult:
    text: str
    cost: CostEvent
    raw: Any


@dataclass
class ImageResult:
    images_b64: list[str]
    cost: CostEvent


@dataclass
class SegmentResult:
    text: str  # SAM 3.1 special-token output; parse with whynot.sam
    cost: CostEvent


def _usage_tokens(usage: Any) -> tuple[int, int, int]:
    """(input, cached, output) from a Chat Completions usage object."""
    if usage is None:
        return 0, 0, 0
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) or 0
    return usage.prompt_tokens or 0, cached, usage.completion_tokens or 0


class ModelClient:
    def __init__(self, settings: Settings | None = None, ledger: CostLedger | None = None,
                 meta: OpenAI | None = None, baseten: OpenAI | None = None):
        self.settings = settings or load_settings()
        self.ledger = ledger or CostLedger(self.settings.cost_log)
        self._meta = meta
        self._baseten = baseten

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

    def _chat(self, client: OpenAI, model: str, messages: list[dict], module: str, **kwargs) -> ChatResult:
        response = client.chat.completions.create(model=model, messages=messages, **kwargs)
        input_tokens, cached, output_tokens = _usage_tokens(response.usage)
        event = self.ledger.record(CostEvent(
            module=module, model=model,
            usd=token_cost(model, input_tokens, cached, output_tokens),
            input_tokens=input_tokens, cached_tokens=cached, output_tokens=output_tokens,
        ))
        text = response.choices[0].message.content or ""
        return ChatResult(text=text, cost=event, raw=response)

    # --- images ------------------------------------------------------------

    def image(self, prompt: str, *, module: str, n: int = 1, size: str = "auto", **kwargs) -> ImageResult:
        """Generate images with Muse Image. Billed per image returned."""
        response = self.meta.images.generate(model=IMAGE, prompt=prompt, n=n, size=size,
                                             response_format="b64_json", **kwargs)
        images = [d.b64_json for d in response.data if getattr(d, "b64_json", None)]
        event = self.ledger.record(CostEvent(
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
        chunks: list[str] = []
        for event in self.meta.responses.create(**request):
            if getattr(event, "type", "") == "response.output_text.delta":
                chunks.append(event.delta)
        cost = self.ledger.record(CostEvent(
            module=module, model=SAM, usd=segment_cost(SAM, images=1), images=1,
        ))
        return SegmentResult(text="".join(chunks), cost=cost)

    # --- discovery ---------------------------------------------------------

    def list_meta_models(self) -> list[str]:
        return sorted(m.id for m in self.meta.models.list())
