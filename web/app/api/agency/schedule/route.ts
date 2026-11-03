import { NextResponse } from "next/server";
import { runSchedule, validateSchedule } from "@/lib/meta";
import { RunPathError } from "@/lib/runs";

export const dynamic = "force-dynamic";

/** Every morning at HH:MM, the agency runs its day by itself (or stop that). */
export async function POST(req: Request) {
  let body: unknown;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "Invalid request." }, { status: 400 }); }
  const v = validateSchedule(body);
  if (!v.ok) return NextResponse.json({ error: v.error }, { status: 400 });
  try {
    const res = await runSchedule(v.value);
    return NextResponse.json(res, { status: res.ok ? 200 : 502 });
  } catch (e) {
    if (e instanceof RunPathError) return NextResponse.json({ error: "Unknown campaign." }, { status: 404 });
    throw e;
  }
}
