"""Cost accounting for every model call.

Every call to a model goes through `whynot.models.ModelClient`, which records a
`CostEvent` here. The ledger is an append-only JSONL file, so the cost counter in
the UI is computed from real calls, and runs can be audited afterwards.

Prices come from Meta's pricing page and Baseten's model page (see
docs/META_APIS.md). Update them here if they change.
"""

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

PER_MILLION = 1_000_000

# USD per 1M tokens: (input, cached input, output).
TOKEN_PRICES: dict[str, tuple[float, float, float]] = {
    "muse-spark-1.3": (1.25, 0.15, 4.25),
    "muse-spark-1.2": (1.25, 0.15, 4.25),
    "muse-spark-1.1": (1.25, 0.15, 4.25),
    "muse-spark-1.3-contributor": (0.10, 0.002, 0.20),
    "muse-spark-1.2-contributor": (0.10, 0.002, 0.20),
    "muse-wonder-1.0": (4.00, 0.20, 20.00),
    # Muse Spark Open on Baseten (public Baseten price; hackathon credits may cover it).
    "meta-models/muse-spark-open": (1.25, 0.15, 4.25),
    "meta-models/muse-spark-open-1026": (1.25, 0.15, 4.25),
}

# USD per unit for non-token models.
IMAGE_PRICE = {"muse-image-1.0": 0.01}  # per image returned
SEGMENT_IMAGE_PRICE = {"sam-3.1": 2.50 / 1000}  # per image
SEGMENT_FRAME_PRICE = {"sam-3.1": 0.20 / 1000}  # per video frame, min 50 per request
SEGMENT_MIN_FRAMES = 50
TRANSCRIBE_HOUR_PRICE = {"muse-voice-transcribe-1.0": 0.18}  # per hour of audio


class UnknownModelPrice(KeyError):
    """Raised when a model has no price: add it to the tables above first."""


def token_cost(model: str, input_tokens: int, cached_tokens: int, output_tokens: int) -> float:
    """USD cost of a text call. `cached_tokens` is a subset of `input_tokens`."""
    if model not in TOKEN_PRICES:
        raise UnknownModelPrice(model)
    price_in, price_cached, price_out = TOKEN_PRICES[model]
    cached = min(cached_tokens, input_tokens)
    fresh = input_tokens - cached
    return (fresh * price_in + cached * price_cached + output_tokens * price_out) / PER_MILLION


def image_cost(model: str, images_returned: int) -> float:
    if model not in IMAGE_PRICE:
        raise UnknownModelPrice(model)
    return images_returned * IMAGE_PRICE[model]


def segment_cost(model: str, images: int = 0, video_frames: int = 0) -> float:
    if model not in SEGMENT_IMAGE_PRICE:
        raise UnknownModelPrice(model)
    frames = max(video_frames, SEGMENT_MIN_FRAMES) if video_frames else 0
    return images * SEGMENT_IMAGE_PRICE[model] + frames * SEGMENT_FRAME_PRICE[model]


def transcribe_cost(model: str, audio_seconds: float) -> float:
    if model not in TRANSCRIBE_HOUR_PRICE:
        raise UnknownModelPrice(model)
    return int(audio_seconds) / 3600 * TRANSCRIBE_HOUR_PRICE[model]


@dataclass
class CostEvent:
    module: str  # which part of whynot made the call, e.g. "strategy", "viewers"
    model: str
    usd: float
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    images: int = 0
    video_frames: int = 0
    audio_seconds: float = 0.0
    ok: bool = True
    ts: float = field(default_factory=time.time)


class CostLedger:
    """Append-only JSONL log of every model call, safe to share between threads."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def record(self, event: CostEvent) -> CostEvent:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event)) + "\n")
        return event

    def events(self) -> list[CostEvent]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as f:
            return [CostEvent(**json.loads(line)) for line in f if line.strip()]

    def total(self, module: str | None = None) -> float:
        return sum(e.usd for e in self.events() if module is None or e.module == module)

    def by_module(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for e in self.events():
            totals[e.module] = totals.get(e.module, 0.0) + e.usd
        return totals
