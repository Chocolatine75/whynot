import { NextResponse } from "next/server";
import { runAgencyStop, validateAgencyStop } from "@/lib/meta";
import { RunPathError } from "@/lib/runs";

export const dynamic = "force-dynamic";

/** The kill switch on the Meta account the agency used: pauses everything it created, now. */
export async function POST(req: Request) {
  let body: unknown;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "Invalid request." }, { status: 400 }); }
  const v = validateAgencyStop(body);
  if (!v.ok) return NextResponse.json({ error: v.error }, { status: 400 });
  try {
    const res = await runAgencyStop(v.value);
    return NextResponse.json(res, { status: res.ok ? 200 : 502 });
  } catch (e) {
    if (e instanceof RunPathError) return NextResponse.json({ error: "Unknown campaign." }, { status: 404 });
    throw e;
  }
}
