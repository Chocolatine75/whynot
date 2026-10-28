"""Command line: `whynot create ...` (and `whynot daily` next)."""

import argparse
import sys
from pathlib import Path

from whynot.config import REPO_ROOT, load_settings
from whynot.run.autopilot import Policy


def _create(args: argparse.Namespace) -> int:
    from whynot.agency.create import CreateConfig, StageError, create, default_clients, new_run_dir

    settings = load_settings()
    policy = Policy.from_env(settings.autonomy_level, settings.max_daily_ad_spend_eur)
    cfg = CreateConfig(
        app_ref=args.app, countries=args.countries, daily_cap_eur=args.daily_cap, budget_usd=args.budget_usd,
        research_countries=args.research_countries, store_country=args.store_country, language=args.language,
        competitor_pages=args.competitor_page or [], max_angles=args.angles,
        variants_per_template=args.variants, policy=policy)
    run_dir = Path(args.resume) if args.resume else new_run_dir(Path(args.out), args.app)
    print(f"run folder: {run_dir}")
    try:
        result = create(cfg, default_clients(cfg.budget_usd, run_dir), run_dir)
    except StageError as exc:
        print(f"\n✗ {exc}\n  inspect {run_dir}/events.jsonl, fix, then resume with --resume {run_dir}",
              file=sys.stderr)
        return 1
    print(f"\n✓ {result.app.name}: {len(result.plan.ad_sets)} ad set(s), {len(result.choices)} ads, "
          f"€{result.plan.daily_total_eur}/day planned (PAUSED, not launched) · model cost ${result.usd:.2f}")
    if result.plan_errors:
        print("  plan problems: " + "; ".join(result.plan_errors))
    print(f"  report: {run_dir / 'report.md'}")
    return 0 if not result.plan_errors else 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="whynot", description="AI ad agency for small businesses on Meta.")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("create", help="research, strategy, ads, simulation and a campaign plan for an app")
    c.add_argument("app", help="App Store URL, app id, or the app's website")
    c.add_argument("--countries", nargs="+", required=True, help="campaign countries, e.g. US or FR GB")
    c.add_argument("--daily-cap", type=float, required=True, help="daily ad budget for the plan, EUR")
    c.add_argument("--budget-usd", type=float, default=3.0, help="hard cap on model spend for this run")
    c.add_argument("--research-countries", nargs="+", help="EU/UK countries for Ad Library research")
    c.add_argument("--store-country", default="us", help="App Store storefront for the page and reviews")
    c.add_argument("--language", default="English", help="language of the ads")
    c.add_argument("--competitor-page", action="append", help="Facebook page id of a known competitor (repeat)")
    c.add_argument("--angles", type=int, default=6, help="max ad concepts")
    c.add_argument("--variants", type=int, default=4, help="variants produced per concept")
    c.add_argument("--out", default=str(REPO_ROOT / "outputs" / "runs"), help="where run folders go")
    c.add_argument("--resume", help="an existing run folder: finished stages are reused, not re-billed")
    c.set_defaults(func=_create)
    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
