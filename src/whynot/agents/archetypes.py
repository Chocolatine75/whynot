"""Archetypes: group the market's ads by what they do, score each group on market signals, pick what fits us.

1. Group deconstructed competitor ads by (emotional pitch, creative style), e.g. "transformation ×
   app_screen". A group needs ads from at least 2 ads to count.
2. Score each group on signals the Ad Library gives, every component shown (auditable):
   - staying power: how long its ads have run (still-active ads, capped at 90 days): ads that pay are kept;
   - reach: its ads' EU reach (log scale);
   - reuse: how often advertisers run the same copy several times (a duplicated ad is one they scale);
   - breadth: how many different advertisers use it (a pattern, not one brand's habit).
   score = 0.4 staying + 0.2 reach + 0.2 reuse + 0.2 breadth, each normalised to 0-1 across groups.
   The weights are a heuristic, stated as such.
3. Muse Spark picks the archetypes that fit this app: for each, a persona and an angle of our strategy,
   and fit scores for the audience, the message, and production (can we make it with the app's real
   screens and generated scenes? A UGC selfie video needs footage we don't have).
"""

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from whynot.agents.ask import Answer, ChatClient, Invalid, ask_json
from whynot.agents.deconstruct import Deconstruction
from whynot.agents.strategist import Strategy
from whynot.ingest.adlibrary import CompetitorAd
from whynot.models import SPARK

WEIGHTS = {"staying": 0.4, "reach": 0.2, "reuse": 0.2, "breadth": 0.2}
MIN_ADS = 2
STAYING_CAP_DAYS = 90


@dataclass
class Archetype:
    key: str  # "<pitch>:<style>"
    pitch: str
    style: str
    ad_ids: list[str]
    advertisers: list[str]
    signals: dict[str, float]  # raw values
    components: dict[str, float]  # normalised 0-1
    score: float
    examples: list[dict[str, Any]] = field(default_factory=list)  # hook / promise / visual of the best ads


def _norm(values: dict[str, float]) -> dict[str, float]:
    lo, hi = min(values.values()), max(values.values())
    return {k: (v - lo) / (hi - lo) if hi > lo else 1.0 for k, v in values.items()}


def copy_key(ad: CompetitorAd) -> tuple[str, str]:
    return (ad.page_id or ad.page_name or "", " ".join((ad.bodies or [""])[0].split()).lower())


def build(decons: dict[str, Deconstruction], ads: list[CompetitorAd], *, as_of: date,
          min_ads: int = MIN_ADS) -> list[Archetype]:
    """Archetypes of the market, best first. `ads` is the whole market (used to count reuse)."""
    by_id = {a.id: a for a in ads}
    reuse_count = Counter(copy_key(a) for a in ads)
    groups: dict[str, list[str]] = defaultdict(list)
    for ad_id, d in decons.items():
        if ad_id in by_id:
            groups[f"{d.emotional_pitch}:{d.creative_style}"].append(ad_id)
    groups = {k: sorted(v) for k, v in groups.items() if len(v) >= min_ads}
    if not groups:
        return []

    raw: dict[str, dict[str, float]] = {}
    for key, ids in groups.items():
        members = [by_id[i] for i in ids]
        staying = [min(a.longevity_days(as_of) or 0, STAYING_CAP_DAYS) for a in members if a.stop_date is None]
        raw[key] = {
            "staying": sum(staying) / len(members),  # stopped ads count as 0: they were not kept
            "reach": sum(math.log10(1 + (a.eu_total_reach or 0)) for a in members) / len(members),
            "reuse": sum(reuse_count[copy_key(a)] for a in members) / len(members),
            "breadth": float(len({a.page_id or a.page_name for a in members})),
        }
    normed = {s: _norm({k: raw[k][s] for k in raw}) for s in WEIGHTS}
    out = []
    for key, ids in groups.items():
        comps = {s: round(normed[s][key], 3) for s in WEIGHTS}
        pitch, style = key.split(":")
        ranked = sorted(ids, key=lambda i: -(by_id[i].longevity_days(as_of) or 0))
        out.append(Archetype(
            key, pitch, style, ids, sorted({by_id[i].page_name or "" for i in ids}),
            {s: round(v, 3) for s, v in raw[key].items()}, comps,
            round(sum(WEIGHTS[s] * comps[s] for s in WEIGHTS), 3),
            [{"ad_id": i, "hook": decons[i].hook, "promise": decons[i].promise,
              "visual": decons[i].visual_subject, "overlays": decons[i].text_overlays[:3],
              "days": by_id[i].longevity_days(as_of)} for i in ranked[:3]],
        ))
    return sorted(out, key=lambda a: (-a.score, a.key))


# --- fit to the app ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Pick:
    archetype: str
    persona: str
    angle: str
    audience_fit: int
    message_fit: int
    production_fit: int
    why: str

    @property
    def fit(self) -> float:
        return (self.audience_fit + self.message_fit + self.production_fit) / 30


FIT_PROMPT = """You are the creative director of a performance ad agency. Pick the {n} market archetypes this
app should use for its next video ads, each with one persona and one angle from our strategy.

App: {app}
What it is: {description}

Our strategy
Personas: {personas}
Angles: {angles}

Market archetypes (from competitor ads, best market score first):
{archetypes}

We produce ads from the app's REAL screenshots, generated background scenes (no people's faces, no
product), animated text and an end card. We have no filmed footage: archetypes that need a real
person on camera (ugc_person) or before/after photos are hard to produce well.

Return JSON only:
{{"picks": [{{"archetype": "<key>", "persona": "<persona id>", "angle": "<angle id>",
  "audience_fit": <0-10>, "message_fit": <0-10>, "production_fit": <0-10>, "why": "<one sentence>"}}]}}
Rules: {n} picks, all different archetypes; the angle must belong to the persona."""


def _validator(keys: set[str], strategy: Strategy, n: int):
    personas = {p.id for p in strategy.personas}
    angle_persona = {a.id: a.persona for a in strategy.angles}

    def validate(data: Any) -> list[Pick]:
        picks = data.get("picks") if isinstance(data, dict) else None
        if not isinstance(picks, list) or len(picks) != n:
            raise Invalid(f"'picks' must be a list of exactly {n} items")
        out = []
        for i, p in enumerate(picks):
            where = f"pick {i + 1}"
            if not isinstance(p, dict):
                raise Invalid(f"{where} must be an object")
            if p.get("archetype") not in keys:
                raise Invalid(f"{where}: archetype {p.get('archetype')!r} is not one of {sorted(keys)}")
            if p.get("persona") not in personas:
                raise Invalid(f"{where}: persona {p.get('persona')!r} is not one of {sorted(personas)}")
            if angle_persona.get(str(p.get("angle"))) != p["persona"]:
                raise Invalid(f"{where}: angle {p.get('angle')!r} is not an angle of persona {p['persona']!r}")
            scores = []
            for s in ("audience_fit", "message_fit", "production_fit"):
                v = p.get(s)
                if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 10:
                    raise Invalid(f"{where}: {s} must be an integer 0-10")
                scores.append(v)
            why = " ".join(str(p.get("why", "")).split())
            if not why:
                raise Invalid(f"{where}: 'why' is required")
            out.append(Pick(p["archetype"], p["persona"], p["angle"], scores[0], scores[1], scores[2], why[:300]))
        if len({p.archetype for p in out}) != n:
            raise Invalid("each pick must use a different archetype")
        return out

    return validate


def pick(client: ChatClient, archetypes: list[Archetype], strategy: Strategy, *, app_name: str,
         description: str, n: int = 3, top: int = 8, model: str = SPARK) -> Answer[list[Pick]]:
    shown = archetypes[:top]
    if len(shown) < n:
        raise ValueError(f"need at least {n} archetypes, the market gave {len(shown)}")
    lines = []
    for a in shown:
        ex = "; ".join(f'"{e["hook"]}" ({e["days"]} days)' for e in a.examples[:2])
        lines.append(f"- {a.key}: score {a.score:.2f}, {len(a.ad_ids)} ads by {len(a.advertisers)} advertisers. "
                     f"Examples: {ex}")
    prompt = FIT_PROMPT.format(
        n=n, app=app_name, description=" ".join(description.split())[:800],
        personas="; ".join(f"{p.id} = {p.description}" for p in strategy.personas),
        angles="; ".join(f"{a.id} (persona {a.persona}) = {a.idea}" for a in strategy.angles),
        archetypes="\n".join(lines))
    return ask_json(client, [{"role": "user", "content": prompt}], _validator({a.key for a in shown}, strategy, n),
                    module="archetypes", model=model, repairs=2, max_tokens=4000, reasoning_effort="low")
