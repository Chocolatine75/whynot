"""R3 experiment: do viewer agents prefer competitor ads that last?

Fetches long-running (still active after --long-days) and short-lived (stopped
within --short-days) ads for the given advertisers, runs the simulated feed on
them, and reports AUC with a confidence interval. All scores are simulated.

Usage:
    uv run python scripts/longevity_check.py --name lacoste --page-ids 25440047420 --per-class 5 --dry-run
    uv run python scripts/longevity_check.py --name lacoste --page-ids 25440047420 --per-class 5

Cost is estimated before running; the run is refused above --max-usd.
"""

import argparse
import json
from dataclasses import asdict
from datetime import date, timedelta

from whynot.config import REPO_ROOT, load_settings
from whynot.ingest.adlibrary import AdLibraryClient, AdLibraryError, save_jsonl
from whynot.models import ModelClient
from whynot.sim.feed import FeedItem, build_market_feeds
from whynot.sim.personas import personas_from_reach
from whynot.sim.scores import score_ads
from whynot.sim.viewer import Viewer, run_simulation
from whynot.validate.longevity import evaluate, select

# Cost of one viewer call on Muse Spark, text feed of 5 ads, measured 2026-10-28
# (reasoning tokens dominate). Update from outputs/costs.jsonl after real runs.
EST_USD_PER_CALL = {"default": 0.012, "low": 0.0055, "minimal": 0.0031}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--page-ids", nargs="+", required=True)
    p.add_argument("--countries", nargs="+", default=["FR"])
    p.add_argument("--per-class", type=int, default=20)
    p.add_argument("--long-days", type=int, default=60)
    p.add_argument("--short-days", type=int, default=14)
    p.add_argument("--feed-size", type=int, default=5)
    p.add_argument("--appearances", type=int, default=3, help="feeds each ad appears in")
    p.add_argument("--viewers-per-feed", type=int, default=3)
    p.add_argument("--personas", type=int, default=30)
    p.add_argument("--max-usd", type=float, default=3.0)
    p.add_argument("--reasoning-effort", default="low", choices=["default", "low", "minimal"],
                   help="viewer reasoning effort; lower is cheaper, ranking quality to be measured")
    p.add_argument("--dry-run", action="store_true", help="fetch and plan, no model calls")
    args = p.parse_args()

    settings = load_settings()
    today = date.today()
    cache = REPO_ROOT / "data" / "cache" / "adlibrary"
    try:
        lib = AdLibraryClient(settings.fb_token or "", version=settings.fb_api_version)
        long_ads = list(lib.search(countries=args.countries, page_ids=args.page_ids, active_status="ACTIVE",
                                   delivery_date_max=today - timedelta(days=args.long_days), max_ads=300))
        old_ads = list(lib.search(countries=args.countries, page_ids=args.page_ids, active_status="INACTIVE",
                                  max_ads=600))
    except AdLibraryError as exc:
        raise SystemExit(f"Ad Library: {exc}") from None
    save_jsonl(long_ads, cache / f"{args.name}-active.jsonl")
    save_jsonl(old_ads, cache / f"{args.name}-inactive.jsonl")

    labelled = select(long_ads + old_ads, as_of=today, per_class=args.per_class,
                      long_days=args.long_days, short_days=args.short_days)
    n_long = sum(la.long_running for la in labelled)
    print(f"fetched {len(long_ads)} active + {len(old_ads)} inactive ads → "
          f"{n_long} long-running vs {len(labelled) - n_long} short-lived (deduplicated, balanced)")
    if n_long < 3:
        raise SystemExit("too few ads per class for a meaningful test: add advertisers")

    personas = personas_from_reach(long_ads + old_ads, args.personas)
    items = [FeedItem.from_ad(la.ad) for la in labelled]
    feeds = build_market_feeds(items, feed_size=args.feed_size, appearances=args.appearances)
    calls = len(feeds) * args.viewers_per_feed
    estimate = calls * EST_USD_PER_CALL[args.reasoning_effort]
    print(f"{len(personas)} personas, {len(feeds)} feeds × {args.viewers_per_feed} viewers = {calls} calls "
          f"≈ ${estimate:.2f} (backend: {settings.viewer_backend}, reasoning: {args.reasoning_effort})")
    if args.dry_run:
        return
    if estimate > args.max_usd:
        raise SystemExit(f"estimate above --max-usd {args.max_usd}: lower the size or raise the cap")

    effort = None if args.reasoning_effort == "default" else args.reasoning_effort
    sim = run_simulation(Viewer(ModelClient(settings), reasoning_effort=effort), personas, feeds,
                         viewers_per_feed=args.viewers_per_feed)
    scores = score_ads(sim.reactions)
    result = evaluate(labelled, scores)

    print(f"\nspent ${sim.usd:.3f} · {len(sim.failures)} failed viewers out of {calls}")
    print(f"AUC preference (primary): {result.auc_preference:.2f}  "
          f"95% CI [{result.ci_preference[0]:.2f}, {result.ci_preference[1]:.2f}]")
    print(f"AUC mean intent:          {result.auc_intent:.2f}  "
          f"95% CI [{result.ci_intent[0]:.2f}, {result.ci_intent[1]:.2f}]")
    print(f"AUC copy length (baseline): {result.auc_copy_length:.2f}   chance: 0.50")

    out = REPO_ROOT / "outputs" / "experiments" / f"longevity-{args.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "simulated": True, "date": today.isoformat(), "args": vars(args),
        "backend": settings.viewer_backend, "model": settings.viewer_model,
        "result": asdict(result), "usd": sim.usd, "failures": sim.failures,
        "ads": [{"id": la.ad.id, "page": la.ad.page_name, "long_running": la.long_running,
                 "days": la.ad.longevity_days(today), "body": (la.ad.bodies or [""])[0][:200],
                 "score": asdict(scores[la.ad.id]) if la.ad.id in scores else None} for la in labelled],
    }, indent=2, ensure_ascii=False))
    print(f"details: {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
