"""Command line: `whynot create`, `whynot video`, `whynot daily`, `whynot publish`, `whynot costs`."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

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
    voice = None
    if settings.elevenlabs_api_key and not args.silent:
        from whynot.agency.video import CACHE
        from whynot.audio.elevenlabs import ElevenLabs
        voice = ElevenLabs(settings.elevenlabs_api_key, CACHE / "audio")
    elif not args.silent:
        print("  (no ELEVENLABS_API_KEY in .env: videos without voice-over or music)")
    try:
        if args.style == "trend":
            from whynot.agency.trend_video import make_trend_videos
            report = make_trend_videos(run_dir, model, cfg=VideoConfig(n_videos=args.n), voice=voice,
                                       voice_id=settings.elevenlabs_voice_id, token=settings.fb_token or "",
                                       renderer_factory=factory, reuse_briefs=args.rerender)
        else:
            report = make_videos(run_dir, model, token=settings.fb_token or "", renderer_factory=factory,
                                 voice=voice, voice_id=settings.elevenlabs_voice_id,
                                 cfg=VideoConfig(n_videos=args.n, renderer=args.renderer))
    except (BudgetExceeded, RuntimeError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    print(f"\n✓ {len(report['videos'])} video(s) in {run_dir / 'videos'} · model cost ${report['usd']:.2f}")
    return 0 if report["videos"] else 2


def _video_launcher(client: Any, run_dir: Path, args: argparse.Namespace) -> Any:
    """The real account's launcher: video ads published with the plan's audiences, or (missing page id or plan)
    a launcher that leaves new ads waiting, with the reason in the report."""
    from whynot.agency.create import plan_from_json
    from whynot.agency.daily import MetaLauncher
    from whynot.run.meta import MetaError
    from whynot.run.video_ads import VideoPublisher

    if not (run_dir / "plan.json").exists():
        print("! no plan.json: new video ads will wait (no audiences to target)", file=sys.stderr)
        return MetaLauncher(client)
    plan = plan_from_json(json.loads((run_dir / "plan.json").read_text()))
    try:
        publisher = VideoPublisher(client, run_dir, store_url=plan.store_url, objective=args.objective,
                                   campaign_name=f"whynot daily · {plan.app_name}")
    except MetaError as exc:
        print(f"! {exc}: new video ads will wait", file=sys.stderr)
        return MetaLauncher(client)
    return MetaLauncher(client, publisher, audiences={a.audience.persona: a.audience for a in plan.ad_sets},
                        videos=run_dir / "videos", title=plan.app_name)


def _daily(args: argparse.Namespace) -> int:
    from datetime import date, timedelta

    from whynot.agency.daily import AlreadyRunning, DailyConfig, SimLauncher, run_day
    from whynot.agency.trend_video import Studio
    from whynot.agency.video import CACHE, VideoConfig
    from whynot.agents.strategist import Strategy
    from whynot.models import BudgetExceeded, ModelClient
    from whynot.run.autopilot import Level
    from whynot.run.insights import MetaInsights, SimulatedAccount
    from whynot.run.meta import Account, MarketingClient

    run_dir = Path(args.run)
    if not (run_dir / "strategy.json").exists():
        print(f"✗ {run_dir} has no strategy.json: run `whynot create` first", file=sys.stderr)
        return 1
    if not args.sim and (args.days != 1 or args.start):
        # several days in one go only make sense on the simulated account: on a real one they would launch
        # tomorrow's ads today
        print("✗ --days and --start are for the simulated account (--sim); a real account runs one day: today",
              file=sys.stderr)
        return 1
    s = load_settings()
    cfg = DailyConfig(target_live=args.target, max_new=args.new, budget_per_ad_eur=args.budget_per_ad)
    source: Any
    launcher: Any
    if args.sim:
        source, launcher = SimulatedAccount(seed=args.seed, daily_budget_eur=args.budget_per_ad), SimLauncher()
        policy = Policy(Level.AUTOPILOT, args.target * args.budget_per_ad, first_live_approved=True)
        print(f"SIMULATED account: results are invented by a known model, not real (cap €{policy.daily_cap_eur:.2f})")
    else:
        client = MarketingClient(Account(s.meta_ad_account_id or "", s.meta_token or "", page_id=s.meta_page_id,
                                         app_id=s.meta_app_id), version=s.fb_api_version)
        source, launcher = MetaInsights(client, objective=args.objective), _video_launcher(client, run_dir, args)
        policy = Policy.from_env(s.autonomy_level, s.max_daily_ad_spend_eur)
    model = ModelClient(s, budget_usd=args.budget_usd)
    voice = None
    if s.elevenlabs_api_key and not args.silent:
        from whynot.audio.elevenlabs import ElevenLabs
        voice = ElevenLabs(s.elevenlabs_api_key, CACHE / "audio")
    try:
        studio = Studio(run_dir, model, cfg=VideoConfig(capture=False), voice=voice,
                        voice_id=s.elevenlabs_voice_id)
        strategy = Strategy.from_json(json.loads((run_dir / "strategy.json").read_text()))
        start = date.fromisoformat(args.start) if args.start else date.today()
        for i in range(args.days):
            rep = run_day(run_dir, start + timedelta(days=i), source=source, producer=studio, launcher=launcher,
                          policy=policy, strategy=strategy, cfg=cfg, approved_by=args.approve)
            print(f"  → {rep.day}: {len(rep.live)} live, {len(rep.paused)} paused, {len(rep.new)} new, "
                  f"{len(rep.waiting_approval)} waiting · report agency/reports/{rep.day}.md")
    except (AlreadyRunning, BudgetExceeded, RuntimeError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    print(f"model cost ${model.spent_usd:.2f}")
    return 0


def _stop(args: argparse.Namespace) -> int:
    from whynot.run.killswitch import stop
    from whynot.run.meta import Account, MarketingClient, MetaError

    s = load_settings()
    live = args.live
    account = Account(account_id=(s.meta_ad_account_id if live else s.meta_sandbox_ad_account_id) or "",
                      token=(s.meta_token if live else s.meta_sandbox_token) or "", sandbox=not live)
    try:
        client = MarketingClient(account, version=s.fb_api_version)
        policy = Policy.from_env(s.autonomy_level, s.max_daily_ad_spend_eur)
        report = stop([Path(r) for r in args.runs], client, by=args.by, policy=policy)
    except (MetaError, ValueError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    for t in report.paused:
        print(f"  ⏸ {t.level:<8} {t.meta_id}  ({t.ref})")
    for meta_id, error in report.failed.items():
        print(f"  ✗ {meta_id}: {error}", file=sys.stderr)
    for run in report.skipped:
        print(f"  • {run}: published to another account, left alone")
    mode = "LIVE" if live else "SANDBOX"
    print(f"{'✓' if report.ok else '✗'} {mode} {account.act}: {len(report.paused)} paused, {len(report.failed)} failed "
          f"in {report.seconds:.1f} s · logged in each run's actions.jsonl")
    return 0 if report.ok else 2


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
    v.add_argument("--renderer", choices=["remotion", "builtin"], default="remotion",
                   help="remotion: voice, captions, music (needs `cd video && npm install`); builtin: silent")
    v.add_argument("--silent", action="store_true", help="no voice-over or music")
    v.add_argument("--rerender", action="store_true",
                   help="trend: render the last scripts again (videos/trends.json) without rewriting them")
    v.add_argument("--style", choices=["trend", "classic"], default="trend",
                   help="trend: viral formats turned into ads (fast cuts, Remotion); classic: storyboard ads")
    v.set_defaults(func=_video)

    dy = sub.add_parser("daily", help="the agency's day: results, decisions, new ads with new ideas, report")
    dy.add_argument("run", help="the run folder (outputs/runs/...)")
    dy.add_argument("--sim", action="store_true", help="a simulated account (results invented, labelled as such)")
    dy.add_argument("--days", type=int, default=1, help="run this many days in a row (with --sim: a week in minutes)")
    dy.add_argument("--start", help="first day, YYYY-MM-DD (default: today)")
    dy.add_argument("--target", type=int, default=4, help="ads running at the same time")
    dy.add_argument("--new", type=int, default=2, help="new ads per day at most")
    dy.add_argument("--budget-per-ad", type=float, default=5.0, help="daily budget per ad, EUR")
    dy.add_argument("--objective", choices=["traffic", "app_promotion"], default="traffic")
    dy.add_argument("--approve", metavar="NAME", help="the owner's approval for today's launches")
    dy.add_argument("--seed", type=int, default=0, help="simulated account seed")
    dy.add_argument("--budget-usd", type=float, default=3.0, help="hard cap on model spend for this command")
    dy.add_argument("--silent", action="store_true", help="no voice-over or music")
    dy.set_defaults(func=_daily)

    st = sub.add_parser("stop", help="kill switch: pause every campaign, ad set and ad whynot created, now")
    st.add_argument("runs", nargs="+", help="run folders (outputs/runs/...) whose objects to pause")
    st.add_argument("--by", required=True, metavar="NAME", help="who pulls the switch (logged)")
    st.add_argument("--live", action="store_true", help="the live ad account (default: the sandbox account)")
    st.set_defaults(func=_stop)

    co = sub.add_parser("costs", help="model spend by day, module, model and run, vs the team budget")
    co.add_argument("--since", type=_iso_day, help="first day to count, YYYY-MM-DD (UTC)")
    co.add_argument("--budget", type=float, default=TEAM_BUDGET_USD, help="team model budget to the deadline, USD")
    co.add_argument("--outputs", default=str(REPO_ROOT / "outputs"), help="folder holding costs.jsonl and runs/")
    co.set_defaults(func=_costs)
    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
