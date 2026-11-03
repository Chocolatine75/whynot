import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { type Day, fatigued, readCrm, sumDays, totals } from "@/lib/crm";

let root: string;

const day = (d: string, spend: number, impressions: number, clicks: number, conversions = 0) =>
  ({ day: d, spend_eur: spend, impressions, clicks, conversions });

function run(id: string, files: Record<string, unknown>) {
  const dir = path.join(root, id);
  for (const [rel, body] of Object.entries({ "config.json": { app_ref: id, countries: ["US"], daily_cap_eur: 20 }, ...files })) {
    fs.mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true });
    fs.writeFileSync(path.join(dir, rel), typeof body === "string" ? body : JSON.stringify(body));
  }
  return dir;
}

beforeEach(() => {
  root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "whynot-crm-")));
});

describe("sums and ratios", () => {
  const d = (x: string, s: number, i: number, c: number, k = 0): Day => ({ day: x, spend: s, impressions: i, clicks: c, conversions: k });

  it("totals give CTR and cost per install, or nothing when undefined", () => {
    expect(totals([d("a", 10, 1000, 20, 2), d("b", 5, 1000, 10, 1)])).toEqual({ spend: 15, impressions: 2000, clicks: 30, conversions: 3, ctr: 0.015, cpa: 5 });
    expect(totals([])).toMatchObject({ ctr: null, cpa: null });
  });

  it("sums several ads day by day", () => {
    expect(sumDays([[d("2", 1, 10, 1)], [d("1", 2, 20, 2), d("2", 3, 30, 3)]]).map((x) => [x.day, x.spend])).toEqual([["1", 2], ["2", 4]]);
  });

  it("calls an ad tired when its click rate falls well below its start", () => {
    const fresh = [1, 2, 3].map((i) => d(`${i}`, 5, 1000, 20));
    expect(fatigued([...fresh, ...[4, 5, 6].map((i) => d(`${i}`, 5, 1000, 10))])).toBe(true);
    expect(fatigued([...fresh, ...[4, 5, 6].map((i) => d(`${i}`, 5, 1000, 18))])).toBe(false);
    expect(fatigued(fresh)).toBe(false); // too young to judge
  });
});

describe("the dashboard reads every app", () => {
  it("lists the daily loop's ads with results, the campaign's static ads, and the alerts", () => {
    run("a", {
      "app.json": { name: "Alpha", reviews: [] },
      "events.jsonl": JSON.stringify({ ts: "2026-11-01T10:00:00Z", stage: "report", status: "ok" }) + "\n",
      "plan.json": { ad_sets: [{ audience: { name: "Families" }, ads: [{ variant_id: "s1", headline_on_image: "Static one", image_path: "ads/s1.png" }] }] },
      "agency/memory.json": { ads: {
        "trend-1-x": { key: "trend-1-x", status: "live", hook: "pov: x", format: "pov", persona: "p", launched: "2026-11-01", file: "videos/trend-1-x.mp4",
          metrics: [day("2026-11-01", 12, 1000, 30, 1), day("2026-11-02", 10, 1000, 25, 1)], notes: [] },
        "trend-2-y": { key: "trend-2-y", status: "live", hook: "no installs", format: "skit", persona: "p", launched: "2026-11-01",
          metrics: [day("2026-11-01", 15, 900, 9), day("2026-11-02", 12, 800, 7)], notes: [] },
        "failed-1": { key: "failed-1", status: "failed", hook: "", metrics: [] },
      } },
      "agency/reports/2026-11-02.json": { simulated: true, waiting_approval: ["trend-3-z"], failures: ["voice/x: Timeout"],
        paused: [{ ad: "trend-0-old", why: "no install after €20" }], committed_eur: 18, cap_eur: 20 },
    });
    const crm = readCrm(root, Date.parse("2026-11-03T00:00:00Z"));
    expect(crm.apps).toHaveLength(1);
    const app = crm.apps[0];
    expect(app).toMatchObject({ appName: "Alpha", simulated: true, live: 2, ads: 3, capEur: 20, committedEur: 18 });
    expect(app.totals).toMatchObject({ spend: 49, impressions: 3700, clicks: 71, conversions: 2 });
    expect(crm.ads.map((a) => [a.kind, a.status])).toEqual([["video", "live"], ["video", "live"], ["static", "planned"]]); // the failed idea is not an ad
    expect(crm.simulated).toBe(true);
    const titles = crm.alerts.map((a) => `${a.level}: ${a.title}`);
    expect(titles[0]).toBe("action: 1 ad waits for your approval"); // actions first
    expect(titles).toContain("warn: no installs: €27 spent, no install");
    expect(titles).toContain("warn: Something failed yesterday");
    expect(titles).toContain("info: Paused trend-0-old");
    expect(titles).toContain("info: At the daily cap");
  });

  it("an app without the daily loop still shows, with no alert", () => {
    run("b", { "app.json": { name: "Beta", reviews: [] } });
    const crm = readCrm(root);
    expect(crm.apps.map((a) => a.appName)).toEqual(["Beta"]);
    expect(crm.alerts).toEqual([]);
    expect(crm.totals.ctr).toBeNull();
  });

  it("reads Python's NaN and Infinity as missing numbers", () => {
    run("d", { "app.json": { name: "Delta", reviews: [] },
      "agency/reports/2026-11-02.json": '{"simulated": true, "learnings": {"cpa": Infinity, "x": [NaN, -Infinity]}, "committed_eur": 20, "cap_eur": 20, "note": "NaN in text stays"}' });
    const crm = readCrm(root);
    expect(crm.apps[0]).toMatchObject({ simulated: true, capEur: 20 });
    expect(crm.alerts.map((a) => a.title)).toContain("At the daily cap");
  });

  it("a broken memory file never breaks the page", () => {
    run("c", { "app.json": { name: "Gamma", reviews: [] }, "agency/memory.json": "{ not json" });
    expect(readCrm(root).ads).toEqual([]);
  });
});
