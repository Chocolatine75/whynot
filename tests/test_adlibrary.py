"""Ad Library ingest on fake Graph API responses (no network)."""

import json
from datetime import date

import httpx
import pytest

from whynot.ingest.adlibrary import (
    AdLibraryClient, AdLibraryError, CompetitorAd, load_jsonl, parse_ad, parse_breakdown,
    save_jsonl, strip_token,
)

TOKEN = "EAAtestSECRET123"


def raw_ad(ad_id: str, start: str = "2026-06-01", stop: str | None = None) -> dict:
    return {
        "id": ad_id,
        "page_id": "111",
        "page_name": "Rival App",
        "ad_creative_bodies": ["Learn in 5 minutes a day"],
        "ad_creative_link_titles": ["Start free"],
        "ad_delivery_start_time": start,
        "ad_delivery_stop_time": stop,
        "ad_snapshot_url": f"https://www.facebook.com/ads/archive/render_ad/?id={ad_id}&access_token={TOKEN}",
        "publisher_platforms": ["facebook", "instagram"],
        "eu_total_reach": "195000",
        "target_ages": ["18", "65+"],
        "target_gender": "All",
        "age_country_gender_reach_breakdown": [
            {"country": "FR", "age_gender_breakdowns": [
                {"age_range": "25-34", "male": 300, "female": 500, "unknown": 0},
                {"age_range": "35-44", "male": 100, "female": 100},
            ]},
        ],
    }


def make_client(pages: list[dict], seen: list[httpx.Request]) -> AdLibraryClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        index = len(seen) - 1
        return httpx.Response(200, json=pages[index])
    return AdLibraryClient(TOKEN, http=httpx.Client(transport=httpx.MockTransport(handler)))


# --- token handling -----------------------------------------------------------

def test_strip_token_keeps_other_params():
    url = f"https://x.test/render?id=9&access_token={TOKEN}&lang=fr"
    clean = strip_token(url)
    assert TOKEN not in clean and "access_token" not in clean
    assert "id=9" in clean and "lang=fr" in clean


def test_strip_token_none():
    assert strip_token(None) is None


def test_parsed_ad_has_no_token():
    ad = parse_ad(raw_ad("1"))
    assert TOKEN not in json.dumps(ad.to_json())


def test_save_refuses_token(tmp_path):
    ad = parse_ad(raw_ad("1"))
    ad.bodies = [f"leak access_token={TOKEN}"]
    with pytest.raises(AdLibraryError):
        save_jsonl([ad], tmp_path / "ads.jsonl")


# --- parsing ------------------------------------------------------------------

def test_parse_fields():
    ad = parse_ad(raw_ad("42", start="2026-06-01T07:00:00+0000"))
    assert ad.id == "42" and ad.page_name == "Rival App"
    assert ad.start_date == date(2026, 6, 1) and ad.stop_date is None
    assert ad.eu_total_reach == 195000
    assert ad.platforms == ["facebook", "instagram"]


def test_breakdown_slices_and_shares():
    ad = parse_ad(raw_ad("1"))
    assert len(ad.reach_breakdown) == 4  # zero-reach slices dropped
    assert ad.reach_share("gender") == pytest.approx({"male": 400 / 1000, "female": 600 / 1000})
    assert ad.reach_share("age_range")["25-34"] == pytest.approx(0.8)


def test_breakdown_tolerates_missing_parts():
    assert parse_breakdown(None) == []
    assert parse_breakdown([{"country": "DE"}]) == []


def test_longevity():
    running = parse_ad(raw_ad("1", start="2026-06-01"))
    stopped = parse_ad(raw_ad("2", start="2026-06-01", stop="2026-06-11"))
    assert running.longevity_days(date(2026, 10, 27)) == 148
    assert stopped.longevity_days(date(2026, 10, 27)) == 10
    no_start = parse_ad({"id": "3"})
    assert no_start.longevity_days(date(2026, 10, 27)) is None


# --- client -------------------------------------------------------------------

def test_search_paginates_with_cursors():
    pages = [
        {"data": [raw_ad("1"), raw_ad("2")],
         "paging": {"cursors": {"after": "CUR1"}, "next": f"https://graph.test/next?access_token={TOKEN}"}},
        {"data": [raw_ad("3")], "paging": {"cursors": {"after": "CUR2"}}},
    ]
    seen: list[httpx.Request] = []
    ads = list(make_client(pages, seen).search(countries=["FR"], page_ids=["111"]))
    assert [a.id for a in ads] == ["1", "2", "3"]
    assert len(seen) == 2
    assert seen[1].url.params["after"] == "CUR1"
    first = seen[0].url.params
    assert json.loads(first["ad_reached_countries"]) == ["FR"]
    assert json.loads(first["search_page_ids"]) == ["111"]
    assert "age_country_gender_reach_breakdown" in first["fields"]


def test_search_respects_max_ads():
    pages = [{"data": [raw_ad("1"), raw_ad("2"), raw_ad("3")],
              "paging": {"cursors": {"after": "C"}, "next": "https://graph.test/next"}}]
    seen: list[httpx.Request] = []
    ads = list(make_client(pages, seen).search(countries=["FR"], terms="language app", max_ads=2))
    assert len(ads) == 2 and len(seen) == 1


def test_search_needs_a_query():
    with pytest.raises(ValueError):
        list(make_client([], []).search(countries=["FR"]))


def test_error_code_1_is_explained_and_redacted():
    pages = [{"error": {"code": 1, "message": f"An unknown error occurred {TOKEN}"}}]
    with pytest.raises(AdLibraryError) as exc:
        list(make_client(pages, []).search(countries=["FR"], page_ids=["111"]))
    assert "token" in str(exc.value) and TOKEN not in str(exc.value)


def test_missing_token():
    with pytest.raises(AdLibraryError):
        AdLibraryClient("")


def test_save_and_load_roundtrip(tmp_path):
    ads = [parse_ad(raw_ad("1")), parse_ad(raw_ad("2", stop="2026-07-01"))]
    path = save_jsonl(ads, tmp_path / "ads.jsonl")
    loaded = load_jsonl(path)
    assert [a.id for a in loaded] == ["1", "2"]
    assert isinstance(loaded[0], CompetitorAd)
    assert loaded[1].stop_date == date(2026, 7, 1)
    assert loaded[0].reach_breakdown == ads[0].reach_breakdown
    assert TOKEN not in path.read_text()
