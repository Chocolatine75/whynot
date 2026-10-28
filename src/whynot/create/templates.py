"""Ad templates: a concept plus a genome that evolution may mutate.

A template is one distinct concept ("Five minutes a day is enough") tied to a
persona and an objection, backed by evidence. Its `genes` list the options the
creative director may pick or mutate (hook, first shot, proof, CTA, format).
`fixed` holds what never changes (brand, real product/app-screen asset).

A variant is one point of the genome space; its id is derived from the genome,
so the same genome always gets the same id (dedup across generations).

Spec: docs/PRODUCT.md, "Template spec (concept + genome)".
"""

import hashlib
import itertools
import json
import random
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

KNOWN_GUARDS = {"product_pixels_unchanged", "brand_palette", "text_legible", "policy_safe"}
REQUIRED_GENES = {"format", "hook", "cta"}
_ID = re.compile(r"^[a-z0-9][a-z0-9_]*$")

Genome = dict[str, str]


class TemplateError(ValueError):
    pass


@dataclass(frozen=True)
class Template:
    id: str
    concept: str
    persona: str
    objection: str
    genes: dict[str, list[str]]
    fixed: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    copy: dict[str, dict[str, str]] = field(default_factory=dict)  # gene -> value -> text shown
    guards: list[str] = field(default_factory=list)

    # --- loading ------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Template":
        if not isinstance(data, dict):
            raise TemplateError(f"a template must be a mapping, got {type(data).__name__}")
        for key in ("id", "concept", "persona", "objection", "genes"):
            if not data.get(key):
                raise TemplateError(f"template is missing '{key}'")
        tid = str(data["id"])
        if not _ID.match(tid):
            raise TemplateError(f"bad template id {tid!r}: lowercase letters, digits, underscores")
        genes = data["genes"]
        if not isinstance(genes, dict):
            raise TemplateError(f"{tid}: 'genes' must be a mapping")
        clean: dict[str, list[str]] = {}
        for name, options in genes.items():
            if not isinstance(options, list) or not options:
                raise TemplateError(f"{tid}: gene '{name}' needs a non-empty list of options")
            opts = [str(o) for o in options]
            if any(not o.strip() for o in opts):
                raise TemplateError(f"{tid}: gene '{name}' has an empty option")
            if len(set(opts)) != len(opts):
                raise TemplateError(f"{tid}: gene '{name}' has duplicate options")
            clean[str(name)] = opts
        missing = REQUIRED_GENES - set(clean)
        if missing:
            raise TemplateError(f"{tid}: missing required genes {sorted(missing)}")
        guards = [str(g) for g in data.get("guards") or []]
        if len(set(guards)) != len(guards):
            raise TemplateError(f"{tid}: duplicate guards")
        unknown = set(guards) - KNOWN_GUARDS
        if unknown:
            raise TemplateError(f"{tid}: unknown guards {sorted(unknown)}")
        copy = data.get("copy") or {}
        if not isinstance(copy, dict):
            raise TemplateError(f"{tid}: 'copy' must be a mapping")
        for gene, texts in copy.items():
            if not isinstance(texts, dict):
                raise TemplateError(f"{tid}: copy for '{gene}' must map options to texts")
            if gene not in clean:
                raise TemplateError(f"{tid}: copy for unknown gene '{gene}'")
            extra = set(texts) - set(clean[gene])
            if extra:
                raise TemplateError(f"{tid}: copy for unknown {gene} options {sorted(extra)}")
        return cls(id=tid, concept=str(data["concept"]), persona=str(data["persona"]),
                   objection=str(data["objection"]), genes=clean, fixed=dict(data.get("fixed") or {}),
                   evidence=dict(data.get("evidence") or {}),
                   copy={g: {str(k): str(v) for k, v in t.items()} for g, t in copy.items()},
                   guards=guards)

    @classmethod
    def load(cls, path: str | Path) -> "Template":
        try:
            data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise TemplateError(f"{path}: invalid YAML: {exc}") from None
        return cls.from_dict(data)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "concept": self.concept, "persona": self.persona, "objection": self.objection,
                "evidence": self.evidence, "fixed": self.fixed, "genes": self.genes, "copy": self.copy,
                "guards": self.guards}

    # --- genome space -------------------------------------------------------

    def space_size(self) -> int:
        n = 1
        for options in self.genes.values():
            n *= len(options)
        return n

    def check(self, genome: Genome) -> None:
        if set(genome) != set(self.genes):
            raise TemplateError(f"{self.id}: genome genes {sorted(genome)} != template genes {sorted(self.genes)}")
        for gene, value in genome.items():
            if value not in self.genes[gene]:
                raise TemplateError(f"{self.id}: {value!r} is not an option of gene '{gene}'")

    def genomes(self) -> Iterator[Genome]:
        names = list(self.genes)
        for values in itertools.product(*(self.genes[n] for n in names)):
            yield dict(zip(names, values, strict=True))

    def sample(self, n: int, *, seed: int = 0) -> list[Genome]:
        """Up to n distinct genomes, reproducible for a given seed."""
        rng = random.Random(seed)
        total = self.space_size()
        if n >= total:
            return list(self.genomes())
        seen: set[str] = set()
        out: list[Genome] = []
        while len(out) < n:
            g = {name: rng.choice(opts) for name, opts in self.genes.items()}
            key = genome_key(g)
            if key not in seen:
                seen.add(key)
                out.append(g)
        return out

    def mutate(self, genome: Genome, gene: str, value: str | None = None, *, seed: int = 0) -> Genome:
        """Change one gene: to `value`, or to a different option picked at random."""
        self.check(genome)
        if gene not in self.genes:
            raise TemplateError(f"{self.id}: no gene '{gene}'")
        others = [o for o in self.genes[gene] if o != genome[gene]]
        if value is None:
            if not others:
                raise TemplateError(f"{self.id}: gene '{gene}' has a single option")
            value = random.Random(seed).choice(others)
        new = {**genome, gene: value}
        self.check(new)
        return new

    def text(self, gene: str, value: str) -> str:
        """Text shown for a gene value: from `copy`, else the value itself."""
        return self.copy.get(gene, {}).get(value, value)


def genome_key(genome: Genome) -> str:
    return json.dumps(genome, sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True)
class Variant:
    template_id: str
    genome: Genome
    generation: int = 0
    parent_id: str | None = None
    mutated_gene: str | None = None

    @property
    def id(self) -> str:
        digest = hashlib.sha1(genome_key(self.genome).encode()).hexdigest()[:8]
        return f"{self.template_id}-{digest}"


def load_dir(path: str | Path) -> list[Template]:
    """All templates in a directory (*.yaml); ids must be unique."""
    templates = [Template.load(p) for p in sorted(Path(path).glob("*.yaml"))]
    ids = [t.id for t in templates]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise TemplateError(f"duplicate template ids: {sorted(dupes)}")
    return templates
