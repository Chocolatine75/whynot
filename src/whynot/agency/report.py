"""The owner's report for a `create` run: what the agency found, made and proposes.

Plain language, every claim traceable: objections show the customer quote and
its source, simulated numbers are labelled SIMULATED, nothing is described as
launched unless the autopilot executed it. Reads only the run folder.
"""

import json
from pathlib import Path
from typing import Any


def _load(run: Path, name: str, default: Any = None) -> Any:
    p = run / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def spent_usd(run: Path) -> float:
    total = 0.0
    events = run / "events.jsonl"
    if events.exists():
        for line in events.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            if e.get("status") in ("ok", "error"):
                total += float(e.get("usd", 0))
    return total


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
            "- " + ("Each variant was tested in simulated feeds next to real competitor ads (SIMULATED)."
                    if sim.get("simulated") else f"Not simulated: {sim.get('reason', 'n/a')}."),
            f"- Proposed campaign: **{n_sets}** ad set(s), **{n_ads}** ads, "
            f"**€{plan.get('daily_total_eur', 0)}/day** (your cap: €{plan.get('daily_cap_eur', 0)}/day).",
            f"- Cost of this run (models): **${spent_usd(run):.2f}**.", ""]

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
                sim_line = (f"Simulated preference vs competitors: **{sc['preference_lift']:.2f}×** chance, "
                            f"intent {sc['mean_intent']:.1f}/5, {sc['views']} simulated views (SIMULATED)")
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
