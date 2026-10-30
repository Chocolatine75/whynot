"""Hard feeds: same language, long-running and on-topic competitors first; a weak ad can no longer win easily."""

import json
import math
import random
import re
from datetime import date, timedelta
from types import SimpleNamespace as NS

import pytest

from whynot.ingest.adlibrary import CompetitorAd
from whynot.sim.feed import FeedItem, build_candidate_feeds
from whynot.sim.personas import Persona
from whynot.sim.relevance import guess_language, hard_competitors, rank_competitors, topic_words
from whynot.sim.scores import score_ads
from whynot.sim.viewer import Viewer, run_simulation

TODAY = date(2026, 10, 30)


def comp(ad_id, body, *, days=90, running=True, title=""):
    start = TODAY - timedelta(days=days)
    return CompetitorAd(ad_id, "p", f"Page {ad_id}", [body], [title] if title else [], start,
                        None if running else start + timedelta(days=days), [], None, [], None)


@pytest.mark.parametrize(("text", "code"), [
    ("Learn the words you need for your next trip, and speak with confidence from day one.", "en"),
    ("Apprenez le vietnamien avec des leçons courtes pour parler avec votre famille.", "fr"),
    ("Lerne die Sprache deiner Familie mit kurzen Lektionen und sprich endlich mit ihr.", "de"),
    ("Aprende el idioma de tu familia con lecciones cortas para hablar con ellos ahora.", "es"),
    ("Impara la lingua della tua famiglia con lezioni brevi per parlare con loro ora.", "it"),
])
def test_guess_language(text, code):
    assert guess_language(text) == code


def test_thin_or_tied_evidence_is_unknown():
    assert guess_language("VietBuddy") is None
    assert guess_language("Download now") is None  # one signal word only


def test_topic_words_drop_stop_words_and_generic_ad_words():
    assert topic_words("Download the free app to learn Vietnamese today") == {"learn", "vietnamese"}


def test_ranking_order_language_then_survival_then_topic_then_days():
    ads = [
        comp("en_long", "Learn Vietnamese with your family, the app that you will love.", days=300),
        comp("fr_short", "Apprenez le vietnamien pour parler avec votre famille.", days=5, running=False),
        comp("fr_long_off", "Réservez vos vacances au soleil avec nos offres pour la famille.", days=200),
        comp("fr_long_on", "Apprenez le vietnamien pour parler avec votre famille.", days=80),
        comp("fr_long_on_older", "Le vietnamien pour parler avec votre famille, avec des leçons.", days=400),
        comp("empty", "   "),
    ]
    ranked = rank_competitors(ads, language="fr", topic="Apprendre le vietnamien, parler avec la famille",
                              as_of=TODAY)
    order = [r.ad.id for r in ranked]
    assert order[-1] == "en_long" and "empty" not in order
    assert order.index("fr_long_on") < order.index("fr_long_off") < order.index("fr_short")
    assert order.index("fr_long_on_older") < order.index("fr_long_off")


def test_shortfall_in_the_language_is_reported():
    ads = [comp("fr", "Apprenez le vietnamien avec votre famille."),
           comp("en", "Learn Vietnamese with your family and your friends.")]
    hard = hard_competitors(ads, language="fr", topic="vietnamien famille", as_of=TODAY, k=2)
    assert [a.id for a in hard.ads] == ["fr", "en"] and hard.wrong_language_used == 1
    assert hard_competitors(ads, language="fr", topic="x", as_of=TODAY, k=1).wrong_language_used == 0
    with pytest.raises(ValueError):
        hard_competitors(ads, language="fr", topic="x", as_of=TODAY, k=0)


# --- fake world: a French viewer, a weak ad of ours -------------------------------------------

class FrenchViewer:
    """Skips ads not in French; otherwise prefers the highest quality Q (title) plus noise."""

    def viewer_chat(self, messages, **kwargs):
        rng = random.Random(json.dumps(messages))
        blocks = re.findall(r"\[(A\d+)\] Sponsored · .*?Title: Q=(-?[\d.]+)\nText: (.*?)(?:\n\n|$)",
                            messages[1]["content"], re.S)
        u = {lab: (float(q) if guess_language(body) in ("fr", None) else -3.0) - math.log(-math.log(rng.random()))
             for lab, q, body in blocks}
        best = max(u, key=lambda k: u[k])
        return NS(text=json.dumps({"reactions": [{"ad": lab, "stopped": lab == best, "understood": True,
                                                  "believed": True, "why_not": "", "intent": "",
                                                  "intent_score": 3} for lab in u], "preferred": best}),
                  cost=NS(usd=0.0))


def market():
    strong = [comp(f"s{i}", "Apprenez le vietnamien pour parler avec votre famille, enfin.", title="Q=1.5",
                   days=120 + i) for i in range(6)]
    english = [comp(f"e{i}", "Learn Vietnamese with your family, the app that you will love.", title="Q=1.5",
                    days=200 + i) for i in range(14)]
    weak = [comp(f"w{i}", "Des vacances au soleil pour toute la famille et les enfants.", title="Q=-1",
                 days=4, running=False) for i in range(6)]
    return strong + english + weak


def lift(competitors, seed=0):
    ours = FeedItem("ours", "Ours", "Q=0", "Le vietnamien en dix minutes par jour, pour votre famille.")
    feeds = build_candidate_feeds(ours, [FeedItem.from_ad(a) for a in competitors], feed_size=4, n_feeds=40,
                                  seed=seed)
    personas = [Persona(f"p{i}", "FR", "25-34", "female") for i in range(4)]
    sim = run_simulation(Viewer(FrenchViewer()), personas, feeds, viewers_per_feed=2)
    return score_ads(sim.reactions)["ours"].preference_lift


def test_a_weak_ad_wins_a_random_market_but_loses_in_hard_feeds():
    ads = market()
    hard = hard_competitors(ads, language="fr", topic="Apprendre le vietnamien pour parler avec sa famille",
                            as_of=TODAY, k=6)
    assert {a.id for a in hard.ads} == {f"s{i}" for i in range(6)} and hard.wrong_language_used == 0
    easy, tough = lift(ads), lift(hard.ads)
    assert easy > 1.5  # looks like a winner next to foreign and off-topic ads
    assert tough < 1.0  # below chance against the ads that survived in its market
