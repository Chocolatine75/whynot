"""Bias suite: does the simulator pick an ad for something other than what it says? (E2-6)

Each check builds twins from real ads: a control and a treated copy that differ
in ONE attribute (the name it runs under, its length, emojis, a leaked "our ad"
label, its language). Both twins go into the same feed, with filler ads, under
neutral labels and in a random order per viewer. A simulator that judges
content picks the treated twin as often as the control. So:

- effect = treated picks / twin picks − 0.5 (0 = no bias, +0.5 = always the treated one);
- flagged when |effect| >= `threshold` AND the two-sided binomial p < `alpha`.
  Both: a tiny effect on many views is not worth failing for, a large one on
  few views may be luck.

The position check reuses every feed of the suite: viewers see items in a
random order, so the first slot should win 1 / feed size of the time.

Checks run on any `Viewer`: on recorded answers (cassettes, $0) on every
simulator change, on the live model when the prompt or the model changes.
All numbers are SIMULATED.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from whynot.sim.feed import Feed, FeedItem
from whynot.sim.personas import Persona
from whynot.sim.viewer import Reaction, Viewer, run_simulation
from whynot.validate.stats import binomial_two_sided_p

CONTROL, TREATED = "~control", "~treated"
FILLER_SENTENCE = " Available on iPhone and Android. Terms apply. Learn more on our website."
EMOJIS = " \U0001f525✨\U0001f680"  # fire, sparkles, rocket: the usual ad emojis
LEAK = " (our ad)"

Treatment = Callable[[FeedItem], FeedItem]


def under_brand(brand: str) -> Treatment:
    """The same ad shown under our brand name instead of its own page name."""
    return lambda item: replace(item, advertiser=brand)


def longer(item: FeedItem) -> FeedItem:
    return replace(item, body=item.body + FILLER_SENTENCE)


def with_emojis(item: FeedItem) -> FeedItem:
    return replace(item, body=item.body + EMOJIS)


def leaked_label(item: FeedItem) -> FeedItem:
    return replace(item, body=item.body + LEAK)


def translated(translations: dict[str, str]) -> Treatment:
    """The same ad in another language (`translations`: ad id → translated body, from a human or a model)."""
    return lambda item: replace(item, body=translations[item.ad_id])


@dataclass(frozen=True)
class Check:
    name: str
    treatment: Treatment
    threshold: float = 0.10


def standard_checks(brand: str) -> list[Check]:
    return [Check("brand_name", under_brand(brand)), Check("copy_length", longer), Check("emoji", with_emojis),
            Check("label_leak", leaked_label)]


def twin_feeds(items: list[FeedItem], fillers: list[FeedItem], treatment: Treatment, *, feed_size: int,
               feeds_per_item: int, seed: int = 0) -> list[Feed]:
    """`feeds_per_item` feeds per item, each = its control twin + its treated twin + fillers."""
    if feed_size < 3:
        raise ValueError("feed_size must be at least 3 (2 twins + 1 filler)")
    ids = {i.ad_id for i in items}
    pool = [f for f in fillers if f.ad_id not in ids]
    if len(pool) < feed_size - 2:
        raise ValueError("not enough filler ads")
    rng = random.Random(seed)
    feeds = []
    for item in items:
        control = replace(item, ad_id=item.ad_id + CONTROL)
        treated = replace(treatment(item), ad_id=item.ad_id + TREATED)
        for _ in range(feeds_per_item):
            feeds.append([control, treated, *rng.sample(pool, feed_size - 2)])
    return feeds


@dataclass(frozen=True)
class CheckResult:
    name: str
    effect: float  # treated share of twin picks − 0.5
    p: float
    picks: int  # picks counted: of one of the twins (twin checks), of any ad (position)
    views: int
    threshold: float
    alpha: float
    simulated: bool = True

    @property
    def flagged(self) -> bool:
        return abs(self.effect) >= self.threshold and self.p < self.alpha


def twin_effect(name: str, reactions: list[Reaction], *, threshold: float, alpha: float) -> CheckResult:
    picks = [r for r in reactions if r.preferred]
    twins = [r for r in picks if r.ad_id.endswith((CONTROL, TREATED))]
    treated = sum(r.ad_id.endswith(TREATED) for r in twins)
    if not twins:
        return CheckResult(name, 0.0, 1.0, 0, len(picks), threshold, alpha)
    return CheckResult(name, treated / len(twins) - 0.5, binomial_two_sided_p(treated, len(twins)), len(twins),
                       len(picks), threshold, alpha)


def position_effect(reactions: list[Reaction], feed_size: int, *, threshold: float = 0.10,
                    alpha: float = 0.05) -> CheckResult:
    """First-slot picks vs 1 / feed_size (feeds of other sizes are ignored)."""
    sizes: dict[tuple[str, str], int] = {}
    for r in reactions:
        sizes[(r.feed_id, r.persona_id)] = sizes.get((r.feed_id, r.persona_id), 0) + 1
    picks = [r for r in reactions if r.preferred and sizes[(r.feed_id, r.persona_id)] == feed_size]
    if not picks:
        return CheckResult("position", 0.0, 1.0, 0, 0, threshold, alpha)
    first = sum(r.position == 0 for r in picks)
    return CheckResult("position", first / len(picks) - 1 / feed_size,
                       binomial_two_sided_p(first, len(picks), 1 / feed_size), len(picks), len(picks), threshold,
                       alpha)


@dataclass
class SuiteResult:
    checks: list[CheckResult] = field(default_factory=list)
    usd: float = 0.0
    failures: int = 0  # viewers that gave no valid answer

    @property
    def flagged(self) -> list[str]:
        return [c.name for c in self.checks if c.flagged]


def run_suite(viewer: Viewer, personas: list[Persona], items: list[FeedItem], fillers: list[FeedItem],
              checks: list[Check], *, feed_size: int = 4, feeds_per_item: int = 3, viewers_per_feed: int = 2,
              alpha: float = 0.05, seed: int = 0) -> SuiteResult:
    """Every check on the same items and fillers, then the position check over all their feeds.

    Default size, measured on a fake world (12 items, 40 seeds): 72 views per check catch a bias worth
    one logit (treated twin picked ~73 % of the time) in >= 92 % of runs, with 3 % false alarms on a
    fair simulator. With 2 feeds per item, detection drops to 75-95 %."""
    result = SuiteResult()
    everything: list[Reaction] = []
    for i, check in enumerate(checks):
        feeds = twin_feeds(items, fillers, check.treatment, feed_size=feed_size, feeds_per_item=feeds_per_item,
                           seed=seed + i)
        sim = run_simulation(viewer, personas, feeds, viewers_per_feed=viewers_per_feed)
        # feed ids restart at F0 for each check: make them unique before pooling for the position check
        everything += [replace(r, feed_id=f"{check.name}:{r.feed_id}") for r in sim.reactions]
        result.usd += sim.usd
        result.failures += len(sim.failures)
        result.checks.append(twin_effect(check.name, sim.reactions, threshold=check.threshold, alpha=alpha))
    result.checks.append(position_effect(everything, feed_size, alpha=alpha))
    return result


def estimated_calls(n_items: int, n_checks: int, *, feeds_per_item: int, viewers_per_feed: int) -> int:
    return n_items * n_checks * feeds_per_item * viewers_per_feed
