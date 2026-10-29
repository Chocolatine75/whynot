"""Test-retest: how much do simulated scores move when the same feeds are watched again? (E3-3)

The same feeds, the same personas, a fresh draw from the model (`Viewer(draw=1)`,
so the answer cache can't return the first answer). Whatever changes between
the two runs is noise, so it sets the smallest difference we may call real:

- `floor`: 1.96 × √2 × the standard deviation of (run 1 − run 2) per ad. A
  retest difference carries two independent draws of noise (SD √2·σ). Two ads
  in the same feeds are not independent: when one is picked the other can't
  be, so the gap between two equally good ads can reach 2·σ = √2 × the retest
  SD (correlation −1, the worst case). A gap below the floor is reported as
  "within noise", never as a win.
  Measured on a noisy fake world (150 seeds, two equal and two clearly
  different groups): with 8 ads, 90 % of real gaps clear it and 9 % of gaps
  between equal ads do; with 4 ads the SD estimate is rough (87 % / 18 %), so
  retest at least 8 ads;
- `rank_agreement`: Kendall tau between the two runs' scores;
- `pick_agreement`: share of views (viewer × feed) where the same ad was
  preferred both times.
All numbers are SIMULATED.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from whynot.sim.feed import Feed
from whynot.sim.personas import Persona
from whynot.sim.scores import AdScore, score_ads
from whynot.sim.viewer import Reaction, SimResult, Viewer, run_simulation
from whynot.validate.stats import kendall_tau

Z95 = 1.959964
WORST_CASE_CORRELATION = math.sqrt(2)  # see `floor` above


@dataclass(frozen=True)
class RetestResult:
    ads: int  # ads scored in both runs
    floor: float  # smallest difference between two ads' scores we report as real (score units)
    rank_agreement: float | None  # Kendall tau between runs; None when a run's scores are all equal
    pick_agreement: float | None  # same preferred ad in both runs, share of matched views; None if no match
    views: int  # matched views
    usd: float = 0.0
    simulated: bool = True

    def is_real(self, difference: float) -> bool:
        return abs(difference) > self.floor


def noise_floor(first: dict[str, float], second: dict[str, float]) -> float:
    """1.96 × √2 × SD of per-ad differences between two runs (sample SD, n − 1)."""
    common = sorted(set(first) & set(second))
    if len(common) < 2:
        raise ValueError("need at least 2 ads scored in both runs")
    diffs = [first[k] - second[k] for k in common]
    mean = sum(diffs) / len(diffs)
    var = sum((d - mean) ** 2 for d in diffs) / (len(diffs) - 1)
    return Z95 * WORST_CASE_CORRELATION * math.sqrt(var)


def pick_agreement(first: list[Reaction], second: list[Reaction]) -> tuple[float | None, int]:
    """(share of views with the same preferred ad in both runs, number of views seen in both)."""
    def picks(rs: list[Reaction]) -> dict[tuple[str, str], str]:
        return {(r.feed_id, r.persona_id): r.ad_id for r in rs if r.preferred}

    a, b = picks(first), picks(second)
    both = set(a) & set(b)
    if not both:
        return None, 0
    return sum(a[k] == b[k] for k in both) / len(both), len(both)


def compare(first: list[Reaction], second: list[Reaction], *, ads: set[str] | None = None,
            metric: Callable[[AdScore], float] = lambda s: s.preference_lift, usd: float = 0.0) -> RetestResult:
    """`ads`: the ads whose differences we will report (our variants). Default: every ad scored.

    Restrict it when the feeds also hold ads that are almost never picked (competitors next to strong
    variants): their scores barely move, and pooling them would make the floor too low for the ads we judge.
    """
    s1 = {k: metric(v) for k, v in score_ads(first).items() if ads is None or k in ads}
    s2 = {k: metric(v) for k, v in score_ads(second).items() if ads is None or k in ads}
    common = sorted(set(s1) & set(s2))
    try:
        tau: float | None = kendall_tau([s1[k] for k in common], [s2[k] for k in common])
    except ValueError:
        tau = None
    picks, views = pick_agreement(first, second)
    return RetestResult(len(common), noise_floor(s1, s2), tau, picks, views, usd)


def retest(viewer: Viewer, personas: list[Persona], feeds: list[Feed], *, viewers_per_feed: int,
           first: SimResult | None = None, **kwargs) -> RetestResult:
    """Run the feeds again with a fresh draw (and the first time too unless `first` is given), then compare."""
    if first is None:
        first = run_simulation(viewer, personas, feeds, viewers_per_feed=viewers_per_feed)
    again = Viewer(viewer.client, max_tokens=viewer.max_tokens, retries=viewer.retries,
                   reasoning_effort=viewer.reasoning_effort, cache=viewer.cache, draw=viewer.draw + 1)
    second = run_simulation(again, personas, feeds, viewers_per_feed=viewers_per_feed)
    return compare(first.reactions, second.reactions, usd=first.usd + second.usd, **kwargs)
