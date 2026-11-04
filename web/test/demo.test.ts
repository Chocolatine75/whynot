import { describe, expect, it } from "vitest";
import { DEMO_REFUSAL, demoRefused } from "../lib/demo";

describe("demo mode", () => {
  it("refuses any action with a 403 that says why", async () => {
    const r = demoRefused();
    expect(r.status).toBe(403);
    expect((await r.json()).error).toBe(DEMO_REFUSAL);
  });
});
