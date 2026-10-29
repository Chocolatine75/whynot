import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { configuredKeys, publishArgs, readiness, validatePublish } from "@/lib/publish";

function envFile(text: string): string {
  const p = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "env-")), ".env");
  fs.writeFileSync(p, text);
  return p;
}

describe("readiness reads which settings exist, never their values", () => {
  it("ignores empty values and inline comments", () => {
    const keys = configuredKeys(envFile([
      "META_SANDBOX_AD_ACCOUNT_ID=123   # sandbox", "META_SANDBOX_TOKEN=\"EAAxyz\"", "META_PAGE_ID=", "META_APP_ID=  # none yet",
      "# META_AD_ACCOUNT_ID=999", "garbage line",
    ].join("\n")));
    expect([...keys].sort()).toEqual(["META_SANDBOX_AD_ACCOUNT_ID", "META_SANDBOX_TOKEN"]);
    const r = readiness(keys);
    expect(r[0]).toMatchObject({ mode: "sandbox", ready: false, missing: ["META_PAGE_ID"], appInstalls: false });
    expect(r[1].missing).toEqual(["META_AD_ACCOUNT_ID", "META_ACCESS_TOKEN", "META_PAGE_ID"]);
    expect(JSON.stringify(r)).not.toContain("EAAxyz");
  });

  it("a missing .env means nothing is configured", () => {
    expect(configuredKeys("/nope/.env").size).toBe(0);
  });
});

describe("publish requests", () => {
  const ok = { id: "web/x", mode: "sandbox", objective: "traffic", approvedBy: "Matteo Atkinson" };

  it("accepts a named approval and builds an argument list", () => {
    const v = validatePublish(ok);
    expect(v.ok).toBe(true);
    if (!v.ok) return;
    expect(publishArgs(v.value, "/runs/web/x")).toEqual(
      ["run", "whynot", "publish", "/runs/web/x", "--objective=traffic", "--approve=Matteo Atkinson"]);
    const live = validatePublish({ ...ok, mode: "live", activate: true });
    expect(live.ok && live.value.activate).toBe(false); // activation is never one click away on a live account
    expect(live.ok && publishArgs(live.value, "/r")).toContain("--live");
  });

  it.each([
    [{ ...ok, approvedBy: "" }, "name"],
    [{ ...ok, approvedBy: "x" }, "name"],
    [{ ...ok, approvedBy: "$(rm -rf ~)" }, "name"],
    [{ ...ok, approvedBy: "--live" }, "name"],  // would be read as an option by the engine (bug found here)
    [{ ...ok, approvedBy: "-x" }, "name"],
    [{ ...ok, mode: "production" }, "sandbox or live"],
    [{ ...ok, objective: "sales" }, "objective"],
    [{ ...ok, id: "" }, "campaign"],
  ])("refuses %j", (input, msg) => {
    const v = validatePublish(input);
    expect(v.ok).toBe(false);
    expect(!v.ok && v.error).toContain(msg);
  });
});
