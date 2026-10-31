"""The only way whynot calls a model.

`ModelClient` wraps the Meta Model API (OpenAI-compatible) and Muse Spark Open on
Baseten. Every call records a `CostEvent` with the module that made it, so the
cost counter is real and every run can be audited.

Chat calls can be recorded and replayed for free (`cassette.py`,
`WHYNOT_CASSETTE=record|replay|off`); spending is capped per command (`budget.py`).

Rule: never call the OpenAI SDK directly elsewhere in the code base.
"""

import base64
import mimetypes
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI

from whynot.budget import Budget, BudgetExceeded
from whynot.cassette import Cassette, CassetteMissing, Recording, request_key
from whynot.config import Settings, load_settings
from whynot.costs import (
    CostEvent,
    CostLedger,
    check_priced,
    image_cost,
    segment_cost,
    token_cost,
    transcribe_cost,
)

SPARK = "muse-spark-1.3"
SPARK_CONTRIBUTOR = "muse-spark-1.3-contributor"  # Meta trains on this data: synthetic content only
WONDER = "muse-wonder-1.0"
IMAGE = "muse-image-1.0"
TRANSCRIBE = "muse-voice-transcribe-1.0"
REQUEST_TIMEOUT_S = 180
SAM = "sam-3.1"


__all__ = ["BudgetExceeded", "ChatResult", "MissingKey", "ModelClient", "TruncatedOutput", "image_data_url"]


class MissingKey(RuntimeError):
    """Raised when a call needs an API key that is not set in .env."""


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
    raw: Any  # the SDK response; None when replayed from a cassette
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
                 meta: OpenAI | None = None, baseten: OpenAI | None = None, *, budget_usd: float | None = None,
                 cassette: Cassette | None = None):
        """`budget_usd`: hard cap on what this client may spend; calls stop once it is reached
        (a call already in flight can overshoot by its own cost). `cassette`: default from the settings."""
        self.settings = settings or load_settings()
        self.ledger = ledger or CostLedger(self.settings.cost_log)
        self._meta = meta
        self._baseten = baseten
        self.budget = Budget(budget_usd)
        s = self.settings
        self.cassette = cassette or Cassette(s.cassette_dir, s.cassette_mode, secrets=(
            s.model_api_key, s.baseten_api_key, s.fb_token, s.meta_token, s.meta_sandbox_token))

    @property
    def budget_usd(self) -> float | None:
        return self.budget.max_usd

    @property
    def spent_usd(self) -> float:
        return self.budget.spent

    def _check_budget(self) -> None:
        self.budget.check()

    def _record(self, event: CostEvent) -> CostEvent:
        self.budget.add(event.usd)
        return self.ledger.record(event)

    @property
    def viewer_model(self) -> str:
        """The model id viewer calls go to (part of every viewer cache key)."""
        if self.settings.viewer_backend == "baseten":
            return self.settings.baseten_model
        return self.settings.viewer_model

    def _refuse_in_replay(self, model: str, module: str) -> None:
        """Only chat answers are recorded; replay must never fall through to the network."""
        if self.cassette.replaying:
            raise CassetteMissing(f"{module}: {model} calls are not recorded in cassettes; replay mode refuses them")

    # --- clients -----------------------------------------------------------

    @property
    def meta(self) -> OpenAI:
        if self._meta is None:
            if not self.settings.model_api_key:
                raise MissingKey("MODEL_API_KEY is not set in .env")
            # a hung request must fail, not freeze a run: 3 minutes is far above any normal call
            self._meta = OpenAI(api_key=self.settings.model_api_key, base_url=self.settings.model_base_url,
                                timeout=REQUEST_TIMEOUT_S, max_retries=2)
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
        return self._chat(lambda: self.meta, model, messages, module, **kwargs)

    def open_chat(self, messages: list[dict], *, module: str, **kwargs) -> ChatResult:
        """Chat completion on Muse Spark Open (open weights, served by Baseten)."""
        return self._chat(lambda: self.baseten, self.settings.baseten_model, messages, module, **kwargs)

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

    def _chat(self, client: Callable[[], OpenAI], model: str, messages: list[dict], module: str,
              **kwargs) -> ChatResult:
        check_priced(model)
        # `draw` > 0 asks for another, independent answer to the same request (test-retest): it is part of
        # the cassette key but never sent to the API. draw 0 keeps the keys of existing recordings.
        draw = kwargs.pop("draw", 0)
        key = request_key(model, messages, {**kwargs, "draw": draw} if draw else kwargs)
        raw: Any = None
        if self.cassette.replaying:  # never the network, never the budget: the answer was paid for once
            rec = self.cassette.load(key, model=model, module=module)
            event = self._record(CostEvent(module=module, model=model, usd=0.0, source="cassette"))
        else:
            self._check_budget()
            rec, event, raw = self._call_api(client(), model, messages, module, **kwargs)
            if self.cassette.recording:
                self.cassette.put(key, rec)
        if rec.finish_reason == "length" and not rec.text.strip():
            raise TruncatedOutput(
                f"{model} used all {rec.output_tokens} output tokens ({rec.reasoning_tokens} reasoning) before "
                "answering; raise max_tokens")
        return ChatResult(text=rec.text, cost=event, raw=raw, finish_reason=rec.finish_reason)

    def _call_api(self, client: OpenAI, model: str, messages: list[dict], module: str,
                  **kwargs) -> tuple[Recording, CostEvent, Any]:
        """One billed chat call: the answer, its logged cost, and the SDK response."""
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
        rec = Recording(model, module, choice.message.content or "", getattr(choice, "finish_reason", None),
                        input_tokens, cached, output_tokens, reasoning)
        return rec, event, response

    # --- images ------------------------------------------------------------

    def image(self, prompt: str, *, module: str, n: int = 1, size: str = "auto", **kwargs) -> ImageResult:
        """Generate images with Muse Image. Billed per image returned."""
        self._refuse_in_replay(IMAGE, module)
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
        self._refuse_in_replay(SAM, module)
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

    # --- speech to text ----------------------------------------------------

    def transcribe(self, wav: bytes, *, module: str, languages: list[str] | None = None,
                   http: Any = None) -> str:
        """Muse Voice Transcribe on a WAV clip (mono PCM, 16 or 24 kHz, up to 10 minutes): the transcript.

        Multipart body: `request` (JSON settings) and `audio` (the clip). Billed per second of audio."""
        import json as _json

        import httpx

        self._refuse_in_replay(TRANSCRIBE, module)
        self._check_budget()
        if not self.settings.model_api_key:
            raise MissingKey("MODEL_API_KEY is not set")
        settings: dict[str, Any] = {"model": TRANSCRIBE, "audioEncoding": "WAV", "mode": "PUSH_TO_TALK"}
        if languages:
            settings["languageBias"] = languages
        client = http or httpx.Client(timeout=120)
        r = client.post(f"{self.settings.model_base_url.rstrip('/')}/asr/transcribe",
                        headers={"Authorization": f"Bearer {self.settings.model_api_key}",
                                 "Accept": "application/json"},
                        files={"request": (None, _json.dumps(settings), "application/json"),
                               "audio": ("clip.wav", wav, "audio/wav")})
        if r.status_code >= 400:
            raise RuntimeError(f"transcribe: HTTP {r.status_code}: {r.text[:300]}")
        body = r.json()
        seconds = float(body.get("audioDurationMs", 0)) / 1000
        self._record(CostEvent(module=module, model=TRANSCRIBE, usd=transcribe_cost(TRANSCRIBE, seconds),
                               audio_seconds=seconds))
        return str(body.get("transcript", ""))

    # --- discovery ---------------------------------------------------------

    def list_meta_models(self) -> list[str]:
        return sorted(m.id for m in self.meta.models.list())
