"""Where does the simulator's preference for our ads come from? Placebo and ablation runs on a `create` run.

Each condition puts ONE item labelled as the app in feeds with real competitor ads and measures its
preference lift (1.0 = chance). Conditions:
  current      our variants, viewers carry the objections the ads answer (the create v0 setup)
  placebo      a real competitor ad presented as the app's ad, same viewers: any lift here is bias
  neutral      our variants, viewers with demographics + motivation only (no objections)
  placebo_neu  the placebo with neutral viewers
All numbers are SIMULATED. Usage:
  uv run python scripts/sim_bias_check.py outputs/runs/<run> --max-usd 0.6
"""

import argparse
import json
import random
from dataclasses import replace
from pathlib import Path

from whynot.agency.create import viewer_personas
from whynot.agents.strategist import Strategy
from whynot.ingest.adlibrary import load_jsonl
from whynot.models import ModelClient
from whynot.sim.feed import FeedItem, build_candidate_feeds
from whynot.sim.scores import score_ads
from whynot.sim.viewer import Viewer, run_simulation

EST_USD_PER_CALL = 0.0065


def ours_item(v: dict, app_name: str) -> FeedItem:
    t = v["texts"]
    return FeedItem(v["variant_id"], app_name, t["title"],
                    f"{t['body']}\n[image text: {t['hook']}" + (f" — {t['proof']}" if t.get("proof") else "") + "]")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("run", type=Path)
    p.add_argument("--items", type=int, default=6, help="items per condition")
    p.add_argument("--feeds", type=int, default=2, help="feeds per item")
    p.add_argument("--viewers", type=int, default=2, help="viewers per feed")
    p.add_argument("--max-usd", type=float, default=0.6)
    p.add_argument("--only", nargs="+", help="run only these conditions")
    args = p.parse_args()

    run = args.run
    app = json.loads((run / "app.json").read_text())
    strategy = Strategy.from_json(json.loads((run / "strategy.json").read_text()))
    ads = [a for a in load_jsonl(run / "market_ads.jsonl") if (a.bodies or [""])[0].strip()]
    variants = [v for v in json.loads((run / "variants.json").read_text()) if v.get("guards_passed")]
    rng = random.Random(0)
    persona = strategy.personas[0]
    mine = [v for v in variants if v["persona"] == persona.id][: args.items]
    placebo_ads = rng.sample(ads, args.items)
    pool = [FeedItem.from_ad(a) for a in ads]

    objections = {o.id: o.text for o in strategy.objections}
    loaded = viewer_personas(persona, objections, 3)
    neutral = [replace(x, traits=x.traits[:2]) for x in loaded]  # description + wants, no objections

    def placebo(a):  # a real competitor ad, presented exactly like ours
        return FeedItem(f"placebo-{a.id}", app["name"], (a.titles or [""])[0],
                        (a.bodies or [""])[0] + "\n[image text: " + (a.titles or [""])[0] + "]")

    def placebo_named(a):  # same ad, app name, competitor-style text (no image-text line)
        return FeedItem(f"placebo-{a.id}", app["name"], (a.titles or [""])[0], (a.bodies or [""])[0])

    def control(a):  # the ad exactly as a competitor: should sit near 1.0 if the feed is fair
        return replace(FeedItem.from_ad(a), ad_id=f"placebo-{a.id}")

    all_conditions = {
        "current": ([ours_item(v, app["name"]) for v in mine], loaded),
        "placebo": ([placebo(a) for a in placebo_ads], loaded),
        "neutral": ([ours_item(v, app["name"]) for v in mine], neutral),
        "placebo_neu": ([placebo(a) for a in placebo_ads], neutral),
        "placebo_name_only": ([placebo_named(a) for a in placebo_ads], neutral),
        "control": ([control(a) for a in placebo_ads], neutral),
    }
    conditions = {k: v for k, v in all_conditions.items() if not args.only or k in args.only}
    calls = len(conditions) * args.items * args.feeds * args.viewers
    print(f"{calls} viewer calls ≈ ${calls * EST_USD_PER_CALL:.2f}")
    if calls * EST_USD_PER_CALL > args.max_usd:
        raise SystemExit("above --max-usd")

    viewer = Viewer(ModelClient(budget_usd=args.max_usd * 1.5), reasoning_effort="low")
    out = {}
    for name, (items, personas) in conditions.items():
        feeds = []
        for i, item in enumerate(items):
            others = [c for c in pool if c.ad_id != item.ad_id.removeprefix("placebo-")]
            feeds += build_candidate_feeds(item, others, feed_size=4, n_feeds=args.feeds, seed=i)
        sim = run_simulation(viewer, personas, feeds, viewers_per_feed=args.viewers)
        scores = score_ads(sim.reactions)
        lifts = [scores[i.ad_id].preference_lift for i in items if i.ad_id in scores]
        intents = [scores[i.ad_id].mean_intent for i in items if i.ad_id in scores]
        out[name] = {"mean_lift": sum(lifts) / len(lifts), "lifts": lifts, "mean_intent": sum(intents) / len(intents),
                     "failures": len(sim.failures), "usd": sim.usd}
        print(f"{name:12s} lift {out[name]['mean_lift']:.2f}× (n={len(lifts)})  intent {out[name]['mean_intent']:.2f}"
              f"  failures {len(sim.failures)}  ${sim.usd:.3f}")
    dest = run / "bias_check.json"
    previous = json.loads(dest.read_text()) if dest.exists() else {}
    dest.write_text(json.dumps({**previous, "simulated": True, **out}, indent=2))
    print(f"details: {dest}")


if __name__ == "__main__":
    main()
