import { NextResponse } from "next/server";
import { startAgency, validateAgency } from "@/lib/meta";
import { DEMO, demoRefused } from "@/lib/demo";

export const dynamic = "force-dynamic";

/** Start the whole agency (connect → create → publish → daily) on a connected account or the simulated one. */
export async function POST(req: Request) {
  if (DEMO) return demoRefused();
  let body: unknown;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "Invalid request." }, { status: 400 }); }
  const v = validateAgency(body);
  if (!v.ok) return NextResponse.json({ error: v.error }, { status: 400 });
  return NextResponse.json({ id: startAgency(v.value) }, { status: 201 });
}
