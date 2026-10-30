"""Command line: `whynot create`, `whynot video`, `whynot publish`, `whynot costs`."""

import argparse
import sys
from pathlib import Path

from whynot.config import REPO_ROOT, load_settings
from whynot.costs import TEAM_BUDGET_USD
from whynot.run.autopilot import Policy


def _create(args: argparse.Namespace) -> int:
    from whynot.agency.create import CreateConfig, StageError, create, default_clients, new_run_dir

    settings = load_settings()
    policy = Policy.from_env(settings.autonomy_level, settings.max_daily_ad_spend_eur)
    cfg = CreateConfig(
        app_ref=args.app, countries=args.countries, daily_cap_eur=args.daily_cap, budget_usd=args.budget_usd,
        research_countries=args.research_countries, store_country=args.store_country, language=args.language,
        competitor_pages=args.competitor_page or [], max_angles=args.angles,
        variants_per_template=args.variants, generations=args.generations, policy=policy)
    run_dir = Path(args.resume) if args.resume else new_run_dir(Path(args.out), args.app)
    print(f"run folder: {run_dir}")
    try:
        result = create(cfg, default_clients(cfg.budget_usd, run_dir), run_dir, redo_from=args.redo_from)
    except StageError as exc:
        print(f"\n✗ {exc}\n  inspect {run_dir}/events.jsonl, fix, then resume with --resume {run_dir}",
              file=sys.stderr)
        return 1
    print(f"\n✓ {result.app.name}: {len(result.plan.ad_sets)} ad set(s), {len(result.choices)} ads, "
          f"€{result.plan.daily_total_eur}/day planned (PAUSED, not launched) · model cost ${result.usd_now:.2f} "
          f"this run (${result.usd:.2f} total for this folder)")
    if result.plan_errors:
        print("  plan problems: " + "; ".join(result.plan_errors))
    print(f"  report: {run_dir / 'report.md'}")
    return 0 if not result.plan_errors else 2


def _publish(args: argparse.Namespace) -> int:
    import json

    from whynot.agency.create import plan_from_json
    from whynot.run.meta import Account, MarketingClient, MetaError
    from whynot.run.publish import PublishError, PublishState, activate_published, publish

    s = load_settings()
    run_dir = Path(args.run)
    if not (run_dir / "plan.json").exists():
        print(f"✗ no plan.json in {run_dir}: run `whynot create` first", file=sys.stderr)
        return 1
    live = args.live
    account = Account(
        account_id=(s.meta_ad_account_id if live else s.meta_sandbox_ad_account_id) or "",
        token=(s.meta_token if live else s.meta_sandbox_token) or "",
        page_id=s.meta_page_id, app_id=s.meta_app_id, sandbox=not live)
    try:
        client = MarketingClient(account, version=s.fb_api_version)
        if args.activate_only:
            state = PublishState.load(run_dir / "publish.json")
            if state is None:
                print("✗ nothing published yet", file=sys.stderr)
                return 1
            if not args.approve:
                print("✗ activation needs --approve <your name>", file=sys.stderr)
                return 1
            state = activate_published(state, client, run_dir)
        else:
            plan = plan_from_json(json.loads((run_dir / "plan.json").read_text()))
            owner = Policy.from_env(s.autonomy_level, s.max_daily_ad_spend_eur)
            state = publish(plan, run_dir, client, owner, objective=args.objective, approved_by=args.approve,
                            activate=args.activate)
    except (MetaError, PublishError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    mode = "SANDBOX" if not live else "LIVE"
    for d in state.decisions:
        print(f"  {d['outcome']:>15}  {d['ad_set']}  ({d['why']})")
    n = {k: sum(1 for r in state.objects if r.startswith(k)) for k in ("adset_", "creative_", "ad_")}
    print(f"\n{'✓' if state.status in ('published', 'active') else '•'} {mode} {account.act}: {state.status} · "
          f"campaign {state.objects.get('campaign', '—')} · {n['adset_']} ad sets · {n['ad_']} ads"
          + ("" if state.status == "active" else " · all PAUSED"))
    if state.campaign_url:
        print(f"  Ads Manager: {state.campaign_url}")
    return 0 if state.status in ("published", "active") else 2


def _iso_day(value: str) -> str:
    from datetime import date

    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date (YYYY-MM-DD): {value!r}") from None


def _costs(args: argparse.Namespace) -> int:
    from whynot.costs import collect_ledgers, format_report, spend_report

    report = spend_report(collect_ledgers(Path(args.outputs)), since=args.since, budget_usd=args.budget)
    print(format_report(report))
    return 0


def _video(args: argparse.Namespace) -> int:
    from whynot.agency.video import VideoConfig, make_videos
    from whynot.models import BudgetExceeded, ModelClient

    run_dir = Path(args.run)
    if not (run_dir / "strategy.json").exists():
        print(f"✗ {run_dir} has no strategy.json: run `whynot create` first", file=sys.stderr)
        return 1
    settings = load_settings()
    factory = None
    if not args.no_capture:
        try:
            from whynot.ingest.creatives import PlaywrightRenderer
            factory = PlaywrightRenderer
        except ImportError:  # pragma: no cover - optional dependency group
            print("  (capture skipped: run with `uv run --group capture` to fetch competitor creatives)")
    model = ModelClient(settings, budget_usd=args.budget_usd)
    try:
        report = make_videos(run_dir, model, token=settings.fb_token or "", renderer_factory=factory,
                             cfg=VideoConfig(n_videos=args.n))
    except BudgetExceeded as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    print(f"\n✓ {len(report['videos'])} video(s) in {run_dir / 'videos'} · model cost ${report['usd']:.2f}")
    return 0 if report["videos"] else 2


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
    c.add_argument("--language", help="force one ad language (code: en, fr, de...); default: per country")
    c.add_argument("--competitor-page", action="append", help="Facebook page id of a known competitor (repeat)")
    c.add_argument("--angles", type=int, default=6, help="max ad concepts")
    c.add_argument("--variants", type=int, default=4, help="variants produced per concept")
    c.add_argument("--out", default=str(REPO_ROOT / "outputs" / "runs"), help="where run folders go")
    c.add_argument("--resume", help="an existing run folder: finished stages are reused, not re-billed")
    c.add_argument("--generations", type=int, default=2, help="evolution rounds after the first test (0 = none)")
    c.add_argument("--redo-from", choices=["market", "strategy", "creative", "produce", "simulate", "evolve", "plan",
                                           "report"],
                   help="with --resume: recompute this stage and the following ones, reuse the earlier ones")
    c.set_defaults(func=_create)

    pub = sub.add_parser("publish", help="publish a run's campaign plan to Meta (sandbox unless --live), all PAUSED")
    pub.add_argument("run", help="the run folder (outputs/runs/...)")
    pub.add_argument("--live", action="store_true", help="the live ad account (default: the sandbox account)")
    pub.add_argument("--objective", choices=["traffic", "app_promotion"], default="traffic",
                     help="app_promotion needs META_APP_ID (the app registered with Meta)")
    pub.add_argument("--approve", metavar="NAME", help="the owner's approval, recorded with every action")
    pub.add_argument("--activate", action="store_true", help="switch everything to ACTIVE after publishing")
    pub.add_argument("--activate-only", action="store_true", help="activate what an earlier run published")
    pub.set_defaults(func=_publish)

    v = sub.add_parser("video", help="video ads for a run, from the market's winning ad archetypes")
    v.add_argument("run", help="the run folder (outputs/runs/...)")
    v.add_argument("-n", type=int, default=3, help="number of videos (one per archetype)")
    v.add_argument("--budget-usd", type=float, default=2.0, help="hard cap on model spend for this command")
    v.add_argument("--no-capture", action="store_true", help="use only competitor creatives already captured")
    v.set_defaults(func=_video)

    co = sub.add_parser("costs", help="model spend by day, module, model and run, vs the team budget")
    co.add_argument("--since", type=_iso_day, help="first day to count, YYYY-MM-DD (UTC)")
    co.add_argument("--budget", type=float, default=TEAM_BUDGET_USD, help="team model budget to the deadline, USD")
    co.add_argument("--outputs", default=str(REPO_ROOT / "outputs"), help="folder holding costs.jsonl and runs/")
    co.set_defaults(func=_costs)
    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
