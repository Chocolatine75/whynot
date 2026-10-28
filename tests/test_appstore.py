"""App Store ingest, checked against real recorded Apple responses (tests/fixtures/appstore)."""

import json
from pathlib import Path

import httpx
import pytest

from whynot.ingest.appstore import (
    AppProfile,
    AppStoreClient,
    AppStoreError,
    find_store_link,
    full_size,
    parse_app_ref,
    parse_lookup,
    parse_reviews,
    parse_search,
)

FIX = Path(__file__).parent / "fixtures" / "appstore"


def load(name):
    return json.loads((FIX / name).read_text())


# --- contract: real responses parse into what the agency needs ------------------

def test_real_lookup_response():
    app = parse_lookup(load("lookup_570060128.json"))
    assert app.app_id == "570060128" and app.name.startswith("Duolingo")
    assert app.free and app.rating and app.rating_count > 1000
    assert "Education" in app.genres and len(app.description) > 200
    assert app.store_url.startswith("https://apps.apple.com/") and "?" not in app.store_url
    assert app.screenshot_urls and all(u.startswith("https://") for u in app.screenshot_urls)


def test_real_reviews_response():
    reviews = parse_reviews(load("reviews_570060128_p1.json"))
    assert len(reviews) == 8
    assert all(1 <= r.rating <= 5 and r.id.isdigit() and r.text for r in reviews)
    assert len({r.id for r in reviews}) == len(reviews)
    assert all(len(r.date) == 10 for r in reviews)


def test_real_search_response():
    hits = parse_search(load("search_learn_vietnamese.json"))
    assert len(hits) >= 4 and any("Duolingo" in h.name for h in hits)
    assert all(h.app_id.isdigit() for h in hits)


def test_profile_roundtrips_through_json():
    app = parse_lookup(load("lookup_570060128.json"))
    app.reviews = parse_reviews(load("reviews_570060128_p1.json"))
    assert AppProfile.from_json(json.loads(json.dumps(app.to_json()))) == app


# --- references -------------------------------------------------------------------

@pytest.mark.parametrize("ref, expected", [
    ("https://apps.apple.com/us/app/vietbuddy-learn-vietnamese/id6796837982", "6796837982"),
    ("https://apps.apple.com/fr/app/duolingo/id570060128?uo=4", "570060128"),
    ("apps.apple.com/app/id570060128", "570060128"),
    ("570060128", "570060128"),
    ("https://www.example.app/", None),
    ("https://apps.apple.com/us/developer/x/id12", None),
    ("12", None),
])
def test_parse_app_ref(ref, expected):
    assert parse_app_ref(ref) == expected


def test_find_store_link_in_landing_page():
    html = '<a class="btn" href="https://apps.apple.com/us/app/some-app/id1234567890?pt=1">Download</a>'
    assert find_store_link(html) == "1234567890"
    assert find_store_link("<html>no store</html>") is None


def test_full_size_screenshot_url():
    thumb = "https://is1-ssl.mzstatic.com/image/thumb/P/v4/a/b/01-x.png/392x696bb.jpg"
    assert full_size(thumb).endswith("/01-x.png/1290x2796bb.png")
    assert full_size("https://example.com/x.png") == "https://example.com/x.png"


# --- edge cases -------------------------------------------------------------------

def test_lookup_not_found_and_not_an_app():
    with pytest.raises(AppStoreError, match="not found"):
        parse_lookup({"resultCount": 0, "results": []})
    with pytest.raises(AppStoreError, match="not an app"):
        parse_lookup({"results": [{"trackId": 1, "kind": "song"}]})


def test_reviews_feed_variants():
    one = {"feed": {"entry": {"im:rating": {"label": "4"}, "id": {"label": "9"}, "title": {"label": "t"},
                              "content": {"label": "c"}, "updated": {"label": "2026-10-01T00:00:00"}}}}
    assert [r.id for r in parse_reviews(one)] == ["9"]
    app_first = {"feed": {"entry": [{"im:name": {"label": "App"}}, one["feed"]["entry"],
                                    {"im:rating": {"label": "9"}, "id": {"label": "x"}}]}}
    assert [r.id for r in parse_reviews(app_first)] == ["9"]  # app entry and out-of-range rating skipped
    assert parse_reviews({"feed": {}}) == [] and parse_reviews({}) == []


# --- client (HTTP mocked) ---------------------------------------------------------

def client(routes, sleeps=None):
    def handler(request: httpx.Request):
        for key, response in routes.items():
            if key in str(request.url):
                return response() if callable(response) else response
        return httpx.Response(404)
    sink = sleeps if sleeps is not None else []
    return AppStoreClient(httpx.Client(transport=httpx.MockTransport(handler)), sleep=sink.append)


def test_profile_from_a_website_link_with_reviews_paging():
    pages = {1: load("reviews_570060128_p1.json"), 2: load("reviews_570060128_p1.json")}  # page 2 repeats
    c = client({
        "example.app": httpx.Response(200, text='<a href="https://apps.apple.com/us/app/x/id570060128">get</a>'),
        "lookup": httpx.Response(200, json=load("lookup_570060128.json")),
        "page=1/": httpx.Response(200, json=pages[1]),
        "page=2/": httpx.Response(200, json=pages[2]),
    })
    app = c.profile("https://example.app", review_pages=5)
    assert app.app_id == "570060128" and len(app.reviews) == 8  # stops when a page brings nothing new


def test_retries_on_5xx_and_429_then_fails_clearly():
    sleeps = []
    calls = iter([httpx.Response(503), httpx.Response(429), httpx.Response(200, json=load("lookup_570060128.json"))])
    c = client({"lookup": lambda: next(calls)}, sleeps)
    assert c.lookup("570060128").name.startswith("Duolingo") and sleeps == [1.0, 2.0]
    with pytest.raises(AppStoreError, match="HTTP 500"):
        client({"lookup": httpx.Response(500)}).lookup("1")
    with pytest.raises(AppStoreError, match="HTTP 404"):
        client({}).lookup("1")


def test_website_without_store_link():
    with pytest.raises(AppStoreError, match="no App Store link"):
        client({"example.app": httpx.Response(200, text="<html></html>")}).resolve("example.app")


def test_screenshots_are_downloaded_full_size_and_must_be_images(tmp_path):
    app = parse_lookup(load("lookup_570060128.json"))
    seen = []

    def png():
        return httpx.Response(200, content=b"\x89PNG...", headers={"content-type": "image/png"})

    c = client({"mzstatic": lambda: (seen.append(1), png())[1]})
    paths = c.download_screenshots(app, tmp_path, limit=2)
    assert [p.name for p in paths] == ["screen_1.png", "screen_2.png"] and paths[0].read_bytes().startswith(b"\x89PNG")
    c.download_screenshots(app, tmp_path, limit=2)
    assert len(seen) == 2  # cached on disk
    bad = client({"mzstatic": httpx.Response(200, text="<html>", headers={"content-type": "text/html"})})
    with pytest.raises(AppStoreError, match="not an image"):
        bad.download_screenshots(app, tmp_path / "other", limit=1)
