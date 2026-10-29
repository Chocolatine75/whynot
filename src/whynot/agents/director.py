"""Creative director: one ad template (concept + genome + copy) per strategy angle.

The model writes the words; code turns them into `Template`s and checks, before
anything is produced:
- structure: one template per requested angle, persona/objection from the angle;
- truthfulness: every number in the copy appears in a verified claim or on the
  store page; claims used must exist; no competitor brand names;
- Meta policy rules (`create/policy.py`) on every text;
- format: lengths that fit Meta placements, characters the font can draw;
- diversity: concepts must be different ideas, not rewordings.
Invalid answers go back to the model with the exact errors (`ask_json`).
"""

import re
from dataclasses import dataclass
from typing import Any

from whynot.agents.ask import Answer, ChatClient, Invalid, ask_json
from whynot.agents.strategist import Strategy, normalise
from whynot.create import fonts, policy
from whynot.create.composer import missing_glyphs
from whynot.create.templates import KNOWN_GUARDS, Template, TemplateError
from whynot.models import SPARK

# Meta call-to-action types that fit an app-install ad.
META_CTAS = {"INSTALL_MOBILE_APP", "DOWNLOAD", "USE_APP", "LEARN_MORE", "SIGN_UP", "SUBSCRIBE"}
LIMITS = {"hook": 70, "body": 280, "title": 40, "proof": 50, "cta": 20}  # characters
COUNTS = {"hook": (2, 3), "body": (2, 2), "title": (1, 2), "proof": (1, 2), "cta": (1, 2)}
DRAWN = ("hook", "proof", "cta")  # texts rendered on the image
# Languages whose normal prose always has accented letters: copy without any is mangled (seen on a real run:
# "Retarde, mais pourquoi" for "Retardé"). German is left out: short German copy can lack umlauts.
ACCENTED_LANGUAGES = {"French", "Spanish", "Portuguese", "Polish", "Czech", "Romanian", "Hungarian", "Swedish",
                      "Danish", "Finnish"}
MIN_LETTERS_FOR_ACCENT_CHECK = 150
_KEY = re.compile(r"^[a-z][a-z0-9_]{0,30}$")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_WORD = re.compile(r"[a-zà-ÿ]{4,}")


@dataclass(frozen=True)
class Context:
    strategy: Strategy
    app_name: str
    store_text: str
    competitor_names: tuple[str, ...]
    palette: tuple[str, str, str]
    product_asset: str  # screenshot used as the product image
    language: str = "English"


def _allowed_numbers(ctx: Context) -> set[str]:
    sources = [c.text for c in ctx.strategy.claims] + [ctx.store_text]
    return {n.replace(",", ".") for s in sources for n in _NUMBER.findall(s)}


def _words(text: str) -> set[str]:
    return set(_WORD.findall(normalise(text)))


def _jaccard(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def _texts(raw: Any, gene: str, where: str) -> dict[str, str]:
    lo, hi = COUNTS[gene]
    if not isinstance(raw, dict) or not lo <= len(raw) <= hi:
        raise Invalid(f"{where}: '{gene}s' must be an object with {lo} to {hi} entries {{key: text}}")
    out = {}
    for key, text in raw.items():
        if gene == "cta":
            if key not in META_CTAS:
                raise Invalid(f"{where}: cta key {key!r} must be one of {sorted(META_CTAS)}")
        elif not _KEY.match(str(key)):
            raise Invalid(f"{where}: key {key!r} must be snake_case")
        if not isinstance(text, str):
            raise Invalid(f"{where}: text for {gene} {key!r} must be a string")
        text = " ".join(text.split())
        if gene == "proof" and key == "none":
            text = ""
        elif not text:
            raise Invalid(f"{where}: empty {gene} text for {key!r}")
        if len(text) > LIMITS[gene]:
            raise Invalid(f"{where}: {gene} {key!r} has {len(text)} characters, max {LIMITS[gene]}")
        out[str(key)] = text
    return out


def make_validator(ctx: Context, angle_ids: list[str]):
    angles = {a.id: a for a in ctx.strategy.angles}
    claims = {c.id for c in ctx.strategy.claims}
    allowed_numbers = _allowed_numbers(ctx)
    font = fonts.load(40)  # the font the composer will draw with
    competitors = [n for n in ctx.competitor_names if len(n) >= 4]

    def validate(data: Any) -> list[Template]:
        rows = data.get("templates") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise Invalid("expected {\"templates\": [...]}")
        by_angle: dict[str, Template] = {}
        problems: list[str] = []
        for i, t in enumerate(rows):
            w = f"templates[{i}]"
            try:
                if not isinstance(t, dict):
                    raise Invalid(f"{w}: must be an object")
                angle = angles.get(str(t.get("angle")))
                if angle is None or angle.id not in angle_ids:
                    raise Invalid(f"{w}: angle {t.get('angle')!r} is not one of {angle_ids}")
                if angle.id in by_angle:
                    raise Invalid(f"{w}: second template for angle {angle.id!r}")
                genes_text = {g: _texts(t.get(f"{g}s"), g, w) for g in LIMITS}
                used = t.get("claims_used", [])
                if not isinstance(used, list) or any(c not in claims for c in used):
                    raise Invalid(f"{w}: claims_used must list claim ids from {sorted(claims)}")
                all_text = {f"{g}.{k}": v for g, texts in genes_text.items() for k, v in texts.items()}
                for field_name, text in all_text.items():
                    for n in _NUMBER.findall(text):
                        if n.replace(",", ".") not in allowed_numbers:
                            raise Invalid(f"{w}: {field_name} says {n!r}, a number not in any verified claim")
                    low = normalise(text)
                    for name in competitors:
                        if re.search(rf"\b{re.escape(normalise(name))}\b", low):
                            raise Invalid(f"{w}: {field_name} names a competitor ({name!r})")
                    if field_name.split(".")[0] in DRAWN:
                        bad = missing_glyphs(font, text)
                        if bad:
                            raise Invalid(f"{w}: {field_name} has characters the ad font cannot draw {bad}; no emoji")
                if ctx.language in ACCENTED_LANGUAGES:
                    letters = "".join(ch for text in all_text.values() for ch in text if ch.isalpha())
                    if len(letters) >= MIN_LETTERS_FOR_ACCENT_CHECK and letters.isascii():
                        raise Invalid(f"{w}: the {ctx.language} copy has no accented letter at all; "
                                      f"write correct {ctx.language} with its accents (é, è, à, ç...)")
                errs = policy.errors(policy.check_ad(all_text))
                if errs:
                    raise Invalid(f"{w}: policy: " + "; ".join(f"{e.field}: {e.message}" for e in errs))
                concept = t.get("concept")
                if not isinstance(concept, str) or not 10 <= len(concept.strip()) <= 160:
                    raise Invalid(f"{w}: 'concept' must be one sentence (10–160 characters)")
                shots = t.get("first_shots", ["app_screen"])
                if isinstance(shots, str):  # a single value is a common, harmless slip
                    shots = [shots]
                if not isinstance(shots, list) or not shots or not set(shots) <= {"app_screen", "result_card"}:
                    raise Invalid(f"{w}: first_shots must be a non-empty subset of ['app_screen', 'result_card']")
                proofs = genes_text["proof"]
                template = Template.from_dict({
                    "id": f"{angle.id}_v1", "concept": concept.strip(), "persona": angle.persona,
                    "objection": angle.objection or "none",
                    "evidence": {"angle": angle.id, "refs": [e.ref for e in angle.evidence], "claims": used},
                    "fixed": {"brand": {"name": ctx.app_name, "palette": list(ctx.palette)},
                              "product": {"source": "app_store_screenshot", "asset": ctx.product_asset}},
                    "genes": {"format": ["static_1080"], "hook": list(genes_text["hook"]),
                              "first_shot": list(dict.fromkeys(shots)), "proof": list(proofs),
                              "body": list(genes_text["body"]), "title": list(genes_text["title"]),
                              "cta": list(genes_text["cta"])},
                    "copy": {g: texts for g, texts in genes_text.items()},
                    "guards": sorted(KNOWN_GUARDS),
                })
                by_angle[angle.id] = template
            except (Invalid, TemplateError) as exc:
                problems.append(str(exc))
        missing = [a for a in angle_ids if a not in by_angle]
        if missing and not problems:
            problems.append(f"no template for angles {missing}")
        templates = list(by_angle.values())
        for i, a in enumerate(templates):
            for b in templates[i + 1:]:
                if _jaccard(a.concept, b.concept) >= 0.6:
                    problems.append(f"{a.id} and {b.id} are the same concept reworded; make them different ideas")
        if problems:
            raise Invalid(" | ".join(problems[:8]))
        return [by_angle[a] for a in angle_ids]

    return validate


SCHEMA = """{"templates": [{
  "angle": "angle id",
  "concept": "the idea in one sentence",
  "hooks": {"question": "headline on the image (≤70 chars)", "bold_claim": "...", "...": "2–3 distinct hooks"},
  "bodys": {"short": "primary text above the ad (≤280 chars)", "story": "..."},
  "titles": {"main": "link headline under the image (≤40 chars)"},
  "proofs": {"rating": "small proof line on the image (≤50 chars), from a claim", "none": ""},
  "ctas": {"INSTALL_MOBILE_APP": "button label on the image (≤20 chars)"},
  "first_shots": ["app_screen", "result_card"],
  "claims_used": ["claim ids"]
}]}"""


def build_prompt(ctx: Context, angle_ids: list[str]) -> str:
    s = ctx.strategy
    angles = [a for a in s.angles if a.id in angle_ids]
    persona_lines = "\n".join(f"- {p.id}: {p.name}, {p.age_min}–{p.age_max}, {p.gender}, {'/'.join(p.countries)}. "
                              f"{p.description} Wants: {'; '.join(p.motivations)}." for p in s.personas)
    objection_lines = "\n".join(f"- {o.id}: \"{o.text}\" → answer: {o.answer}" for o in s.objections)
    angle_lines = "\n".join(f"- {a.id} (persona {a.persona}, objection {a.objection or 'none'}"
                            f"{', used by competitors' if a.competitors_use_it else ', not used by competitors'}): {a.idea}"
                            for a in angles)
    claim_lines = "\n".join(f"- {c.id}: {c.text}" for c in s.claims)
    return f"""You are the creative director of an ad agency writing Meta (Facebook/Instagram) app-install ads for {ctx.app_name}.
Positioning: {s.positioning}

Personas:
{persona_lines}

Objections:
{objection_lines}

Verified claims (the ONLY facts an ad may state; numbers only from here):
{claim_lines}

Write one template per angle below. A template is a distinct concept with options the agency will combine and test:
2–3 hooks (the big line on the image), 2 primary texts, 1–2 link headlines, 1–2 proof lines (one may be "none": ""),
1–2 call-to-action labels keyed by Meta CTA type ({', '.join(sorted(META_CTAS))}).
Angles:
{angle_lines}

Rules:
- Language: {ctx.language}. Plain, specific, human. Speak to the persona's situation and answer the objection.
- Only facts from the verified claims. No invented numbers, prices, ratings, awards or testimonials.
- Never name competitors. Write correct {ctx.language}: full accents and normal punctuation (commas, apostrophes,
  question marks) are expected. Only emoji and pictograms (★, ✓, →, flags) are not allowed on the image texts.
- Meta policy: never assert or imply the viewer's personal traits (health, finances, religion, ethnicity...),
  no "guaranteed", "#1", "100%", no engagement bait, no ALL CAPS.
- Each concept must be a different idea, not a rewording of another.

Reply with JSON only, this schema (note the key "bodys"):
{SCHEMA}"""


def write_templates(client: ChatClient, ctx: Context, angle_ids: list[str], *, model: str = SPARK,
                    repairs: int = 2) -> Answer[list[Template]]:
    if not angle_ids:
        raise ValueError("no angles to write")
    return ask_json(client, [{"role": "user", "content": build_prompt(ctx, angle_ids)}],
                    make_validator(ctx, angle_ids), module="director", model=model, repairs=repairs,
                    max_tokens=16000, reasoning_effort="low")
