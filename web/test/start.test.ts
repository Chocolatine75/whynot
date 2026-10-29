import { describe, expect, it } from "vitest";
import { engineArgs, newRunId, validateCampaign } from "@/lib/start";

const ok = { app: "https://apps.apple.com/us/app/x/id1234567890", countries: "fr gb", dailyCapEur: 20 };

describe("new campaign input", () => {
  it("accepts a store link or an id, normalises countries", () => {
    const v = validateCampaign(ok);
    expect(v.ok && v.value.countries).toEqual(["FR", "GB"]);
    expect(validateCampaign({ ...ok, app: "1234567890" }).ok).toBe(true);
    expect(v.ok && v.value.budgetUsd).toBe(3);
  });

  it.each([
    [{ ...ok, app: "" }, "App Store"],
    [{ ...ok, app: "https://x.com/a b" }, "App Store"],
    [{ ...ok, app: "$(rm -rf ~)" }, "App Store"],
    [{ ...ok, app: "https://apps.apple.com/x; rm -rf /" }, "App Store"],
    [{ ...ok, countries: "France" }, "2-letter"],
    [{ ...ok, countries: "" }, "2-letter"],
    [{ ...ok, dailyCapEur: 2 }, "€5"],
    [{ ...ok, dailyCapEur: "lots" }, "€5"],
    [{ ...ok, budgetUsd: 500 }, "AI budget"],
  ])("refuses %j", (input, msg) => {
    const v = validateCampaign(input);
    expect(v.ok).toBe(false);
    expect(!v.ok && v.error).toContain(msg);
  });

  it("builds an argument list for the engine, never a shell string", () => {
    const v = validateCampaign(ok);
    if (!v.ok) throw new Error("invalid");
    const args = engineArgs(v.value, "/runs/web/x");
    expect(args).toEqual(["run", "whynot", "create", ok.app, "--countries", "FR", "GB", "--daily-cap", "20", "--budget-usd", "3",
      "--resume", "/runs/web/x"]);
  });

  it("run ids are web/<timestamp>-<slug> with safe characters", () => {
    const id = newRunId("https://apps.apple.com/us/app/vietbuddy-learn/id6796837982", new Date("2026-10-29T10:11:12Z"));
    expect(id).toBe("web/20261029-101112-id6796837982");
    expect(newRunId("../../etc", new Date("2026-10-29T10:11:12Z"))).toMatch(/^web\/20261029-101112-[a-z0-9-]+$/);
  });
});
