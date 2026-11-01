"""E8-4: compare a frozen prediction with the pilot's real results (link CTR, read-only from Insights).

Usage (after a few days of delivery; the hash was posted before activation):
    uv run whynot predict --verify validate/predictions/pilot-2026-11-02.json --sha <posted hash>
    uv run python scripts/compare_predictions.py validate/predictions/pilot-2026-11-02.json outputs/runs/<run>
Prints the accuracy on pairs the noise lets anyone order, with a CI; writes the result next to the prediction.
The predictions are SIMULATED; the results are real.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from whynot.config import load_settings
from whynot.run.insights import MetaInsights
from whynot.run.meta import Account, MarketingClient, MetaError
from whynot.run.publish import PublishState
from whynot.validate.predictions import PredictionError, compare, results_by_variant, totals


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("prediction", type=Path)
    p.add_argument("run", type=Path)
    p.add_argument("--since", help="first day of results, YYYY-MM-DD (default: the prediction's day)")
    args = p.parse_args()

    doc = json.loads(args.prediction.read_text())
    state = PublishState.load(args.run / "publish.json")
    if state is None:
        print("✗ nothing was published from this run", file=sys.stderr)
        return 1
    s = load_settings()
    try:
        client = MarketingClient(Account(s.meta_ad_account_id or "", s.meta_token or ""), version=s.fb_api_version)
        ad_ids = [v for k, v in state.objects.items() if k.startswith("ad_")]
        since = date.fromisoformat(args.since or doc["created_at"][:10])
        daily = MetaInsights(client, objective=state.objective).fetch(ad_ids, since, date.today())
        result = compare(doc, results_by_variant(state.objects, totals(daily)))
    except (MetaError, PredictionError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    print(f"frozen ranking vs real CTR: {result.accuracy:.2f} [{result.ci[0]:.2f}, {result.ci[1]:.2f}] on "
          f"{result.pairs} pairs of {result.ads} ads (chance 0.50) · predictions SIMULATED, results real")
    out = args.prediction.with_name(args.prediction.stem + ".result.json")
    out.write_text(json.dumps({"prediction": args.prediction.name, "checked": date.today().isoformat(),
                               "accuracy": round(result.accuracy, 3), "ci": [round(x, 3) for x in result.ci],
                               "pairs": result.pairs, "ads": result.ads}, indent=2) + "\n")
    print(f"result: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
