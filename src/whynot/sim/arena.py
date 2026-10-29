"""Fair simulated feeds for our ad variants, with a built-in placebo.

What we learned on the first real runs (scripts/sim_bias_check.py, VietBuddy):
the same competitor ads scored 0.50× chance under their own page name and
3.50× under "VietBuddy: Learn Vietnamese" — the advertiser name alone drove
preference. So:

- our ads appear under the brand name a Facebook page would show ("VietBuddy"),
  not the App Store title ("VietBuddy: Learn Vietnamese");
- every feed holds TWO candidate slots (two of our variants, or one variant and
  a placebo) plus real competitor ads; the name is identical in both slots, so
  name bias cancels in the head-to-head;
- placebos are real competitor ads presented exactly like ours (our name, our
  format). Their lift measures the bias left in the setup. Our variants are
  judged relative to it, and the run is flagged when the placebo itself wins.
All numbers are SIMULATED.
"""

import random
import re
from dataclasses import dataclass

from whynot.sim.feed import Feed, FeedItem, build_market_feeds
from whynot.sim.scores import AdScore

PLACEBO = "placebo:"
# A fair setup puts a typical competitor ad near 1.0× chance; a fully name-driven viewer puts anything under our
# name at feed_size / 2 (2.0× in feeds of 4: it picks one of the two candidate slots). Flag at the midpoint.
BIAS_THRESHOLD = 1.5


def brand_name(app_name: str) -> str:
    """The page-style name: "VietBuddy: Learn Vietnamese" → "VietBuddy"; "Flighty – Live…" → "Flighty"."""
    head = re.split(r"\s*[:|]\s*|\s+[-–—]\s+", app_name.strip(), maxsplit=1)[0].strip()
    return head or app_name.strip()


def our_item(variant_id: str, brand: str, texts: dict[str, str]) -> FeedItem:
    image = texts["hook"] + (f" — {texts['proof']}" if texts.get("proof") else "")
    return FeedItem(variant_id, brand, texts.get("title", ""), f"{texts['body']}\n[image text: {image}]")


def placebo_item(ad: FeedItem, brand: str) -> FeedItem:
    """A real competitor ad dressed exactly like ours: same name, same layout."""
    image = ad.title or ad.body.split(".")[0][:70]
    return FeedItem(PLACEBO + ad.ad_id, brand, ad.title, f"{ad.body}\n[image text: {image}]")


def is_placebo(ad_id: str) -> bool:
    return ad_id.startswith(PLACEBO)


def paired_feeds(candidates: list[FeedItem], competitors: list[FeedItem], *, feed_size: int, appearances: int,
                 seed: int = 0) -> list[Feed]:
    """Each feed = 2 candidate slots (balanced pairs) + (feed_size - 2) competitor ads, never duplicated."""
    if feed_size < 3:
        raise ValueError("feed_size must be at least 3 (2 candidates + 1 competitor)")
    if len(candidates) < 2:
        raise ValueError("need at least 2 candidates (variants or placebos)")
    rng = random.Random(seed)
    used_as_placebo = {c.ad_id.removeprefix(PLACEBO) for c in candidates if is_placebo(c.ad_id)}
    pool = [c for c in competitors if c.ad_id not in used_as_placebo]
    if len(pool) < feed_size - 2:
        raise ValueError("not enough competitor ads to fill the feeds")
    pairs = build_market_feeds(candidates, feed_size=2, appearances=appearances, seed=seed)
    return [[*pair, *rng.sample(pool, feed_size - 2)] for pair in pairs]


@dataclass(frozen=True)
class Verdict:
    variant_id: str
    lift: float  # preference vs chance, in fair feeds
    lift_over_placebo: float  # lift − mean placebo lift (chance units): > 0 = beats a real competitor ad under our name
    intent: float
    intent_vs_placebo: float  # difference in mean intent (1–5 scale)
    views: int


@dataclass(frozen=True)
class ArenaResult:
    verdicts: dict[str, Verdict]
    placebo_lift: float
    placebo_intent: float
    placebos: int
    placebo_views: int

    @property
    def biased(self) -> bool:
        return self.placebo_lift > BIAS_THRESHOLD


def judge(scores: dict[str, AdScore], candidates: set[str]) -> ArenaResult:
    """Verdicts for our candidates only (competitor ads in the same feeds are ignored)."""
    scores = {k: s for k, s in scores.items() if k in candidates}
    placebos = [s for k, s in scores.items() if is_placebo(k)]
    if not placebos:
        raise ValueError("no placebo was scored: cannot judge bias")
    p_lift = sum(s.preference_lift for s in placebos) / len(placebos)
    p_intent = sum(s.mean_intent for s in placebos) / len(placebos)
    verdicts = {k: Verdict(k, s.preference_lift, s.preference_lift - p_lift, s.mean_intent, s.mean_intent - p_intent,
                           s.views)
                for k, s in scores.items() if not is_placebo(k)}
    return ArenaResult(verdicts, p_lift, p_intent, len(placebos), sum(s.views for s in placebos))
