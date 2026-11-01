"""Tomorrow's ideas: build on what works, explore what was never tried, never repeat an ad.

An idea is (format, persona, angle). Two ideas are far apart when they differ on the format (how the ad
plays), the angle (what it says) and the persona (who it speaks to); `distance` weighs those.

Every day the planner fills the free slots with:
- EXPLOIT (a share, only when a winner exists): the winner's persona and angle in a format it never used,
  so what sells gets a fresh execution instead of a copy that will tire the same way;
- EXPLORE (the rest): the untried idea farthest from everything tried and from the ideas already picked
  today (greedy farthest-point), so the account keeps discovering new directions.

Guarantees (tested on random histories): an idea already made is never proposed again, and two ideas of
the same day always differ. After writing, `too_similar` compares the new hook and voice with every past ad
so a different idea can't come back with the same words.
"""

import math
import re
from dataclasses import dataclass

from whynot.agency.memory import AdRecord

WEIGHTS = {"format": 0.45, "angle": 0.35, "persona": 0.20}
MIN_SPEND_TO_JUDGE = 10.0
EXPLOIT_SHARE = 0.34
MAX_TEXT_OVERLAP = 0.55


@dataclass(frozen=True)
class Idea:
    format: str
    persona: str
    angle: str
    why: str = ""
    parent: str | None = None  # exploit: the winning ad whose message this idea re-uses (the selection tree)

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.format, self.persona, self.angle)


def distance(a: tuple[str, str, str], b: tuple[str, str, str]) -> float:
    """0 = the same idea, 1 = nothing in common (format, persona, angle)."""
    return (WEIGHTS["format"] * (a[0] != b[0]) + WEIGHTS["persona"] * (a[1] != b[1])
            + WEIGHTS["angle"] * (a[2] != b[2]))


def winners(ads: list[AdRecord], *, min_spend: float = MIN_SPEND_TO_JUDGE) -> list[AdRecord]:
    """Ads that spent enough and converted, best cost per conversion first."""
    judged = [a for a in ads if a.spend >= min_spend and a.cpa is not None]
    return sorted(judged, key=lambda a: (a.cpa, a.key))


def _account_rate(ads: list[AdRecord]) -> float:
    spend = sum(a.spend for a in ads)
    return sum(a.conversions for a in ads) / spend if spend else 0.0


def format_scores(ads: list[AdRecord], *, prior_spend: float = 10.0) -> dict[str, float]:
    """Conversions per euro of each format so far, shrunk toward the account's rate (few euros prove little)."""
    base = _account_rate(ads)
    spend: dict[str, float] = {}
    conv: dict[str, float] = {}
    for a in ads:
        spend[a.format] = spend.get(a.format, 0.0) + a.spend
        conv[a.format] = conv.get(a.format, 0.0) + a.conversions
    return {f: (conv[f] + base * prior_spend) / (spend[f] + prior_spend) for f in spend}


def plan(n: int, *, formats: list[str], pairs: list[tuple[str, str]], tried: list[tuple[str, str, str]],
         ads: list[AdRecord] | None = None, exploit_share: float = EXPLOIT_SHARE) -> list[Idea]:
    """`n` new ideas. `pairs`: the strategy's (persona, angle) pairs; `tried`: (format, persona, angle) made."""
    if n <= 0:
        return []
    done = set(tried)
    candidates = [(f, p, a) for f in formats for p, a in pairs if (f, p, a) not in done]
    picked: list[Idea] = []

    best = winners(ads or [])
    # rounded up: with one free slot a day, rounding down would never build on what sells
    n_exploit = min(len(best), math.ceil(n * exploit_share)) if best and exploit_share > 0 else 0
    for w in best[:n_exploit]:
        options = [c for c in candidates if c[1] == w.persona and c[2] == w.angle and c[0] != w.format
                   and c not in {i.key for i in picked}]
        if not options:
            continue
        # same message, new execution: the format that has sold best so far (untried formats get the
        # account's average, so they stay in the running), ties broken by distance to today's picks
        scores = format_scores(ads or [])
        prior = _account_rate(ads or [])
        c = max(options, key=lambda c: (scores.get(c[0], prior), min([distance(c, i.key) for i in picked] or [1.0]),
                                        c))
        cpa = f"€{w.cpa:.2f}" if w.cpa is not None else "?"
        picked.append(Idea(*c, why=f"exploit: '{w.angle}' sells ({cpa} per conversion with {w.format}); "
                                    f"same message, new format", parent=w.key))

    while len(picked) < n:
        pool = [c for c in candidates if c not in {i.key for i in picked}]
        if not pool:
            break
        anchors = list(done) + [i.key for i in picked]
        c = max(pool, key=lambda c: _far(c, anchors))
        picked.append(Idea(*c, why=f"explore: far from everything tried (distance {_far(c, anchors)[0]:.2f})"))
    return picked


def _far(c: tuple[str, str, str], anchors: list[tuple[str, str, str]]) -> tuple[float, float, tuple[str, str, str]]:
    """How far `c` is from the closest anchor (then on average): the explore ranking."""
    dists = [distance(c, x) for x in anchors] or [1.0]
    return (min(dists), sum(dists) / len(dists), c)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-zà-ỹ0-9']{3,}", text.lower()))


def overlap(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / min(len(wa), len(wb)) if wa and wb else 0.0


def too_similar(hook: str, voice: str, past: list[AdRecord], *, limit: float = MAX_TEXT_OVERLAP) -> AdRecord | None:
    """The past ad whose words this one repeats too much (hook or voice), if any."""
    for r in past:
        if overlap(hook, r.hook) > limit or (voice and r.voice and overlap(voice, r.voice) > limit):
            return r
    return None


def plan_random(n: int, *, formats: list[str], pairs: list[tuple[str, str]], tried: list[tuple[str, str, str]],
                seed: str) -> list[Idea]:
    """The no-learning baseline: untried ideas drawn at random (same idea space, same "never twice" rule)."""
    import random

    done = set(tried)
    pool = sorted((f, p, a) for f in formats for p, a in pairs if (f, p, a) not in done)
    rng = random.Random(seed)
    return [Idea(*c, why="random: no learning (baseline)") for c in rng.sample(pool, min(n, len(pool)))]
