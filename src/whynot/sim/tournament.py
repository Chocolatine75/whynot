"""Tournament between our variants: round-robin fair feeds, ranked by Bradley-Terry with CIs (E3-2).

Why: in arena feeds (`arena.py`) our variants are scored against competitor ads.
When they beat the market easily, every variant hits the ceiling (always
picked) and the scores can no longer tell them apart, nor show evolution's
progress. Head-to-head games between our own variants have no ceiling.

- `round_robin_feeds`: every pair of candidates meets in `rounds` feeds; each
  feed = the two candidates + real competitor ads, so viewers still scroll a
  realistic feed and can prefer neither of ours;
- `head_to_head`: one game per viewer per feed: the candidate the viewer
  preferred wins; if they preferred a competitor ad, the higher intent wins; an
  equal intent is a tie (half a win each);
- `rank`: Bradley-Terry log-strengths, with bootstrap CIs over viewers.

Add a placebo (a competitor ad under our name, `arena.placebo_item`) as a
candidate to get a reference point: variants below it lose to a real
competitor ad presented like ours. All numbers are SIMULATED.
"""

import random
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from whynot.sim.feed import Feed, FeedItem
from whynot.sim.viewer import Reaction
from whynot.validate.stats import Outcome, bradley_terry


def round_robin_feeds(candidates: list[FeedItem], competitors: list[FeedItem], *, feed_size: int, rounds: int = 1,
                      seed: int = 0) -> list[Feed]:
    """`rounds` feeds per pair of candidates, each with (feed_size - 2) different competitor ads."""
    if feed_size < 3:
        raise ValueError("feed_size must be at least 3 (2 candidates + 1 competitor)")
    if rounds < 1:
        raise ValueError("rounds must be at least 1")
    ids = [c.ad_id for c in candidates]
    if len(set(ids)) != len(ids) or len(ids) < 2:
        raise ValueError("need at least 2 candidates with unique ids")
    pool = [c for c in competitors if c.ad_id not in set(ids)]
    if len(pool) < feed_size - 2:
        raise ValueError("not enough competitor ads to fill the feeds")
    rng = random.Random(seed)
    feeds = []
    for _ in range(rounds):
        for a, b in combinations(candidates, 2):
            feed = [a, b, *rng.sample(pool, feed_size - 2)]
            rng.shuffle(feed)
            feeds.append(feed)
    rng.shuffle(feeds)  # pairs in random order: viewers assigned round-robin don't all see the same pairs
    return feeds


def head_to_head(reactions: list[Reaction], candidates: set[str]) -> list[list[Outcome]]:
    """Games between candidates, grouped by view (one viewer watching one feed): the unit to resample."""
    views: dict[tuple[str, str], list[Reaction]] = defaultdict(list)
    for r in reactions:
        if r.ad_id in candidates:
            views[(r.feed_id, r.persona_id)].append(r)
    out = []
    for key in sorted(views):
        games: list[Outcome] = []
        for x, y in combinations(sorted(views[key], key=lambda r: r.ad_id), 2):
            if x.preferred != y.preferred:
                score = 1.0 if x.preferred else 0.0
            elif x.intent_score != y.intent_score:
                score = 1.0 if x.intent_score > y.intent_score else 0.0
            else:
                score = 0.5
            games.append((x.ad_id, y.ad_id, score))
        if games:
            out.append(games)
    return out


@dataclass(frozen=True)
class Standing:
    ad_id: str
    strength: float  # Bradley-Terry log-strength, mean 0 across candidates
    ci: tuple[float, float]  # 95 % bootstrap interval over viewers
    games: int
    wins: float  # ties count half


@dataclass(frozen=True)
class TournamentResult:
    standings: list[Standing]  # strongest first
    views: int  # viewer x feed observations that produced games
    simulated: bool = True

    def strength(self, ad_id: str) -> float:
        return next(s.strength for s in self.standings if s.ad_id == ad_id)

    def clearly_ahead(self, a: str, b: str) -> bool:
        """`a`'s whole CI is above `b`'s: a difference we are willing to report."""
        sa = next(s for s in self.standings if s.ad_id == a)
        sb = next(s for s in self.standings if s.ad_id == b)
        return sa.ci[0] > sb.ci[1]


def rank(reactions: list[Reaction], candidates: set[str], *, bootstrap: int = 300, seed: int = 0) -> TournamentResult:
    """Bradley-Terry standings of `candidates` from viewer reactions to round-robin feeds."""
    views = head_to_head(reactions, candidates)
    if not views:
        raise ValueError("no head-to-head game between candidates: nothing to rank")
    names = sorted(candidates)
    flat = [g for v in views for g in v]
    point = bradley_terry(flat, names)
    rng = random.Random(seed)
    samples: dict[str, list[float]] = {n: [] for n in names}
    for _ in range(bootstrap):
        resample = [g for _ in views for g in views[rng.randrange(len(views))]]
        for n, v in bradley_terry(resample, names, iterations=200, tol=1e-8).items():
            samples[n].append(v)
    games: dict[str, int] = dict.fromkeys(names, 0)
    wins: dict[str, float] = dict.fromkeys(names, 0.0)
    for a, b, score in flat:
        games[a] += 1
        games[b] += 1
        wins[a] += score
        wins[b] += 1 - score

    def ci(values: list[float]) -> tuple[float, float]:
        if not values:  # bootstrap=0: no interval, so nothing is ever "clearly ahead"
            return float("-inf"), float("inf")
        values = sorted(values)
        cut = int(0.025 * (len(values) - 1))
        return values[cut], values[-1 - cut]

    standings = [Standing(n, point[n], ci(samples[n]), games[n], wins[n]) for n in names]
    standings.sort(key=lambda s: (-s.strength, s.ad_id))
    return TournamentResult(standings, len(views))
