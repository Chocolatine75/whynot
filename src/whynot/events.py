"""The agents' shared event log (E0-7): one line per agent step in `<run>/events.jsonl`.

Every step of the agency (the orchestrator's steps and the stages of `create` inside them) appends one event
when it starts and one when it ends:

    {"ts", "id", "parent", "agent", "stage", "status", "seconds", "usd", "inputs", "outputs", "guards",
     "detail", "error", "rollup"}

- `parent`: the event id of the step this one runs inside (a `create` stage → the orchestrator's `create` step),
  so the web app can draw the tree and a run can be resumed from any step.
- `inputs` / `outputs`: short digests (sha256, 16 hex) of what went in and the files that came out, so two runs
  can be compared without storing the content twice.
- `usd`: model spend of this step. A step whose spend is already counted by its own inner events sets
  `rollup: true`, so totals never count the same dollar twice (`agency/report.spent_usd`).

Security: secrets passed to the log and any `access_token=` in a URL are removed before a line is written.
"""

import hashlib
import json
import re
import threading
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATUSES = ("start", "ok", "error", "cached", "skipped", "waiting", "redo")
_TOKEN_IN_URL = re.compile(r"(access_token=)[^&\s\"']+")


def digest(value: Any) -> str:
    """Stable short hash of a JSON-able value (dict keys sorted)."""
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def file_digest(path: Path) -> str | None:
    """Short hash of a file, or of every file under a folder (names + bytes); None when missing."""
    path = Path(path)
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    if path.is_dir():
        h = hashlib.sha256()
        for p in sorted(x for x in path.rglob("*") if x.is_file()):
            h.update(str(p.relative_to(path)).encode())
            h.update(p.read_bytes())
        return h.hexdigest()[:16]
    return None


def new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class AgentEvent:
    agent: str  # who acted: scout, strategist, director, composer, viewers, evolver, planner, publisher, ...
    stage: str  # the step's name (a `create` stage or an orchestrator step)
    status: str  # one of STATUSES
    id: str = field(default_factory=new_id)
    parent: str | None = None
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    seconds: float | None = None
    usd: float | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    guards: dict[str, Any] = field(default_factory=dict)
    detail: str = ""
    error: str | None = None
    rollup: bool = False

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"unknown event status {self.status!r}; one of {STATUSES}")

    def to_json(self) -> dict[str, Any]:
        """Without empty fields, so lines stay short and readable."""
        return {k: v for k, v in asdict(self).items() if v not in (None, "", {}, False)}


class EventLog:
    """Append-only `events.jsonl`, safe to share between threads, never writes a secret."""

    def __init__(self, path: Path, secrets: Iterable[str | None] = ()):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._secrets = sorted({s for s in secrets if s and len(s) >= 8}, key=len, reverse=True)
        self._lock = threading.Lock()

    def add_secret(self, secret: str | None) -> None:
        if secret and len(secret) >= 8 and secret not in self._secrets:
            self._secrets = sorted([*self._secrets, secret], key=len, reverse=True)

    def scrub(self, text: str) -> str:
        for s in self._secrets:
            text = text.replace(s, "[REDACTED]")
        return _TOKEN_IN_URL.sub(r"\1[REDACTED]", text)

    def write(self, event: AgentEvent | dict[str, Any]) -> dict[str, Any]:
        """Append one event; returns what was written (ids included)."""
        row = event.to_json() if isinstance(event, AgentEvent) else dict(event)
        row.setdefault("ts", datetime.now(UTC).isoformat())
        row.setdefault("id", new_id())
        line = self.scrub(json.dumps(row, ensure_ascii=False, default=str))
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return row

    def rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]


def total_usd(rows: Iterable[dict[str, Any]]) -> float:
    """Model spend in a log: finished steps only, roll-ups skipped (their inner events carry the cost)."""
    return sum(float(r.get("usd") or 0) for r in rows if r.get("status") in ("ok", "error") and not r.get("rollup"))
