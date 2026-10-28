"""Viewer agents, parsing and scores, on a scripted fake model (no network)."""

import json
import re
from types import SimpleNamespace as NS

import pytest

from whynot.sim.feed import FeedItem, build_market_feeds
from whynot.sim.personas import Persona
from whynot.sim.scores import score_ads
from whynot.sim.viewer import (
    Viewer,
    ViewerParseError,
    build_messages,
    parse_reactions,
    render_feed,
    run_simulation,
)


def item(i, body):
    return FeedItem(str(i), f"Brand {i}", f"Title {i}", body)


PERSONAS = [Persona(f"p{i}", "FR", "25-34", "female" if i % 2 else "male") for i in range(4)]


class ScriptedClient:
    """Prefers and rates highly any ad whose text contains GOOD."""

    def __init__(self, broken_first: int = 0):
        self.calls = 0
        self.broken_first = broken_first

    def viewer_chat(self, messages, **kwargs):
        self.calls += 1
        if self.calls <= self.broken_first:
            return NS(text="sorry, no JSON", cost=NS(usd=0.001))
        user = messages[1]["content"]
        blocks = re.findall(r"\[(A\d+)\] Sponsored · .*?\n.*?Text: (.*?)(?:\n\n|$)", user, re.S)
        reactions, preferred = [], None
        for label, body in blocks:
            good = "GOOD" in body
            if good and preferred is None:
                preferred = label
            reactions.append({"ad": label, "stopped": good, "understood": True, "believed": good,
                              "why_not": "" if good else "Not for me", "intent": "maybe",
                              "intent_score": 5 if good else 2})
        return NS(text="```json\n" + json.dumps({"reactions": reactions,
                                                 "preferred": preferred or blocks[0][0]}) + "\n```",
                  cost=NS(usd=0.002))


# --- prompt -------------------------------------------------------------------

def test_render_feed_uses_neutral_labels():
    text, labels = render_feed([item(7, "hello"), item(9, "world")])
    assert labels == {"A1": "7", "A2": "9"}
    assert "[A1] Sponsored · Brand 7" in text and "Text: world" in text


def test_messages_include_persona_and_images():
    feed = [item(1, "a"), FeedItem("2", "B", "", "b", image_url="data:image/png;base64,AAAA")]
    messages, _ = build_messages(PERSONAS[1], feed)
    assert "a woman aged 25-34 living in FR" in messages[0]["content"]
    parts = messages[1]["content"]
    assert parts[-1] == {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}


# --- parsing ------------------------------------------------------------------

LABELS = {"A1": "x", "A2": "y"}


def answer(**override):
    data = {"reactions": [
        {"ad": "A1", "stopped": True, "understood": True, "believed": "yes", "why_not": "",
         "intent": "I'd click", "intent_score": 4},
        {"ad": "A2", "stopped": False, "understood": "false", "believed": False, "why_not": "Too pricey",
         "intent": "No", "intent_score": "1"}],
        "preferred": "A1"}
    data.update(override)
    return json.dumps(data)


def test_parse_valid_answer():
    rs = parse_reactions("Here you go:\n" + answer(), LABELS, feed_id="F0", persona_id="p0")
    assert [r.ad_id for r in rs] == ["x", "y"]
    assert rs[0].preferred and not rs[1].preferred
    assert rs[0].believed is True and rs[1].understood is False
    assert rs[1].intent_score == 1 and rs[1].why_not == "Too pricey"


def test_parse_clamps_scores():
    data = json.loads(answer())
    data["reactions"][0]["intent_score"] = 9
    assert parse_reactions(json.dumps(data), LABELS, feed_id="F", persona_id="p")[0].intent_score == 5


@pytest.mark.parametrize("bad", [
    "no json here",
    answer(preferred="A9"),
    answer(reactions=[{"ad": "A1", "stopped": True, "understood": True, "believed": True,
                       "intent_score": 3}]),
    answer(reactions="nope"),
])
def test_parse_rejects_bad_answers(bad):
    with pytest.raises(ViewerParseError):
        parse_reactions(bad, LABELS, feed_id="F", persona_id="p")


def test_parse_rejects_bad_boolean_and_score():
    data = json.loads(answer())
    data["reactions"][0]["stopped"] = "perhaps"
    with pytest.raises(ViewerParseError):
        parse_reactions(json.dumps(data), LABELS, feed_id="F", persona_id="p")
    data = json.loads(answer())
    data["reactions"][0]["intent_score"] = "high"
    with pytest.raises(ViewerParseError):
        parse_reactions(json.dumps(data), LABELS, feed_id="F", persona_id="p")


# --- viewer + simulation --------------------------------------------------------

def test_viewer_retries_once_then_succeeds():
    client = ScriptedClient(broken_first=1)
    reactions, usd = Viewer(client).react(PERSONAS[0], [item(1, "GOOD"), item(2, "meh")], feed_id="F0")
    assert client.calls == 2 and usd == pytest.approx(0.003)
    assert {r.ad_id for r in reactions if r.preferred} == {"1"}


def test_viewer_passes_reasoning_effort():
    class Recording(ScriptedClient):
        def viewer_chat(self, messages, **kwargs):
            self.kwargs = kwargs
            return super().viewer_chat(messages, **kwargs)
    client = Recording()
    Viewer(client, reasoning_effort="minimal").react(PERSONAS[0], [item(1, "a"), item(2, "b")], feed_id="F")
    assert client.kwargs["reasoning_effort"] == "minimal"
    client = Recording()
    Viewer(client).react(PERSONAS[0], [item(1, "a"), item(2, "b")], feed_id="F")
    assert "reasoning_effort" not in client.kwargs


def test_viewer_gives_up_and_reports_cost():
    with pytest.raises(ViewerParseError) as exc:
        Viewer(ScriptedClient(broken_first=5), retries=1).react(PERSONAS[0], [item(1, "a"), item(2, "b")],
                                                                feed_id="F0")
    assert exc.value.usd == pytest.approx(0.002)


def test_simulation_recovers_the_signal():
    items = [item(i, "GOOD offer" if i < 3 else "plain ad") for i in range(12)]
    feeds = build_market_feeds(items, feed_size=4, appearances=2, seed=0)
    result = run_simulation(Viewer(ScriptedClient()), PERSONAS, feeds, viewers_per_feed=2, max_workers=4)
    assert not result.failures
    assert len(result.reactions) == len(feeds) * 2 * 4
    scores = score_ads(result.reactions)
    good = [scores[str(i)] for i in range(3)]
    plain = [scores[str(i)] for i in range(3, 12)]
    assert min(s.mean_intent for s in good) > max(s.mean_intent for s in plain)
    # two good ads can share a feed (one then loses on order), so compare groups, not extremes
    mean_good = sum(s.preference_lift for s in good) / len(good)
    mean_plain = sum(s.preference_lift for s in plain) / len(plain)
    assert mean_good >= 2.0 and mean_plain < 1.0  # holds for every seed (checked on 300)
    assert result.usd == pytest.approx(0.002 * len(feeds) * 2)


def test_simulation_counts_failures_without_crashing():
    feeds = build_market_feeds([item(i, "x") for i in range(4)], feed_size=2, appearances=1)
    result = run_simulation(Viewer(ScriptedClient(broken_first=100), retries=0), PERSONAS, feeds,
                            viewers_per_feed=1, max_workers=2)
    assert result.reactions == [] and len(result.failures) == 2
    assert result.usd == pytest.approx(0.002)


# --- scores ---------------------------------------------------------------------

def test_preference_lift_is_relative_to_chance():
    from whynot.sim.viewer import Reaction

    def r(ad, feed, persona, pref):
        return Reaction(feed, persona, ad, 0, True, True, True, "", "", 3, pref)
    # 2 viewers, feeds of 2 ads: "a" picked both times → lift 2.0; "b" never → 0
    rs = [r("a", "F0", "p0", True), r("b", "F0", "p0", False), r("a", "F0", "p1", True), r("b", "F0", "p1", False)]
    scores = score_ads(rs)
    assert scores["a"].preference_lift == pytest.approx(2.0)
    assert scores["b"].preference_lift == 0.0
    assert scores["a"].views == 2
