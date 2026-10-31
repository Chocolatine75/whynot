"""R1 (E2-4): rank the partner's past ads blind with the simulator, then compare with their real CTR.

Monday, with the partner's written consent. Two ways in:
    # an Ads Manager export at ad level (Ad ID, Amount spent, Impressions, Link clicks; Body/Title if possible)
    uv run python scripts/r1_backtest.py --name vietbuddy --csv data/private/partner/ads.csv --brand VietBuddy --dry-run
    # read access to his ad account (PARTNER_AD_ACCOUNT_ID + META_ACCESS_TOKEN), creatives included
    uv run python scripts/r1_backtest.py --name vietbuddy --api --brand VietBuddy --dry-run
Drop --dry-run to run (cost estimated first, refused above --max-usd, hard cap during the run).

Writes: data/private/partner/<name>/ (history, creatives, scores: never committed) and
validate/results/r1-<name>.json (numbers only: may be committed). Scores are SIMULATED; outcomes are real.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from whynot.budget import Budget, BudgetExceeded, CallEstimate, estimate_usd
from whynot.config import REPO_ROOT, load_settings
from whynot.models import ModelClient, image_data_url
from whynot.sim.feed import build_market_feeds
from whynot.sim.personas import Persona
from whynot.validate.backtest import (
    CONDITIONS,
    HistoryError,
    creative_items,
    eligible,
    fetch_history,
    load_csv,
    run,
    save_history,
    separable_pairs,
)

# Token sizes (Muse Spark Open, low effort), from R3 v1: text feed ~1,500 in / ~900 out; images ~1,000 in each.
FEED_IN, FEED_OUT, IMAGE_IN, JUDGE_IN, JUDGE_OUT = 1500, 900, 1000, 350, 500
AGES = ("18-24", "25-34", "35-44")


def personas(countries: list[str], n: int) -> list[Persona]:
    """Demographic viewers spread over the campaign's countries (his ads carry no reach breakdown)."""
    cells = [(c, a, g) for c in countries for a in AGES for g in ("female", "male")]
    return [Persona(f"{c}-{a}-{g}-{i}", c, a, g) for i, (c, a, g) in enumerate((cells * n)[:n])]


def download_thumbnails(thumbs: dict[str, str], folder: Path) -> dict[str, str]:
    """Creatives to local JPEGs at once (CDN URLs expire and are never stored). Failures are skipped, counted."""
    import httpx

    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    with httpx.Client(timeout=30, follow_redirects=True) as http:
        for ad_id, url in thumbs.items():
            path = folder / f"{ad_id}.jpg"
            if not path.exists():
                try:
                    r = http.get(url)
                    r.raise_for_status()
                except httpx.HTTPError:
                    continue
                path.write_bytes(r.content)
            out[ad_id] = str(path)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--name", required=True, help="label for this dataset (folder and result file)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", type=Path, help="Ads Manager export (keep it under data/private/)")
    src.add_argument("--api", action="store_true", help="read PARTNER_AD_ACCOUNT_ID with META_ACCESS_TOKEN")
    p.add_argument("--brand", required=True, help="the page name viewers see on every ad")
    p.add_argument("--images", type=Path, help="with --csv: a folder of <ad id>.jpg creatives")
    p.add_argument("--countries", nargs="+", default=["US"])
    p.add_argument("--personas", type=int, default=12)
    p.add_argument("--min-impressions", type=int, default=1000)
    p.add_argument("--feed-size", type=int, default=4)
    p.add_argument("--appearances", type=int, default=3)
    p.add_argument("--viewers-per-feed", type=int, default=2)
    p.add_argument("--conditions", nargs="+", choices=CONDITIONS)
    p.add_argument("--max-usd", type=float, default=3.0)
    p.add_argument("--dry-run", action="store_true", help="load, check and estimate; no model call")
    args = p.parse_args()

    folder = REPO_ROOT / "data" / "private" / "partner" / args.name
    settings = load_settings()
    try:
        if args.csv:
            ads = load_csv(args.csv)
            images = {f.stem: str(f) for f in args.images.glob("*.jpg")} if args.images else {}
        else:
            from whynot.run.meta import Account, MarketingClient

            account = Account(settings.partner_ad_account_id or "", settings.meta_token or "")
            client = MarketingClient(account, version=settings.fb_api_version)
            ads, thumbs = fetch_history(lambda path, q: client._call("GET", path, params=q), account.act)
            images = download_thumbnails(thumbs, folder / "creatives")
    except (HistoryError, OSError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    save_history(ads, folder / "history.json")
    ads = eligible(ads, args.min_impressions)
    images = {k: v for k, v in images.items() if k in {a.id for a in ads}}
    pairs = separable_pairs(ads)
    with_text = sum(1 for a in ads if a.body or a.title)
    print(f"{len(ads)} ads with ≥ {args.min_impressions} impressions · {pairs} pairs with clearly different CTRs · "
          f"{with_text} with copy · {len(images)} with a creative")
    if len(ads) < 4 or pairs < 6:
        print("✗ too few ads or separable pairs for a meaningful R1 (need ≥ 4 ads, ≥ 6 pairs)", file=sys.stderr)
        return 1
    if with_text < len(ads) and not images:
        print("! some ads have no copy and there are no creatives: viewers would judge empty ads. Export Body/Title "
              "or use --api", file=sys.stderr)

    conditions = args.conditions or [c for c in CONDITIONS if images or c.endswith("text")]
    feeds = build_market_feeds(creative_items(ads, args.brand), feed_size=args.feed_size,
                               appearances=args.appearances)
    model_id = settings.baseten_model if settings.viewer_backend == "baseten" else settings.viewer_model
    calls = []
    for c in conditions:
        img = IMAGE_IN if c.endswith("image") else 0
        if c.startswith("viewers"):
            calls.append(CallEstimate(model_id, FEED_IN + args.feed_size * img, FEED_OUT,
                                      len(feeds) * args.viewers_per_feed))
        else:
            calls.append(CallEstimate(model_id, JUDGE_IN + img, JUDGE_OUT, len(ads)))
    cost = estimate_usd(*calls)
    print(f"conditions {', '.join(conditions)} · {len(feeds)} feeds × {args.viewers_per_feed} viewers "
          f"≈ ${cost:.2f} before cache (cap ${args.max_usd:.2f}, backend {settings.viewer_backend})")
    if args.dry_run:
        return 0
    try:
        Budget(args.max_usd).require(cost)
    except BudgetExceeded as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    model = ModelClient(settings, budget_usd=args.max_usd)
    report, scores = run(model, ads, advertiser=args.brand, personas=personas(args.countries, args.personas),
                         conditions=conditions, images={k: image_data_url(v) for k, v in images.items()},
                         feed_size=args.feed_size, appearances=args.appearances,
                         viewers_per_feed=args.viewers_per_feed)
    print(f"\n  {'condition':<16} accuracy (95% CI)        pairs")
    for r in sorted(report.results, key=lambda r: -r.accuracy):
        print(f"  {r.name:<16} {r.accuracy:.2f} [{r.ci[0]:.2f}, {r.ci[1]:.2f}]   {r.pairs}")
    print(f"  {'chance':<16} 0.50\nspent ${report.usd:.2f} · predictions SIMULATED, outcomes real")
    (folder / "scores.json").write_text(json.dumps(scores, indent=1))
    out = REPO_ROOT / "validate" / "results" / f"r1-{args.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**report.summary(args.name), "date": date.today().isoformat(),
                               "design": {k: v for k, v in vars(args).items() if k not in ("csv", "images", "brand")
                                          } | {"conditions": conditions}}, indent=2, default=str) + "\n")
    print(f"summary (numbers only): {out.relative_to(REPO_ROOT)} · private details: {folder.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
