"""The business side of research for a mobile app: its App Store page.

Public Apple endpoints, no key needed:
- lookup  `https://itunes.apple.com/lookup?id=<id>&country=<cc>`: name, seller,
  description, rating, price, genres, screenshot URLs;
- reviews `https://itunes.apple.com/<cc>/rss/customerreviews/page=<n>/id=<id>/sortby=mostrecent/json`
  (≤ 10 pages of 50): what customers love and *why they hesitate*;
- search  `https://itunes.apple.com/search?term=...&entity=software`: competitor apps.

Screenshots are the app's real pixels (never generated): downloaded at full
resolution and used as the product asset in ads.

Data use: the owner's own App Store page and screenshots, for the owner's own
campaign. Competitor apps: name and metadata only. Reviewer names are dropped.
"""

import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

ITUNES = "https://itunes.apple.com"
_ID_IN_URL = re.compile(r"/id(\d{6,12})(?:[/?#]|$)")
_STORE_LINK = re.compile(r"https?://(?:apps|itunes)\.apple\.com/[^\s\"'<>]*?/id(\d{6,12})")
_THUMB_SIZE = re.compile(r"/\d+x\d+bb(?:-\d+)?\.(?:jpg|png|webp)$")


class AppStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class Review:
    id: str
    rating: int  # 1–5
    title: str
    text: str
    version: str
    date: str  # ISO

    @property
    def negative(self) -> bool:
        return self.rating <= 3


@dataclass
class AppProfile:
    app_id: str
    name: str
    seller: str
    bundle_id: str
    store_url: str
    description: str
    genres: list[str]
    price: float
    currency: str
    rating: float | None
    rating_count: int
    screenshot_urls: list[str]
    icon_url: str | None
    languages: list[str] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)

    @property
    def free(self) -> bool:
        return self.price == 0

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "AppProfile":
        data = dict(data)
        data["reviews"] = [Review(**r) for r in data.get("reviews", [])]
        return cls(**data)


@dataclass(frozen=True)
class AppHit:
    """A search result: a possible competitor app."""
    app_id: str
    name: str
    seller: str
    genre: str
    rating_count: int
    store_url: str


def parse_app_ref(ref: str) -> str | None:
    """App id from an App Store URL or a bare id; None for anything else (e.g. a website)."""
    ref = ref.strip()
    if ref.isdigit() and 6 <= len(ref) <= 12:
        return ref
    if "apple.com" in urlsplit(ref if "://" in ref else f"https://{ref}").netloc:
        m = _ID_IN_URL.search(urlsplit(ref).path + "/")
        if m:
            return m.group(1)
    return None


def find_store_link(html: str) -> str | None:
    """First App Store app id linked from a web page (an app's landing page)."""
    m = _STORE_LINK.search(html)
    return m.group(1) if m else None


def full_size(url: str, size: str = "1290x2796bb.png") -> str:
    """mzstatic serves any size: swap the thumbnail suffix for a full-size one."""
    return _THUMB_SIZE.sub("/" + size, url) if _THUMB_SIZE.search(url) else url


def parse_lookup(body: dict[str, Any]) -> AppProfile:
    results = body.get("results") or []
    if not results:
        raise AppStoreError("app not found on the App Store (check the id and the country)")
    r = results[0]
    if r.get("kind") not in (None, "software"):
        raise AppStoreError(f"not an app: kind={r.get('kind')!r}")
    shots = list(r.get("screenshotUrls") or []) or list(r.get("ipadScreenshotUrls") or [])
    return AppProfile(
        app_id=str(r["trackId"]), name=str(r.get("trackName", "")).strip(), seller=str(r.get("sellerName", "")),
        bundle_id=str(r.get("bundleId", "")), store_url=str(r.get("trackViewUrl", "")).split("?")[0],
        description=str(r.get("description", "")), genres=list(r.get("genres") or []),
        price=float(r.get("price") or 0.0), currency=str(r.get("currency", "USD")),
        rating=float(r["averageUserRating"]) if r.get("averageUserRating") is not None else None,
        rating_count=int(r.get("userRatingCount") or 0), screenshot_urls=shots,
        icon_url=r.get("artworkUrl512"), languages=list(r.get("languageCodesISO2A") or []),
    )


def parse_reviews(body: dict[str, Any]) -> list[Review]:
    entries = (body.get("feed") or {}).get("entry") or []
    if isinstance(entries, dict):  # a single review comes as an object
        entries = [entries]
    reviews = []
    for e in entries:
        if "im:rating" not in e:  # older feeds put the app itself first
            continue
        try:
            rating = int(e["im:rating"]["label"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 1 <= rating <= 5:
            continue
        reviews.append(Review(
            id=str(e.get("id", {}).get("label", "")), rating=rating,
            title=str(e.get("title", {}).get("label", "")).strip(),
            text=str(e.get("content", {}).get("label", "")).strip(),
            version=str(e.get("im:version", {}).get("label", "")),
            date=str(e.get("updated", {}).get("label", ""))[:10],
        ))
    return reviews


def parse_search(body: dict[str, Any]) -> list[AppHit]:
    return [AppHit(app_id=str(r["trackId"]), name=str(r.get("trackName", "")), seller=str(r.get("sellerName", "")),
                   genre=str(r.get("primaryGenreName", "")), rating_count=int(r.get("userRatingCount") or 0),
                   store_url=str(r.get("trackViewUrl", "")).split("?")[0])
            for r in body.get("results") or [] if "trackId" in r]


class AppStoreClient:
    def __init__(self, http: httpx.Client | None = None, *, retries: int = 2, backoff_s: float = 1.0,
                 sleep: Callable[[float], None] = time.sleep):
        self.http = http or httpx.Client(timeout=30, follow_redirects=True,
                                         headers={"User-Agent": "whynot/0.1 (+https://github.com/Chocolatine75/whynot)"})
        self.retries = retries
        self.backoff_s = backoff_s
        self._sleep = sleep

    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        for attempt in range(self.retries + 1):
            try:
                response = self.http.get(url, params=params)
            except httpx.HTTPError as exc:
                if attempt == self.retries:
                    raise AppStoreError(f"request failed: {exc}") from None
            else:
                if response.status_code < 500 and response.status_code != 429:
                    if response.status_code >= 400:
                        raise AppStoreError(f"HTTP {response.status_code} for {url}")
                    return response
                if attempt == self.retries:
                    raise AppStoreError(f"HTTP {response.status_code} for {url}")
            self._sleep(self.backoff_s * 2**attempt)
        raise AssertionError("unreachable")

    def _json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            body = self._get(url, params).json()
        except ValueError:
            raise AppStoreError(f"non-JSON response from {url}") from None
        if not isinstance(body, dict):
            raise AppStoreError(f"unexpected response from {url}")
        return body

    def resolve(self, ref: str) -> str:
        """App id from an App Store URL, an id, or the app's website (which links to the store)."""
        app_id = parse_app_ref(ref)
        if app_id:
            return app_id
        url = ref if "://" in ref else f"https://{ref}"
        app_id = find_store_link(self._get(url).text)
        if not app_id:
            raise AppStoreError(f"no App Store link found on {url}: pass the App Store URL instead")
        return app_id

    def lookup(self, app_id: str, *, country: str = "us") -> AppProfile:
        return parse_lookup(self._json(f"{ITUNES}/lookup", {"id": app_id, "country": country}))

    def reviews(self, app_id: str, *, country: str = "us", pages: int = 3) -> list[Review]:
        out: list[Review] = []
        seen: set[str] = set()
        for page in range(1, min(pages, 10) + 1):
            batch = parse_reviews(self._json(
                f"{ITUNES}/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"))
            fresh = [r for r in batch if r.id not in seen]
            if not fresh:
                break
            seen.update(r.id for r in fresh)
            out.extend(fresh)
        return out

    def search(self, term: str, *, country: str = "us", limit: int = 15) -> list[AppHit]:
        return parse_search(self._json(f"{ITUNES}/search",
                                       {"term": term, "entity": "software", "country": country, "limit": limit}))

    def profile(self, ref: str, *, country: str = "us", review_pages: int = 3) -> AppProfile:
        app = self.lookup(self.resolve(ref), country=country)
        app.reviews = self.reviews(app.app_id, country=country, pages=review_pages)
        return app

    def download_screenshots(self, app: AppProfile, folder: Path, *, limit: int = 6) -> list[Path]:
        """Full-resolution screenshots, saved as PNG files (the real app pixels)."""
        folder.mkdir(parents=True, exist_ok=True)
        paths = []
        for i, url in enumerate(app.screenshot_urls[:limit]):
            path = folder / f"screen_{i + 1}.png"
            if not path.exists():
                response = self._get(full_size(url))
                if not response.headers.get("content-type", "").startswith("image/"):
                    raise AppStoreError(f"screenshot {i + 1} is not an image")
                path.write_bytes(response.content)
            paths.append(path)
        return paths
