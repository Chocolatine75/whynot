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


def test_longevity_check_asks_the_ad_library_for_at_most_10_pages_at_a_time(monkeypatch, capsys):
    """Regression: the Ad Library refuses more than 10 `search_page_ids` (error 100), so R3 on 31 advertisers
    failed before any ad was fetched."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("longevity_check", SCRIPTS[0].parent / "longevity_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    asked: list[list[str]] = []

    class FakeLibrary:
        def __init__(self, *a, **k):
            pass

        def search(self, *, page_ids, **kwargs):
            if len(page_ids) > 10:
                raise AssertionError("more than 10 page ids in one call")
            asked.append(page_ids)
            return iter(())

    monkeypatch.setattr(mod, "AdLibraryClient", FakeLibrary)
    monkeypatch.setattr(mod, "save_jsonl", lambda *a, **k: None)
    ids = [str(i) for i in range(23)]
    monkeypatch.setattr(sys, "argv", ["longevity_check.py", "--name", "t", "--dry-run", "--page-ids", *ids])
    with pytest.raises(SystemExit, match="too few ads"):
        mod.main()
    assert sorted({i for chunk in asked for i in chunk}, key=int) == ids  # every page asked, active and inactive
    assert len(asked) == 6  # 3 chunks × (active, inactive)
