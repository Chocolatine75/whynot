"""`whynot reproduce`: every number the demo and the README show, recomputed from what was logged (D-1).

No model is called: $0. Each claim names its source (a committed result file, a run folder, the cost ledgers),
recomputes the number from it, and compares with the number shown:
- `ok`: recomputed = shown (within rounding);
- `differs`: the shown number is wrong or stale (exit code 1, so it cannot slip into the demo);
- `missing`: the source is not on this machine (run folders live in `outputs/`, not in git) or has no data yet.
Committed sources (`validate/results/`) reproduce from a clean clone; run-based numbers need their run folder.
"""

import json
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from whynot.config import REPO_ROOT


@dataclass
class Claim:
    id: str
    what: str
    shown: str  # as the demo / README says it
    recomputed: str | None = None
    status: str = "missing"  # ok | differs | missing
    source: str = ""
    note: str = ""


def _close(a: float, b: float, tol: float) -> bool:
    return math.isfinite(a) and abs(a - b) <= tol


def _json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


# --- the claims -------------------------------------------------------------------------------------------------

def r3(root: Path) -> list[Claim]:
    """R3 v1: does the simulator predict which competitor ads run long? (committed result)."""
    p = root / "validate" / "results" / "r3-v1-apps-gb-v1.json"
    c1 = Claim("r3_within_auc", "R3 within-advertiser AUC, viewers (text)", "0.52 [0.44, 0.60]",
               source=str(p.relative_to(root)))
    c2 = Claim("r3_shorter_copy", "R3 baseline: shorter copy, within-advertiser AUC", "0.62",
               source=str(p.relative_to(root)))
    c3 = Claim("r3_sample", "R3 sample", "186 ads, 44 advertisers", source=str(p.relative_to(root)))
    if not p.exists():
        return [c1, c2, c3]
    d = _json(p)
    rows = {r["name"]: r for r in d["results"]}
    v, b = rows["viewers-text"], rows["baseline: shorter copy"]
    c1.recomputed = f"{v['within_auc']:.2f} [{v['within_ci'][0]:.2f}, {v['within_ci'][1]:.2f}]"
    c1.status = "ok" if c1.recomputed == c1.shown else "differs"
    c2.recomputed = f"{b['within_auc']:.2f}"
    c2.status = "ok" if c2.recomputed == c2.shown else "differs"
    c3.recomputed = f"{d['sample']['ads']} ads, {d['sample']['advertisers']} advertisers"
    c3.status = "ok" if c3.recomputed == c3.shown else "differs"
    return [c1, c2, c3]


def evolution(root: Path, run: str = "20261102-e6-tournament-vietbuddy") -> list[Claim]:
    """Evolution verdicts recomputed from the logged tournaments and retests (floor and verdict, E3-3)."""
    from whynot.agency.create import add_verdicts, pooled_floor

    p = root / "outputs" / "runs" / run / "evolution.json"
    c = Claim("evolution_vietbuddy", "Evolution: gen 2 beats gen 0 beyond the noise floor (simulated)",
              "2/2 (+3.89 vs floor 2.31; +3.46 vs 1.55)", source=f"outputs/runs/{run}/evolution.json")
    if not p.exists():
        return [c]
    d = _json(p)
    groups = [dict(g) for g in d["groups"]]
    for g in groups:
        g.pop("result", None)
    pooled = pooled_floor(groups)
    for g in groups:
        add_verdicts(g, pooled)
    res = [g["result"] for g in groups if "result" in g]
    improved = sum(r["verdict"] == "improved" for r in res)
    parts = "; ".join(f"+{r['difference']:.2f} vs {'floor ' if i == 0 else ''}{r['noise_floor']:.2f}"
                      for i, r in enumerate(res))
    c.recomputed = f"{improved}/{len(res)} ({parts})"
    c.status = "ok" if c.recomputed == c.shown else "differs"
    return [c]


def fake_world(root: Path, seeds: int = 60) -> list[Claim]:
    """The noisy fake world with a known better mutation (pure code, deterministic): found / false alarms."""
    c = Claim("evolution_fake_world", f"Fake world ({seeds} seeds): known better mutation found / false alarms",
              "92 % / 7 %", source="tests/test_evolution_tournament.py (noisy fake world)")
    test = root / "tests" / "test_evolution_tournament.py"
    if not test.exists():
        return [c]
    import importlib.util
    import sys
    sys.path.insert(0, str(root / "tests"))
    try:
        spec = importlib.util.spec_from_file_location("_fake_world", test)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        found = sum(mod.found(mod.run_evolution(s, good=mod.GOOD)[0]) for s in range(seeds))
        alarms = sum(mod.run_evolution(s, good=mod.GOOD, better_exists=False)[0]["result"]["verdict"] == "improved"
                     for s in range(seeds))
    finally:
        sys.path.remove(str(root / "tests"))
    c.recomputed = f"{round(100 * found / seeds)} % / {round(100 * alarms / seeds)} %"
    c.status = "ok" if c.recomputed == c.shown else "differs"
    return [c]


def pixel_guard(root: Path) -> list[Claim]:
    """Static ads whose product pixels were checked identical when they were made (guard results logged)."""
    c = Claim("pixel_guard", "Static ads with 0 product pixels changed (pixel guard, logged at creation)",
              "80/80", source="outputs/runs/*/variants.json")
    runs = sorted((root / "outputs" / "runs").glob("**/variants.json"))
    checked = passed = 0
    for p in runs:
        for v in _json(p):
            g = (v.get("guards") or {}).get("product_pixels_unchanged")
            if g is not None:
                checked += 1
                passed += g.get("passed") is True
    if not checked:
        return [c]
    c.recomputed = f"{passed}/{checked}"
    c.note = f"over {len(runs)} run folder(s) on this machine (the README's 80 = two runs: VietBuddy 56, WhatsApp 24)"
    c.status = "ok" if passed == checked else "differs"
    return [c]


def publishing(root: Path) -> list[Claim]:
    """Real-account publishing: what each paused test created, as read back and logged."""
    c = Claim("publishing_real", "Publishing on a real ad account: created, read back, PAUSED, $0 ad spend",
              "no issue, all PAUSED", source="outputs/runs/**/publish.json + agency/state.json")
    found = []
    for p in sorted((root / "outputs" / "runs").glob("**/agency/state.json")):
        s = _json(p)
        pub = (s.get("steps") or {}).get("publish") or {}
        out = pub.get("outputs") or {}
        if pub.get("status") == "ok" and out.get("paused_only") and out.get("committed_eur", 0) == 0:
            found.append(f"{p.parent.parent.name}: campaign {out.get('campaign')}, {out.get('objects')} objects")
    if not found:
        return [c]
    c.recomputed = f"{len(found)} paused real-account publish(es), €0 committed"
    c.note = "; ".join(found)
    c.status = "ok"
    return [c]


def images_cost(root: Path, run: str = "20261103-e2-2-images-vietbuddy") -> list[Claim]:
    p = root / "outputs" / "runs" / run / "simulation.json"
    c = Claim("images_cost_per_feed", "Simulated feed with pictures: cost per feed", "$0.0138",
              source=f"outputs/runs/{run}/simulation.json")
    if not p.exists():
        return [c]
    s = _json(p)
    c.recomputed = f"${s['usd'] / s['feeds']:.4f}"
    c.status = "ok" if c.recomputed == c.shown else "differs"
    return [c]


def spend(root: Path) -> list[Claim]:
    from whynot.costs import collect_ledgers, spend_report

    c = Claim("model_spend", "Total model spend logged on this machine, since the first call", "see `whynot costs`",
              source="outputs/costs.jsonl + outputs/runs/**/costs.jsonl")
    r = spend_report(collect_ledgers(root / "outputs"))
    if not r.calls:
        return [c]
    c.recomputed = f"${r.usd:.2f} ({r.calls} billed calls)"
    c.status = "ok"
    c.note = "the README's \"$5.5\" is stale if it differs from this"
    return [c]


CHECKS: list[Callable[[Path], list[Claim]]] = [r3, evolution, fake_world, pixel_guard, publishing, images_cost,
                                               spend]


def reproduce(root: Path = REPO_ROOT, *, checks: list[Callable[[Path], list[Claim]]] | None = None,
              fast: bool = False) -> list[Claim]:
    out: list[Claim] = []
    for check in checks or CHECKS:
        if fast and check is fake_world:
            continue
        try:
            out += check(root)
        except Exception as exc:  # a broken source is reported, never hidden
            out.append(Claim(check.__name__, check.__doc__ or check.__name__, "?", status="differs",
                             note=f"could not recompute: {type(exc).__name__}: {exc}"[:300]))
    return out


def report(claims: list[Claim]) -> str:
    mark = {"ok": "✓", "differs": "✗", "missing": "·"}
    lines = []
    for c in claims:
        got = c.recomputed if c.recomputed is not None else "(source not on this machine)"
        lines.append(f"{mark[c.status]} {c.what}\n    shown {c.shown} · recomputed {got}\n    from {c.source}"
                     + (f"\n    {c.note}" if c.note else ""))
    n = {s: sum(c.status == s for c in claims) for s in ("ok", "differs", "missing")}
    lines.append(f"\n{n['ok']} reproduced, {n['differs']} differ, {n['missing']} missing here · $0 (no model call)")
    return "\n".join(lines)


def to_json(claims: list[Claim]) -> list[dict[str, Any]]:
    return [asdict(c) for c in claims]
