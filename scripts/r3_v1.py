"""R3 v1: does the simulator tell competitor ads that last from ads stopped fast, within one advertiser?

What changed since v0 (`longevity_check.py`, AUC 0.49, no evidence):
- selection: only advertisers with both classes, the same number of each (`select_paired`);
- primary metric: within-advertiser AUC with a CI that resamples advertisers (`stratified_auc`);
- images: the viewers and the judge can see each ad's real creative (`ingest/creatives.py`);
- baselines: a simple judge (one call per ad, no personas, no feed), shorter copy, and chance.

Conditions, on the same ads, feeds and personas: viewers-text, viewers-image, judge-text, judge-image.
When an image condition is on, only ads whose creative was captured are used (all conditions alike).
All scores are simulated. Cost is estimated first and the run refused above --max-usd; a hard cap also
stops it during the run. Viewer and judge answers are cached; record cassettes with WHYNOT_CASSETTE=record.

Usage:
    uv run --group capture python scripts/r3_v1.py --name apps-gb --page-ids-file pages.txt --dry-run
    VIEWER_BACKEND=baseten uv run --group capture python scripts/r3_v1.py --name apps-gb --page-ids-file pages.txt
"""

import argparse
import json
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from whynot.budget import Budget, BudgetExceeded, CallEstimate, estimate_usd
from whynot.config import REPO_ROOT, load_settings
from whynot.ingest.adlibrary import AdLibraryClient, AdLibraryError, load_jsonl, save_jsonl
from whynot.ingest.creatives import CreativeStore, capture
from whynot.models import ModelClient, image_data_url
from whynot.sim.feed import FeedItem, build_market_feeds
from whynot.sim.personas import personas_from_reach
from whynot.sim.scores import score_ads
from whynot.sim.viewer import Viewer, ViewerCache, run_simulation
from whynot.validate.judge import Judge
from whynot.validate.longevity import LabelledAd, advertiser, select_paired
from whynot.validate.stats import auc, auc_ci, stratified_auc, stratified_auc_ci

PAGE_IDS_PER_CALL = 10  # the Ad Library refuses more search_page_ids in one call
CONDITIONS = ("viewers-text", "viewers-image", "judge-text", "judge-image")
# Token sizes for the estimate (Muse Spark Open, low effort), from R3 v0: ~1,500 in / ~700 out per text feed.
# An image is assumed to cost 1,000 input tokens at 512 px: deliberately high until measured.
FEED_TEXT_IN, FEED_OUT, IMAGE_IN, JUDGE_IN, JUDGE_OUT = 1500, 900, 1000, 350, 500


def fetch(args, today: date) -> list:
    cache = REPO_ROOT / "data" / "cache" / "adlibrary"
    active, inactive = cache / f"{args.name}-active.jsonl", cache / f"{args.name}-inactive.jsonl"
    if args.reuse_ads and active.exists() and inactive.exists():
        return load_jsonl(active) + load_jsonl(inactive)
    settings = load_settings()
    lib = AdLibraryClient(settings.fb_token or "", version=settings.fb_api_version)
    long_ads, old_ads = [], []
    try:
        for i in range(0, len(args.page_ids), PAGE_IDS_PER_CALL):
            chunk = args.page_ids[i:i + PAGE_IDS_PER_CALL]
            long_ads += lib.search(countries=args.countries, page_ids=chunk, active_status="ACTIVE",
                                   delivery_date_max=today - timedelta(days=args.long_days), max_ads=500)
            old_ads += lib.search(countries=args.countries, page_ids=chunk, active_status="INACTIVE", max_ads=1500)
    except AdLibraryError as exc:
        raise SystemExit(f"Ad Library: {exc}") from None
    save_jsonl(long_ads, active)
    save_jsonl(old_ads, inactive)
    return long_ads + old_ads


def estimate(n_feeds: int, viewers: int, feed_size: int, n_ads: int, conditions: list[str]) -> float:
    model = "meta-models/muse-spark-open-1026"
    calls = []
    if "viewers-text" in conditions:
        calls.append(CallEstimate(model, FEED_TEXT_IN, FEED_OUT, n_feeds * viewers))
    if "viewers-image" in conditions:
        calls.append(CallEstimate(model, FEED_TEXT_IN + feed_size * IMAGE_IN, FEED_OUT, n_feeds * viewers))
    if "judge-text" in conditions:
        calls.append(CallEstimate(model, JUDGE_IN, JUDGE_OUT, n_ads))
    if "judge-image" in conditions:
        calls.append(CallEstimate(model, JUDGE_IN + IMAGE_IN, JUDGE_OUT, n_ads))
    return estimate_usd(*calls)


def metric(name: str, scores: dict[str, float], labelled: list[LabelledAd], seed: int = 0) -> dict:
    rows = [la for la in labelled if la.ad.id in scores]
    s = [scores[la.ad.id] for la in rows]
    y = [la.long_running for la in rows]
    g = [advertiser(la.ad) for la in rows]
    out = {"name": name, "ads": len(rows), "advertisers": len(set(g))}
    try:
        out["within_auc"] = round(stratified_auc(s, y, g), 3)
        out["within_ci"] = [round(x, 3) for x in stratified_auc_ci(s, y, g, seed=seed)]
        out["pooled_auc"] = round(auc(s, y), 3)
        out["pooled_ci"] = [round(x, 3) for x in auc_ci(s, y, seed=seed)]
    except ValueError as exc:
        out["error"] = str(exc)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--name", required=True)
    p.add_argument("--page-ids", nargs="*", default=[])
    p.add_argument("--page-ids-file", type=Path)
    p.add_argument("--countries", nargs="+", default=["GB"])
    p.add_argument("--per-advertiser", type=int, default=4)
    p.add_argument("--long-days", type=int, default=60)
    p.add_argument("--short-days", type=int, default=14)
    p.add_argument("--feed-size", type=int, default=5)
    p.add_argument("--appearances", type=int, default=3)
    p.add_argument("--viewers-per-feed", type=int, default=3)
    p.add_argument("--personas", type=int, default=30)
    p.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=CONDITIONS)
    p.add_argument("--max-usd", type=float, default=8.0)
    p.add_argument("--reuse-ads", action="store_true", help="use the cached Ad Library fetch for --name")
    p.add_argument("--dry-run", action="store_true", help="fetch, select and capture images; no model calls")
    args = p.parse_args()
    if args.page_ids_file:
        args.page_ids += args.page_ids_file.read_text().split()
    if not args.page_ids and not args.reuse_ads:
        raise SystemExit("give --page-ids or --page-ids-file")

    today = date.today()
    ads = fetch(args, today)
    candidates = select_paired(ads, as_of=today, per_advertiser=10_000, long_days=args.long_days,
                               short_days=args.short_days)  # every usable pair, before images
    print(f"fetched {len(ads)} ads → {len(candidates)} usable in "
          f"{len({advertiser(la.ad) for la in candidates})} advertisers with both classes")

    images_on = any(c.endswith("image") for c in args.conditions)
    store = CreativeStore(REPO_ROOT / "data" / "cache" / "creatives")
    if images_on:
        from whynot.ingest.creatives import PlaywrightRenderer

        todo = [la.ad for la in candidates if not store.has(la.ad.id)]
        print(f"capturing {len(todo)} creatives ({len(candidates) - len(todo)} already on disk)...")
        if todo:
            renderer = PlaywrightRenderer()
            try:
                report = capture(todo, store, token=load_settings().fb_token or "", renderer=renderer,
                                 progress=lambda n, _: print(f"  {n}/{len(todo)}", flush=True) if n % 25 == 0 else None)
            finally:
                renderer.close()
            print(f"  captured {len(report.captured)}, failed {len(report.failed)}")
            for ad_id, why in list(report.failed.items())[:5]:
                print(f"    {ad_id}: {why}")
        with_image = [la.ad for la in candidates if store.has(la.ad.id)]
        labelled = select_paired(with_image, as_of=today, per_advertiser=args.per_advertiser,
                                 long_days=args.long_days, short_days=args.short_days)
    else:
        labelled = select_paired([la.ad for la in candidates], as_of=today, per_advertiser=args.per_advertiser,
                                 long_days=args.long_days, short_days=args.short_days)
    n_adv = len({advertiser(la.ad) for la in labelled})
    print(f"selected {len(labelled)} ads ({len(labelled) // 2} per class) from {n_adv} advertisers")
    if n_adv < 5:
        raise SystemExit("fewer than 5 advertisers with both classes: add advertisers")

    personas = personas_from_reach(ads, args.personas)
    text_items = [FeedItem.from_ad(la.ad) for la in labelled]
    feeds = build_market_feeds(text_items, feed_size=args.feed_size, appearances=args.appearances)
    cost = estimate(len(feeds), args.viewers_per_feed, args.feed_size, len(labelled), args.conditions)
    print(f"{len(personas)} personas, {len(feeds)} feeds × {args.viewers_per_feed} viewers; conditions "
          f"{', '.join(args.conditions)} ≈ ${cost:.2f} before cache (cap ${args.max_usd:.2f})")
    if args.dry_run:
        return
    try:
        Budget(args.max_usd).require(cost)
    except BudgetExceeded as exc:
        raise SystemExit(str(exc)) from None

    settings = load_settings()
    model = ModelClient(settings, budget_usd=args.max_usd)
    image = {la.ad.id: image_data_url(store.path(la.ad.id)) for la in labelled if store.has(la.ad.id)}

    def with_images(items: list[FeedItem]) -> list[FeedItem]:
        return [replace(it, image_url=image.get(it.ad_id)) for it in items]

    results, details = [], {}
    for cond in args.conditions:
        spent_before = model.spent_usd
        if cond.startswith("viewers"):
            run_feeds = [with_images(f) if cond.endswith("image") else f for f in feeds]
            viewer = Viewer(model, reasoning_effort="low")
            sim = run_simulation(viewer, personas, run_feeds, viewers_per_feed=args.viewers_per_feed)
            scored = score_ads(sim.reactions)
            scores = {k: v.preference_lift for k, v in scored.items()}
            intent = {k: v.mean_intent for k, v in scored.items()}
            results.append({**metric(cond, scores, labelled), "failures": len(sim.failures)})
            results.append({**metric(cond + " (intent)", intent, labelled), "failures": len(sim.failures)})
            details[cond] = {k: {"preference_lift": v.preference_lift, "mean_intent": v.mean_intent,
                                 "top_why_not": v.top_why_not} for k, v in scored.items()}
        else:
            items = with_images(text_items) if cond.endswith("image") else text_items
            judged = Judge(model, cache=ViewerCache(REPO_ROOT / "data" / "cache" / "judge")).run(items)
            results.append({**metric(cond, judged.scores, labelled), "failures": len(judged.failures)})
            details[cond] = {k: {"score": v, "why": judged.why.get(k, "")} for k, v in judged.scores.items()}
        results[-1]["usd"] = round(model.spent_usd - spent_before, 3)
        print(f"  {cond}: {results[-1]}", flush=True)

    shorter = {la.ad.id: -float(len((la.ad.bodies or [""])[0])) for la in labelled}
    results.append(metric("baseline: shorter copy", shorter, labelled))
    print("\n  condition                     within-advertiser AUC (95% CI)   pooled AUC")
    for r in results:
        if "within_auc" in r:
            print(f"  {r['name']:28s}  {r['within_auc']:.2f} [{r['within_ci'][0]:.2f}, {r['within_ci'][1]:.2f}]"
                  f"          {r['pooled_auc']:.2f}")
    print(f"  {'chance':28s}  0.50\nspent ${model.spent_usd:.2f} (cap ${args.max_usd:.2f})")

    summary = {
        "simulated": True, "experiment": "R3 v1", "date": today.isoformat(),
        "design": {"countries": args.countries, "long_days": args.long_days, "short_days": args.short_days,
                   "per_advertiser": args.per_advertiser, "feed_size": args.feed_size,
                   "appearances": args.appearances, "viewers_per_feed": args.viewers_per_feed,
                   "personas": args.personas, "primary": "within-advertiser AUC of preference lift (viewers-image)"},
        "viewer": {"backend": settings.viewer_backend, "model": model.viewer_model, "reasoning_effort": "low"},
        "sample": {"ads": len(labelled), "advertisers": n_adv,
                   "videos_as_poster": sum(1 for la in labelled if (i := store.info(la.ad.id)) and i.kind == "video")},
        "results": results, "usd": round(model.spent_usd, 3),
    }
    out = REPO_ROOT / "validate" / "results" / f"r3-v1-{args.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    detail_path = REPO_ROOT / "outputs" / "experiments" / f"r3-v1-{args.name}-details.json"
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text(json.dumps({
        "ads": [{"id": la.ad.id, "advertiser": la.ad.page_name, "long_running": la.long_running,
                 "days": la.ad.longevity_days(today), "body": (la.ad.bodies or [""])[0][:300]} for la in labelled],
        "scores": details}, indent=1, ensure_ascii=False))
    print(f"summary: {out.relative_to(REPO_ROOT)} · details: {detail_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
