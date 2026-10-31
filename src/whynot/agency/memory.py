"""The agency's memory of one client: every ad it made, the idea behind it, and how it did.

Each ad is recorded with its idea (format, persona, angle, hook), its files, its Meta id once published,
its status (proposed → live → paused, or rejected by the owner) and its results day by day. This is what
lets the daily loop learn what works for THIS client and never make the same ad twice.

One JSON file per client (`<run>/agency/memory.json`), written atomically. No token, no personal data:
ideas, file names, ids and numbers only.
"""

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from whynot.run.autopilot import DailyMetrics

STATUSES = ("proposed", "live", "paused", "rejected", "failed")  # failed: the idea never became an ad


@dataclass
class AdRecord:
    key: str  # our id (the video file stem)
    day: str  # ISO date it was made
    format: str
    persona: str
    angle: str
    hook: str
    voice: str = ""
    file: str = ""
    why: str = ""  # explore / exploit and the reason
    status: str = "proposed"
    meta_ad_id: str | None = None
    launched: str | None = None  # ISO date it went live
    metrics: list[DailyMetrics] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # decisions about it, in order

    @property
    def spend(self) -> float:
        return round(sum(m.spend_eur for m in self.metrics), 2)

    @property
    def conversions(self) -> int:
        return sum(m.conversions for m in self.metrics)

    @property
    def cpa(self) -> float | None:
        return self.spend / self.conversions if self.conversions else None

    @property
    def ctr(self) -> float | None:
        imp = sum(m.impressions for m in self.metrics)
        return sum(m.clicks for m in self.metrics) / imp if imp else None

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "AdRecord":
        return cls(**{**d, "metrics": [DailyMetrics(**m) for m in d.get("metrics", [])]})


class Memory:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.ads: dict[str, AdRecord] = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.ads = {k: AdRecord.from_json(v) for k, v in data.get("ads", {}).items()}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".memory-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"ads": {k: asdict(v) for k, v in self.ads.items()}}, f, indent=1, ensure_ascii=False)
        os.replace(tmp, self.path)

    def add(self, rec: AdRecord) -> None:
        if rec.key in self.ads:
            raise ValueError(f"ad {rec.key!r} is already in memory")
        if rec.status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        self.ads[rec.key] = rec

    def set_status(self, key: str, status: str, note: str, *, day: str | None = None) -> None:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        rec = self.ads[key]
        if status == "live" and rec.launched is None:
            rec.launched = day
        rec.status = status
        rec.notes.append(f"{day or ''} {status}: {note}".strip())

    def record_metrics(self, key: str, days: list[DailyMetrics]) -> None:
        """Merge results: a day seen again replaces the old numbers (Meta revises recent days)."""
        rec = self.ads[key]
        by_day = {m.day: m for m in rec.metrics}
        for m in days:
            by_day[m.day] = m
        rec.metrics = [by_day[d] for d in sorted(by_day)]

    def by_status(self, *statuses: str) -> list[AdRecord]:
        return [r for r in self.ads.values() if r.status in statuses]

    def ideas(self) -> list[tuple[str, str, str, str]]:
        """(format, persona, angle, hook) of every idea ever tried (made, rejected or failed): never again."""
        return [(r.format, r.persona, r.angle, r.hook) for r in self.ads.values()]

    def learnings(self, *, min_spend: float = 10.0) -> dict[str, dict[str, dict[str, float]]]:
        """Results grouped by format, angle and persona (only ads that spent enough to be judged)."""
        out: dict[str, dict[str, dict[str, float]]] = {"format": {}, "angle": {}, "persona": {}}
        for r in self.ads.values():
            if r.spend < min_spend:
                continue
            for dim, value in (("format", r.format), ("angle", r.angle), ("persona", r.persona)):
                g = out[dim].setdefault(value, {"ads": 0, "spend": 0.0, "conversions": 0})
                g["ads"] += 1
                g["spend"] = round(g["spend"] + r.spend, 2)
                g["conversions"] += r.conversions
        for groups in out.values():
            for g in groups.values():
                g["cpa"] = round(g["spend"] / g["conversions"], 2) if g["conversions"] else float("inf")
        return out
