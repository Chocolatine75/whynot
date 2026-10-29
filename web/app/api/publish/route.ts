import { NextResponse } from "next/server";
import { readiness, startPublish, validatePublish } from "@/lib/publish";
import { RunPathError } from "@/lib/runs";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(readiness());
}

export async function POST(req: Request) {
  let body: unknown;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "Invalid request." }, { status: 400 }); }
  const v = validatePublish(body);
  if (!v.ok) return NextResponse.json({ error: v.error }, { status: 400 });
  const ready = readiness().find((r) => r.mode === v.value.mode)!;
  if (!ready.ready) return NextResponse.json({ error: `Missing settings: ${ready.missing.join(", ")}` }, { status: 409 });
  if (v.value.objective === "app_promotion" && !ready.appInstalls)
    return NextResponse.json({ error: "App installs need META_APP_ID; use traffic or add it." }, { status: 409 });
  try {
    startPublish(v.value);
  } catch (e) {
    if (e instanceof RunPathError) return NextResponse.json({ error: "Unknown campaign." }, { status: 404 });
    throw e;
  }
  return NextResponse.json({ started: true }, { status: 202 });
}
