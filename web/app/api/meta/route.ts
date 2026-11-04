import { NextResponse } from "next/server";
import { listConnections, loginAppId, runConnect, validateConnect } from "@/lib/meta";
import { DEMO, demoRefused } from "@/lib/demo";

export const dynamic = "force-dynamic";

/** The saved Meta connections (never a token) and whynot's app id for Facebook Login. */
export async function GET() {
  return NextResponse.json({ appId: loginAppId(), connections: listConnections() });
}

/** Connect: the owner's login token goes to the engine on stdin; the answer never contains it. */
export async function POST(req: Request) {
  if (DEMO) return demoRefused();
  let body: unknown;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "Invalid request." }, { status: 400 }); }
  const v = validateConnect(body);
  if (!v.ok) return NextResponse.json({ error: v.error }, { status: 400 });
  const res = await runConnect(v.value);
  return res.ok ? NextResponse.json(res.connection) : NextResponse.json({ error: res.error }, { status: 502 });
}
