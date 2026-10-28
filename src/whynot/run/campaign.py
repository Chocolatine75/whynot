"""Campaign plan: winning ads → a Meta app-install campaign, in Marketing API shape.

Structure (one campaign, budgets at ad-set level):
- campaign: objective OUTCOME_APP_PROMOTION, created PAUSED;
- one ad set per persona: its countries, ages, gender, iOS; optimised for app
  installs; daily budget = the owner's cap split evenly over ad sets (the
  simulator is not trusted to move money before real results exist);
- 2–6 ads per ad set, at most 2 variants of one template (concept diversity,
  which Meta's delivery system rewards).

`validate` checks the plan against the owner's cap and Meta's rules before
anything is sent; `launch_decisions` runs every publish through the autopilot
(autonomy level, cap, first-launch approval). Ids Meta must supply (ad account,
Facebook page, Meta app id, image hashes) are placeholders until publishing.
"""

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from whynot.run.autopilot import AccountState, Action, Decision, Kind, Policy, decide

COUNTRY = re.compile(r"^[A-Z]{2}$")
MIN_ADSET_DAILY_EUR = 5.0  # below this an app-install ad set rarely exits the learning phase
MAX_ADS_PER_ADSET = 6
MAX_PER_TEMPLATE = 2
GENDER_CODES = {"male": [1], "female": [2], "all": None}
PLACEHOLDERS = ("{AD_ACCOUNT_ID}", "{PAGE_ID}", "{META_APP_ID}")


@dataclass(frozen=True)
class AdChoice:
    """One produced, guard-checked, simulated ad variant."""
    variant_id: str
    template_id: str
    persona: str
    image_path: str
    headline_on_image: str
    body: str  # primary text
    title: str  # link headline
    cta: str  # Meta CTA type
    guards_passed: bool
    sim_score: float  # simulated preference lift; ranking only


@dataclass(frozen=True)
class Audience:
    persona: str
    name: str
    countries: tuple[str, ...]
    age_min: int
    age_max: int
    gender: str


@dataclass
class AdSetPlan:
    name: str
    audience: Audience
    daily_budget_eur: float
    ads: list[AdChoice] = field(default_factory=list)


@dataclass
class CampaignPlan:
    name: str
    app_name: str
    store_url: str
    daily_cap_eur: float
    ad_sets: list[AdSetPlan]
    notes: list[str] = field(default_factory=list)

    @property
    def daily_total_eur(self) -> float:
        return round(sum(s.daily_budget_eur for s in self.ad_sets), 2)

    def to_json(self) -> dict[str, Any]:
        return {**asdict(self), "daily_total_eur": self.daily_total_eur}


def select_ads(candidates: list[AdChoice], persona: str, *, k: int = 4) -> list[AdChoice]:
    """Top-k guard-passing variants for a persona, best simulated score first, ≤ 2 per template."""
    pool = sorted((c for c in candidates if c.persona == persona and c.guards_passed),
                  key=lambda c: (-c.sim_score, c.variant_id))
    chosen: list[AdChoice] = []
    per_template: dict[str, int] = {}
    for c in pool:
        if per_template.get(c.template_id, 0) < MAX_PER_TEMPLATE and len(chosen) < k:
            chosen.append(c)
            per_template[c.template_id] = per_template.get(c.template_id, 0) + 1
    return chosen


def build_plan(app_name: str, store_url: str, audiences: list[Audience], candidates: list[AdChoice], *,
               daily_cap_eur: float, ads_per_adset: int = 4, name: str | None = None) -> CampaignPlan:
    """Ad sets for as many personas as the cap can fund at the minimum budget (best-supplied first)."""
    if daily_cap_eur < MIN_ADSET_DAILY_EUR:
        raise ValueError(f"daily cap €{daily_cap_eur:.2f} is below the €{MIN_ADSET_DAILY_EUR:.0f} minimum per ad set")
    notes = []
    funded = int(daily_cap_eur // MIN_ADSET_DAILY_EUR)
    usable = [(a, select_ads(candidates, a.persona, k=ads_per_adset)) for a in audiences]
    usable = [(a, ads) for a, ads in usable if len(ads) >= 2]
    skipped = [a.persona for a in audiences if a.persona not in {u[0].persona for u in usable}]
    if skipped:
        notes.append(f"personas without at least 2 publishable ads, no ad set: {skipped}")
    usable.sort(key=lambda u: -sum(c.sim_score for c in u[1]) / len(u[1]))
    if len(usable) > funded:
        notes.append(f"cap €{daily_cap_eur:.2f}/day funds {funded} ad set(s) at €{MIN_ADSET_DAILY_EUR:.0f} minimum; "
                     f"dropped: {[a.persona for a, _ in usable[funded:]]}")
        usable = usable[:funded]
    if not usable:
        raise ValueError("no persona has at least 2 publishable ads: nothing to launch")
    per_set = math.floor(daily_cap_eur / len(usable) * 100) / 100  # never round up past the cap
    ad_sets = [AdSetPlan(f"{a.name} · {'/'.join(a.countries)} · {a.age_min}-{a.age_max}", a, per_set, ads)
               for a, ads in usable]
    notes.append("budget split evenly: simulated scores rank ads but do not move money before real results")
    return CampaignPlan(name or f"whynot · {app_name}", app_name, store_url, daily_cap_eur, ad_sets, notes)


def validate(plan: CampaignPlan) -> list[str]:
    """Every rule the plan must satisfy before anything is sent to Meta. Empty list = valid."""
    errors = []
    if plan.daily_total_eur > plan.daily_cap_eur + 1e-9:
        errors.append(f"daily total €{plan.daily_total_eur} exceeds the cap €{plan.daily_cap_eur}")
    if not plan.store_url.startswith("https://apps.apple.com/"):
        errors.append("store_url must be an App Store link")
    if not plan.ad_sets:
        errors.append("no ad sets")
    seen_variants: set[str] = set()
    for s in plan.ad_sets:
        a = s.audience
        where = f"ad set {s.name!r}"
        if s.daily_budget_eur < MIN_ADSET_DAILY_EUR:
            errors.append(f"{where}: €{s.daily_budget_eur}/day below the €{MIN_ADSET_DAILY_EUR} minimum")
        if not (18 <= a.age_min <= a.age_max <= 65):
            errors.append(f"{where}: ages {a.age_min}-{a.age_max} outside 18-65")
        if not a.countries or not all(COUNTRY.match(c) for c in a.countries):
            errors.append(f"{where}: countries must be ISO codes, got {a.countries}")
        if a.gender not in GENDER_CODES:
            errors.append(f"{where}: gender {a.gender!r}")
        if not 2 <= len(s.ads) <= MAX_ADS_PER_ADSET:
            errors.append(f"{where}: {len(s.ads)} ads, need 2 to {MAX_ADS_PER_ADSET}")
        per_template: dict[str, int] = {}
        for ad in s.ads:
            if not ad.guards_passed:
                errors.append(f"{where}: ad {ad.variant_id} did not pass its guards")
            if ad.persona != a.persona:
                errors.append(f"{where}: ad {ad.variant_id} was made for persona {ad.persona!r}")
            if ad.variant_id in seen_variants:
                errors.append(f"ad {ad.variant_id} appears in two ad sets")
            seen_variants.add(ad.variant_id)
            per_template[ad.template_id] = per_template.get(ad.template_id, 0) + 1
            if not ad.body.strip() or not ad.title.strip():
                errors.append(f"{where}: ad {ad.variant_id} has empty text")
        crowded = [t for t, n in per_template.items() if n > MAX_PER_TEMPLATE]
        if crowded:
            errors.append(f"{where}: more than {MAX_PER_TEMPLATE} variants of {crowded}")
    return errors


def to_api(plan: CampaignPlan, *, api_version: str = "v26.0") -> dict[str, Any]:
    """Marketing API request bodies, in creation order, everything PAUSED. Placeholders in braces."""
    campaign = {"name": plan.name, "objective": "OUTCOME_APP_PROMOTION", "status": "PAUSED",
                "buying_type": "AUCTION", "special_ad_categories": []}
    ad_sets, creatives, ads = [], [], []
    for i, s in enumerate(plan.ad_sets):
        targeting: dict[str, Any] = {"geo_locations": {"countries": list(s.audience.countries)},
                                     "age_min": s.audience.age_min, "age_max": s.audience.age_max,
                                     "user_os": ["iOS"], "publisher_platforms": ["facebook", "instagram"]}
        if GENDER_CODES[s.audience.gender]:
            targeting["genders"] = GENDER_CODES[s.audience.gender]
        ad_sets.append({"ref": f"adset_{i}", "name": s.name, "campaign_id": "{campaign}", "status": "PAUSED",
                        "daily_budget": round(s.daily_budget_eur * 100), "billing_event": "IMPRESSIONS",
                        "optimization_goal": "APP_INSTALLS", "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                        "promoted_object": {"application_id": "{META_APP_ID}", "object_store_url": plan.store_url},
                        "targeting": targeting})
        for ad in s.ads:
            creatives.append({"ref": f"creative_{ad.variant_id}", "name": ad.variant_id,
                              "object_story_spec": {"page_id": "{PAGE_ID}", "link_data": {
                                  "image_hash": f"{{image:{ad.image_path}}}", "link": plan.store_url,
                                  "message": ad.body, "name": ad.title,
                                  "call_to_action": {"type": ad.cta, "value": {"link": plan.store_url}}}}})
            ads.append({"ref": f"ad_{ad.variant_id}", "name": ad.variant_id, "adset_id": f"{{adset_{i}}}",
                        "creative": {"creative_id": f"{{creative_{ad.variant_id}}}"}, "status": "PAUSED"})
    return {"api_version": api_version, "account": "act_{AD_ACCOUNT_ID}", "campaign": campaign,
            "ad_sets": ad_sets, "creatives": creatives, "ads": ads,
            "currency_note": "daily_budget is in the ad account's minor units (cents for EUR)"}


def launch_decisions(plan: CampaignPlan, policy: Policy, state: AccountState | None = None,
                     *, approved_by: str | None = None) -> list[tuple[str, Decision]]:
    """What the autopilot would do with each ad set's launch, under the owner's policy."""
    running = dict((state or AccountState()).daily_budgets_eur)
    out = []
    for s in plan.ad_sets:
        guards_ok = all(a.guards_passed for a in s.ads)
        d = decide(Action(Kind.PUBLISH, s.name, "launch", s.daily_budget_eur, guards_ok), policy,
                   AccountState(dict(running)), approved_by=approved_by)
        if d.outcome.value in ("execute", "simulated"):
            running[s.name] = s.daily_budget_eur
        out.append((s.name, d))
    return out
