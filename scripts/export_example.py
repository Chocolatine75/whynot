"""Copy a finished run into examples/ so anyone can open what the agency really produced.

Usage: uv run python scripts/export_example.py outputs/runs/<run> examples/<name>

What is kept: every JSON / JSONL / Markdown / YAML file the stages wrote (market, strategy, templates,
variants, simulated feed, evolution, plan, Meta API payloads, events, costs, report) and the pictures of
the planned ads and the ads the report shows (feed and story). What is left out: the store
screenshots and videos (the app owner's assets; too heavy), lock files and server logs.
What is redacted: access tokens in URLs, the owner's ad account, Page and campaign ids.
"""

import argparse
import re
import shutil
from pathlib import Path

from whynot.ingest.adlibrary import strip_token

TEXT = {".json", ".jsonl", ".md", ".yaml"}
SKIP = {"daily.lock", "site.log", "strategy.raw.json"}
URL = re.compile(r"https?://[^\s\"'<>]+")
IDS = [
    (re.compile(r"act_\d+"), "act_REDACTED"),
    (re.compile(r"act=\d+"), "act=REDACTED"),
    (re.compile(r'("account_id"\s*:\s*")\d+(")'), r"\1REDACTED\2"),
    (re.compile(r"/Users/[^/\s\"]+"), "~"),
    (re.compile(r'("(?:page|page_id|campaign|campaign_id|adset_id|ad_id|creative_id|id)"\s*:\s*")\d{9,}(")'),
     r"\1REDACTED\2"),
]


def clean(text: str) -> str:
    text = URL.sub(lambda m: strip_token(m.group(0)) or "", text)
    for pattern, repl in IDS:
        text = pattern.sub(repl, text)
    return text


MEDIA = {".png", ".jpg", ".jpeg", ".mp4"}


def export(run: Path, dest: Path, *, media: bool = False) -> list[Path]:
    if dest.exists():
        shutil.rmtree(dest)
    written = []
    for src in sorted(run.rglob("*")):
        rel = src.relative_to(run)
        if not src.is_file() or src.name in SKIP or src.suffix not in TEXT or rel.parts[0] in {"assets", "videos"}:
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(clean(src.read_text(encoding="utf-8")), encoding="utf-8")
        written.append(out)
    if media:  # the public demo site: every picture and video the run made (store screenshots included)
        for src in sorted(run.rglob("*")):
            if src.is_file() and src.suffix.lower() in MEDIA:
                out = dest / src.relative_to(run)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, out)
                written.append(out)
        return written
    wanted = "".join((run / f).read_text(encoding="utf-8") for f in ("plan.json", "report.md"))
    for png in sorted((run / "ads").glob("*.png")):
        variant = png.name.split(".")[0]
        if variant in wanted:
            out = dest / "ads" / png.name
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(png, out)
            written.append(out)
    return written


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copy a finished run into examples/, tokens and account ids removed.")
    parser.add_argument("run", type=Path, help="the run folder (outputs/runs/...)")
    parser.add_argument("dest", type=Path, help="where to write it (examples/<name>)")
    parser.add_argument("--media", action="store_true", help="copy every picture and video too (the demo site)")
    args = parser.parse_args()
    files = export(args.run, args.dest, media=args.media)
    print(f"{len(files)} files → {args.dest}")
