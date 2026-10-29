import { NextResponse } from "next/server";
import { listRuns } from "@/lib/runs";
import { startCampaign, validateCampaign } from "@/lib/start";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(listRuns());
}

export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid request." }, { status: 400 });
  }
  const v = validateCampaign(body);
  if (!v.ok) return NextResponse.json({ error: v.error }, { status: 400 });
  const id = startCampaign(v.value);
  return NextResponse.json({ id }, { status: 201 });
}
