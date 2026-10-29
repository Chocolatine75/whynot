import { NextResponse } from "next/server";
import { RunPathError, readRun } from "@/lib/runs";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const id = new URL(req.url).searchParams.get("id") ?? "";
  try {
    return NextResponse.json(readRun(id));
  } catch (e) {
    if (e instanceof RunPathError) return NextResponse.json({ error: e.message }, { status: 404 });
    throw e;
  }
}
