"""Every script must at least start and print its help (catches broken imports early)."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = sorted((Path(__file__).resolve().parents[1] / "scripts").glob("*.py"))


@pytest.mark.parametrize("script", SCRIPTS, ids=[s.name for s in SCRIPTS])
def test_script_help(script):
    result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "usage" in result.stdout.lower()
