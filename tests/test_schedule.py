"""The daily automatic run: a LaunchAgent on macOS, a crontab line elsewhere, recorded in the run's state."""

import json
import plistlib
from pathlib import Path

import pytest

from whynot.run.schedule import ScheduleError, cron_line, install, parse, remove


@pytest.fixture
def run(tmp_path: Path) -> Path:
    d = tmp_path / "runs" / "20261102-080000-id123"
    (d / "agency").mkdir(parents=True)
    (d / "agency" / "state.json").write_text(json.dumps({"steps": {}, "days": {}}))
    return d


def test_only_an_agency_run_and_a_real_time_are_accepted(tmp_path, run):
    with pytest.raises(ScheduleError, match="not an agency run"):
        parse(tmp_path, "08:00")
    for bad in ("8h", "25:00", "07:61", ""):
        with pytest.raises(ScheduleError, match="HH:MM"):
            parse(run, bad)
    assert parse(run, "7:05").at == "07:05"


def test_macos_installs_a_launch_agent_that_resumes_the_run(tmp_path, run):
    calls = []
    info = install(parse(run, "08:30"), home=tmp_path, runner=calls.append, system="Darwin", uv="/opt/uv")
    plist = plistlib.loads(Path(info["plist"]).read_bytes())
    assert plist["StartCalendarInterval"] == {"Hour": 8, "Minute": 30}
    assert plist["ProgramArguments"][-3:] == ["agency", "--resume", str(run.resolve())]
    assert plist["ProgramArguments"][0] == "/opt/uv" and plist["StandardOutPath"].endswith("agency/schedule.log")
    assert calls == [["launchctl", "load", info["plist"]]]
    assert json.loads((run / "agency" / "state.json").read_text())["schedule"]["at"] == "08:30"
    # again at another time: the old one is unloaded first, never two
    install(parse(run, "09:00"), home=tmp_path, runner=calls.append, system="Darwin", uv="/opt/uv")
    assert calls[1][1] == "unload" and calls[2][1] == "load"
    assert len(list((tmp_path / "Library" / "LaunchAgents").iterdir())) == 1


def test_elsewhere_the_crontab_line_is_given_not_installed(run):
    info = install(parse(run, "06:15"), system="Linux", uv="/usr/bin/uv")
    assert not info["installed"] and info["cron"].startswith("15 6 * * * ")
    assert "agency --resume" in info["cron"] and cron_line(parse(run, "06:15"), "/usr/bin/uv") == info["cron"]


def test_remove_stops_it_and_forgets_it(tmp_path, run):
    calls = []
    install(parse(run, "08:00"), home=tmp_path, runner=calls.append, system="Darwin", uv="uv")
    assert remove(run, home=tmp_path, runner=calls.append)
    assert calls[-1][1] == "unload" and not list((tmp_path / "Library" / "LaunchAgents").iterdir())
    assert "schedule" not in json.loads((run / "agency" / "state.json").read_text())
    assert not remove(run, home=tmp_path, runner=calls.append)
