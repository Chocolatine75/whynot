"""Contract checks against the real services (free endpoints, no model calls). Run: pytest --live -k live

They catch the day Apple or Meta change a response format our parsers rely on.
"""

from datetime import date, timedelta

import pytest

from whynot.config import load_settings
from whynot.ingest.adlibrary import AdLibraryClient
from whynot.ingest.appstore import AppStoreClient, full_size

pytestmark = pytest.mark.live
DUOLINGO = "570060128"  # large public app, stable page


def test_live_app_store_profile_reviews_and_screenshot(tmp_path):
    c = AppStoreClient()
    app = c.profile(f"https://apps.apple.com/us/app/duolingo/id{DUOLINGO}", review_pages=1)
    assert app.app_id == DUOLINGO and app.rating_count > 1000 and app.screenshot_urls
    assert len(app.reviews) >= 10 and all(1 <= r.rating <= 5 for r in app.reviews)
    response = c._get(full_size(app.screenshot_urls[0]))
    assert response.headers["content-type"].startswith("image/") and len(response.content) > 50_000
    hits = c.search("learn vietnamese", limit=10)
    assert any(h.app_id == DUOLINGO for h in hits)


def test_live_ad_library_search_and_long_running_filter():
    s = load_settings()
    if not s.fb_token:
        pytest.skip("FB_TOKEN not set")
    lib = AdLibraryClient(s.fb_token, version=s.fb_api_version)
    ads = list(lib.search(countries=["GB"], terms="language app", active_status="ACTIVE", max_ads=30))
    assert ads and all(a.page_id and a.start_date for a in ads)
    assert all("access_token" not in (a.snapshot_url or "") for a in ads)
    old = list(lib.search(countries=["GB"], page_ids=[ads[0].page_id], active_status="ACTIVE",
                          delivery_date_max=date.today() - timedelta(days=30), max_ads=10))
    assert all(a.start_date <= date.today() - timedelta(days=30) for a in old if a.start_date)
