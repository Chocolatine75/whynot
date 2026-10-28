"""Competitor ads from the Meta Ad Library API.

What we keep per ad: copy, titles, start/stop dates (longevity), platforms, EU
reach and the reach split by country / age / gender (who Meta really showed the ad
to). Commercial ads are only returned for ads delivered in the EU/UK.

Security: the API puts the access token inside every `ad_snapshot_url` and every
paging URL. We strip it before anything is stored, logged or displayed, and we
paginate with cursors instead of following `paging.next`.

The reach breakdown format below is parsed defensively; confirm it on the first
real call and update docs/META_APIS.md.
"""

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

GRAPH_URL = "https://graph.facebook.com"
DEFAULT_VERSION = "v26.0"
DEFAULT_FIELDS = (
    "id", "page_id", "page_name", "ad_creative_bodies", "ad_creative_link_titles",
    "ad_delivery_start_time", "ad_delivery_stop_time", "ad_snapshot_url",
    "publisher_platforms", "eu_total_reach", "target_ages", "target_gender",
    "age_country_gender_reach_breakdown",
)
_SECRET_PARAMS = {"access_token"}


# Graph API codes worth retrying: temporary service issue, app/user/page rate limits.
# Code 1 is not retried: with this API it is almost always a bad or expired token.
TRANSIENT_CODES = {2, 4, 17, 341, 613}


class AdLibraryError(RuntimeError):
    pass


def strip_token(url: str | None) -> str | None:
    """Remove access_token from a URL's query string."""
    if not url:
        return url
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in _SECRET_PARAMS]
    return urlunsplit(parts._replace(query=urlencode(query)))


def redact(text: str, token: str | None) -> str:
    return text.replace(token, "[REDACTED]") if token else text


@dataclass
class ReachSlice:
    country: str
    age_range: str
    gender: str  # male | female | unknown
    reach: int


@dataclass
class CompetitorAd:
    id: str
    page_id: str | None
    page_name: str | None
    bodies: list[str]
    titles: list[str]
    start_date: date | None
    stop_date: date | None  # None = still running
    platforms: list[str]
    eu_total_reach: int | None
    target_ages: list[str]
    target_gender: str | None
    reach_breakdown: list[ReachSlice] = field(default_factory=list)
    snapshot_url: str | None = None  # token stripped

    def longevity_days(self, as_of: date) -> int | None:
        """Days the ad has run (until it stopped, or until `as_of`)."""
        if self.start_date is None:
            return None
        end = self.stop_date or as_of
        return max(0, (end - self.start_date).days)

    def reach_share(self, by: str) -> dict[str, float]:
        """Share of breakdown reach per `country`, `age_range` or `gender`."""
        total = sum(s.reach for s in self.reach_breakdown)
        if total == 0:
            return {}
        shares: dict[str, float] = {}
        for s in self.reach_breakdown:
            key = getattr(s, by)
            shares[key] = shares.get(key, 0) + s.reach / total
        return shares

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["start_date"] = self.start_date.isoformat() if self.start_date else None
        data["stop_date"] = self.stop_date.isoformat() if self.stop_date else None
        return data


def _date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_breakdown(raw: Any) -> list[ReachSlice]:
    """[{country, age_gender_breakdowns: [{age_range, male, female, unknown}]}] → slices."""
    slices: list[ReachSlice] = []
    for country_block in raw or []:
        country = country_block.get("country", "??")
        for row in country_block.get("age_gender_breakdowns", []) or []:
            for gender in ("male", "female", "unknown"):
                reach = _int(row.get(gender))
                if reach:
                    slices.append(ReachSlice(country, row.get("age_range", "?"), gender, reach))
    return slices


def parse_ad(raw: dict[str, Any]) -> CompetitorAd:
    return CompetitorAd(
        id=str(raw["id"]),
        page_id=raw.get("page_id"),
        page_name=raw.get("page_name"),
        bodies=list(raw.get("ad_creative_bodies") or []),
        titles=list(raw.get("ad_creative_link_titles") or []),
        start_date=_date(raw.get("ad_delivery_start_time")),
        stop_date=_date(raw.get("ad_delivery_stop_time")),
        platforms=list(raw.get("publisher_platforms") or []),
        eu_total_reach=_int(raw.get("eu_total_reach")),
        target_ages=list(raw.get("target_ages") or []),
        target_gender=raw.get("target_gender"),
        reach_breakdown=parse_breakdown(raw.get("age_country_gender_reach_breakdown")),
        snapshot_url=strip_token(raw.get("ad_snapshot_url")),
    )


class AdLibraryClient:
    def __init__(self, token: str, *, version: str = DEFAULT_VERSION,
                 http: httpx.Client | None = None, base_url: str = GRAPH_URL,
                 retries: int = 3, backoff_s: float = 2.0, sleep: Callable[[float], None] = time.sleep):
        if not token:
            raise AdLibraryError("FB_TOKEN is not set in .env")
        self.token = token
        self.retries = retries
        self.backoff_s = backoff_s
        self._sleep = sleep
        self.url = f"{base_url}/{version}/ads_archive"
        self.http = http or httpx.Client(timeout=30)

    def search(self, *, countries: list[str], page_ids: list[str] | None = None,
               terms: str | None = None, active_status: str = "ALL",
               delivery_date_max: date | None = None, limit: int = 100,
               max_ads: int | None = None, fields: tuple[str, ...] = DEFAULT_FIELDS) -> Iterator[CompetitorAd]:
        """Yield ads page by page. Prefer `page_ids`: keyword search is noisy."""
        if not page_ids and not terms:
            raise ValueError("give page_ids or terms")
        if not countries:
            raise ValueError("give at least one country (commercial ads: EU/UK only)")
        params: dict[str, Any] = {
            "access_token": self.token,
            "ad_type": "ALL",
            "ad_reached_countries": json.dumps(countries),
            "ad_active_status": active_status,
            "fields": ",".join(fields),
            "limit": limit,
        }
        if page_ids:
            params["search_page_ids"] = json.dumps(page_ids)
        if terms:
            params["search_terms"] = terms
        if delivery_date_max:
            params["ad_delivery_date_max"] = delivery_date_max.isoformat()

        yielded = 0
        while True:
            body = self._get(params)
            for raw in body.get("data", []):
                yield parse_ad(raw)
                yielded += 1
                if max_ads is not None and yielded >= max_ads:
                    return
            paging = body.get("paging") or {}
            after = (paging.get("cursors") or {}).get("after")
            if not paging.get("next") or not after:
                return
            params = {**params, "after": after}

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        """One page, retried with exponential backoff on network errors, 5xx and rate limits."""
        for attempt in range(self.retries + 1):
            last = attempt == self.retries
            try:
                response = self.http.get(self.url, params=params)
            except httpx.HTTPError as exc:
                if last:
                    raise AdLibraryError(redact(f"request failed: {exc}", self.token)) from None
                self._sleep(self.backoff_s * 2**attempt)
                continue
            try:
                body = response.json()
            except ValueError:
                if response.status_code >= 500 and not last:
                    self._sleep(self.backoff_s * 2**attempt)
                    continue
                raise AdLibraryError(f"non-JSON response (HTTP {response.status_code})") from None
            if not isinstance(body, dict):
                raise AdLibraryError("unexpected response shape")
            if "error" in body:
                err = body["error"] if isinstance(body["error"], dict) else {}
                code = err.get("code")
                transient = bool(err.get("is_transient")) or code in TRANSIENT_CODES
                if transient and not last:
                    self._sleep(self.backoff_s * 2**attempt)
                    continue
                message = redact(str(err.get("message", "")), self.token)
                hint = " (usually a missing, expired or invalid token)" if code == 1 else ""
                raise AdLibraryError(f"Ad Library error {code}: {message}{hint}")
            return body
        raise AssertionError("unreachable")


def save_jsonl(ads: list[CompetitorAd], path: Path) -> Path:
    """Write ads as JSONL. Refuses to write anything that still contains a token."""
    lines = [json.dumps(ad.to_json(), ensure_ascii=False) for ad in ads]
    if any("access_token" in line for line in lines):
        raise AdLibraryError("refusing to save: an access_token is still present")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def load_jsonl(path: Path) -> list[CompetitorAd]:
    ads: list[CompetitorAd] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        d["start_date"] = _date(d.get("start_date"))
        d["stop_date"] = _date(d.get("stop_date"))
        d["reach_breakdown"] = [ReachSlice(**s) for s in d.get("reach_breakdown", [])]
        ads.append(CompetitorAd(**d))
    return ads
