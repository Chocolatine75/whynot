import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { byteRange } from "@/lib/range";
import { readMarketAds, readRun, readVideos, resolveRunFile } from "@/lib/runs";

let root: string;
let dir: string;

beforeEach(() => {
  root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "whynot-media-")));
  dir = path.join(root, "r");
  fs.mkdirSync(path.join(dir, "videos"), { recursive: true });
  fs.writeFileSync(path.join(dir, "config.json"), "{}");
});

const video = (n: number, extra: Record<string, unknown> = {}) => ({
  brief: { hook: `hook ${n}`, format: "pov", persona: "p", tone: n === 2 ? "humor" : undefined },
  file: { path: `trend-${n}-x.mp4`, seconds: 16, loudness: { lufs: -14.2 }, qa: { flags: [], word_error_rate: 0.08 } },
  poster: `trend-${n}-x.poster.jpg`, why: "because", ...extra,
});

describe("video ads", () => {
  it("merges every trends file, keeps files on disk, newest first", () => {
    for (const [i, n] of [1, 2, 10].entries()) {
      const f = path.join(dir, "videos", `trend-${n}-x.mp4`);
      fs.writeFileSync(f, "mp4");
      fs.utimesSync(f, 1_700_000_000 + i, 1_700_000_000 + i); // rendered in this order
    }
    fs.writeFileSync(path.join(dir, "videos", "trend-2-x.poster.jpg"), "jpg");
    fs.writeFileSync(path.join(dir, "videos", "trends-1.json"), JSON.stringify({ videos: [video(1), video(2), video(3)] }));
    fs.writeFileSync(path.join(dir, "videos", "trends.json"), JSON.stringify({ videos: [video(10)] }));
    fs.writeFileSync(path.join(dir, "videos", "trends-failed.json"), JSON.stringify({ videos: [video(1)] }));
    const v = readVideos(dir);
    expect(v.map((x) => x.path)).toEqual(["videos/trend-10-x.mp4", "videos/trend-2-x.mp4", "videos/trend-1-x.mp4"]); // 3 is gone
    expect(v[1]).toMatchObject({ tone: "humor", poster: "videos/trend-2-x.poster.jpg", lufs: -14.2, wordErrorRate: 0.08 });
    expect(v[0].poster).toBeNull(); // the poster file is missing
  });

  it("never follows a path out of the videos folder", () => {
    fs.writeFileSync(path.join(dir, "videos", "trend-1-x.mp4"), "mp4");
    fs.writeFileSync(path.join(dir, "videos", "trends.json"), JSON.stringify({ videos: [
      video(2, { file: { path: "../config.json" } }), video(3, { file: { path: ".." } }), video(1, { poster: "../../x.png" })] }));
    const v = readVideos(dir);
    expect(v.map((x) => [x.path, x.poster])).toEqual([["videos/trend-1-x.mp4", null]]);
  });

  it("serves mp4 files but nothing else new", () => {
    fs.writeFileSync(path.join(dir, "videos", "trend-1-x.mp4"), "mp4");
    expect(resolveRunFile("r", "videos/trend-1-x.mp4", root).type).toBe("video/mp4");
    expect(() => resolveRunFile("r", "videos/trends.json", root)).toThrow();
  });
});

describe("competitor ads", () => {
  it("reads the market, longest-running first, without the snapshot URL", () => {
    const rows = [
      { id: "1", page_name: "A", bodies: ["short"], titles: [], start_date: "2026-10-31", stop_date: null, platforms: ["instagram"],
        snapshot_url: "https://x/?access_token=SECRET" },
      { id: "2", page_name: "B", bodies: ["long"], titles: ["T"], start_date: "2026-08-01", stop_date: "2026-10-01", platforms: [] },
    ];
    fs.writeFileSync(path.join(dir, "market_ads.jsonl"), rows.map((r) => JSON.stringify(r)).join("\n") + "\nnot json\n");
    const ads = readMarketAds(dir, Date.parse("2026-11-03"));
    expect(ads.map((a) => [a.id, a.days])).toEqual([["2", 61], ["1", 3]]);
    fs.writeFileSync(path.join(dir, "market.json"), JSON.stringify({ terms: ["x"], ads: 2, competitors: [], rejected: [], research_countries: ["GB"],
      next: "https://graph.facebook.com/v26.0/ads_archive?access_token=SECRET2" }));
    const json = JSON.stringify(readRun("r", root));
    expect(json).not.toContain("SECRET");
    expect(json).not.toContain("access_token");
    expect(readRun("r", root).market?.terms).toEqual(["x"]);
  });
});

describe("byte ranges", () => {
  it.each([
    ["bytes=0-", 100, { start: 0, end: 99 }],
    ["bytes=10-19", 100, { start: 10, end: 19 }],
    ["bytes=90-500", 100, { start: 90, end: 99 }],
    ["bytes=-10", 100, { start: 90, end: 99 }],
  ])("%s of %i", (h, size, want) => expect(byteRange(h, size)).toEqual(want));

  it.each(["bytes=100-", "bytes=-0"])("cannot satisfy %s", (h) => expect(byteRange(h, 100)).toBeNull());

  it.each(["bytes=5-2", "bytes=-", "items=0-1", "bytes=0-1,4-5"])("ignores %s (whole file)", (h) => expect(byteRange(h, 100)).toBe("ignore"));

  it("never reads more than a chunk at once", () => expect(byteRange("bytes=0-", 10_000_000, 1000)).toEqual({ start: 0, end: 999 }));
});
