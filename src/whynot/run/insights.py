"""Results per ad and per day: from Meta (the Insights API), or from a simulated account for tests and demos.

Meta: `GET act_<id>/insights?level=ad&time_increment=1` gives, per ad and day, spend, impressions, clicks and
`actions` (installs, link clicks...). Pages are followed with the `after` cursor, never the `next` URL (it
carries the token). The last `settle_days` are marked provisional: Meta keeps attributing conversions for a
while, so a decision should not rest on yesterday alone.

Simulated: a deterministic account where each ad has a hidden quality drawn from its id; spend follows its
budget, conversions follow quality with noise, and every ad slowly tires. Every number it gives is labelled
simulated; it exists so the daily loop can be tested and shown before a real account runs.
"""

import hashlib
import json
import math
import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Protocol

from whynot.run.autopilot import DailyMetrics
from whynot.run.meta import MarketingClient, MetaError

# action types that count as a conversion, by campaign objective
CONVERSIONS = {
    "app_promotion": ("mobile_app_install", "app_install", "omni_app_install"),
    "traffic": ("link_click",),
}


class MetricsSource(Protocol):
    simulated: bool

    def fetch(self, ad_ids: list[str], since: date, until: date) -> dict[str, list[DailyMetrics]]: ...


def _num(value: Any) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return 0.0
    return x if math.isfinite(x) and x >= 0 else 0.0  # Meta never sends negatives; refuse NaN or junk


def parse_rows(rows: list[dict[str, Any]], conversion_types: tuple[str, ...]) -> dict[str, list[DailyMetrics]]:
    """Insights rows (one per ad and day) → metrics per ad, days in order. Duplicate rows for a day are summed."""
    acc: dict[tuple[str, str], list[float]] = {}
    for r in rows:
        ad, day = str(r.get("ad_id", "")), str(r.get("date_start", ""))
        if not ad or not day:
            continue
        conv = sum(_num(a.get("value")) for a in r.get("actions") or [] if a.get("action_type") in conversion_types)
        cur = acc.setdefault((ad, day), [0.0, 0.0, 0.0, 0.0])
        for i, v in enumerate((_num(r.get("spend")), _num(r.get("impressions")), _num(r.get("clicks")), conv)):
            cur[i] += v
    out: dict[str, list[DailyMetrics]] = {}
    for (ad, day), (spend, imp, clicks, conv) in sorted(acc.items()):
        out.setdefault(ad, []).append(DailyMetrics(day, round(spend, 2), int(imp), int(clicks), int(conv)))
    return out


class MetaInsights:
    """Real results from the ad account (read-only)."""

    simulated = False

    def __init__(self, client: MarketingClient, *, objective: str = "traffic", settle_days: int = 1):
        if objective not in CONVERSIONS:
            raise ValueError(f"objective must be one of {sorted(CONVERSIONS)}")
        self.client = client
        self.conversions = CONVERSIONS[objective]
        self.settle_days = settle_days

    def fetch(self, ad_ids: list[str], since: date, until: date) -> dict[str, list[DailyMetrics]]:
        if not ad_ids:
            return {}
        params: dict[str, Any] = {
            "level": "ad", "time_increment": 1, "fields": "ad_id,date_start,spend,impressions,clicks,actions",
            "time_range": json.dumps({"since": since.isoformat(), "until": until.isoformat()}),
            "filtering": json.dumps([{"field": "ad.id", "operator": "IN", "value": ad_ids}]), "limit": 500}
        rows: list[dict[str, Any]] = []
        for _ in range(50):  # pages; a day of a small account fits in one
            body = self.client._call("GET", f"{self.client.account.act}/insights", params=params)
            rows += body.get("data") or []
            after = ((body.get("paging") or {}).get("cursors") or {}).get("after")
            if not after or not (body.get("paging") or {}).get("next"):
                break
            params = {**params, "after": after}  # the cursor only: `next` carries the token
        else:
            raise MetaError("insights: too many pages")
        return parse_rows(rows, self.conversions)

    def provisional(self, day: date, today: date) -> bool:
        return (today - day).days <= self.settle_days


@dataclass
class SimulatedAccount:
    """A fake account with known truths, for tests and demos. Labelled simulated everywhere it is shown."""

    daily_budget_eur: float = 6.0
    base_cpm_eur: float = 7.0
    seed: int = 0
    fatigue_per_day: float = 0.04
    simulated = True

    def quality(self, ad_id: str) -> float:
        """Hidden truth: how good the ad is (0.3-1.7), fixed by its id."""
        h = int(hashlib.sha256(f"{self.seed}:{ad_id}".encode()).hexdigest()[:8], 16)
        return 0.3 + 1.4 * (h / 0xFFFFFFFF)

    def day(self, ad_id: str, d: date, age_days: int) -> DailyMetrics:
        rng = random.Random(f"{self.seed}:{ad_id}:{d.isoformat()}")
        q = self.quality(ad_id) * (1 - self.fatigue_per_day) ** age_days
        spend = round(self.daily_budget_eur * rng.uniform(0.85, 1.0), 2)
        impressions = int(spend / self.base_cpm_eur * 1000)
        ctr = max(0.002, rng.gauss(0.009 * q, 0.0015))
        clicks = int(impressions * ctr)
        conversions = sum(1 for _ in range(clicks) if rng.random() < 0.08 * q)
        return DailyMetrics(d.isoformat(), spend, impressions, clicks, conversions)

    def fetch(self, ad_ids: list[str], since: date, until: date, *, launched: dict[str, date] | None = None
              ) -> dict[str, list[DailyMetrics]]:
        out: dict[str, list[DailyMetrics]] = {}
        for ad in ad_ids:
            start = max(since, (launched or {}).get(ad, since))
            d, days = start, []
            while d <= until:
                days.append(self.day(ad, d, (d - (launched or {}).get(ad, start)).days))
                d += timedelta(days=1)
            if days:
                out[ad] = days
        return out
