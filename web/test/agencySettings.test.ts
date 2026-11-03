import { describe, expect, it } from "vitest";
import { DEFAULT_SETTINGS, parseSettings } from "@/lib/agencySettings";

describe("agency settings kept in the browser", () => {
  it("reads what was saved", () => {
    expect(parseSettings(JSON.stringify({ mode: "propose", website: " https://x.app " }))).toEqual({ mode: "propose", website: "https://x.app" });
  });

  it.each([null, "", "not json", JSON.stringify({ mode: "spend_everything" }), JSON.stringify({ website: "javascript:alert(1)" })])(
    "falls back to the safe default for %j", (raw) => {
      const s = parseSettings(raw);
      expect(s.mode).toBe(raw && raw.includes("spend") ? DEFAULT_SETTINGS.mode : s.mode);
      expect(s.website).toBe("");
      expect(Object.keys(s).sort()).toEqual(["mode", "website"]);
    });

  it("defaults to a paused test", () => expect(parseSettings(null).mode).toBe("paused"));
});
