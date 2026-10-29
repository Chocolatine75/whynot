"""Evolver: improve an ad by changing one element to answer what viewers objected to.

Input: a parent variant (its texts, its simulated score, the viewers' "why not"
in their own words). Output: mutations, each replacing ONE gene's text (hook,
body, title or proof) — the change is small enough that a score difference can
be attributed to it. Code checks every mutation with the same `CopyRules` as
the creative director (verified numbers only, no competitor names, Meta policy,
drawable characters, accents) and refuses texts identical to an existing option.

`apply` adds the new text as a new option of the template's gene and returns
the child genome: the template's genome space grows with evolution, and every
child stays reproducible from its template file.
"""

import re
from dataclasses import dataclass
from typing import Any

from whynot.agents.ask import Answer, ChatClient, Invalid, ask_json
from whynot.agents.director import Context, CopyRules
from whynot.agents.strategist import normalise
from whynot.create.templates import Genome, Template
from whynot.models import SPARK

MUTABLE = ("hook", "body", "title", "proof")


@dataclass(frozen=True)
class Parent:
    variant_id: str
    template: Template
    genome: Genome
    lift_over_placebo: float
    intent: float
    why_not: tuple[str, ...]  # simulated viewers' objections, most frequent first

    def text(self, gene: str) -> str:
        return self.template.text(gene, self.genome[gene]) if gene in self.genome else ""


@dataclass(frozen=True)
class Mutation:
    gene: str
    text: str
    why: str  # which objection it answers, and how


def make_validator(ctx: Context, parent: Parent, n: int):
    rules = CopyRules(ctx)

    def validate(data: Any) -> list[Mutation]:
        rows = data.get("mutations") if isinstance(data, dict) else None
        if not isinstance(rows, list) or not 1 <= len(rows) <= n:
            raise Invalid(f"expected {{\"mutations\": [...]}} with 1 to {n} items")
        out: list[Mutation] = []
        for i, m in enumerate(rows):
            w = f"mutations[{i}]"
            if not isinstance(m, dict):
                raise Invalid(f"{w}: must be an object")
            gene = m.get("gene")
            if gene not in MUTABLE or gene not in parent.template.genes:
                raise Invalid(f"{w}: gene must be one of {[g for g in MUTABLE if g in parent.template.genes]}")
            text = " ".join(str(m.get("text", "")).split())
            if not text:
                raise Invalid(f"{w}: empty text")
            existing = {normalise(parent.template.text(gene, k)) for k in parent.template.genes[gene]}
            if normalise(text) in existing or any(normalise(text) == normalise(o.text) for o in out):
                raise Invalid(f"{w}: this {gene} already exists; write a different one")
            rules.check({f"{gene}.new": text}, w)
            why = str(m.get("why", "")).strip()
            if not why:
                raise Invalid(f"{w}: say which objection it answers in 'why'")
            out.append(Mutation(gene, text, why[:200]))
        return out

    return validate


def build_prompt(ctx: Context, parent: Parent, n: int) -> str:
    s = ctx.strategy
    persona = s.persona(parent.template.persona)
    claims = "\n".join(f"- {c.text}" for c in s.claims)
    objections = "\n".join(f"- “{w}”" for w in parent.why_not[:5]) or "- (no objection given; viewers just preferred other ads)"
    return f"""You are improving a Meta app-install ad for {ctx.app_name}. In a simulated feed next to real competitor ads,
viewers who match the target ({persona.name}: {persona.description}) did not pick it often enough.

The ad now:
- hook (big text on the image): {parent.text('hook')}
- primary text: {parent.text('body')}
- link headline: {parent.text('title')}
- proof line on the image: {parent.text('proof') or '(none)'}
Concept: {parent.template.concept}

What simulated viewers said stopped them (SIMULATED, their words):
{objections}

Verified claims (the ONLY facts an ad may state; numbers only from here):
{claims}

Propose {n} different mutations. Each changes exactly ONE element (hook, body, title or proof) to answer the most
important objection above, keeping the concept. Change the element that matters most for that objection.
Rules: language {ctx.language} with correct accents and punctuation; only verified facts; never name competitors;
no emoji or pictograms; Meta policy (no personal attributes, no "guaranteed"/"#1"/"100%", no engagement bait,
no ALL CAPS); limits: hook ≤70, body ≤280, title ≤40, proof ≤50 characters.

Reply with JSON only:
{{"mutations": [{{"gene": "hook | body | title | proof", "text": "the new text", "why": "the objection it answers and how"}}]}}"""


def propose(client: ChatClient, ctx: Context, parent: Parent, *, n: int = 2, model: str = SPARK,
            repairs: int = 2) -> Answer[list[Mutation]]:
    return ask_json(client, [{"role": "user", "content": build_prompt(ctx, parent, n)}],
                    make_validator(ctx, parent, n), module="evolver", model=model, repairs=repairs,
                    max_tokens=8000, reasoning_effort="low")


def apply(template: Template, genome: Genome, mutation: Mutation, *, tag: str) -> tuple[Template, Genome]:
    """The template with the new text as an extra option of the gene, and the child genome using it."""
    key = re.sub(r"[^a-z0-9_]", "_", f"{mutation.gene}_{tag}".lower())
    d = template.to_dict()
    if key in d["genes"][mutation.gene]:
        raise ValueError(f"option {key!r} already exists in {template.id}.{mutation.gene}")
    d["genes"][mutation.gene] = [*d["genes"][mutation.gene], key]
    d["copy"].setdefault(mutation.gene, {})[key] = mutation.text
    child = Template.from_dict(d)
    new_genome = {**genome, mutation.gene: key}
    child.check(new_genome)
    return child, new_genome

