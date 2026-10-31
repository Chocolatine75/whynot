"""Competitor ad creatives (the image a viewer sees), captured from Ad Library snapshot pages (E2-3).

Why: until R3 v0 the simulator judged ads on text only. A feed is mostly pictures, so viewers must see
the creative. The Ad Library API gives no image URL, only `ad_snapshot_url`, a page that loads the ad
with JavaScript. We render it in a headless browser, read the address of the main creative (an image
on Meta's CDN), download that image and keep a small copy.

What is kept per ad: `<ad id>.jpg` (longest side `max_side` px) and one line in `index.json` (kind,
size, sha256, CDN host). No URL is stored: the snapshot URL needs the access token, and CDN URLs are
signed and expire. Video ads are represented by their poster frame (`kind="video"`), a stated limit.

Security: the token is added to the snapshot URL in memory only, for the browser; every error message
is redacted. The browser never clicks anything (cookie banners stay unanswered); we only read the page.
"""

import hashlib
import io
import json
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import urlencode, urlsplit

import httpx
from PIL import Image

from whynot.ingest.adlibrary import CompetitorAd, redact

CDN_SUFFIXES = (".fbcdn.net", ".cdninstagram.com")  # where creatives live; the rest is Facebook's own UI
MIN_SIDE = 300  # smaller images are icons or avatars (Instagram profile pictures are 206 px)


@dataclass(frozen=True)
class Media:
    url: str
    width: int
    height: int
    poster: bool = False  # a video's poster frame (video ads have no <img> for the creative)


@dataclass(frozen=True)
class Snapshot:
    """What a snapshot page shows: its images in page order, then its video posters."""

    images: list[Media]
    has_video: bool = False


class Renderer(Protocol):
    def render(self, url: str) -> Snapshot: ...


@dataclass
class Captured:
    kind: str  # image | video (poster frame)
    width: int
    height: int
    sha256: str
    host: str


@dataclass
class CaptureReport:
    captured: dict[str, Captured] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)  # already on disk
    failed: dict[str, str] = field(default_factory=dict)  # ad id -> reason (redacted)

    def rate(self) -> float:
        done = len(self.captured) + len(self.skipped)
        total = done + len(self.failed)
        return done / total if total else 0.0


def is_creative(m: Media) -> bool:
    host = urlsplit(m.url).hostname or ""
    return host.endswith(CDN_SUFFIXES) and min(m.width, m.height) >= MIN_SIDE


def pick(snapshot: Snapshot) -> Media | None:
    """The main creative: the first ad-sized image from Meta's CDN, in page order (first card of a carousel);
    for a video ad without one, the video's poster frame."""
    return next((m for m in snapshot.images if is_creative(m) and not m.poster), None) or next(
        (m for m in snapshot.images if m.poster and is_creative(m)), None)


def with_token(snapshot_url: str, token: str) -> str:
    return snapshot_url + ("&" if "?" in snapshot_url else "?") + urlencode({"access_token": token})


def shrink(data: bytes, max_side: int) -> tuple[bytes, int, int]:
    """JPEG with the longest side at most `max_side` (viewers don't need more; images cost tokens)."""
    with Image.open(io.BytesIO(data)) as src:
        im = src.convert("RGB")
    im.thumbnail((max_side, max_side))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=85)
    return out.getvalue(), im.width, im.height


class CreativeStore:
    """`folder/<ad id>.jpg` + `folder/index.json`."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.index_path = self.folder / "index.json"
        self.index: dict[str, dict] = json.loads(self.index_path.read_text()) if self.index_path.exists() else {}

    def path(self, ad_id: str) -> Path:
        return self.folder / f"{ad_id}.jpg"

    def has(self, ad_id: str) -> bool:
        return ad_id in self.index and self.path(ad_id).exists()

    def put(self, ad_id: str, jpeg: bytes, info: Captured) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path(ad_id).write_bytes(jpeg)
        self.index[ad_id] = asdict(info)
        self.index_path.write_text(json.dumps(self.index, indent=1, sort_keys=True) + "\n")

    def info(self, ad_id: str) -> Captured | None:
        d = self.index.get(ad_id)
        return Captured(**d) if d and self.path(ad_id).exists() else None


def capture(ads: Iterable[CompetitorAd], store: CreativeStore, *, token: str, renderer: Renderer,
            http: httpx.Client | None = None, max_side: int = 512,
            progress: Callable[[int, str], None] | None = None) -> CaptureReport:
    """Capture the main creative of each ad; ads already in the store are skipped (resumable)."""
    http = http or httpx.Client(timeout=30, follow_redirects=True)
    report = CaptureReport()
    for n, ad in enumerate(ads, 1):
        if store.has(ad.id):
            report.skipped.append(ad.id)
            continue
        try:
            if not ad.snapshot_url:
                raise ValueError("no snapshot url")
            snap = renderer.render(with_token(ad.snapshot_url, token))
            media = pick(snap)
            if media is None:
                raise ValueError(f"no creative image on the page ({len(snap.images)} images)")
            response = http.get(media.url)
            response.raise_for_status()
            jpeg, w, h = shrink(response.content, max_side)
            kind = "video" if media.poster or snap.has_video else "image"
            info = Captured(kind, w, h, hashlib.sha256(jpeg).hexdigest(), urlsplit(media.url).hostname or "")
            store.put(ad.id, jpeg, info)
            report.captured[ad.id] = info
        except Exception as exc:  # one bad page must not stop a capture of hundreds
            report.failed[ad.id] = redact(f"{type(exc).__name__}: {exc}", token)[:300]
        if progress:
            progress(n, ad.id)
    return report


class PlaywrightRenderer:  # pragma: no cover - needs a browser; exercised by scripts/r3_v1.py on real pages
    """Headless Chromium (`uv run --group capture`, then `playwright install chromium` once)."""

    def __init__(self, *, timeout_ms: int = 45_000, settle_s: float = 1.0):
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found,unused-ignore]

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._page = self._browser.new_page(viewport={"width": 600, "height": 1000})
        self.timeout_ms = timeout_ms
        self.settle_s = settle_s

    def render(self, url: str) -> Snapshot:
        self._page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
        time.sleep(self.settle_s)
        raw = self._page.eval_on_selector_all(
            "img", "els => els.map(e => [e.currentSrc || e.src || '', e.naturalWidth, e.naturalHeight])")
        posters = self._page.eval_on_selector_all(
            "video", "els => els.map(e => [e.getAttribute('poster') || '', e.videoWidth, e.videoHeight])")
        images = [Media(u, int(w), int(h)) for u, w, h in raw if u]
        # a poster's size is the video's; before the video loads it reads 0, yet a poster is the ad itself
        images += [Media(u, int(w) or MIN_SIDE, int(h) or MIN_SIDE, poster=True) for u, w, h in posters if u]
        return Snapshot(images, bool(posters))

    def close(self) -> None:
        self._browser.close()
        self._pw.stop()
