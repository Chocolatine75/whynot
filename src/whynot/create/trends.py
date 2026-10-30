"""Viral formats: the structures people already watch to the end, turned into ads ("trend-jacking").

A trend ad is 70 % the trend (people stay for it), then the twist where the app is the punchline, then
the call to action. We reuse a FORMAT (a structure, which nobody owns), never a trending song or someone
else's clip: sounds are licensed, and Meta mutes or rejects ads using them.

`FORMATS` is our library (written for whynot): each format has its beats (what happens, in order, and
how long), why it holds attention, and what it takes to produce with our assets (text, the app's real
screens, the mascot, generated photos, a voice). `trending` measures which formats competitors are
starting to use now, from the deconstructed Ad Library ads (start dates).
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from whynot.ingest.adlibrary import CompetitorAd

if TYPE_CHECKING:  # deconstruct imports this module for the format ids
    from whynot.agents.deconstruct import Deconstruction


@dataclass(frozen=True)
class Format:
    id: str
    name: str
    beats: tuple[str, ...]  # what happens, in order
    why: str  # why it holds attention
    needs: tuple[str, ...]  # assets: text, screen, mascot, photo, voice
    example: str  # the shape, with a placeholder app


FORMATS: tuple[Format, ...] = (
    Format("pov", "POV", ("POV caption sets a relatable situation (0-1.5 s)",
                          "the situation escalates in 3-5 quick shots", "twist: the app saves the moment", "CTA"),
           "Second person puts the viewer inside the scene; escalation keeps them waiting for the release.",
           ("text", "photo", "screen", "voice"), "POV: your grandma calls and she only speaks the Southern dialect"),
    Format("tell_me_without", "Tell me you're X without telling me you're X",
           ("the challenge line", "3-4 telltale signs, one per shot, faster each time",
            "twist: the app as the last sign", "CTA"),
           "Recognition: viewers tick the signs off for themselves and stay to see if the last one is theirs.",
           ("text", "photo", "screen"), "Tell me you're learning Vietnamese without telling me"),
    Format("expectation_reality", "Expectation vs reality",
           ("EXPECTATION label + the glossy version", "REALITY label + the honest, funny version",
            "twist: the app closes the gap", "CTA"),
           "Contrast and self-mockery; the cut to REALITY is the laugh.", ("text", "photo", "screen"),
           "Expectation: fluent after a month. Reality: 'ma' means six different things"),
    Format("nobody_me", "Nobody: / Me:",
           ("'Nobody:' on an empty frame", "'Me:' + an over-the-top behaviour", "twist: the app is why", "CTA"),
           "A meme everyone reads in half a second; the absurd beat is the hook.", ("text", "mascot", "screen"),
           "Nobody: / Me at 2 am: practising tones with a cartoon buffalo"),
    Format("things_that_make_sense", "Things that just make sense",
           ("title card", "3-4 satisfying 'it just makes sense' items, quick cuts", "the app as the final item", "CTA"),
           "A list of small satisfactions; each cut is a tiny reward.", ("text", "photo", "screen"),
           "Things that just make sense: learning the accent your family actually speaks"),
    Format("rating", "Rating X out of 10",
           ("'Rating every way to learn Vietnamese'", "3 options rated low with a reason each, fast",
            "the app rated 10/10 with the reason", "CTA"),
           "Scores create suspense: viewers wait for the top score.", ("text", "photo", "screen", "voice"),
           "Rating ways to learn Vietnamese: textbooks 3/10, flashcards 5/10..."),
    Format("wait_for_it", "Wait for it",
           ("'wait for it' caption over a slow build", "tension shots", "payoff: the app moment", "CTA"),
           "An explicit promise of a payoff keeps thumbs still.", ("text", "screen", "mascot"),
           "Wait for it... grandma understanding you for the first time"),
    Format("this_or_that", "This or that",
           ("split choice A vs B", "2-3 rounds, faster", "last round: old way vs the app", "CTA"),
           "The viewer plays along and picks; a game in the feed.", ("text", "photo", "screen"),
           "Northern or Southern? Pick the one your family speaks"),
    Format("starter_pack", "Starter pack",
           ("'<persona> starter pack' title", "4-5 items pop in one by one", "the app pops in last, biggest", "CTA"),
           "Identity: people share what describes them.", ("text", "photo", "mascot", "screen"),
           "Heritage Vietnamese learner starter pack"),
    Format("day_in_the_life", "Day in the life",
           ("time stamps through a day, 1 s each", "the struggle moment", "the app in a 5-minute gap", "CTA"),
           "Voyeur rhythm: time stamps promise a story with an end.", ("text", "photo", "screen", "voice"),
           "Day in the life of someone learning Vietnamese for their in-laws"),
    Format("unhinged_mascot", "Unhinged mascot",
           ("the mascot breaks the fourth wall", "it escalates (guilt, threats, drama)", "it shows the app", "CTA"),
           "A brand character with personality; viewers follow it like a creator.",
           ("mascot", "text", "screen", "voice"),
           "The buffalo when you skip your tones practice"),
    Format("green_screen_reply", "Replying to a comment",
           ("a comment bubble asking a real question", "the answer, step by step", "the app as the answer", "CTA"),
           "Looks like a creator answering a fan; native to the feed.", ("text", "screen", "voice"),
           "Replying to: 'is Southern Vietnamese really that different?'"),
)
BY_ID = {f.id: f for f in FORMATS}
NONE = "none"  # a competitor ad that follows no known format


@dataclass(frozen=True)
class TrendSignal:
    format: str
    ads: int  # competitor ads in this format
    new_ads: int  # started in the last `window_days`
    advertisers: int
    share_new: float  # new_ads / all new ads in the market


def trending(decons: "dict[str, Deconstruction]", ads: list[CompetitorAd], *, as_of: date,
             window_days: int = 14) -> list[TrendSignal]:
    """Formats competitors use, most started recently first (from deconstructions with a `trend_format`)."""
    by_id = {a.id: a for a in ads}
    since = as_of - timedelta(days=window_days)
    total: Counter[str] = Counter()
    new: Counter[str] = Counter()
    advertisers: dict[str, set[str]] = {}
    for ad_id, d in decons.items():
        f = getattr(d, "trend_format", NONE) or NONE
        a = by_id.get(ad_id)
        if a is None or f == NONE:
            continue
        total[f] += 1
        advertisers.setdefault(f, set()).add(a.page_id or a.page_name or "")
        if a.start_date and a.start_date >= since:
            new[f] += 1
    all_new = sum(new.values()) or 1
    out = [TrendSignal(f, total[f], new[f], len(advertisers[f]), round(new[f] / all_new, 3)) for f in total]
    return sorted(out, key=lambda s: (-s.new_ads, -s.ads, s.format))
