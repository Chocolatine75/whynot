"""Scout on fake Ad Library + scripted model: noise is filtered, ids are checked, countries enforced."""

import json
from datetime import date

import httpx
import pytest

from fakes import ScriptedChat
from whynot.agents.ask import AgentError, Invalid
from whynot.agents.scout import (
    Advertiser,
    check_countries,
    dedupe_by_copy,
    group_advertisers,
    make_filter_validator,
    scan,
    validate_plan,
)
from whynot.ingest.adlibrary import AdLibraryClient, CompetitorAd
from whynot.ingest.appstore import AppProfile

APP = AppProfile("1", "LinguaApp: Learn Vietnamese", "Lingua Ltd", "com.x", "https://apps.apple.com/app/id1",
                 "Learn Vietnamese by listening.", ["Education"], 0.0, "USD", 4.5, 120, [], None)


def ad(i, page, body, start="2026-06-01", stop=None):
    return CompetitorAd(str(i), page, f"Page {page}", [body], [], date.fromisoformat(start),
                        date.fromisoformat(stop) if stop else None, [], None, [], None)


def raw(i, page, body, start="2026-06-01", stop=None):
    return {"id": str(i), "page_id": page, "page_name": f"Page {page}", "ad_creative_bodies": [body],
            "ad_delivery_start_time": start, "ad_delivery_stop_time": stop}


def fake_library(by_term, by_page):
    def handler(request: httpx.Request):
        q = dict(request.url.params)
        if "search_terms" in q:
            data = by_term.get(q["search_terms"], [])
        else:
            pages = json.loads(q["search_page_ids"])
            status = q["ad_active_status"]
            data = [r for p in pages for r in by_page.get(p, [])
                    if (r.get("ad_delivery_stop_time") is None) == (status == "ACTIVE")]
        return httpx.Response(200, json={"data": data, "paging": {}})
    return AdLibraryClient("TOKEN", http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_group_advertisers_counts_each_ad_once_across_terms():
    a1, a2 = ad(1, "p1", "Speak Vietnamese fast"), ad(2, "p1", "Learn by listening")
    groups = group_advertisers({"vietnamese": [a1, a2], "learn": [a1, ad(3, "p2", "Diet pills")]})
    assert [(g.page_id, g.ads, g.terms) for g in groups] == [("p1", 2, ["vietnamese", "learn"]), ("p2", 1, ["learn"])]
    assert groups[0].samples == ["Speak Vietnamese fast", "Learn by listening"]


def test_dedupe_by_copy_per_advertiser():
    ads = [ad(1, "p1", "Same  copy"), ad(2, "p1", "same copy"), ad(3, "p2", "same copy"), ad(4, "p1", "")]
    assert [a.id for a in dedupe_by_copy(ads)] == ["1", "3"]


@pytest.mark.parametrize("data", [
    {"category": "x", "terms": ["a", "b"]},
    {"category": "x", "terms": ["a", "a", "A"]},
    {"category": "", "terms": ["a", "b", "c"]},
    {"category": "x", "terms": ["a", "b", "x" * 41]},
    ["a", "b", "c"],
])
def test_search_plan_validation(data):
    with pytest.raises(Invalid):
        validate_plan(data)


def test_filter_rejects_invented_or_missing_ids():
    v = make_filter_validator({"p1", "p2"})
    with pytest.raises(Invalid, match="unknown page_id"):
        v({"advertisers": [{"page_id": "p9", "competitor": True}]})
    with pytest.raises(Invalid, match="missing"):
        v({"advertisers": [{"page_id": "p1", "competitor": True}]})
    with pytest.raises(Invalid, match="true or false"):
        v({"advertisers": [{"page_id": "p1", "competitor": "yes"}, {"page_id": "p2", "competitor": False}]})


def test_research_countries_must_be_eu_uk():
    assert check_countries(["fr", "GB"]) == ["FR", "GB"]
    with pytest.raises(ValueError, match="US"):
        check_countries(["US"])
    with pytest.raises(ValueError):
        check_countries([])


def scout_model(verdicts):
    def reply(messages, module):
        text = messages[-1]["content"]
        if "search terms" in text:
            return json.dumps({"category": "Vietnamese learning app", "terms": ["learn vietnamese", "language app",
                                                                               "Duolingo"]})
        return json.dumps({"advertisers": [{"page_id": p, "competitor": c, "why": "test"} for p, c in verdicts]})
    return reply


def test_scan_keeps_competitors_and_owner_pages_and_drops_noise():
    by_term = {"learn vietnamese": [raw(1, "lingo", "Speak Vietnamese in 5 min"), raw(2, "spam", "Win an iPhone")],
               "language app": [raw(3, "lingo", "The language app"), raw(4, "diet", "Lose weight")],
               "Duolingo": [raw(5, "rival", "Better than Duolingo")]}
    by_page = {"lingo": [raw(10, "lingo", "Active copy"), raw(11, "lingo", "Old copy", "2026-01-01", "2026-01-05")],
               "rival": [raw(12, "rival", "Rival copy")], "owner_named": [raw(13, "owner_named", "Named by owner")],
               "spam": [raw(14, "spam", "spam")]}
    chat = ScriptedChat(scout_model([("lingo", True), ("rival", True), ("spam", False), ("diet", False)]))
    result = scan(chat, fake_library(by_term, by_page), APP, ["FR", "GB"], known_pages=["owner_named"])
    assert result.competitor_pages == ["owner_named", "lingo", "rival"]
    assert {a.id for a in result.ads} == {"10", "11", "12", "13"}  # active + inactive, no spam
    s = result.summary()
    assert {r["page_id"] for r in s["rejected"]} == {"spam", "diet"} and s["advertisers_found"] == 4
    assert result.usd == pytest.approx(0.02) and {c["module"] for c in chat.calls} == {"scout"}


def test_scan_fails_loudly_when_the_model_keeps_inventing_pages():
    by_term = {"learn vietnamese": [raw(1, "lingo", "x")]}
    chat = ScriptedChat(scout_model([("ghost", True)]))
    with pytest.raises(AgentError, match="unknown page_id"):
        scan(chat, fake_library(by_term, {}), APP, ["FR"])
    assert len(chat.calls) == 1 + 3  # plan + 3 filter attempts, all billed


def test_scan_with_no_ads_found_still_uses_owner_pages():
    chat = ScriptedChat(scout_model([]))
    result = scan(chat, fake_library({}, {"mine": [raw(1, "mine", "x")]}), APP, ["FR"], known_pages=["mine"])
    assert result.competitor_pages == ["mine"] and len(chat.calls) == 1  # no filter call without candidates


def test_advertiser_dataclass_defaults():
    assert Advertiser("p", "n", 0).samples == []
