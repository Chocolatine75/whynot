/**
 * The validation page's data: every reliability number we claim, read from `validate/results/*.json`
 * (written by the experiments, committed) and `validate/predictions/*.result.json`. Nothing is computed
 * here beyond picking the primary row and comparing it with the target in TARGETS.md: the numbers are the
 * files' numbers. A file this page can't read is listed, never silently dropped.
 */
import fs from "node:fs";
import path from "node:path";
import { REPO_ROOT, runsRoot } from "./runs";

export interface Row { name: string; value: number; ci: [number, number] | null; note?: string; primary: boolean; baseline: boolean }
export type Verdict = "meets target" | "above floor" | "no evidence" | "below chance";

export interface Experiment {
  id: string;
  title: string;
  question: string;
  metric: string;
  target: number;
  floor: number;
  date: string;
  sample: string;
  usd: number | null;
  rows: Row[];
  verdict: Verdict;
  method: string;
  limits: string[];
  command: string;
  file: string;
}

export interface ValidationView { experiments: Experiment[]; unread: string[] }

type Json = Record<string, unknown>;

const isBaseline = (name: string) => /baseline|shorter|longer|most_recent|judge/.test(name);
const pair = (x: unknown): [number, number] | null =>
  Array.isArray(x) && x.length === 2 && x.every((v) => typeof v === "number") ? [x[0], x[1]] : null;

/** Primary result vs the target: the CI must exclude chance (0.5) before any claim. */
export function verdict(row: Row | undefined, target: number, floor: number): Verdict {
  if (!row || !row.ci) return "no evidence";
  if (row.ci[1] < 0.5) return "below chance";
  if (row.ci[0] <= 0.5) return "no evidence";
  if (row.value >= target) return "meets target";
  return row.value > floor ? "above floor" : "no evidence";
}

const R3 = {
  question: "Does the simulator tell competitor ads that ran for months from ads stopped within two weeks?",
  metric: "AUC within advertiser (0.5 = chance)",
  method: "Real competitor ads from the Meta Ad Library: still running after 60 days vs stopped within 14. " +
    "Viewer agents react to feeds of these ads without knowing which lasted; we measure how often they prefer " +
    "the long-running one, comparing ads of the same advertiser. Baselines: a single-LLM judge and copy length.",
  limits: ["Longevity is a proxy for performance, not a measured result.", "One market (GB) and mostly app advertisers."],
};

function readR3v1(d: Json, file: string): Experiment {
  const design = (d.design ?? {}) as Json;
  const primaryName = String(design.primary ?? "").match(/\(([^)]+)\)/)?.[1] ?? "viewers-image";
  const rows: Row[] = ((d.results ?? []) as Json[]).filter((r) => typeof r.within_auc === "number").map((r) => ({
    name: String(r.name), value: Number(r.within_auc), ci: pair(r.within_ci), primary: r.name === primaryName,
    baseline: isBaseline(String(r.name)),
  }));
  const s = (d.sample ?? {}) as Json;
  return { id: path.basename(file, ".json"), title: `R3 · longevity ${String(d.experiment ?? "").replace(/^R3\s*/, "")}`,
    ...R3, limits: [...R3.limits, "Video ads are seen as their poster frame."], target: 0.65, floor: 0.55, date: String(d.date ?? ""), usd: typeof d.usd === "number" ? d.usd : null,
    sample: `${s.ads ?? "?"} ads from ${s.advertisers ?? "?"} advertisers`, rows,
    verdict: verdict(rows.find((r) => r.primary), 0.65, 0.55),
    command: "uv run --group capture python scripts/r3_v1.py --name apps-gb --reuse-ads", file };
}

function readR3v0(d: Json, file: string): Experiment {
  const w = (d.within_advertiser ?? {}) as Json;
  const s = (d.sample ?? {}) as Json;
  const rows: Row[] = [
    { name: "viewers-text", value: Number(w.auc_preference), ci: pair(w.ci_preference), primary: true, baseline: false },
    { name: "viewers-text (intent)", value: Number(w.auc_intent), ci: pair(w.ci_intent), primary: false, baseline: false },
    { name: "baseline: shorter copy", value: Number(w.auc_shorter_copy), ci: pair(w.ci_shorter_copy), primary: false,
      baseline: true },
  ].filter((r) => Number.isFinite(r.value));
  return { id: path.basename(file, ".json"), title: `R3 · longevity ${String(d.experiment ?? "").replace(/^R3\s*/, "")}`,
    ...R3, target: 0.65,
    floor: 0.55, date: String(d.date ?? ""), usd: typeof d.usd === "number" ? d.usd : null,
    sample: `${s.ads ?? "?"} ads, ${s.advertisers_with_both_classes ?? "?"} advertisers with both classes`, rows,
    verdict: verdict(rows[0], 0.65, 0.55), limits: [...R3.limits, "Classes were not balanced per advertiser (fixed in v1)."],
    command: "uv run python scripts/longevity_check.py ...", file };
}

function readR1(d: Json, file: string): Experiment {
  const results = (d.results ?? []) as Json[];
  const names = results.map((r) => String(r.name));
  const primaryName = names.includes("viewers-image") ? "viewers-image" : "viewers-text";
  const rows: Row[] = results.map((r) => ({
    name: String(r.name), value: Number(r.accuracy), ci: pair(r.ci), note: `${r.pairs} pairs`,
    primary: r.name === primaryName, baseline: isBaseline(String(r.name)),
  }));
  return { id: path.basename(file, ".json"), title: "R1 · the partner's past ads",
    question: "Does the simulator rank the partner's own past ads the way their real click-through rate did?",
    metric: "pairwise accuracy on real link CTR (0.5 = chance)", target: 0.65, floor: 0.55,
    date: String(d.date ?? ""), usd: typeof d.usd === "number" ? d.usd : null,
    sample: `${d.ads ?? "?"} ads, ${d.separable_pairs ?? "?"} pairs with clearly different CTRs`, rows,
    verdict: verdict(rows.find((r) => r.primary), 0.65, 0.55),
    method: "His past ads are shown to viewer agents without any result; their ranking is then compared with the " +
      "real CTR, only on pairs whose CTRs differ by more than chance. Protocol fixed before seeing his data.",
    limits: ["One advertiser.", "CTR, not installs: conversions are too few to rank ads."],
    command: `uv run python scripts/r1_backtest.py --name ${String(d.r1 ?? "...")} --csv data/private/partner/ads.csv --brand ...`,
    file };
}

function readPrediction(d: Json, file: string): Experiment {
  const row: Row = { name: "frozen ranking", value: Number(d.accuracy), ci: pair(d.ci), note: `${d.pairs} pairs`,
    primary: true, baseline: false };
  return { id: path.basename(file, ".json"), title: "R5 · predictions published before results",
    question: "Did the ranking we froze and hashed before launch match the pilot's real CTRs?",
    metric: "pairwise accuracy within ad sets (0.5 = chance)", target: 0.65, floor: 0.55,
    date: String(d.checked ?? ""), usd: null, sample: `${d.ads ?? "?"} ads live in the pilot`, rows: [row],
    verdict: verdict(row, 0.65, 0.55),
    method: "Before activation the ranking was written to a file whose SHA-256 was posted publicly; the file can be " +
      "checked with `whynot predict --verify`. Results are read from Meta after delivery.",
    limits: ["A few days of delivery on one account."], command: `uv run python scripts/compare_predictions.py ${
      String(d.prediction ?? "")} outputs/runs/<run>`, file };
}

/** Every result file we know how to read, newest first; the others are listed as unread. */
export function readValidation(root: string = REPO_ROOT): ValidationView {
  const view: ValidationView = { experiments: [], unread: [] };
  const sources: [string, RegExp][] = [[path.join(root, "validate", "results"), /\.json$/],
    [path.join(root, "validate", "predictions"), /\.result\.json$/]];
  for (const [dir, pattern] of sources) {
    if (!fs.existsSync(dir)) continue;
    for (const name of fs.readdirSync(dir).filter((n) => pattern.test(n)).sort()) {
      const rel = path.relative(root, path.join(dir, name));
      try {
        const d = JSON.parse(fs.readFileSync(path.join(dir, name), "utf8")) as Json;
        const exp = name.endsWith(".result.json") ? readPrediction(d, rel)
          : "r1" in d ? readR1(d, rel)
          : String(d.experiment ?? "").startsWith("R3 v1") ? readR3v1(d, rel)
          : String(d.experiment ?? "").startsWith("R3 v0") ? readR3v0(d, rel)
          : null;
        if (exp && exp.rows.length) view.experiments.push(exp);
        else view.unread.push(rel);
      } catch {
        view.unread.push(rel);
      }
    }
  }
  view.experiments.sort((a, b) => b.date.localeCompare(a.date) || b.id.localeCompare(a.id));  // newest version first
  return view;
}

// --- the claims summary: one line per thing we say about the agency, with its measured status ---------------

export type ClaimStatus = "passed" | "failed" | "not yet run";
export interface Claim { what: string; status: ClaimStatus; value: string; how: string }

/** Pixel guard and evolution verdicts counted over every run on disk; R1/R3 from the experiments above. */
export function readClaims(view: ValidationView, runs: string = runsRoot()): Claim[] {
  let ads = 0, real = 0, judged = 0, improved = 0;
  const dirs = fs.existsSync(runs) ? fs.readdirSync(runs, { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => path.join(runs, d.name)) : [];
  for (const dir of dirs) {
    try {
      const variants = JSON.parse(fs.readFileSync(path.join(dir, "variants.json"), "utf8")) as Json[];
      for (const v of variants) {
        const g = ((v.guards ?? {}) as Json).product_pixels_unchanged as Json | undefined;
        if (!g) continue;
        ads += 1;
        if (g.passed === true) real += 1;
      }
    } catch { /* a run without ads */ }
    try {
      const evo = JSON.parse(fs.readFileSync(path.join(dir, "evolution.json"), "utf8")) as Json;
      for (const g of (evo.groups ?? []) as Json[]) {
        const r = g.result as Json | undefined;
        if (!r) continue;
        judged += 1;
        if (r.verdict === "improved") improved += 1;
      }
    } catch { /* not evolved */ }
  }
  const latest = (prefix: string) => view.experiments.find((e) => e.title.startsWith(prefix));
  const r3 = latest("R3");
  const r1 = latest("R1");
  const p = (e: Experiment | undefined) => e?.rows.find((r) => r.primary);
  return [
    { what: "Your app is never invented", status: ads ? (real === ads ? "passed" : "failed") : "not yet run", value: ads ? `${real} / ${ads} ads` : "—",
      how: "Pixel check: the app screen in every ad is identical to the store screenshot." },
    { what: "Evolution beats the noise", status: judged ? (improved > 0 ? "passed" : "failed") : "not yet run", value: judged ? `${improved} / ${judged} audiences · simulated` : "—",
      how: "The evolved ad beats the original head to head, beyond a measured retest noise floor." },
    { what: "Ranks your past ads like real CTR (R1)", status: r1 ? (r1.verdict === "meets target" || r1.verdict === "above floor" ? "passed" : "failed") : "not yet run",
      value: p(r1) ? `${p(r1)!.value.toFixed(2)} accuracy` : "waiting for partner data", how: "Backtest on the design partner's own past ads, blind to results." },
    { what: "Predicts which competitor ads run long (R3)", status: r3 ? (r3.verdict === "meets target" || r3.verdict === "above floor" ? "passed" : "failed") : "not yet run",
      value: p(r3) ? `AUC ${p(r3)!.value.toFixed(2)}` : "—", how: "So we never use the simulator to forecast how long an ad will run." },
  ];
}
