"""Scout: find the market's real competitor ads in the Ad Library.

1. `plan_search` (Muse Spark): from the app's store page, the words its
   competitors' ads would use, in the languages of the research countries.
2. `collect` (Ad Library, free): active ads matching those words, grouped by
   advertiser. Keyword search is noisy (spam pages, unrelated products), so:
3. `filter_advertisers` (Muse Spark): keep only advertisers selling something a
   customer of this app could buy instead. The owner can also name competitor
   pages directly (`known_pages`), which skips the filter for them.
4. `market_ads`: every ad of the kept advertisers (active and recent inactive),
   deduplicated by copy — the corpus for the simulated feed and for strategy.

Commercial ads are only visible for EU/UK delivery: research countries must be
EU/UK even when the campaign targets elsewhere (the market is used as a proxy).
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from whynot.agents.ask import Answer, ChatClient, Invalid, ask_json
from whynot.ingest.adlibrary import AdLibraryClient, CompetitorAd
from whynot.ingest.appstore import AppProfile
from whynot.models import SPARK

EU_UK = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU",
         "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "GB"}


@dataclass(frozen=True)
class SearchPlan:
    terms: list[str]  # words competitors' ads would contain
    category: str  # one line: what the app sells, for the filter


@dataclass
class Advertiser:
    page_id: str
    page_name: str
    ads: int
    samples: list[str] = field(default_factory=list)  # a few ad copies
    terms: list[str] = field(default_factory=list)  # which search terms found it


@dataclass(frozen=True)
class Verdict:
    page_id: str
    competitor: bool
    why: str


def check_countries(countries: Iterable[str]) -> list[str]:
    cs = [c.upper() for c in countries]
    bad = [c for c in cs if c not in EU_UK]
    if not cs or bad:
        raise ValueError(f"research countries must be EU/UK (Ad Library limit); not allowed: {bad or 'none given'}")
    return cs


def app_brief(app: AppProfile, *, max_chars: int = 1500) -> str:
    rating = f"{app.rating:.1f}/5 from {app.rating_count} ratings" if app.rating else "no rating yet"
    price = "free (in-app purchases possible)" if app.free else f"{app.price} {app.currency}"
    return (f"App: {app.name} by {app.seller}\nCategory: {', '.join(app.genres)}\nPrice: {price}\nRating: {rating}\n"
            f"Store description:\n{app.description[:max_chars]}")


# --- 1. search plan ----------------------------------------------------------------

def validate_plan(data: Any) -> SearchPlan:
    if not isinstance(data, dict):
        raise Invalid("expected a JSON object")
    terms = data.get("terms")
    if not isinstance(terms, list) or not 3 <= len(terms) <= 10:
        raise Invalid("'terms' must be a list of 3 to 10 search terms")
    clean: list[str] = []
    for t in terms:
        if not isinstance(t, str) or not t.strip() or len(t) > 40:
            raise Invalid(f"bad term {t!r}: non-empty strings of at most 40 characters")
        if t.strip().lower() not in {c.lower() for c in clean}:
            clean.append(t.strip())
    if len(clean) < 3:
        raise Invalid("need at least 3 distinct terms")
    category = data.get("category")
    if not isinstance(category, str) or not category.strip():
        raise Invalid("'category' must be a one-line description")
    return SearchPlan(clean, category.strip()[:200])


def plan_search(client: ChatClient, app: AppProfile, countries: list[str]) -> Answer[SearchPlan]:
    prompt = f"""{app_brief(app)}

We want to find the Facebook/Instagram ads of this app's competitors in the Meta Ad Library,
for ads delivered in: {', '.join(countries)}.
The Ad Library searches the words inside ad copy. Give 5 to 8 short search terms (1–3 words) that competitors' ads
would contain: product category words, the job the app does, and well-known competitor brand names. Mix English and
the main languages of those countries. Avoid words too generic to be useful on their own.
Reply with JSON only: {{"category": "one line: what this app sells and to whom", "terms": ["...", "..."]}}"""
    return ask_json(client, [{"role": "user", "content": prompt}], validate_plan, module="scout", model=SPARK,
                    max_tokens=3000, reasoning_effort="low")


# --- 2. collect ---------------------------------------------------------------------

def group_advertisers(found: dict[str, list[CompetitorAd]], *, samples: int = 2) -> list[Advertiser]:
    """Ads found per term → advertisers, most ads first; ads counted once across terms."""
    by_page: dict[str, Advertiser] = {}
    seen_ads: set[str] = set()
    for term, ads in found.items():
        for ad in ads:
            key = ad.page_id or ad.page_name or ""
            if not key:
                continue
            adv = by_page.setdefault(key, Advertiser(key, ad.page_name or "?", 0))
            if term not in adv.terms:
                adv.terms.append(term)
            if ad.id in seen_ads:
                continue
            seen_ads.add(ad.id)
            adv.ads += 1
            body = (ad.bodies or [""])[0].strip()
            if body and len(adv.samples) < samples and body not in adv.samples:
                adv.samples.append(body[:300])
    return sorted(by_page.values(), key=lambda a: (-a.ads, a.page_name))


def collect(lib: AdLibraryClient, plan: SearchPlan, countries: list[str], *, per_term: int = 100) -> list[Advertiser]:
    found = {t: list(lib.search(countries=countries, terms=t, active_status="ACTIVE", max_ads=per_term))
             for t in plan.terms}
    return group_advertisers(found)


# --- 3. filter ----------------------------------------------------------------------

def make_filter_validator(ids: set[str]):
    def validate(data: Any) -> list[Verdict]:
        rows = data.get("advertisers") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise Invalid("expected {\"advertisers\": [...]}")
        verdicts: dict[str, Verdict] = {}
        for r in rows:
            if not isinstance(r, dict):
                raise Invalid("each advertiser must be an object")
            pid = str(r.get("page_id", ""))
            if pid not in ids:
                raise Invalid(f"unknown page_id {pid!r}: use only the ids given")
            comp = r.get("competitor")
            if not isinstance(comp, bool):
                raise Invalid(f"'competitor' must be true or false for {pid}")
            verdicts[pid] = Verdict(pid, comp, str(r.get("why", ""))[:200])
        missing = ids - set(verdicts)
        if missing:
            raise Invalid(f"missing verdicts for page_ids {sorted(missing)}")
        return [verdicts[i] for i in sorted(verdicts)]
    return validate


def filter_advertisers(client: ChatClient, app: AppProfile, plan: SearchPlan, advertisers: list[Advertiser],
                       *, max_candidates: int = 40) -> Answer[list[Verdict]]:
    candidates = advertisers[:max_candidates]
    listing = "\n".join(
        f'- page_id {a.page_id}: "{a.page_name}" ({a.ads} ads). Copy: ' + " | ".join(s[:160] for s in a.samples)
        for a in candidates)
    prompt = f"""{app_brief(app, max_chars=600)}
In one line: {plan.category}

Below are advertisers found in the Meta Ad Library with keyword search. Keyword search is noisy.
Mark "competitor": true only if the advertiser sells something a customer of this app could choose instead
(same need, same kind of product). Spam pages, unrelated products and pages that only mention a keyword: false.

{listing}

Reply with JSON only: {{"advertisers": [{{"page_id": "...", "competitor": true, "why": "short reason"}}]}}
One entry per page_id above, no other ids."""
    validate = make_filter_validator({a.page_id for a in candidates})
    return ask_json(client, [{"role": "user", "content": prompt}], validate,
                    module="scout", model=SPARK, max_tokens=6000, reasoning_effort="low")


# --- 4. market corpus -----------------------------------------------------------------

def dedupe_by_copy(ads: list[CompetitorAd]) -> list[CompetitorAd]:
    seen: set[tuple[str, str]] = set()
    out = []
    for ad in ads:
        body = " ".join((ad.bodies or [""])[0].split()).lower()
        key = (ad.page_id or ad.page_name or "", body)
        if not body or key in seen:
            continue
        seen.add(key)
        out.append(ad)
    return out


def market_ads(lib: AdLibraryClient, page_ids: list[str], countries: list[str], *,
               per_status: int = 300) -> list[CompetitorAd]:
    if not page_ids:
        return []
    active = list(lib.search(countries=countries, page_ids=page_ids, active_status="ACTIVE", max_ads=per_status))
    inactive = list(lib.search(countries=countries, page_ids=page_ids, active_status="INACTIVE", max_ads=per_status))
    return dedupe_by_copy(active + inactive)


@dataclass
class MarketScan:
    plan: SearchPlan
    advertisers: list[Advertiser]
    verdicts: list[Verdict]
    competitor_pages: list[str]
    ads: list[CompetitorAd]
    usd: float

    def summary(self) -> dict[str, Any]:
        per_page = Counter(a.page_name for a in self.ads)
        return {"terms": self.plan.terms, "category": self.plan.category,
                "advertisers_found": len(self.advertisers),
                "competitors": [asdict(v) for v in self.verdicts if v.competitor],
                "rejected": [asdict(v) for v in self.verdicts if not v.competitor],
                "ads": len(self.ads), "ads_per_competitor": dict(per_page.most_common())}


def scan(client: ChatClient, lib: AdLibraryClient, app: AppProfile, countries: list[str], *,
         known_pages: list[str] | None = None, max_competitors: int = 8) -> MarketScan:
    countries = check_countries(countries)
    plan = plan_search(client, app, countries)
    advertisers = collect(lib, plan.value, countries)
    usd = plan.usd
    verdicts: list[Verdict] = []
    if advertisers:
        filt = filter_advertisers(client, app, plan.value, advertisers)
        verdicts, usd = filt.value, usd + filt.usd
    kept = {v.page_id for v in verdicts if v.competitor}
    ranked = [a.page_id for a in advertisers if a.page_id in kept][:max_competitors]
    pages = list(dict.fromkeys([*(known_pages or []), *ranked]))
    return MarketScan(plan.value, advertisers, verdicts, pages, market_ads(lib, pages, countries), usd)
