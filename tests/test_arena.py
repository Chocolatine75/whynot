"""Fair feeds with placebos: name bias is detected, content wins only on content."""

import json
import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fakes import ScriptedChat
from whynot.sim.arena import (
    BIAS_THRESHOLD,
    brand_name,
    is_placebo,
    judge,
    our_item,
    paired_feeds,
    placebo_item,
)
from whynot.sim.feed import FeedItem
from whynot.sim.personas import Persona
from whynot.sim.scores import AdScore, score_ads
from whynot.sim.viewer import Viewer, run_simulation


@pytest.mark.parametrize("name, brand", [
    ("VietBuddy: Learn Vietnamese", "VietBuddy"),
    ("Flighty – Live Flight Tracker", "Flighty"),
    ("Finch: Self-Care Pet", "Finch"),
    ("Duolingo - Language Lessons", "Duolingo"),
    ("Notion | Notes, Docs", "Notion"),
    ("Self-Care Daily", "Self-Care Daily"),  # a hyphen inside a word is not a separator
    ("Calm", "Calm"),
])
def test_brand_name_is_what_a_facebook_page_would_show(name, brand):
    assert brand_name(name) == brand


def comp(i, body="Some competitor copy. More text."):
    return FeedItem(f"c{i}", f"Rival {i}", f"Title {i}", body)


def test_placebo_looks_exactly_like_our_ads():
    ours = our_item("v1", "Brand", {"hook": "Hook", "body": "Body.", "title": "T", "proof": ""})
    fake = placebo_item(comp(1), "Brand")
    assert (ours.advertiser, fake.advertiser) == ("Brand", "Brand")
    assert "\n[image text: " in ours.body and "\n[image text: " in fake.body
    assert is_placebo(fake.ad_id) and not is_placebo(ours.ad_id)


@given(st.integers(2, 8), st.integers(1, 3), st.integers(3, 6), st.integers(0, 500))
def test_paired_feeds_are_fair(n_candidates, appearances, feed_size, seed):
    competitors = [comp(i) for i in range(12)]
    candidates = [our_item(f"v{i}", "B", {"hook": "h", "body": "b", "title": "t"}) for i in range(n_candidates - 1)]
    candidates.append(placebo_item(competitors[0], "B"))
    feeds = paired_feeds(candidates, competitors, feed_size=feed_size, appearances=appearances, seed=seed)
    cand_ids = {c.ad_id for c in candidates}
    shown = dict.fromkeys(cand_ids, 0)
    for f in feeds:
        ids = [x.ad_id for x in f]
        assert len(f) == feed_size and len(set(ids)) == feed_size
        assert sum(i in cand_ids for i in ids) == 2  # exactly two candidate slots
        assert "c0" not in ids  # the placebo's source ad never sits next to its disguise
        for i in ids:
            if i in shown:
                shown[i] += 1
    assert min(shown.values()) >= appearances and max(shown.values()) - min(shown.values()) <= 1


def test_paired_feeds_need_enough_material():
    with pytest.raises(ValueError, match="at least 2 candidates"):
        paired_feeds([comp(1)], [comp(2), comp(3)], feed_size=3, appearances=1)
    with pytest.raises(ValueError, match="feed_size"):
        paired_feeds([comp(1), comp(2)], [comp(3)], feed_size=2, appearances=1)
    with pytest.raises(ValueError, match="not enough competitor"):
        paired_feeds([comp(1), comp(2)], [comp(3)], feed_size=4, appearances=1)


def score(ad_id, lift, intent=3.0, views=4):
    return AdScore(ad_id, views, lift, intent, 0.5, 0.5, 0.5, [])


def test_judge_relative_to_placebo():
    r = judge({"v1": score("v1", 2.0, 4.0), "v2": score("v2", 0.5, 2.0), "rival": score("rival", 9.0),
               "placebo:a": score("placebo:a", 1.0, 2.5), "placebo:b": score("placebo:b", 0.6, 2.5)},
              {"v1", "v2", "placebo:a", "placebo:b"})
    assert set(r.verdicts) == {"v1", "v2"}  # competitor ads in the feeds are not verdicts
    assert r.placebo_lift == pytest.approx(0.8) and not r.biased and r.placebos == 2
    assert r.verdicts["v1"].lift_over_placebo == pytest.approx(1.2) and r.placebo_views == 8
    assert r.verdicts["v2"].intent_vs_placebo == pytest.approx(-0.5)
    assert judge({"v": score("v", 3.0), "placebo:x": score("placebo:x", 3.0)}, {"v", "placebo:x"}).biased
    with pytest.raises(ValueError, match="no placebo"):
        judge({"v": score("v", 1.0)}, {"v"})


# --- the two failure modes we must tell apart, with scripted viewers -----------------------

def scripted_viewer(prefer):
    def reply(messages, module):
        text = messages[1]["content"]
        blocks = [(m.group(1), m.group(2).strip(), body) for body in re.split(r"(?=\[A\d+\] Sponsored)", text)
                  for m in [re.match(r"\[(A\d+)\] Sponsored · (.*)", body)] if m]
        chosen = prefer(blocks) or blocks[-1][0]
        return json.dumps({"reactions": [{"ad": lab, "stopped": lab == chosen, "understood": True, "believed": True,
                                          "why_not": "", "intent": "", "intent_score": 4 if lab == chosen else 2}
                                         for lab, _, _ in blocks], "preferred": chosen})
    return ScriptedChat(reply, usd=0.0)


def arena(chat):
    competitors = [comp(i) for i in range(10)]
    ours = [our_item(f"good{i}", "Brand", {"hook": "GOOD hook", "body": "Body.", "title": "t"}) for i in range(2)]
    ours += [our_item(f"plain{i}", "Brand", {"hook": "plain hook", "body": "Body.", "title": "t"}) for i in range(2)]
    candidates = ours + [placebo_item(competitors[i], "Brand") for i in range(2)]
    feeds = paired_feeds(candidates, competitors, feed_size=4, appearances=4, seed=1)
    personas = [Persona(f"p{i}", "GB", "25-34", "female") for i in range(3)]
    sim = run_simulation(Viewer(chat), personas, feeds, viewers_per_feed=2)
    return judge(score_ads(sim.reactions), {c.ad_id for c in candidates})


def test_a_content_driven_viewer_ranks_good_ads_above_the_placebo():
    r = arena(scripted_viewer(lambda bs: next((lab for lab, _, b in bs if "GOOD" in b), None)))
    assert not r.biased
    assert min(r.verdicts[f"good{i}"].lift_over_placebo for i in range(2)) > 1.0
    assert max(r.verdicts[f"plain{i}"].lift for i in range(2)) < min(r.verdicts[f"good{i}"].lift for i in range(2))


def test_a_name_driven_viewer_is_flagged_as_biased():
    """What the real model did: anything under our name wins. The placebo must expose it."""
    r = arena(scripted_viewer(lambda bs: next((lab for lab, adv, _ in bs if adv == "Brand"), None)))
    assert r.biased and r.placebo_lift > BIAS_THRESHOLD
    mean = sum(v.lift_over_placebo for v in r.verdicts.values()) / len(r.verdicts)
    assert abs(mean) < 0.6  # on average our ads do no better than a competitor ad under our name
