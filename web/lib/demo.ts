/**
 * Demo mode (the public deployment): the site reads a bundled example instead of the engine's output folder, and
 * every action that would run the engine or touch Meta is refused. No API key is needed to look around.
 *
 * On: WHYNOT_DEMO=1 (server) and NEXT_PUBLIC_WHYNOT_DEMO=1 (browser). The example lives in web/demo/ (written
 * by scripts/export_example.py --media: tokens, ad account and Page ids redacted).
 */
import path from "node:path";

export const DEMO = process.env.WHYNOT_DEMO === "1" || process.env.NEXT_PUBLIC_WHYNOT_DEMO === "1";

/** web/demo: holds runs/ (the example campaign) and validate/results/ (the published experiments). */
export const DEMO_ROOT = path.join(process.cwd(), "demo");

/** The example campaigns bundled with the demo (run ids), the search bar opens one of them. */
export const DEMO_RUNS = { duolingo: "20261104-demo-duolingo", vietbuddy: "20261103-vietbuddy" } as const;

export const DEMO_REFUSAL = "This is the read-only demo (the example run we made on Duolingo): nothing runs here. "
  + "To run whynot on your own app, run it locally and connect your Meta account and your Meta AI keys.";

/** Every POST in demo mode answers this instead of starting the engine. */
export function demoRefused(): Response {
  return Response.json({ error: DEMO_REFUSAL }, { status: 403 });
}
