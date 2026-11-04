"""examples/ is public: an exported run must carry no token, ad account, Page or home path."""

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("export_example", ROOT / "scripts" / "export_example.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

LEAKS = re.compile(r"access_token|act_\d|EAA[A-Za-z0-9]{20}|/Users/|\"page\"\s*:\s*\"\d{9,}")


def test_export_redacts_tokens_accounts_and_paths(tmp_path):
    run = tmp_path / "run"
    (run / "ads").mkdir(parents=True)
    (run / "assets").mkdir()
    (run / "plan.json").write_text(json.dumps({"ads": ["a-1"]}))
    (run / "report.md").write_text("![x](ads/b-2.png)")
    (run / "market_ads.jsonl").write_text(json.dumps(
        {"ad_snapshot_url": "https://www.facebook.com/ads/archive/render_ad/?id=1&access_token=EAAsecret123"}) + "\n")
    (run / "state.json").write_text(json.dumps(
        {"account": "act_2579757785851312", "page": "1352874221250687", "connection": "/Users/someone/x.json"}))
    (run / "assets" / "screen_1.png").write_bytes(b"png")
    (run / "daily.lock").write_text("lock")
    for name in ("a-1.png", "b-2.png", "c-3.png"):
        (run / "ads" / name).write_bytes(b"png")

    mod.export(run, tmp_path / "out")
    out = tmp_path / "out"
    text = "".join(p.read_text() for p in out.rglob("*") if p.suffix in mod.TEXT)
    assert not LEAKS.search(text)
    assert "render_ad/?id=1" in text and "act_REDACTED" in text
    assert sorted(p.name for p in (out / "ads").iterdir()) == ["a-1.png", "b-2.png"]  # planned + shown only
    assert not (out / "assets").exists() and not (out / "daily.lock").exists()


def test_committed_examples_carry_no_secret():
    files = [p for p in (ROOT / "examples").rglob("*") if p.suffix in mod.TEXT]
    assert files, "examples/ should hold at least one exported run"
    for p in files:
        assert not LEAKS.search(p.read_text(encoding="utf-8")), p


def test_media_export_keeps_every_picture_and_video_but_still_redacts(tmp_path):
    run = tmp_path / "run"
    (run / "videos").mkdir(parents=True)
    (run / "ads").mkdir()
    (run / "plan.json").write_text("{}")
    (run / "report.md").write_text("")
    (run / "state.json").write_text(json.dumps({"account": "act_123456789"}))
    (run / "videos" / "v.mp4").write_bytes(b"mp4")
    (run / "ads" / "x.png").write_bytes(b"png")
    out = tmp_path / "out"
    mod.export(run, out, media=True)
    assert (out / "videos" / "v.mp4").exists() and (out / "ads" / "x.png").exists()
    assert "act_REDACTED" in (out / "state.json").read_text()
