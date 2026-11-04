"""Verified facts a static ad may show in a layout of its own (E5-2), taken by code, never written by a model.

- `review`: a sentence of a real 4-5★ App Store review, word for word (the angle's own evidence first);
- `number`: a number from a verified claim (store page or review), with the claim as its label;
- `benefits`: up to three short verified claims;
- `offer`: what the store page supports ("Free to download" for a free app, "Free trial" only if it says so);
- `objection`: the customer's objection, as the strategy words it (its first clause when long). The strategy's
  "answer" is an instruction to the copywriter, never ad copy: the ad's own headline answers it on the picture.
A fact is left out when it is too long to show whole: a quote is never cut mid-sentence, a claim never shortened.
Facts are in the strategy's language (English): they are offered to English ads only.
"""

import re
from typing import Any

from whynot.agents.strategist import Strategy
from whynot.ingest.appstore import AppProfile

MAX_QUOTE = 140
MAX_LABEL = 60
MAX_BENEFIT = 48
MAX_OBJECTION = 90
NUMBER = re.compile(r"\d+(?:[.,]\d+)?(?:\s?(?:%|\+|k\b|K\b|M\b))?")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
DANGLING = re.compile(r"^(but|and|so|or|also|though|which|because|then|plus)\b", re.I)  # needs the sentence before


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(" ".join(text.split())) if s.strip()]


def review_quote(app: AppProfile, refs: list[str]) -> dict[str, Any] | None:
    """A whole sentence of a 4-5★ review: from the reviews the angle cites first, else any 5★ review."""
    by_id = {r.id: r for r in app.reviews}
    cited = [by_id[r.split(":", 1)[1]] for r in refs if r.startswith("review:") and r.split(":", 1)[1] in by_id]
    for pool in (cited, [r for r in app.reviews if r.rating == 5]):
        # a sentence that stands on its own (not "But it's great!!"), the most telling: the longest that fits
        found = [(len(s), s, r) for r in pool if r.rating >= 4 for s in _sentences(r.text)
                 if 40 <= len(s) <= MAX_QUOTE and not DANGLING.match(s) and s.count("!") <= 1]
        if found:
            _, s, r = max(found, key=lambda x: (x[0], x[2].id))
            return {"text": s, "rating": r.rating, "review": r.id}
    return None


def number_claim(strategy: Strategy) -> dict[str, Any] | None:
    for c in strategy.claims:
        m = NUMBER.search(c.text)
        if m and len(c.text) <= MAX_LABEL:
            return {"value": m.group(0).strip(), "label": c.text, "claim": c.id}
    return None


def benefits(strategy: Strategy) -> list[str]:
    short = sorted((c.text for c in strategy.claims if len(c.text) <= MAX_BENEFIT), key=len)
    out = list(dict.fromkeys(short))[:3]
    return out if len(out) >= 2 else []


def objection(strategy: Strategy, objection_id: str | None) -> dict[str, str] | None:
    if not objection_id:
        return None
    try:
        o = strategy.objection(objection_id)
    except (KeyError, ValueError, StopIteration):
        return None
    text = " ".join(o.text.split())
    if len(text) > MAX_OBJECTION:  # the first clause, whole: never a word cut in half
        text = re.split(r"\s*[,;:—–]\s*|\s+-\s+", text, maxsplit=1)[0].strip()
    if 12 <= len(text) <= MAX_OBJECTION:
        return {"text": text, "objection": o.id}
    return None


def offer(app: AppProfile) -> str | None:
    """An offer the store page itself supports, word for word true: a free app is "Free to download"; a free
    trial only when the store page says so. Never a discount or a number nobody stated."""
    if app.price == 0:
        return "Free to download"
    if "free trial" in app.description.lower():
        return "Free trial"
    return None


def verified_content(strategy: Strategy, app: AppProfile, angle_id: str, language: str) -> dict[str, Any]:
    """The facts an ad for `angle_id` may show; empty for ads not in the strategy's language (English)."""
    if language != "en":
        return {}
    angle = next((a for a in strategy.angles if a.id == angle_id), None)
    refs = [e.ref for e in angle.evidence] if angle else []
    out: dict[str, Any] = {"review": review_quote(app, refs), "number": number_claim(strategy), "offer": offer(app),
                           "benefits": benefits(strategy),
                           "objection": objection(strategy, angle.objection if angle else None)}
    return {k: v for k, v in out.items() if v}
