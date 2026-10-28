"""Viewer personas built from real Meta reach data.

The Ad Library tells us who Meta actually showed a market's ads to, split by
country, age range and gender. We allocate N personas to those cells in
proportion to reach (largest-remainder rounding, deterministic), so the
simulated audience looks like the real one.

Traits (objections, segments from the strategy) are optional and added later;
v0 personas are demographic only.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from whynot.ingest.adlibrary import CompetitorAd

GENDER_WORDS = {"male": "man", "female": "woman", "unknown": "person"}


@dataclass(frozen=True)
class Persona:
    id: str
    country: str
    age_range: str
    gender: str
    traits: tuple[str, ...] = field(default=())

    def describe(self) -> str:
        who = f"a {GENDER_WORDS.get(self.gender, 'person')} aged {self.age_range} living in {self.country}"
        if self.traits:
            who += "; " + "; ".join(self.traits)
        return who


def reach_cells(ads: Iterable[CompetitorAd]) -> dict[tuple[str, str, str], int]:
    """Total reach per (country, age_range, gender) across ads."""
    cells: dict[tuple[str, str, str], int] = {}
    for ad in ads:
        for s in ad.reach_breakdown:
            key = (s.country, s.age_range, s.gender)
            cells[key] = cells.get(key, 0) + s.reach
    return cells


def allocate(weights: dict, n: int) -> dict:
    """Split n into integer counts proportional to weights (largest remainder)."""
    total = sum(weights.values())
    if n <= 0 or total <= 0:
        return {}
    exact = {k: n * w / total for k, w in weights.items()}
    counts = {k: int(v) for k, v in exact.items()}
    leftover = n - sum(counts.values())
    # ties broken by key so the result is deterministic
    for k in sorted(exact, key=lambda k: (-(exact[k] - counts[k]), str(k)))[:leftover]:
        counts[k] += 1
    return {k: c for k, c in counts.items() if c > 0}


def personas_from_reach(ads: Iterable[CompetitorAd], n: int, *,
                        include_unknown_gender: bool = False) -> list[Persona]:
    cells = reach_cells(ads)
    if not include_unknown_gender:
        cells = {k: v for k, v in cells.items() if k[2] != "unknown"}
    if not cells:
        raise ValueError("no reach breakdown in these ads: cannot build personas")
    personas: list[Persona] = []
    for (country, age, gender), count in sorted(allocate(cells, n).items()):
        for i in range(count):
            personas.append(Persona(f"{country}-{age}-{gender}-{i}", country, age, gender))
    return personas
