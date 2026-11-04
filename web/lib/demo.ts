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

/** The example campaign's run id, the one the landing page opens. */
export const DEMO_RUN = "20261104-demo-duolingo";

export const DEMO_REFUSAL = "This is the read-only demo: nothing runs here and no API key is used. "
  + "Clone the repository to run the agency on your own app.";

/** Every POST in demo mode answers this instead of starting the engine. */
export function demoRefused(): Response {
  return Response.json({ error: DEMO_REFUSAL }, { status: 403 });
}
