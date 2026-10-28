"""Strategist (Muse Wonder): personas, objections, angles and allowed claims, with evidence.

Input: the app's store page, its reviews, the market's competitor ads, target
countries. Output: a `Strategy` the creative director must follow.

Anti-hallucination, enforced by code (not by the prompt):
- every objection and angle cites evidence: `review:<id>`, `ad:<id>` or `store`,
  each with a verbatim quote that must appear in that source;
- every claim an ad may make (`claims`) is a fact quoted from the store page or
  a review — ads can only state facts the business already states or customers
  confirm (a real client's ad must not invent features, prices or results);
- personas only target the requested countries, adults 18–65.
Invalid answers are sent back to the model with the exact errors (`ask_json`).
"""

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from whynot.agents.ask import Answer, ChatClient, Invalid, ask_json
from whynot.ingest.adlibrary import CompetitorAd
from whynot.ingest.appstore import AppProfile, Review
from whynot.models import WONDER

_SLUG = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
GENDERS = {"all", "female", "male"}
AGE_MIN, AGE_MAX = 18, 65


@dataclass(frozen=True)
class Evidence:
    ref: str  # "store", "review:<id>" or "ad:<id>"
    quote: str


@dataclass(frozen=True)
class Persona:
    id: str
    name: str
    description: str
    age_min: int
    age_max: int
    gender: str  # all | female | male
    countries: tuple[str, ...]
    motivations: tuple[str, ...]
    objections: tuple[str, ...]  # objection ids


@dataclass(frozen=True)
class Objection:
    id: str
    text: str  # in the customer's words
    answer: str  # how an ad can answer it truthfully
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class Angle:
    id: str
    idea: str
    persona: str
    objection: str | None
    competitors_use_it: bool
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class Claim:
    id: str
    text: str  # what an ad may say
    evidence: Evidence  # must be "store" or "review:<id>"


@dataclass
class Strategy:
    positioning: str
    personas: list[Persona]
    objections: list[Objection]
    angles: list[Angle]
    claims: list[Claim]
    notes: list[str] = field(default_factory=list)

    def persona(self, pid: str) -> Persona:
        return next(p for p in self.personas if p.id == pid)

    def objection(self, oid: str) -> Objection:
        return next(o for o in self.objections if o.id == oid)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Strategy":
        def ev(e): return Evidence(**e)
        return cls(
            positioning=d["positioning"],
            personas=[Persona(**{**p, "countries": tuple(p["countries"]), "motivations": tuple(p["motivations"]),
                                 "objections": tuple(p["objections"])}) for p in d["personas"]],
            objections=[Objection(**{**o, "evidence": tuple(ev(e) for e in o["evidence"])}) for o in d["objections"]],
            angles=[Angle(**{**a, "evidence": tuple(ev(e) for e in a["evidence"])}) for a in d["angles"]],
            claims=[Claim(**{**c, "evidence": ev(c["evidence"])}) for c in d["claims"]],
            notes=list(d.get("notes", [])),
        )


def normalise(text: str) -> str:
    """Lowercase, unify quotes/dashes, collapse whitespace: for verbatim-quote checks."""
    t = text.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = t.replace("–", "-").replace("—", "-")
    return " ".join(t.split())


@dataclass
class Sources:
    """Everything the strategy may cite, by reference."""
    store: str
    reviews: dict[str, Review]
    ads: dict[str, CompetitorAd]

    @classmethod
    def build(cls, app: AppProfile, ads: list[CompetitorAd]) -> "Sources":
        return cls(app.description, {r.id: r for r in app.reviews}, {a.id: a for a in ads})

    def text(self, ref: str) -> str | None:
        if ref == "store":
            return self.store
        kind, _, rid = ref.partition(":")
        if kind == "review" and rid in self.reviews:
            r = self.reviews[rid]
            return f"{r.title}\n{r.text}"
        if kind == "ad" and rid in self.ads:
            a = self.ads[rid]
            return "\n".join([*a.bodies, *a.titles])
        return None


# --- validation ----------------------------------------------------------------------

def _str(d: dict, key: str, where: str, *, max_len: int = 400) -> str:
    v = d.get(key)
    if not isinstance(v, str) or not v.strip():
        raise Invalid(f"{where}: '{key}' must be a non-empty string")
    if len(v) > max_len:
        raise Invalid(f"{where}: '{key}' is longer than {max_len} characters")
    return v.strip()


def _slug(d: dict, where: str, seen: set[str]) -> str:
    sid = d.get("id")
    if not isinstance(sid, str) or not _SLUG.match(sid):
        raise Invalid(f"{where}: id {sid!r} must be snake_case (a-z, 0-9, _), 2–41 chars")
    if sid in seen:
        raise Invalid(f"{where}: duplicate id {sid!r}")
    seen.add(sid)
    return sid


def _list(d: dict, key: str, where: str, lo: int, hi: int) -> list:
    v = d.get(key)
    if not isinstance(v, list) or not lo <= len(v) <= hi:
        raise Invalid(f"{where}: '{key}' must be a list of {lo} to {hi} items")
    return v


def _evidence(raw: Any, sources: Sources, where: str, *, allowed: tuple[str, ...]) -> Evidence:
    if not isinstance(raw, dict):
        raise Invalid(f"{where}: evidence must be {{\"ref\": ..., \"quote\": ...}}")
    ref = str(raw.get("ref", "")).strip()
    quote = str(raw.get("quote", "")).strip().strip('"').strip()
    kind_ok = (ref == "store" and "store" in allowed) or any(
        ref.startswith(prefix) for prefix in allowed if prefix.endswith(":"))
    if not kind_ok:
        raise Invalid(f"{where}: ref {ref!r} must be one of {allowed}")
    text = sources.text(ref)
    if text is None:
        raise Invalid(f"{where}: {ref!r} does not exist; cite only ids given in the input")
    if len(quote) < 8:
        raise Invalid(f"{where}: quote from {ref} is too short (≥ 8 characters, verbatim)")
    if normalise(quote) not in normalise(text):
        raise Invalid(f"{where}: quote {quote[:80]!r} is not verbatim in {ref}; copy the exact words")
    return Evidence(ref, quote)


def make_validator(sources: Sources, countries: list[str]):
    targets = {c.upper() for c in countries}

    def validate(data: Any) -> Strategy:
        if not isinstance(data, dict):
            raise Invalid("expected a JSON object")
        positioning = _str(data, "positioning", "strategy", max_len=300)

        obj_ids: set[str] = set()
        objections = []
        for i, o in enumerate(_list(data, "objections", "strategy", 3, 8)):
            w = f"objections[{i}]"
            if not isinstance(o, dict):
                raise Invalid(f"{w}: must be an object")
            oid = _slug(o, w, obj_ids)
            evs = tuple(_evidence(e, sources, f"{w}.evidence[{j}]", allowed=("review:", "ad:", "store"))
                        for j, e in enumerate(_list(o, "evidence", w, 1, 5)))
            objections.append(Objection(oid, _str(o, "text", w), _str(o, "answer", w), evs))

        persona_ids: set[str] = set()
        personas = []
        for i, p in enumerate(_list(data, "personas", "strategy", 2, 4)):
            w = f"personas[{i}]"
            if not isinstance(p, dict):
                raise Invalid(f"{w}: must be an object")
            pid = _slug(p, w, persona_ids)
            lo, hi = p.get("age_min"), p.get("age_max")
            if not (isinstance(lo, int) and isinstance(hi, int) and AGE_MIN <= lo <= hi <= AGE_MAX):
                raise Invalid(f"{w}: ages must be integers with {AGE_MIN} ≤ age_min ≤ age_max ≤ {AGE_MAX}")
            gender = p.get("gender")
            if gender not in GENDERS:
                raise Invalid(f"{w}: gender must be one of {sorted(GENDERS)}")
            cs = [str(c).upper() for c in _list(p, "countries", w, 1, len(targets))]
            if not set(cs) <= targets:
                raise Invalid(f"{w}: countries {sorted(set(cs) - targets)} are not targeted; use {sorted(targets)}")
            objs = [str(x) for x in _list(p, "objections", w, 1, 4)]
            unknown = [x for x in objs if x not in obj_ids]
            if unknown:
                raise Invalid(f"{w}: unknown objection ids {unknown}")
            motivations = tuple(str(m).strip() for m in _list(p, "motivations", w, 1, 4) if str(m).strip())
            personas.append(Persona(pid, _str(p, "name", w, max_len=60), _str(p, "description", w), lo, hi, gender,
                                    tuple(dict.fromkeys(cs)), motivations, tuple(dict.fromkeys(objs))))

        angle_ids: set[str] = set()
        angles = []
        for i, a in enumerate(_list(data, "angles", "strategy", 4, 10)):
            w = f"angles[{i}]"
            if not isinstance(a, dict):
                raise Invalid(f"{w}: must be an object")
            aid = _slug(a, w, angle_ids)
            persona = a.get("persona")
            if persona not in persona_ids:
                raise Invalid(f"{w}: persona {persona!r} is not one of {sorted(persona_ids)}")
            objection = a.get("objection")
            if objection is not None and objection not in obj_ids:
                raise Invalid(f"{w}: objection {objection!r} is not one of {sorted(obj_ids)} (or null)")
            used = a.get("competitors_use_it")
            if not isinstance(used, bool):
                raise Invalid(f"{w}: 'competitors_use_it' must be true or false")
            evs = tuple(_evidence(e, sources, f"{w}.evidence[{j}]", allowed=("review:", "ad:", "store"))
                        for j, e in enumerate(_list(a, "evidence", w, 1, 5)))
            angles.append(Angle(aid, _str(a, "idea", w), persona, objection, used, evs))
        uncovered = persona_ids - {a.persona for a in angles}
        if uncovered:
            raise Invalid(f"every persona needs at least one angle; none for {sorted(uncovered)}")

        claim_ids: set[str] = set()
        claims = []
        for i, c in enumerate(_list(data, "claims", "strategy", 3, 15)):
            w = f"claims[{i}]"
            if not isinstance(c, dict):
                raise Invalid(f"{w}: must be an object")
            cid = _slug(c, w, claim_ids)
            claims.append(Claim(cid, _str(c, "text", w, max_len=160),
                                _evidence(c.get("evidence"), sources, f"{w}.evidence", allowed=("review:", "store"))))

        notes = [str(n)[:300] for n in data.get("notes", []) if isinstance(n, str)][:8]
        return Strategy(positioning, personas, objections, angles, claims, notes)

    return validate


# --- prompt ----------------------------------------------------------------------------

SCHEMA = """{
 "positioning": "one sentence: for whom, what, why it beats the alternatives",
 "objections": [{"id": "snake_case", "text": "the hesitation in the customer's words", "answer": "how an ad can answer it truthfully",
                 "evidence": [{"ref": "review:<id> | ad:<id> | store", "quote": "exact words copied from that source"}]}],
 "personas": [{"id": "snake_case", "name": "short label", "description": "who they are, what they want",
               "age_min": 18, "age_max": 34, "gender": "all | female | male", "countries": ["FR"],
               "motivations": ["..."], "objections": ["objection ids"]}],
 "angles": [{"id": "snake_case", "idea": "the ad concept in one sentence", "persona": "persona id",
             "objection": "objection id or null", "competitors_use_it": false,
             "evidence": [{"ref": "...", "quote": "..."}]}],
 "claims": [{"id": "snake_case", "text": "a fact an ad may state", "evidence": {"ref": "store | review:<id>", "quote": "..."}}],
 "notes": ["risks, gaps, what we could not verify"]
}"""


def build_prompt(app: AppProfile, ads: list[CompetitorAd], countries: list[str], *,
                 max_reviews: int = 150, max_ads: int = 150) -> str:
    reviews = sorted(app.reviews, key=lambda r: (r.rating, r.id))[:max_reviews]  # negatives first: objections
    review_lines = "\n".join(f"[review:{r.id}] {r.rating}★ {r.title} — {' '.join(r.text.split())[:500]}"
                             for r in reviews) or "(no reviews yet)"
    ad_lines = "\n".join(f"[ad:{a.id}] {a.page_name} (running since {a.start_date}"
                         f"{', stopped ' + str(a.stop_date) if a.stop_date else ', still active'}): "
                         f"{' '.join((a.bodies or [''])[0].split())[:400]}" for a in ads[:max_ads]) or "(none found)"
    return f"""You are the strategist of an ad agency. Build the Meta (Facebook/Instagram) ad strategy for this app.

# The app (store page = "store")
{app.name} by {app.seller}. Category: {', '.join(app.genres)}. {'Free' if app.free else f'{app.price} {app.currency}'}.
Rating: {app.rating or 'n/a'} ({app.rating_count} ratings).
{app.description}

# Customer reviews (cite as review:<id>)
{review_lines}

# Competitors' ads in the market (cite as ad:<id>; long-running ads are usually the ones that pay)
{ad_lines}

# Campaign countries: {', '.join(countries)}

# What to produce
- 3–8 objections: why people who see this kind of ad would NOT install or pay. Use reviews and competitors' ads.
- 2–4 personas: distinct customer profiles worth a separate ad set, with the objections they have.
- 4–10 angles: distinct ad concepts (not variations), each for one persona, ideally answering one objection.
  Prefer angles that work for competitors (long-running ads) and angles nobody uses yet; say which.
- 3–15 claims: the only facts ads may state (features, price model, results) — each quoted from the store page or a review.
Rules: every quote must be copied EXACTLY from the cited source. Cite only refs that appear above.
Never invent features, prices, numbers or testimonials. Ages 18–65. Countries only from the campaign countries.

Reply with JSON only, this schema:
{SCHEMA}"""


def plan_strategy(client: ChatClient, app: AppProfile, ads: list[CompetitorAd], countries: list[str], *,
                  model: str = WONDER, repairs: int = 2) -> Answer[Strategy]:
    sources = Sources.build(app, ads)
    return ask_json(client, [{"role": "user", "content": build_prompt(app, ads, countries)}],
                    make_validator(sources, countries), module="strategy", model=model, repairs=repairs,
                    max_tokens=24000)
