"""Creative capture from Ad Library snapshot pages, on a fake browser and a fake CDN."""

import io
import json

import httpx
from PIL import Image

from test_longevity import ad
from whynot.ingest.creatives import (
    Captured,
    CreativeStore,
    Media,
    Snapshot,
    capture,
    pick,
    shrink,
    with_token,
)

TOKEN = "EAAsecretTOKEN1234567890abcdef"
CDN = "https://scontent-cdg4-1.xx.fbcdn.net/v/t39/{}.jpg?oh=sig&oe=123"


def png(w=1080, h=1920, color=(200, 30, 30)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (w, h), color).save(out, "PNG")
    return out.getvalue()


class FakeBrowser:
    def __init__(self, pages):
        self.pages = pages  # ad id -> Snapshot or Exception
        self.urls = []

    def render(self, url):
        self.urls.append(url)
        ad_id = url.split("id=")[1].split("&")[0]
        page = self.pages[ad_id]
        if isinstance(page, Exception):
            raise page
        return page


def cdn(requests_seen):
    def handler(request):
        requests_seen.append(str(request.url))
        if "missing" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(200, content=png())
    return httpx.Client(transport=httpx.MockTransport(handler))


def snap_ad(i):
    a = ad(i)
    a.snapshot_url = f"https://www.facebook.com/ads/archive/render_ad/?id={i}"
    return a


def test_pick_skips_facebook_ui_and_small_images():
    ui = Media("https://www.facebook.com/images/cookies/card.png", 312, 200)
    avatar = Media(CDN.format("avatar"), 60, 60)
    main = Media(CDN.format("main"), 1080, 1920)
    second = Media(CDN.format("card2"), 1080, 1080)
    assert pick(Snapshot([ui, avatar, main, second])) == main  # first ad-sized CDN image, in page order
    assert pick(Snapshot([ui, avatar])) is None
    assert pick(Snapshot([Media("https://evil.example/fbcdn.net/x.jpg", 1080, 1080)])) is None  # host, not path


def test_shrink_caps_the_longest_side_and_keeps_the_ratio():
    jpeg, w, h = shrink(png(1080, 1920), 512)
    assert (w, h) == (288, 512)
    assert Image.open(io.BytesIO(jpeg)).format == "JPEG"


def test_capture_stores_small_images_and_an_index_without_urls_or_token(tmp_path):
    browser = FakeBrowser({"1": Snapshot([Media(CDN.format("a"), 1080, 1920)]),
                           "2": Snapshot([Media(CDN.format("b"), 1080, 1080)], has_video=True)})
    store = CreativeStore(tmp_path / "creatives")
    seen = []
    report = capture([snap_ad(1), snap_ad(2)], store, token=TOKEN, renderer=browser, http=cdn(seen))
    assert set(report.captured) == {"1", "2"} and report.rate() == 1.0
    assert report.captured["2"].kind == "video" and report.captured["1"].kind == "image"
    assert all(TOKEN in u for u in browser.urls)  # the browser needs the token...
    assert not any(TOKEN in u for u in seen)  # ...the CDN never gets it
    for f in (tmp_path / "creatives").iterdir():  # ...and it is stored nowhere, nor any URL
        blob = f.read_bytes()
        assert TOKEN.encode() not in blob and b"oh=sig" not in blob and b"render_ad" not in blob
    index = json.loads((tmp_path / "creatives" / "index.json").read_text())
    assert index["1"]["host"].endswith("fbcdn.net") and max(index["1"]["width"], index["1"]["height"]) == 512


def test_capture_is_resumable_and_one_failure_does_not_stop_it(tmp_path):
    store = CreativeStore(tmp_path)
    store.put("1", shrink(png(), 64)[0], Captured("image", 36, 64, "x", "h"))
    browser = FakeBrowser({
        "2": RuntimeError(f"timeout loading {with_token('https://www.facebook.com/x?id=2', TOKEN)}"),
        "3": Snapshot([Media("https://www.facebook.com/ui.png", 600, 600)]),
        "4": Snapshot([Media(CDN.format("missing"), 1080, 1080)]),
        "5": Snapshot([Media(CDN.format("ok"), 1080, 1080)]),
    })
    a6 = ad(6)  # no snapshot url at all
    report = capture([snap_ad(i) for i in (1, 2, 3, 4, 5)] + [a6], store, token=TOKEN, renderer=browser,
                     http=cdn([]))
    assert report.skipped == ["1"] and list(report.captured) == ["5"]
    assert set(report.failed) == {"2", "3", "4", "6"}
    assert "1" not in [u.split("id=")[1].split("&")[0] for u in browser.urls]  # not rendered again
    assert all(TOKEN not in why for why in report.failed.values())  # errors are redacted
    assert "no creative image" in report.failed["3"] and "404" in report.failed["4"]
    assert report.rate() == 2 / 6
    assert CreativeStore(tmp_path).has("5")  # the index survives a reload


def test_video_ads_use_the_poster_frame_and_avatars_are_never_picked():
    """Regression: 180 of 298 R3 v1 pages were video ads (no <img> for the creative), so capture failed;
    and an Instagram profile picture (206 px, cdninstagram.com) could pass for a creative."""
    avatar = Media("https://scontent-cdg6-1.cdninstagram.com/v/t51/avatar.jpg", 206, 206)
    small = Media(CDN.format("logo"), 60, 60)
    poster = Media(CDN.format("poster"), 360, 640, poster=True)
    assert pick(Snapshot([small, avatar, poster], has_video=True)) == poster
    image = Media("https://scontent-cdg6-1.cdninstagram.com/v/t51/creative.jpg", 1080, 1350)
    assert pick(Snapshot([avatar, image, poster], has_video=True)) == image  # an ad-sized image comes first


def test_a_captured_poster_is_recorded_as_a_video(tmp_path):
    browser = FakeBrowser({"7": Snapshot([Media(CDN.format("p"), 360, 640, poster=True)], has_video=True)})
    report = capture([snap_ad(7)], CreativeStore(tmp_path), token=TOKEN, renderer=browser, http=cdn([]))
    assert report.captured["7"].kind == "video"
