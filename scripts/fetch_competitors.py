"""Fetch competitor ads from the Meta Ad Library into data/cache/adlibrary/.

Usage:
    uv run python scripts/fetch_competitors.py --name language-apps --page-ids 123 456 --countries FR
    uv run python scripts/fetch_competitors.py --name test --terms "learn languages" --max 50
    # long-running ads: still active and started more than 60 days ago
    uv run python scripts/fetch_competitors.py --name winners --page-ids 123 --active ACTIVE --started-before-days 60

Prefer --page-ids (keyword search is noisy). Needs FB_TOKEN in .env.
Tokens are stripped before saving; the output never contains access_token.
"""

import argparse
import statistics
from collections import Counter
from datetime import date, timedelta

from whynot.config import REPO_ROOT, load_settings
from whynot.ingest.adlibrary import AdLibraryClient, AdLibraryError, save_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="output file name (no extension)")
    parser.add_argument("--page-ids", nargs="*")
    parser.add_argument("--terms")
    parser.add_argument("--countries", nargs="+", default=["FR"])
    parser.add_argument("--active", default="ALL", choices=["ALL", "ACTIVE", "INACTIVE"])
    parser.add_argument("--max", type=int, default=200)
    parser.add_argument("--started-before-days", type=int,
                        help="only ads that started at least N days ago (the API returns newest first)")
    args = parser.parse_args()

    settings = load_settings()
    try:
        client = AdLibraryClient(settings.fb_token or "", version=settings.fb_api_version)
        started_before = (date.today() - timedelta(days=args.started_before_days)
                          if args.started_before_days else None)
        ads = list(client.search(countries=args.countries, page_ids=args.page_ids, terms=args.terms,
                                 active_status=args.active, delivery_date_max=started_before,
                                 max_ads=args.max))
    except AdLibraryError as exc:
        raise SystemExit(f"Ad Library: {exc}")

    path = save_jsonl(ads, REPO_ROOT / "data" / "cache" / "adlibrary" / f"{args.name}.jsonl")
    today = date.today()
    days = [d for a in ads if (d := a.longevity_days(today)) is not None]
    print(f"{len(ads)} ads saved to {path.relative_to(REPO_ROOT)}")
    if days:
        print(f"longevity: median {statistics.median(days):.0f} days, "
              f"{sum(d > 60 for d in days)} ads over 60 days")
    with_breakdown = sum(bool(a.reach_breakdown) for a in ads)
    print(f"{with_breakdown} ads with a reach breakdown")
    for page, count in Counter(a.page_name for a in ads).most_common(10):
        print(f"  {count:>4}  {page}")


if __name__ == "__main__":
    main()
