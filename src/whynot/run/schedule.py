"""Run the agency's day by itself every morning: `whynot schedule RUN --at 08:00` (one click on the site).

On macOS a LaunchAgent (`~/Library/LaunchAgents/ai.whynot.<run>.plist`) runs `whynot agency --resume RUN` at the
chosen time; its output goes to `<run>/agency/schedule.log`. Elsewhere the matching crontab line is returned for
the owner to add. The agency itself enforces every rule (autonomy level, cap, approvals, kill switch): a scheduled
run can do nothing a manual one could not.

The schedule is recorded in the run's `agency/state.json` (`schedule`), so the site can show it.
"""

import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from whynot.config import REPO_ROOT

_TIME = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
Runner = Callable[[Sequence[str]], Any]


class ScheduleError(RuntimeError):
    pass


@dataclass(frozen=True)
class Schedule:
    run_dir: Path
    hour: int
    minute: int

    @property
    def label(self) -> str:
        return "ai.whynot." + re.sub(r"[^A-Za-z0-9.-]", "-", self.run_dir.name)[:80]

    @property
    def at(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"

    @property
    def log(self) -> Path:
        return self.run_dir / "agency" / "schedule.log"


def parse(run_dir: Path, at: str) -> Schedule:
    run_dir = Path(run_dir).resolve()
    if not (run_dir / "agency" / "state.json").exists():
        raise ScheduleError(f"{run_dir} is not an agency run (no agency/state.json): start it with `whynot agency`")
    m = _TIME.match(at.strip())
    if not m:
        raise ScheduleError(f"time must be HH:MM (24 h), got {at!r}")
    return Schedule(run_dir, int(m.group(1)), int(m.group(2)))


def command(s: Schedule, uv: str | None = None) -> list[str]:
    """The exact command the schedule runs (absolute paths: launchd and cron start with an empty environment)."""
    uv = uv or shutil.which("uv") or "uv"
    return [uv, "run", "--project", str(REPO_ROOT), "whynot", "agency", "--resume", str(s.run_dir)]


def plist(s: Schedule, uv: str | None = None) -> bytes:
    return plistlib.dumps({
        "Label": s.label,
        "ProgramArguments": command(s, uv),
        "WorkingDirectory": str(REPO_ROOT),
        "StartCalendarInterval": {"Hour": s.hour, "Minute": s.minute},
        "StandardOutPath": str(s.log),
        "StandardErrorPath": str(s.log),
        "EnvironmentVariables": {"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        "RunAtLoad": False,
    })


def cron_line(s: Schedule, uv: str | None = None) -> str:
    cmd = " ".join(f"'{x}'" if " " in x else x for x in command(s, uv))
    return f"{s.minute} {s.hour} * * * cd {REPO_ROOT} && {cmd} >> '{s.log}' 2>&1"


def _agents_dir(home: Path | None) -> Path:
    return (home or Path.home()) / "Library" / "LaunchAgents"


def _record(s: Schedule, value: dict[str, Any] | None) -> None:
    path = s.run_dir / "agency" / "state.json"
    state = json.loads(path.read_text())
    if value is None:
        state.pop("schedule", None)
    else:
        state["schedule"] = value
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, ensure_ascii=False))
    tmp.replace(path)


def install(s: Schedule, *, home: Path | None = None, runner: Runner | None = None, system: str | None = None,
            uv: str | None = None) -> dict[str, Any]:
    """Install (or replace) the daily run. macOS: writes and loads the LaunchAgent. Elsewhere: returns the crontab
    line to add (nothing is changed on the machine)."""
    system = system or platform.system()
    s.log.parent.mkdir(parents=True, exist_ok=True)
    if system != "Darwin":
        info = {"at": s.at, "how": "cron", "cron": cron_line(s, uv), "installed": False}
        _record(s, info)
        return info
    run = runner or (lambda args: subprocess.run(list(args), check=False, capture_output=True))
    path = _agents_dir(home) / f"{s.label}.plist"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        run(["launchctl", "unload", str(path)])
    path.write_bytes(plist(s, uv))
    run(["launchctl", "load", str(path)])
    info = {"at": s.at, "how": "launchd", "label": s.label, "plist": str(path), "log": str(s.log), "installed": True}
    _record(s, info)
    return info


def remove(run_dir: Path, *, home: Path | None = None, runner: Runner | None = None) -> bool:
    """Stop the daily run of this agency run. Returns whether a schedule was found."""
    s = Schedule(Path(run_dir).resolve(), 0, 0)
    run = runner or (lambda args: subprocess.run(list(args), check=False, capture_output=True))
    path = _agents_dir(home) / f"{s.label}.plist"
    found = path.exists()
    if found:
        run(["launchctl", "unload", str(path)])
        path.unlink()
    if (s.run_dir / "agency" / "state.json").exists():
        found = found or "schedule" in json.loads((s.run_dir / "agency" / "state.json").read_text())
        _record(s, None)
    return found
