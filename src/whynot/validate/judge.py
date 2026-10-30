"""The simple-judge baseline for R1/R3: one model call per ad, no personas, no feed.

If the simulated feed (personas reacting to a feed with competitors) cannot beat this judge, the
personas and the feed add nothing, and we must say so. The judge sees exactly what a viewer sees
(advertiser, title, text, and the image when the feed has images) and runs on the same backend as the
viewers, so the comparison is about the method, not the model.

Answers are strict JSON `{"score": 1-10, "why": "..."}`, retried once, then counted as a failure.
Valid answers are cached like viewer answers (a judgement is never paid twice).
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from whynot.cassette import request_key
from whynot.jsonio import JSONExtractError, extract_json
from whynot.models import ModelClient
from whynot.sim.feed import FeedItem
from whynot.sim.viewer import ViewerCache

PROMPT = """You are a senior performance marketer who has run thousands of Facebook and Instagram ads.
Here is one ad as it appears in the feed.

Sponsored · {advertiser}
{title}{body}{image}
How likely is it that this ad performs well enough that the advertiser keeps it running for months?
Answer with JSON only: {{"score": <integer 1-10, 10 = almost certainly kept for months>, "why": "<one sentence>"}}"""


class JudgeFailure(ValueError):
    """No valid answer after the retries; carries what the attempts cost (they were billed)."""

    def __init__(self, message: str, usd: float):
        super().__init__(message)
        self.usd = usd


@dataclass
class JudgeResult:
    scores: dict[str, float] = field(default_factory=dict)  # ad id -> 1..10
    why: dict[str, str] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)
    usd: float = 0.0
    cache_hits: int = 0


def build_messages(item: FeedItem) -> list[dict[str, Any]]:
    text = PROMPT.format(advertiser=item.advertiser, title=f"Title: {item.title}\n" if item.title else "",
                         body=f"Text: {item.body}\n" if item.body else "",
                         image="(image below)\n" if item.image_url else "")
    if not item.image_url:
        return [{"role": "user", "content": text}]
    return [{"role": "user", "content": [{"type": "text", "text": text},
                                         {"type": "image_url", "image_url": {"url": item.image_url}}]}]


def parse(text: str) -> tuple[int, str]:
    try:
        data = extract_json(text)
    except JSONExtractError as exc:
        raise ValueError(f"no JSON: {exc}") from None
    if not isinstance(data, dict):
        raise ValueError("answer is not an object")
    score = data.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or score != int(score) or not 1 <= score <= 10:
        raise ValueError(f"score must be an integer 1-10, got {score!r}")
    return int(score), str(data.get("why", ""))[:300]


class Judge:
    def __init__(self, client: ModelClient, *, cache: ViewerCache | None = None, max_tokens: int = 3000,
                 reasoning_effort: str | None = "low", retries: int = 1):
        self.client = client
        self.cache = cache
        self.params: dict[str, Any] = {"max_tokens": max_tokens}
        if reasoning_effort:
            self.params["reasoning_effort"] = reasoning_effort
        self.retries = retries

    def one(self, item: FeedItem) -> tuple[int, str, float, bool]:
        """(score, why, $ spent, from cache)."""
        messages = build_messages(item)
        key = request_key(getattr(self.client, "viewer_model", "unknown"), messages, {**self.params, "judge": 1})
        if self.cache and (hit := self.cache.get(key)) is not None:
            try:
                return (*parse(hit), 0.0, True)
            except ValueError:
                pass
        spent, last = 0.0, ""
        for _ in range(self.retries + 1):
            result = self.client.viewer_chat(messages, module="judge", **self.params)
            spent += result.cost.usd
            try:
                score, why = parse(result.text)
            except ValueError as exc:
                last = str(exc)
                continue
            if self.cache:
                self.cache.put(key, result.text)
            return score, why, spent, False
        raise JudgeFailure(f"{last} (after {self.retries + 1} tries)", spent)

    def run(self, items: list[FeedItem], *, max_workers: int = 8) -> JudgeResult:
        out = JudgeResult()

        def job(item: FeedItem) -> tuple[str, Any]:
            try:
                return item.ad_id, self.one(item)
            except Exception as exc:  # recorded, never guessed
                return item.ad_id, exc

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for ad_id, res in pool.map(job, items):
                if isinstance(res, Exception):
                    out.failures[ad_id] = f"{type(res).__name__}: {res}"[:300]
                    out.usd += getattr(res, "usd", 0.0)  # failed attempts were paid for too
                    continue
                score, why, usd, hit = res
                out.scores[ad_id], out.why[ad_id] = float(score), why
                out.usd += usd
                out.cache_hits += hit
        return out
