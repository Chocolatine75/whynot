import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { REPO_ROOT } from "@/lib/runs";
import { readValidation, verdict } from "@/lib/validation";

function repo(files: Record<string, unknown>): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "val-"));
  for (const [rel, body] of Object.entries(files)) {
    const p = path.join(root, rel);
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(p, typeof body === "string" ? body : JSON.stringify(body));
  }
  return root;
}

const R1 = { r1: "partner", metric: "link CTR", ads: 14, separable_pairs: 64, usd: 0.15, simulated_scores: true,
  date: "2026-11-02", results: [
    { name: "viewers-text", accuracy: 0.71, ci: [0.6, 0.82], pairs: 64 },
    { name: "judge-text", accuracy: 0.55, ci: [0.43, 0.66], pairs: 64 },
    { name: "shorter_copy", accuracy: 0.48, ci: [0.37, 0.6], pairs: 64 }] };

describe("verdicts never claim more than the interval allows", () => {
  const row = (value: number, lo: number, hi: number) => ({ name: "x", value, ci: [lo, hi] as [number, number], primary: true, baseline: false });
  it("needs the CI to exclude chance", () => {
    expect(verdict(row(0.7, 0.6, 0.8), 0.65, 0.55)).toBe("meets target");
    expect(verdict(row(0.6, 0.52, 0.7), 0.65, 0.55)).toBe("above floor");
    expect(verdict(row(0.7, 0.45, 0.9), 0.65, 0.55)).toBe("no evidence");  // high value, CI includes 0.5
    expect(verdict(row(0.41, 0.36, 0.47), 0.65, 0.55)).toBe("below chance");
    expect(verdict(undefined, 0.65, 0.55)).toBe("no evidence");
  });
});

describe("reading result files", () => {
  it("reads R1 with its primary row and baselines, newest first", () => {
    const root = repo({ "validate/results/r1-partner.json": R1,
      "validate/results/r3-v1-x.json": { experiment: "R3 v1", date: "2026-10-30", usd: 0.34,
        design: { primary: "within-advertiser AUC of preference lift (viewers-image)" },
        sample: { ads: 186, advertisers: 44 },
        results: [{ name: "viewers-image", within_auc: 0.414, within_ci: [0.363, 0.473] },
          { name: "baseline: shorter copy", within_auc: 0.624, within_ci: [0.52, 0.73] }] } });
    const { experiments, unread } = readValidation(root);
    expect(unread).toEqual([]);
    expect(experiments.map((e) => e.title)).toEqual(["R1 · the partner's past ads", "R3 · longevity v1"]);
    const r1 = experiments[0];
    expect(r1.verdict).toBe("meets target");
    expect(r1.rows.find((r) => r.primary)?.name).toBe("viewers-text");
    expect(r1.rows.filter((r) => r.baseline).map((r) => r.name)).toEqual(["judge-text", "shorter_copy"]);
    expect(experiments[1].verdict).toBe("below chance");
  });

  it("lists files it cannot read instead of hiding them", () => {
    const root = repo({ "validate/results/broken.json": "{not json", "validate/results/other.json": { hello: 1 },
      "validate/predictions/pilot.json": { not: "a result" },
      "validate/predictions/pilot.result.json": { prediction: "pilot.json", checked: "2026-11-04", accuracy: 0.6,
        ci: [0.4, 0.8], pairs: 6, ads: 5 } });
    const { experiments, unread } = readValidation(root);
    expect(unread.sort()).toEqual(["validate/results/broken.json", "validate/results/other.json"]);
    expect(experiments.map((e) => e.verdict)).toEqual(["no evidence"]);  // the prediction file itself is not a result
  });

  it("reads the repo's real result files without error", () => {
    const { experiments, unread } = readValidation(REPO_ROOT);
    expect(unread).toEqual([]);
    expect(experiments.length).toBeGreaterThanOrEqual(2);
    for (const e of experiments) expect(e.rows.every((r) => Number.isFinite(r.value))).toBe(true);
    const r3 = experiments.filter((e) => e.title.startsWith("R3")).map((e) => e.title);
    expect(r3.indexOf("R3 · longevity v1")).toBeLessThan(r3.findIndex((t) => t.includes("v0")));
  });
});
