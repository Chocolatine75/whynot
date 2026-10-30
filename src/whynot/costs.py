"""Cost accounting for every model call.

Every call to a model goes through `whynot.models.ModelClient`, which records a
`CostEvent` here. The ledger is an append-only JSONL file, so the cost counter in
the UI is computed from real calls, and runs can be audited afterwards.

Prices come from Meta's pricing page and Baseten's model page (see
docs/META_APIS.md). Update them here if they change.
"""

import json
import math
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


def check_priced(model: str) -> None:
    """Fail before a call, not after it was billed, if we could not log its cost."""
    if not any(model in table for table in (TOKEN_PRICES, IMAGE_PRICE, SEGMENT_IMAGE_PRICE,
                                              TRANSCRIBE_HOUR_PRICE)):
        raise UnknownModelPrice(model)


def token_cost(model: str, input_tokens: int, cached_tokens: int, output_tokens: int) -> float:
    """USD cost of a text call. `cached_tokens` is a subset of `input_tokens`."""
    if model not in TOKEN_PRICES:
        raise UnknownModelPrice(model)
    if min(input_tokens, cached_tokens, output_tokens) < 0:
        raise ValueError("token counts cannot be negative")
    price_in, price_cached, price_out = TOKEN_PRICES[model]
    cached = min(cached_tokens, input_tokens)
    fresh = input_tokens - cached
    return (fresh * price_in + cached * price_cached + output_tokens * price_out) / PER_MILLION


def image_cost(model: str, images_returned: int) -> float:
    if model not in IMAGE_PRICE:
        raise UnknownModelPrice(model)
    if images_returned < 0:
        raise ValueError("image count cannot be negative")
    return images_returned * IMAGE_PRICE[model]


def segment_cost(model: str, images: int = 0, video_frames: int = 0) -> float:
    if model not in SEGMENT_IMAGE_PRICE:
        raise UnknownModelPrice(model)
    if images < 0 or video_frames < 0:
        raise ValueError("counts cannot be negative")
    frames = max(video_frames, SEGMENT_MIN_FRAMES) if video_frames else 0
    return images * SEGMENT_IMAGE_PRICE[model] + frames * SEGMENT_FRAME_PRICE[model]


def transcribe_cost(model: str, audio_seconds: float) -> float:
    if model not in TRANSCRIBE_HOUR_PRICE:
        raise UnknownModelPrice(model)
    if audio_seconds < 0:
        raise ValueError("duration cannot be negative")
    # billing granularity is not documented: round up to the second so we never under-count
    return math.ceil(audio_seconds) / 3600 * TRANSCRIBE_HOUR_PRICE[model]


@dataclass
class CostEvent:
    module: str  # which part of whynot made the call, e.g. "strategy", "viewers"
    model: str
    usd: float
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0  # part of output_tokens, billed as output
    images: int = 0
    video_frames: int = 0
    audio_seconds: float = 0.0
    ok: bool = True
    ts: float = field(default_factory=time.time)
    source: str = "api"  # "api" (billed), "cassette" (replayed recording, $0) or "cache" (cached viewer answer, $0)


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


# --- spend report (`whynot costs`) -------------------------------------------------------

TEAM_BUDGET_USD = 60.0  # Meta Model API budget to the deadline, both people together (ROADMAP.md)


def collect_ledgers(outputs: Path) -> list[tuple[str, CostEvent]]:
    """(run, event) for every call logged under `outputs/`: scripts' ledger and each run folder's ledger.

    The run is the run folder's name, or "scripts" for `outputs/costs.jsonl`.
    """
    outputs = Path(outputs)
    found: list[tuple[str, CostEvent]] = [("scripts", e) for e in CostLedger(outputs / "costs.jsonl").events()]
    for path in sorted(outputs.glob("runs/*/costs.jsonl")):
        found += [(path.parent.name, e) for e in CostLedger(path).events()]
    return found


@dataclass(frozen=True)
class SpendReport:
    usd: float
    calls: int  # billed calls (failed ones included: they were billed)
    free_calls: int  # answers replayed from cassettes or the viewer cache
    by_day: dict[str, float]  # UTC dates
    by_module: dict[str, float]
    by_model: dict[str, float]
    by_run: dict[str, float]
    budget_usd: float

    @property
    def remaining_usd(self) -> float:
        return self.budget_usd - self.usd


def _add(totals: dict[str, float], key: str, usd: float) -> None:
    totals[key] = totals.get(key, 0.0) + usd


def spend_report(events: list[tuple[str, CostEvent]], *, since: str | None = None,
                 budget_usd: float = TEAM_BUDGET_USD) -> SpendReport:
    """Totals by day, module, model and run; `since` is an ISO date (UTC), inclusive."""
    by_day: dict[str, float] = {}
    by_module: dict[str, float] = {}
    by_model: dict[str, float] = {}
    by_run: dict[str, float] = {}
    usd, calls, free = 0.0, 0, 0
    for run, e in events:
        day = time.strftime("%Y-%m-%d", time.gmtime(e.ts))
        if since and day < since:
            continue
        if e.source != "api":
            free += 1
            continue
        calls += 1
        usd += e.usd
        for totals, key in ((by_day, day), (by_module, e.module), (by_model, e.model), (by_run, run)):
            _add(totals, key, e.usd)
    return SpendReport(usd, calls, free, dict(sorted(by_day.items())), by_module, by_model, by_run, budget_usd)


def format_report(r: SpendReport, *, top: int = 10) -> str:
    def table(title: str, totals: dict[str, float], ordered: bool = False) -> list[str]:
        rows = totals.items() if ordered else sorted(totals.items(), key=lambda kv: -kv[1])[:top]
        return [f"\n{title}"] + [f"  {k:<44} ${v:8.3f}" for k, v in rows]

    lines = [f"model spend ${r.usd:.2f} of ${r.budget_usd:.0f} budget · ${r.remaining_usd:.2f} left · "
             f"{r.calls} billed calls, {r.free_calls} free (cassette/cache)"]
    if r.usd > 2 / 3 * r.budget_usd:
        lines.append("! above 2/3 of the budget: only critical-path (★) tasks may spend")
    lines += table("by day (UTC)", r.by_day, ordered=True)
    lines += table("by module", r.by_module) + table("by model", r.by_model) + table(f"by run (top {top})", r.by_run)
    lines.append("\n(this machine's ledgers only: add the other person's total for the team budget)")
    return "\n".join(lines)
