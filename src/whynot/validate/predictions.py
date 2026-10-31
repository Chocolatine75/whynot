"""Predictions published before results (E8-4, R5): the simulator's ranking of the pilot's ads, frozen.

Before the pilot's ads go live, `freeze` writes the ranking of every planned ad to
`validate/predictions/<name>.json` and returns the SHA-256 of its canonical form. Commit the file and post the
hash publicly *before* activation: anyone can then check that the ranking was not edited after the results.

What the file holds: per ad set (one audience), the ads in predicted order with their simulated score and the
SHA-256 of their image (it proves which creative was meant, without publishing the copy). No ad text, no
partner metric. Files are never overwritten.

Comparison rule (fixed here, before any result): pairs of ads in the SAME ad set (same audience, same budget),
only pairs whose real link CTRs differ by more than noise (`backtest.separable`), pairwise accuracy with a
bootstrap CI over ads. Ads that never reached `min_impressions` are left out.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from whynot.validate.backtest import PastAd, R1Result, separable
from whynot.validate.stats import bootstrap_ci

RULE = ("pairs within the same ad set whose real link CTRs differ by more than 1.96 sigma (binomial); pairwise "
        "accuracy of the simulated ranking; bootstrap CI over ads; ads under the impression minimum left out")


class PredictionError(ValueError):
    pass


def canonical(doc: dict[str, Any]) -> bytes:
    return json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(doc: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(doc)).hexdigest()


def _file_sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def build(plan: dict[str, Any], run_dir: Path, *, name: str, now: datetime | None = None,
          min_impressions: int = 1000) -> dict[str, Any]:
    """The prediction document for a run's plan (`plan.json`): ads ranked by simulated score within each ad set."""
    sets = []
    for s in plan.get("ad_sets", []):
        ads = sorted(s.get("ads", []), key=lambda a: (-float(a.get("sim_score", 0.0)), a["variant_id"]))
        if not ads:
            continue
        sets.append({"audience": s["audience"]["persona"], "ads": [
            {"id": a["variant_id"], "rank": i, "sim_score": round(float(a.get("sim_score", 0.0)), 4),
             "image_sha256": _file_sha(Path(run_dir) / a["image_path"])} for i, a in enumerate(ads, 1)]})
    if not sets:
        raise PredictionError("the plan has no ads to predict")
    return {"version": 1, "name": name, "created_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
            "simulated": True, "metric": "link CTR", "min_impressions": min_impressions, "rule": RULE,
            "ad_sets": sets}


def freeze(doc: dict[str, Any], folder: Path) -> tuple[Path, str]:
    """Write the document once (never overwritten) and return (path, sha256 of its canonical form)."""
    path = Path(folder) / f"{doc['name']}.json"
    if path.exists():
        raise PredictionError(f"{path} already exists: predictions are never rewritten, use a new name")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(doc) + b"\n")
    return path, digest(doc)


def verify(path: Path, sha256: str) -> bool:
    """True when the file is exactly what the published hash says."""
    return digest(json.loads(Path(path).read_text(encoding="utf-8"))) == sha256.strip().lower()


def _pairs(doc: dict[str, Any], results: dict[str, PastAd]) -> list[tuple[str, str, str]]:
    """(ad set, ad a, ad b) for every comparable pair, a ranked above b by the prediction."""
    out = []
    for s in doc["ad_sets"]:
        ads = [a["id"] for a in s["ads"] if a["id"] in results and results[a["id"]].impressions
               >= doc["min_impressions"]]
        out += [(s["audience"], a, b) for i, a in enumerate(ads) for b in ads[i + 1:]]
    return out


def compare(doc: dict[str, Any], results: dict[str, PastAd], *, seed: int = 0) -> R1Result:
    """How often the frozen ranking ordered real CTRs right, on pairs the noise lets anyone order."""
    pairs = [p for p in _pairs(doc, results) if separable(results[p[1]], results[p[2]])]
    if not pairs:
        raise PredictionError("no pair of ads with clearly different CTRs yet: wait for more impressions")
    score = {a["id"]: a["sim_score"] for s in doc["ad_sets"] for a in s["ads"]}

    def right(a: str, b: str) -> float:  # a was ranked above b; equal simulated scores predicted nothing
        return 0.5 if score[a] == score[b] else float(results[a].ctr > results[b].ctr)

    def accuracy(chosen: list[tuple[str, str, str]]) -> float:
        if not chosen:
            raise ValueError("empty resample")
        return sum(right(a, b) for _, a, b in chosen) / len(chosen)

    ads = sorted({x for _, a, b in pairs for x in (a, b)})

    def resampled(idx: list[int]) -> float:
        picked: dict[str, int] = {}
        for i in idx:
            picked[ads[i]] = picked.get(ads[i], 0) + 1
        return accuracy([p for p in pairs for _ in range(picked.get(p[1], 0) * picked.get(p[2], 0))])

    return R1Result("frozen prediction", accuracy(pairs), bootstrap_ci(resampled, len(ads), seed=seed), len(pairs),
                    len(ads))


def results_by_variant(publish_objects: dict[str, str], metrics: dict[str, PastAd]) -> dict[str, PastAd]:
    """Real results keyed by our variant id: `publish.json` maps `ad_<variant>` to the Meta ad id."""
    out = {}
    for ref, meta_id in publish_objects.items():
        if ref.startswith("ad_") and meta_id in metrics:
            out[ref.removeprefix("ad_")] = metrics[meta_id]
    return out


def totals(daily: dict[str, list[Any]]) -> dict[str, PastAd]:
    """Daily Insights rows (`DailyMetrics` per Meta ad id) summed into one result per ad."""
    return {ad: PastAd(ad, "", "", "", None, round(sum(d.spend_eur for d in days), 2),
                       sum(d.impressions for d in days), sum(d.clicks for d in days),
                       sum(d.conversions for d in days)) for ad, days in daily.items()}
