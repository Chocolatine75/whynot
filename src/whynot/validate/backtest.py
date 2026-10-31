"""R1: does the simulator rank the partner's past ads the way reality did? (E2-4)

Pre-registered (Oct 31, before seeing any partner data; see DECISIONS.md):
- metric: link CTR = link clicks / impressions (conversions are too sparse on a small account to rank ads);
  CPA is reported as secondary when both ads of a pair have >= `min_conversions` conversions;
- an ad counts if it had >= `min_impressions` impressions;
- a pair counts only if its two CTRs differ by more than noise: |ctr_a − ctr_b| > z × sqrt(var_a + var_b),
  var = p(1 − p) / impressions, z = 1.96. Pairs inside the noise are not "orderable" by anyone;
- score = pairwise accuracy (simulator ties count half), 95 % CI by bootstrap over ads;
- baselines on the same pairs: chance (0.5), the simple judge, shorter copy, longer copy, most recent.

Blind by construction: predictions are computed from `creative_items` (advertiser, title, text, image),
which never carry a metric. Only `evaluate` joins predictions with results.

Privacy: partner data lives in `data/private/` (gitignored). `summary` is what may enter the repo:
numbers only, no ad text, no ad ids, no names.
"""

import csv
import json
import math
import re
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from whynot.sim.feed import FeedItem
from whynot.validate.stats import bootstrap_ci

Z95 = 1.959964


class HistoryError(ValueError):
    """The export or the API answer can't be read; the message says what is missing."""


@dataclass(frozen=True)
class PastAd:
    id: str
    name: str
    body: str
    title: str
    started: date | None
    spend: float
    impressions: int
    link_clicks: int
    conversions: int
    image: str | None = None  # local path of the creative (data/private/...), if we have it

    @property
    def ctr(self) -> float:
        return self.link_clicks / self.impressions if self.impressions else 0.0

    @property
    def cpa(self) -> float | None:
        return self.spend / self.conversions if self.conversions else None


# --- loading ---------------------------------------------------------------------------------

# Ads Manager export headers, English and French (lowercase, matched as prefixes: "amount spent (eur)").
COLUMNS: dict[str, tuple[str, ...]] = {
    "id": ("ad id", "identifiant de la publicité", "id de la publicité"),
    "name": ("ad name", "nom de la publicité"),
    "spend": ("amount spent", "montant dépensé"),
    "impressions": ("impressions",),
    "link_clicks": ("link clicks", "clics sur un lien"),
    "conversions": ("results", "résultats", "app installs", "installations de l’app", "installations de l'app"),
    "body": ("body", "corps du texte", "texte principal", "primary text"),
    "title": ("title", "titre", "headline"),
    "started": ("reporting starts", "début des rapports", "starts", "début"),
}
REQUIRED = ("id", "spend", "impressions", "link_clicks")


def _number(raw: str | None) -> float:
    """'1 234,56 €', '1,234.56', '' → float (empty or '-' = 0)."""
    s = (raw or "").strip().replace(" ", "").replace("\xa0", "").replace(" ", "")
    s = re.sub(r"[^\d,.\-]", "", s)
    if s in ("", "-"):
        return 0.0
    if "," in s and "." in s:  # the last separator is the decimal one
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif s.count(",") > 1:  # 1,234,567
        s = s.replace(",", "")
    elif "," in s:  # "1,234" is a thousand (EN); "12,5" and "0,123" are decimals (FR)
        head, tail = s.split(",")
        thousands = len(tail) == 3 and head.lstrip("-") not in ("", "0")
        s = s.replace(",", "") if thousands else s.replace(",", ".")
    try:
        x = float(s)
    except ValueError:
        raise HistoryError(f"not a number: {raw!r}") from None
    if not math.isfinite(x) or x < 0:
        raise HistoryError(f"not a valid amount: {raw!r}")
    return x


def _date(raw: str | None) -> date | None:
    s = (raw or "").strip()[:10]
    for pattern in (r"(\d{4})-(\d{2})-(\d{2})", r"(\d{2})/(\d{2})/(\d{4})"):
        m = re.fullmatch(pattern, s)
        if m:
            y, mo, d = (m[1], m[2], m[3]) if len(m[1]) == 4 else (m[3], m[2], m[1])  # dd/mm/yyyy (FR export)
            return date(int(y), int(mo), int(d))
    return None


def _header_map(headers: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for key, aliases in COLUMNS.items():
        for h in headers:
            if any(h.strip().lower().startswith(a) for a in aliases) and key not in found:
                found[key] = h
    missing = [k for k in REQUIRED if k not in found]
    if missing:
        raise HistoryError(f"the export has no column for {missing}; columns found: {headers}. Export at ad level "
                           "with Ad ID, Amount spent, Impressions and Link clicks (add Body/Title if available)")
    return found


def load_csv(path: Path) -> list[PastAd]:
    """An Ads Manager export at ad level (EN or FR headers, `,` or `;` separated). Duplicate ad ids are summed."""
    text = Path(path).read_text(encoding="utf-8-sig")
    dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",;\t")
    rows = list(csv.DictReader(text.splitlines(), dialect=dialect))
    if not rows:
        raise HistoryError("the export has no rows")
    cols = _header_map(list(rows[0].keys()))
    ads: dict[str, PastAd] = {}
    for r in rows:
        ad_id = (r.get(cols["id"]) or "").strip()
        if not ad_id or not ad_id.replace(".", "").isdigit():
            continue  # totals line, empty line
        get = {k: r.get(h) for k, h in cols.items()}
        ad = PastAd(ad_id, (get.get("name") or "").strip(), (get.get("body") or "").strip(),
                    (get.get("title") or "").strip(), _date(get.get("started")), _number(get["spend"]),
                    int(_number(get["impressions"])), int(_number(get["link_clicks"])),
                    int(_number(get.get("conversions"))))
        if ad_id in ads:
            old = ads[ad_id]
            ad = PastAd(ad_id, old.name or ad.name, old.body or ad.body, old.title or ad.title,
                        min(filter(None, (old.started, ad.started)), default=None), old.spend + ad.spend,
                        old.impressions + ad.impressions, old.link_clicks + ad.link_clicks,
                        old.conversions + ad.conversions)
        ads[ad_id] = ad
    return list(ads.values())


INSIGHT_FIELDS = "ad_id,spend,impressions,inline_link_clicks,actions"
AD_FIELDS = "id,name,created_time,creative{body,title,thumbnail_url}"
CONVERSION_TYPES = ("mobile_app_install", "app_install", "omni_app_install")


def _pages(call: Callable[[str, dict[str, Any]], dict[str, Any]], path: str, params: dict[str, Any]
           ) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _ in range(100):
        body = call(path, params)
        rows += body.get("data") or []
        paging = body.get("paging") or {}
        after = (paging.get("cursors") or {}).get("after")
        if not after or not paging.get("next"):
            return rows
        params = {**params, "after": after}  # the cursor only: the `next` URL carries the token
    raise HistoryError(f"{path}: too many pages")


def fetch_history(call: Callable[[str, dict[str, Any]], dict[str, Any]], act: str) -> tuple[list[PastAd],
                                                                                           dict[str, str]]:
    """Every ad of the account with its lifetime results and creative text, read-only.

    `call(path, params)` is a GET on the Graph API (e.g. `lambda p, q: client._call("GET", p, params=q)`).
    Returns the ads and {ad id: thumbnail URL} (CDN URLs, short-lived: download them at once, never store them).
    Field names follow Meta's docs; not yet checked against a real response.
    """
    ads_raw = _pages(call, f"{act}/ads", {"fields": AD_FIELDS, "limit": 200})
    stats = _pages(call, f"{act}/insights", {"level": "ad", "date_preset": "maximum", "fields": INSIGHT_FIELDS,
                                             "limit": 500})
    by_ad = {str(s.get("ad_id")): s for s in stats}
    out, thumbs = [], {}
    for a in ads_raw:
        s = by_ad.get(str(a.get("id")))
        if s is None:
            continue  # never delivered
        creative = a.get("creative") or {}
        conv = sum(_number(str(x.get("value"))) for x in s.get("actions") or [] if x.get("action_type")
                   in CONVERSION_TYPES)
        out.append(PastAd(str(a["id"]), str(a.get("name", "")), str(creative.get("body") or ""),
                          str(creative.get("title") or ""), _date(str(a.get("created_time", ""))),
                          _number(str(s.get("spend"))), int(_number(str(s.get("impressions")))),
                          int(_number(str(s.get("inline_link_clicks")))), int(conv)))
        if creative.get("thumbnail_url"):
            thumbs[str(a["id"])] = str(creative["thumbnail_url"])
    return out, thumbs


def save_history(ads: list[PastAd], path: Path) -> Path:
    """Partner data: only under data/private/ (gitignored)."""
    # a folder named "private" in the project's own path; not macOS's system /private (every temp dir is under it)
    parts = Path(path).resolve().parts
    if "private" not in parts[2:]:
        raise HistoryError(f"partner data must be saved under data/private/, not {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([{**asdict(a), "started": a.started.isoformat() if a.started else None}
                                for a in ads], indent=1, ensure_ascii=False))
    return path


def load_history(path: Path) -> list[PastAd]:
    rows = json.loads(Path(path).read_text())
    return [PastAd(**{**r, "started": date.fromisoformat(r["started"]) if r["started"] else None}) for r in rows]


# --- blind predictions ---------------------------------------------------------------------------

def creative_items(ads: Iterable[PastAd], advertiser: str, images: dict[str, str] | None = None) -> list[FeedItem]:
    """What a viewer sees of each ad, and nothing else: no metric can leak into a prompt."""
    return [FeedItem(a.id, advertiser, a.title, a.body, (images or {}).get(a.id)) for a in ads]


def heuristic_scores(ads: list[PastAd]) -> dict[str, dict[str, float]]:
    """Baselines that need no model: shorter copy, longer copy, most recent."""
    length = {a.id: float(len(a.body) + len(a.title)) for a in ads}
    first = min((a.started for a in ads if a.started), default=None)
    return {"shorter_copy": {k: -v for k, v in length.items()}, "longer_copy": length,
            "most_recent": {a.id: float((a.started - first).days) if a.started and first else 0.0 for a in ads}}


# --- evaluation -----------------------------------------------------------------------------

def eligible(ads: list[PastAd], min_impressions: int = 1000) -> list[PastAd]:
    return [a for a in ads if a.impressions >= min_impressions]


def separable(a: PastAd, b: PastAd, z: float = Z95) -> bool:
    """Their CTRs differ by more than sampling noise (normal approximation of two proportions)."""
    var = sum(x.ctr * (1 - x.ctr) / x.impressions for x in (a, b))
    return abs(a.ctr - b.ctr) > z * math.sqrt(var)


def separable_pairs(ads: list[PastAd], z: float = Z95) -> int:
    return sum(separable(a, b, z) for i, a in enumerate(ads) for b in ads[i + 1:])


def _accuracy(scores: dict[str, float], ads: list[PastAd], z: float) -> tuple[float, int]:
    score, pairs = 0.0, 0
    for i in range(len(ads)):
        for j in range(i + 1, len(ads)):
            a, b = ads[i], ads[j]
            if a.id == b.id or a.id not in scores or b.id not in scores or not separable(a, b, z):
                continue
            pairs += 1
            pred, real = scores[a.id] - scores[b.id], a.ctr - b.ctr
            score += 0.5 if pred == 0 else float((pred > 0) == (real > 0))
    if not pairs:
        raise ValueError("no pair of ads with clearly different CTRs")
    return score / pairs, pairs


@dataclass(frozen=True)
class R1Result:
    name: str
    accuracy: float
    ci: tuple[float, float]
    pairs: int
    ads: int


def evaluate(name: str, scores: dict[str, float], ads: list[PastAd], *, z: float = Z95, seed: int = 0) -> R1Result:
    """Pairwise accuracy on CTR over separable pairs, with a bootstrap CI over ads."""
    scored = [a for a in ads if a.id in scores]
    acc, pairs = _accuracy(scores, scored, z)
    ci = bootstrap_ci(lambda idx: _accuracy(scores, [scored[i] for i in idx], z)[0], len(scored), seed=seed)
    return R1Result(name, acc, ci, pairs, len(scored))


@dataclass
class R1Report:
    results: list[R1Result] = field(default_factory=list)
    ads: int = 0
    separable_pairs: int = 0
    usd: float = 0.0
    simulated_scores: bool = True  # the predictions are simulated; the outcomes are real

    def summary(self, dataset: str) -> dict[str, Any]:
        """What may be published: numbers only (no text, no ids, no names). `dataset` is a label we choose."""
        return {"r1": dataset, "metric": "link CTR", "ads": self.ads, "separable_pairs": self.separable_pairs,
                "usd": round(self.usd, 3), "simulated_scores": self.simulated_scores,
                "results": [{"name": r.name, "accuracy": round(r.accuracy, 3), "ci": [round(x, 3) for x in r.ci],
                             "pairs": r.pairs} for r in self.results]}


# --- the whole backtest ----------------------------------------------------------------------

CONDITIONS = ("viewers-text", "viewers-image", "judge-text", "judge-image")


def run(model: Any, ads: list[PastAd], *, advertiser: str, personas: list[Any], conditions: Iterable[str],
        images: dict[str, str] | None = None, feed_size: int = 4, appearances: int = 3, viewers_per_feed: int = 2,
        viewer_cache: Any = None, judge_cache: Any = None, z: float = Z95, seed: int = 0
        ) -> tuple[R1Report, dict[str, dict[str, float]]]:
    """Blind predictions for every condition, then each scored against real CTRs. Returns (report, scores)."""
    from whynot.sim.feed import build_market_feeds
    from whynot.sim.scores import score_ads
    from whynot.sim.viewer import Viewer, run_simulation
    from whynot.validate.judge import Judge

    conditions = list(conditions)
    unknown = [c for c in conditions if c not in CONDITIONS]
    if unknown:
        raise ValueError(f"unknown conditions {unknown}; use {CONDITIONS}")
    if any(c.endswith("image") for c in conditions) and not images:
        raise ValueError("image conditions need the ads' creatives (images)")
    report = R1Report(ads=len(ads), separable_pairs=separable_pairs(ads, z))
    text_items = creative_items(ads, advertiser)
    image_items = creative_items(ads, advertiser, images)
    feeds = build_market_feeds(text_items, feed_size=feed_size, appearances=appearances, seed=seed)
    by_id = {it.ad_id: it for it in image_items}
    all_scores: dict[str, dict[str, float]] = {}
    for cond in conditions:
        before = model.spent_usd
        if cond.startswith("viewers"):
            run_feeds = [[by_id[it.ad_id] for it in f] for f in feeds] if cond.endswith("image") else feeds
            sim = run_simulation(Viewer(model, reasoning_effort="low", cache=viewer_cache), personas, run_feeds,
                                 viewers_per_feed=viewers_per_feed)
            all_scores[cond] = {k: v.preference_lift for k, v in score_ads(sim.reactions).items()}
        else:
            judged = Judge(model, cache=judge_cache).run(image_items if cond.endswith("image") else text_items)
            all_scores[cond] = judged.scores
        report.usd += model.spent_usd - before
    all_scores.update(heuristic_scores(ads))
    for name, scores in all_scores.items():
        try:
            report.results.append(evaluate(name, scores, ads, z=z, seed=seed))
        except ValueError:
            continue  # no separable pair among the ads this condition scored: nothing to report for it
    return report, all_scores
