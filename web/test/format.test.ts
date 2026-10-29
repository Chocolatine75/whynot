import { describe, expect, it } from "vitest";
import { ago, eur, fileUrl, joinPhrases, runUrl, signed, usd } from "@/lib/format";

describe("formatting", () => {
  it("joins phrases without doubled punctuation", () => {
    expect(joinPhrases(["Too expensive.", " It won't hear me; ", "", "Too fast"])).toBe("Too expensive · It won't hear me · Too fast");
  });
  it("money and signs", () => {
    expect([usd(1.094), eur(20), eur(6.66), signed(0.5), signed(-1.25)]).toEqual(["$1.09", "€20", "€6.66", "+0.50", "−1.25"]);
  });
  it("urls encode run ids and paths", () => {
    expect(runUrl("generic/20261029-x")).toBe("/runs/generic/20261029-x");
    expect(fileUrl("a b", "ads/x y.png")).toBe("/api/file?run=a%20b&path=ads%2Fx%20y.png");
  });
  it("relative time", () => {
    const now = Date.parse("2026-10-29T12:00:00Z");
    expect([ago("2026-10-29T11:59:40Z", now), ago("2026-10-29T11:30:00Z", now), ago("2026-10-29T06:00:00Z", now), ago(null, now)])
      .toEqual(["just now", "30 min ago", "6 h ago", ""]);
  });
});
