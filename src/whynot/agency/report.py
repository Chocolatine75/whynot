"""The owner's report for a `create` run: what the agency found, made and proposes.

Plain language, every claim traceable: objections show the customer quote and
its source, simulated numbers are labelled SIMULATED, nothing is described as
launched unless the autopilot executed it. Reads only the run folder.
"""

import json
from pathlib import Path
from typing import Any

from whynot.events import EventLog, total_usd


def _load(run: Path, name: str, default: Any = None) -> Any:
    p = run / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def spent_usd(run: Path) -> float:
    """Model spend recorded in the run's event log (roll-up events skipped: never counted twice)."""
    return total_usd(EventLog(run / "events.jsonl").rows()) if (run / "events.jsonl").exists() else 0.0


def _cell(text: Any) -> str:
    return str(text).replace("|", "/").replace("\n", " ")


def build_report(run: Path) -> str:
    app = _load(run, "app.json", {})
    market = _load(run, "market.json", {})
    strategy = _load(run, "strategy.json", {})
    variants = _load(run, "variants.json", [])
    sim = _load(run, "simulation.json", {})
    plan = _load(run, "plan.json", {})
    launch = _load(run, "launch.json", [])
    config = _load(run, "config.json", {})
    scores = sim.get("scores", {})
    by_variant = {v["variant_id"]: v for v in variants}

    out: list[str] = [f"# Campaign proposal: {app.get('name', '?')}", ""]
    level = config.get("policy", {}).get("level", "dry_run")
    out += ["> **Status: not launched.** Everything below is a proposal, created PAUSED. "
            f"Autonomy level: `{level}`. Nothing is spent until you approve and set a live budget cap.", ""]

    passed = [v for v in variants if v.get("guards_passed")]
    n_sets = len(plan.get("ad_sets", []))
    n_ads = sum(len(s["ads"]) for s in plan.get("ad_sets", []))
    out += ["## Summary", "",
            f"- Researched **{market.get('advertisers_found', 0)}** advertisers, kept "
            f"**{len(market.get('competitors', []))}** real competitors, read **{market.get('ads', 0)}** of their ads "
            f"(Ad Library, {', '.join(market.get('research_countries', []))}).",
            f"- Read **{len(app.get('reviews', []))}** App Store reviews.",
            f"- **{len(strategy.get('personas', []))}** customer profiles, **{len(strategy.get('objections', []))}** "
            f"objections, **{len(strategy.get('angles', []))}** ad angles, all backed by quotes.",
            f"- Produced **{len(variants)}** ad variants; **{len(passed)}** passed every check "
            "(real app pixels, legibility, brand colours, Meta policy rules).",
            "- " + ("Each variant was tested head-to-head in simulated feeds next to real competitor ads, "
                    "against a placebo (a real competitor ad shown under our name) (SIMULATED)."
                    if sim.get("simulated") else f"Not simulated: {sim.get('reason', 'n/a')}."),
            f"- Proposed campaign: **{n_sets}** ad set(s), **{n_ads}** ads, "
            f"**€{plan.get('daily_total_eur', 0)}/day** (your cap: €{plan.get('daily_cap_eur', 0)}/day).",
            f"- Model spend for this campaign folder (all runs and redos): **${spent_usd(run):.2f}**.", ""]

    groups = sim.get("groups", [])
    if groups:
        out += ["## How reliable is the simulation?", "",
                "Each audience's feeds include placebos: real competitor ads shown under our name and layout. "
                "If placebos win as often as our ads, the setup, not the ad, is doing the work.", "",
                "| Audience | Placebo preference | Placebo intent | Placebo views | Verdict |", "|---|---|---|---|---|"]
        for g in groups:
            if "error" in g:
                out.append(f"| {g['persona']} ({g['language']}) | — | — | — | not judged: {_cell(g['error'])} |")
                continue
            verdict = "⚠ biased: rank within audience only" if g["biased"] else "usable for ranking"
            out.append(f"| {g['persona']} ({g['language']}) | {g['placebo_lift']:.2f}× | "
                       f"{g['placebo_intent']:.1f}/5 | {g.get('placebo_views', '?')} | {verdict} |")
        out.append("")

    evolution = _load(run, "evolution.json", {}) or {}
    if evolution.get("groups"):
        out += ["## How the ads evolved (SIMULATED)", "",
                "Each round, the best ads were changed in ONE element to answer what simulated viewers objected to, "
                "then re-tested against their parents and placebos in fresh feeds.", ""]
        for g in evolution["groups"]:
            chain, vid = [], g.get("champion")
            while vid:  # champion back to its generation-0 ancestor
                chain.append(by_variant[vid])
                vid = by_variant[vid].get("parent_id")
            chain.reverse()
            out += [f"### {g['persona']} ({g['language']})", ""]
            rounds = [h for h in g["history"] if "scores" in h]
            out += ["| Round | Best ad | vs placebo | Intent |", "|---|---|---|---|"]
            for h in rounds:
                best = h["kept"][0] if h["kept"] else None
                s = h["scores"].get(best, {}) if best else {}
                hook = _cell(by_variant.get(best, {}).get("texts", {}).get("hook", "")) if best else "—"
                out.append(f"| {h['generation']} | {hook} | {s.get('lift_over_placebo', 0):+.2f} | "
                           f"{s.get('intent', 0):.1f}/5 |")
            stopped = [h for h in g["history"] if h.get("stopped")]
            if stopped:
                out.append(f"\nStopped at round {stopped[0]['generation']}: {stopped[0]['stopped']}.")
            out += ["", "Lineage of the winning ad:", ""]
            for v in chain:
                m = v.get("mutation")
                change = f" — changed **{m['gene']}**: “{m['text']}” ({m['why']})" if m else " — original"
                out.append(f"- Gen {v.get('generation', 0)}: ![{v['variant_id']}]({v['image']}){change}")
            out.append("")

    if plan.get("errors"):
        out += ["## ⚠ The plan has problems", ""] + [f"- {e}" for e in plan["errors"]] + [""]

    out += ["## Positioning", "", strategy.get("positioning", ""), ""]

    objections = {o["id"]: o for o in strategy.get("objections", [])}
    out += ["## Who we target", "", "| Profile | Ages | Gender | Countries | Wants | Hesitates because |",
            "|---|---|---|---|---|---|"]
    for p in strategy.get("personas", []):
        hes = "; ".join(objections[o]["text"] for o in p["objections"] if o in objections)
        wants = _cell("; ".join(p["motivations"]))
        out.append(f"| **{_cell(p['name'])}**: {_cell(p['description'])} | {p['age_min']}–{p['age_max']} | "
                   f"{p['gender']} | {', '.join(p['countries'])} | {wants} | {_cell(hes)} |")
    out.append("")

    out += ["## Why people don't buy (and how the ads answer)", ""]
    for o in strategy.get("objections", []):
        quotes = "; ".join(f"“{e['quote']}” ({e['ref']})" for e in o["evidence"])
        out += [f"- **{o['text']}** → {o['answer']}  ", f"  Evidence: {quotes}"]
    out.append("")

    comps = market.get("competitors", [])
    if comps:
        names = {a["page_id"]: a["page_name"] for a in market.get("advertisers", [])}
        out += ["## Competitors in the market", ""]
        out += [f"- {names.get(c['page_id'], c['page_id'])}: {c['why']}" for c in comps]
        rejected = market.get("rejected", [])
        if rejected:
            out += ["", f"Ignored {len(rejected)} unrelated advertisers found by keyword search."]
        out.append("")

    out += ["## Proposed campaign", ""]
    launch_by = {x["ad_set"]: x for x in launch}
    for s in plan.get("ad_sets", []):
        decision = launch_by.get(s["name"], {})
        out += [f"### {s['audience']['name']} · {s['name']} · €{s['daily_budget_eur']}/day",
                f"Launch: **{decision.get('outcome', '?')}** ({decision.get('why', '')})", ""]
        for ad in s["ads"]:
            v = by_variant.get(ad["variant_id"], {})
            t = v.get("texts", {})
            sc = scores.get(ad["variant_id"])
            sim_line = "Not simulated"
            if sc:
                sim_line = (f"Preference **{sc['lift']:.2f}×** chance, **{sc['lift_over_placebo']:+.2f}** vs a real "
                            "competitor ad shown under our name; "
                            f"intent {sc['intent']:.1f}/5 ({sc['intent_vs_placebo']:+.1f} vs placebo); "
                            f"{sc['views']} simulated views (SIMULATED)")
                if sc.get("biased_group"):
                    sim_line += " ⚠ placebo also won here: ranking within this audience only"
            why = f" · Top objection: “{sc['top_why_not'][0]}”" if sc and sc.get("top_why_not") else ""
            out += [f"![{ad['variant_id']}]({ad['image_path']})", "",
                    f"- **Primary text:** {t.get('body', '')}", f"- **Headline:** {t.get('title', '')} · "
                    f"**Button:** {ad['cta']}", f"- {sim_line}{why}", ""]

    if plan.get("notes") or strategy.get("notes"):
        out += ["## Notes and limits", ""] + [f"- {n}" for n in plan.get("notes", []) + strategy.get("notes", [])]
        out.append("")
    out += ["## Before launch, you need", "",
            "- Your Meta ad account id, Facebook page id and Meta app id (for app-install campaigns).",
            "- To set a live daily cap and approve the first launch. whynot never spends above the cap.",
            "- Simulated scores rank the ads; real results decide. "
            "The agency adjusts daily from real installs and cost.",
            ""]
    return "\n".join(out)


def write_report(run: Path) -> Path:
    path = Path(run) / "report.md"
    path.write_text(build_report(Path(run)), encoding="utf-8")
    return path
