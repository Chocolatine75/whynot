"""Hard feeds: put the competitor ads that survived in our market next to ours (E3-1).

The first real runs showed our variants winning almost every feed. Part of the
reason was the feeds: the research market (EU/UK Ad Library) mixes ads in
other languages and ads for other products, which a viewer skips at once. An
ad that beats those proves little. So each feed now takes the most relevant
competitor ads first:

1. same language as our ads (an English ad in a French feed is no rival);
2. long-running (still active after `long_days`): ads that paid for themselves;
3. closest in topic to our app (shared content words);
4. longest-running.

Scout has already kept only advertisers judged to be competitors (category).
When too few ads match the language, the rest is filled from the next best and
the shortfall is reported, never hidden.

`guess_language` is a stop-word heuristic for the languages we advertise in:
cheap, deterministic, and good enough to drop obvious mismatches. It answers
None when the text has too few signal words, and such ads are kept (unknown is
not a mismatch).
"""

import re
from dataclasses import dataclass
from datetime import date

from whynot.ingest.adlibrary import CompetitorAd

STOPWORDS = {
    "en": "the and you your for with this that are our now from get can will what more all have just",
    "fr": "le la les de des une est vous votre pour avec dans sur pas qui que nos plus tout et du au",
    "de": "der die das und ist sie ihr mit für nicht ein eine auf den dem jetzt auch wie noch zu",
    "es": "el los las una por para con que del más ahora sin sus está como pero muy tu y",
    "it": "il gli una per con che non più sono della alla questo come anche tuo ora di",
    "pt": "os uma para com que não mais seu sua você agora como pelo dos das também",
    "nl": "de het een en van voor met niet je jouw ook nu op zijn dat wat",
}
_WORDS = {code: set(words.split()) for code, words in STOPWORDS.items()}
_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)
# Words too common in ads to say anything about the topic.
_GENERIC = {"app", "free", "now", "today", "new", "download", "get", "try", "best", "day", "days", "minutes"}


def words(text: str) -> list[str]:
    return [w.lower() for w in _TOKEN.findall(text)]


def guess_language(text: str, *, min_hits: int = 2) -> str | None:
    """The language whose stop words appear most, or None when the evidence is thin or tied."""
    counts = {code: 0 for code in _WORDS}
    for w in words(text):
        for code, stop in _WORDS.items():
            if w in stop:
                counts[code] += 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    (best, n), (_, runner_up) = ranked[0], ranked[1]
    if n < min_hits or n == runner_up:
        return None
    return best


def topic_words(text: str) -> set[str]:
    """Content words: no stop word in any language, no generic ad word, at least 4 letters."""
    every_stop = set().union(*_WORDS.values())
    return {w for w in words(text) if len(w) >= 4 and w not in every_stop and w not in _GENERIC}


def ad_text(ad: CompetitorAd) -> str:
    return " ".join([*(ad.titles or [])[:1], *(ad.bodies or [])[:1]])


@dataclass(frozen=True)
class Ranked:
    ad: CompetitorAd
    language: str | None
    language_ok: bool
    long_running: bool
    topic_overlap: float  # share of the ad's content words that are in our topic
    days: int

    @property
    def key(self) -> tuple:
        return (not self.language_ok, not self.long_running, -round(self.topic_overlap, 2), -self.days, self.ad.id)


@dataclass(frozen=True)
class HardSet:
    ads: list[CompetitorAd]  # most relevant first
    ranked: list[Ranked]
    wrong_language_used: int  # ads taken from another language to reach `k` (0 when enough matched)


def rank_competitors(ads: list[CompetitorAd], *, language: str, topic: str, as_of: date,
                     long_days: int = 60) -> list[Ranked]:
    mine = topic_words(topic)
    out = []
    for ad in ads:
        text = ad_text(ad)
        if not text.strip():
            continue  # nothing for a viewer to read
        lang = guess_language(text)
        theirs = topic_words(text)
        days = ad.longevity_days(as_of) or 0
        out.append(Ranked(ad, lang, lang in (None, language), ad.stop_date is None and days >= long_days,
                          len(theirs & mine) / len(theirs) if theirs else 0.0, days))
    return sorted(out, key=lambda r: r.key)


def hard_competitors(ads: list[CompetitorAd], *, language: str, topic: str, as_of: date, k: int,
                     long_days: int = 60) -> HardSet:
    """The `k` most relevant competitor ads for feeds in `language` (fewer only if fewer have text)."""
    if k < 1:
        raise ValueError("k must be at least 1")
    ranked = rank_competitors(ads, language=language, topic=topic, as_of=as_of, long_days=long_days)[:k]
    return HardSet([r.ad for r in ranked], ranked, sum(not r.language_ok for r in ranked))
