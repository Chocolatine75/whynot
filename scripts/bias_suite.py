"""E2-6: run the simulator bias suite on the competitor ads of a `create` run.

Twins of real competitor ads (brand name, copy length, emoji, leaked "our ad" label) and the feed position.
Exit code 1 when a bias is flagged, so it can gate CI on recorded answers (WHYNOT_CASSETTE=replay).
All numbers are SIMULATED. Usage:
    uv run python scripts/bias_suite.py outputs/runs/<run> --dry-run
    uv run python scripts/bias_suite.py outputs/runs/<run> --max-usd 1.5
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from whynot.budget import Budget, BudgetExceeded
from whynot.config import REPO_ROOT, load_settings
from whynot.ingest.adlibrary import load_jsonl
from whynot.models import ModelClient
from whynot.sim.arena import brand_name
from whynot.sim.feed import FeedItem
from whynot.sim.personas import personas_from_reach
from whynot.sim.viewer import Viewer
from whynot.validate.bias import estimated_calls, run_suite, standard_checks

# One viewer call, text feed of 4 ads, reasoning "low" (measured 2026-10-29 on Baseten: $0.0034; Spark similar).
EST_USD_PER_CALL = 0.004


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run", type=Path)
    p.add_argument("--items", type=int, default=12, help="competitor ads turned into twins")
    p.add_argument("--feeds-per-item", type=int, default=3)
    p.add_argument("--viewers-per-feed", type=int, default=2)
    p.add_argument("--personas", type=int, default=12)
    p.add_argument("--max-usd", type=float, default=1.5)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    ads = [a for a in load_jsonl(args.run / "market_ads.jsonl") if (a.bodies or [""])[0].strip()]
    items = [FeedItem.from_ad(a) for a in ads[:args.items]]
    fillers = [FeedItem.from_ad(a) for a in ads[args.items:]]
    if len(items) < args.items or len(fillers) < 2:
        raise SystemExit(f"need {args.items} + 2 competitor ads with text, the run has {len(ads)}")
    brand = brand_name(json.loads((args.run / "app.json").read_text())["name"])
    checks = standard_checks(brand)
    calls = estimated_calls(len(items), len(checks), feeds_per_item=args.feeds_per_item,
                            viewers_per_feed=args.viewers_per_feed)
    estimate = calls * EST_USD_PER_CALL
    print(f"{len(checks)} twin checks + position · {calls} viewer calls ≈ ${estimate:.2f} (cap ${args.max_usd:.2f})")
    if args.dry_run:
        return 0
    try:
        Budget(args.max_usd).require(estimate)
    except BudgetExceeded as exc:
        raise SystemExit(str(exc)) from None

    model = ModelClient(load_settings(), budget_usd=args.max_usd)
    personas = personas_from_reach(ads, args.personas)
    result = run_suite(Viewer(model, reasoning_effort="low"), personas, items, fillers, checks,
                       feeds_per_item=args.feeds_per_item, viewers_per_feed=args.viewers_per_feed)
    for c in result.checks:
        print(f"  {'FLAG' if c.flagged else 'ok':>4}  {c.name:<12} effect {c.effect:+.2f}  p={c.p:.3f}  "
              f"({c.twin_picks} picks)")
    print(f"spent ${result.usd:.3f} · {result.failures} failed viewers · SIMULATED")
    out = REPO_ROOT / "outputs" / "experiments" / f"bias-{args.run.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"simulated": True, "args": {k: str(v) for k, v in vars(args).items()},
                               "brand": brand, "usd": result.usd, "failures": result.failures,
                               "flagged": result.flagged, "checks": [asdict(c) for c in result.checks]}, indent=2))
    print(f"details: {out.relative_to(REPO_ROOT)}")
    return 1 if result.flagged else 0


if __name__ == "__main__":
    sys.exit(main())
