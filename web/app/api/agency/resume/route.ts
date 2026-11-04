import { NextResponse } from "next/server";
import { resumeAgency, validateResume } from "@/lib/meta";
import { RunPathError } from "@/lib/runs";
import { DEMO, demoRefused } from "@/lib/demo";

export const dynamic = "force-dynamic";

/** Run today's day now, or continue a step that waited for the owner's approval. */
export async function POST(req: Request) {
  if (DEMO) return demoRefused();
  let body: unknown;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "Invalid request." }, { status: 400 }); }
  const v = validateResume(body);
  if (!v.ok) return NextResponse.json({ error: v.error }, { status: 400 });
  try {
    resumeAgency(v.value);
  } catch (e) {
    if (e instanceof RunPathError) return NextResponse.json({ error: "Unknown campaign." }, { status: 404 });
    return NextResponse.json({ error: "This campaign was not started by the agency." }, { status: 409 });
  }
  return NextResponse.json({ started: true }, { status: 202 });
}
