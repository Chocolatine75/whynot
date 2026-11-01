import { NextResponse } from "next/server";
import { RunPathError } from "@/lib/runs";
import { missingForStop, runStop, validateStop } from "@/lib/stop";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  let body: unknown;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "Invalid request." }, { status: 400 }); }
  const v = validateStop(body);
  if (!v.ok) return NextResponse.json({ error: v.error }, { status: 400 });
  const missing = missingForStop(v.value.mode);
  if (missing.length) return NextResponse.json({ error: `Missing settings: ${missing.join(", ")}` }, { status: 409 });
  try {
    const result = await runStop(v.value);
    return NextResponse.json(result, { status: result.ok ? 200 : 502 });
  } catch (e) {
    if (e instanceof RunPathError) return NextResponse.json({ error: "Unknown campaign." }, { status: 404 });
    throw e;
  }
}
