"""Viewer agents: one persona scrolls one feed and reacts to every ad.

What a viewer reports per ad (cognitive reactions only, see CLAUDE.md):
- stopped: would they stop scrolling on it;
- understood / believed: did they get the message, do they believe it;
- why_not: in their own words, what would stop them from clicking or buying;
- intent: free text (kept for SSR) + a 1–5 score (v0);
and which ad of the feed they prefer.

Ads are shown with neutral labels (A1, A2, ...) in a per-viewer random order.
Answers are strict JSON, validated; a malformed answer is retried once, then
counted as a failure rather than guessed.

Valid answers are cached on disk (`ViewerCache`), keyed by the exact request:
persona, feed items in the order this viewer sees them, prompt, model and
parameters. A view is never paid twice; a hit is logged at $0 (source "cache").
`draw` asks for a fresh, independent answer to the same request (test-retest).
"""

import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from whynot.cassette import request_key
from whynot.costs import CostEvent
from whynot.jsonio import JSONExtractError, extract_json
from whynot.models import ModelClient
from whynot.sim.feed import Feed, order_for
from whynot.sim.personas import Persona

SYSTEM = """You simulate one specific person scrolling their Instagram or Facebook feed.
You are: {who}.
Stay in character. You are not a marketer and you don't analyse ads. Be realistic:
people scroll past most ads, are wary of advertising, and rarely want to buy.
React only to what is shown."""

INSTRUCTIONS = """These are the next {n} posts in your feed. They are all ads, in the order you see them.

{ads}

For each ad, answer as this person. Reply with JSON only, no other text:
{{"reactions": [{{"ad": "A1", "stopped": true, "understood": true, "believed": false,
  "why_not": "what would stop you from clicking or buying, in your own words (empty if nothing)",
  "intent": "would you click or buy, in your own words, one sentence",
  "intent_score": 1}}],
 "preferred": "A1"}}
Rules: one entry per ad, every ad from A1 to A{n}. intent_score is 1 (definitely not) to 5
(definitely yes). "preferred" is the one ad you liked most."""


class ViewerParseError(ValueError):
    def __init__(self, message: str, usd: float = 0.0):
        super().__init__(message)
        self.usd = usd  # spent on the failed attempts


@dataclass
class Reaction:
    feed_id: str
    persona_id: str
    ad_id: str
    position: int  # 0-based position this viewer saw the ad at
    stopped: bool
    understood: bool
    believed: bool
    why_not: str
    intent_text: str
    intent_score: int
    preferred: bool


@dataclass
class SimResult:
    reactions: list[Reaction] = field(default_factory=list)
    failures: list[dict[str, str]] = field(default_factory=list)
    usd: float = 0.0


def render_feed(feed: Feed) -> tuple[str, dict[str, str]]:
    """Text for the prompt + label → ad_id map."""
    blocks, labels = [], {}
    for i, item in enumerate(feed, start=1):
        label = f"A{i}"
        labels[label] = item.ad_id
        lines = [f"[{label}] Sponsored · {item.advertiser}"]
        if item.title:
            lines.append(f"Title: {item.title}")
        if item.body:
            lines.append(f"Text: {item.body}")
        if item.image_url:
            lines.append("(image below)")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks), labels


def build_messages(persona: Persona, feed: Feed) -> tuple[list[dict], dict[str, str]]:
    text, labels = render_feed(feed)
    content: list[dict[str, Any]] = [{"type": "text", "text": INSTRUCTIONS.format(n=len(feed), ads=text)}]
    for item in feed:
        if item.image_url:
            content.append({"type": "image_url", "image_url": {"url": item.image_url}})
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM.format(who=persona.describe())},
        {"role": "user", "content": content if len(content) > 1 else content[0]["text"]},
    ]
    return messages, labels


def _extract_json(text: str) -> Any:
    try:
        return extract_json(text)
    except JSONExtractError as exc:
        raise ViewerParseError(str(exc)) from None


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "yes", "1"}:
        return True
    if isinstance(value, str) and value.strip().lower() in {"false", "no", "0", ""}:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    raise ViewerParseError(f"not a boolean: {value!r}")


def parse_reactions(text: str, labels: dict[str, str], *, feed_id: str, persona_id: str) -> list[Reaction]:
    data = _extract_json(text)
    if not isinstance(data, dict):
        raise ViewerParseError("answer is not a JSON object")
    raw = data.get("reactions")
    if not isinstance(raw, list):
        raise ViewerParseError("missing 'reactions' list")
    preferred = str(data.get("preferred", "")).strip()
    if preferred not in labels:
        raise ViewerParseError(f"'preferred' is not one of the ads: {preferred!r}")
    by_label: dict[str, dict] = {}
    for r in raw:
        if not isinstance(r, dict):
            raise ViewerParseError(f"reaction is not an object: {r!r}"[:120])
        label = str(r.get("ad", "")).strip()
        if label in labels and label not in by_label:
            by_label[label] = r
    missing = set(labels) - set(by_label)
    if missing:
        raise ViewerParseError(f"no reaction for {sorted(missing)}")
    order = list(labels)
    reactions = []
    for label in order:
        r = by_label[label]
        try:
            score = round(float(r.get("intent_score")))  # type: ignore[arg-type]
        except (TypeError, ValueError, OverflowError):
            raise ViewerParseError(f"bad intent_score for {label}") from None
        reactions.append(Reaction(
            feed_id=feed_id, persona_id=persona_id, ad_id=labels[label], position=order.index(label),
            stopped=_bool(r.get("stopped")), understood=_bool(r.get("understood")),
            believed=_bool(r.get("believed")), why_not=str(r.get("why_not") or "").strip(),
            intent_text=str(r.get("intent") or "").strip(), intent_score=min(5, max(1, score)),
            preferred=(label == preferred),
        ))
    return reactions


class ViewerCache:
    """Valid viewer answers on disk, one file per request key. Atomic writes: threads and runs can share it."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        p = self.folder / f"{key}.txt"
        text = p.read_text(encoding="utf-8") if p.exists() else None
        with self._lock:
            if text is None:
                self.misses += 1
            else:
                self.hits += 1
        return text

    def put(self, key: str, text: str) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.folder, prefix=".tmp-", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, self.folder / f"{key}.txt")

    def size(self) -> tuple[int, int]:
        """(answers stored, bytes on disk)."""
        files = list(self.folder.glob("*.txt")) if self.folder.exists() else []
        return len(files), sum(f.stat().st_size for f in files)


class Viewer:
    def __init__(self, client: ModelClient, *, max_tokens: int = 6000, retries: int = 1,
                 reasoning_effort: str | None = None, cache: ViewerCache | None = None, draw: int = 0):
        """`cache`: default from the settings (WHYNOT_VIEWER_CACHE); `draw` > 0 asks for fresh answers."""
        # Muse Spark reasons ~2k tokens per feed before answering (observed); keep headroom.
        self.client = client
        self.max_tokens = max_tokens
        self.retries = retries
        self.reasoning_effort = reasoning_effort
        self.draw = draw
        if cache is None:
            folder = getattr(getattr(client, "settings", None), "viewer_cache_dir", None)
            cache = ViewerCache(folder) if folder else None
        self.cache = cache

    def _key(self, messages: list[dict], params: dict[str, Any]) -> str:
        model = getattr(self.client, "viewer_model", "unknown")
        return request_key(model, messages, {**params, "draw": self.draw})

    def _log_hit(self) -> None:
        ledger = getattr(self.client, "ledger", None)
        if ledger is not None:
            ledger.record(CostEvent(module="viewers", model=getattr(self.client, "viewer_model", "unknown"),
                                    usd=0.0, source="cache"))

    def react(self, persona: Persona, feed: Feed, *, feed_id: str) -> tuple[list[Reaction], float]:
        """Reactions of one persona to one feed, plus the $ spent (retries included; $0 on a cache hit)."""
        seen = order_for(feed, f"{feed_id}|{persona.id}")
        messages, labels = build_messages(persona, seen)
        params: dict[str, Any] = {"max_tokens": self.max_tokens}
        if self.reasoning_effort:
            params["reasoning_effort"] = self.reasoning_effort
        key = self._key(messages, params) if self.cache else ""
        if self.cache and (cached := self.cache.get(key)) is not None:
            try:
                reactions = parse_reactions(cached, labels, feed_id=feed_id, persona_id=persona.id)
                self._log_hit()
                return reactions, 0.0
            except ViewerParseError:
                pass  # a damaged entry: ask again and overwrite it
        # the draw reaches the cassette key too, so a retest never replays the first answer
        call: dict[str, Any] = {**params, **({"draw": self.draw} if self.draw else {})}
        spent = 0.0
        last_error: Exception | None = None
        for _ in range(self.retries + 1):
            result = self.client.viewer_chat(messages, **call)
            spent += result.cost.usd
            try:
                reactions = parse_reactions(result.text, labels, feed_id=feed_id, persona_id=persona.id)
            except ViewerParseError as exc:
                last_error = exc
                continue
            if self.cache:  # only valid answers: a bad one must be asked again, not replayed
                self.cache.put(key, result.text)
            return reactions, spent
        raise ViewerParseError(f"{last_error} (after {self.retries + 1} tries)", usd=spent)


def run_simulation(viewer: Viewer, personas: list[Persona], feeds: list[Feed], *,
                   viewers_per_feed: int, max_workers: int = 8) -> SimResult:
    """Each feed is watched by `viewers_per_feed` personas (assigned round-robin)."""
    if not personas:
        raise ValueError("no personas")
    if viewers_per_feed < 1:
        raise ValueError("viewers_per_feed must be at least 1")
    if viewers_per_feed > len(personas):
        # the same persona would see the same feed twice and skew the scores
        raise ValueError(f"viewers_per_feed ({viewers_per_feed}) > personas ({len(personas)})")
    if len({p.id for p in personas}) != len(personas):
        raise ValueError("persona ids must be unique")
    jobs = []
    k = 0
    for f_index, feed in enumerate(feeds):
        for _ in range(viewers_per_feed):
            jobs.append((f"F{f_index}", personas[k % len(personas)], feed))
            k += 1

    result = SimResult()

    def run(job):
        feed_id, persona, feed = job
        try:
            reactions, usd = viewer.react(persona, feed, feed_id=feed_id)
            return reactions, usd, None
        except Exception as exc:  # one bad viewer must not stop the run
            return [], getattr(exc, "usd", 0.0), {"feed_id": feed_id, "persona_id": persona.id,
                             "error": f"{type(exc).__name__}: {str(exc)[:200]}"}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for reactions, usd, failure in pool.map(run, jobs):
            result.reactions.extend(reactions)
            result.usd += usd
            if failure:
                result.failures.append(failure)
    return result
