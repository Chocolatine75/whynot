import fs from "node:fs";
import { RunPathError, resolveRunFile } from "@/lib/runs";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const q = new URL(req.url).searchParams;
  try {
    const { file, type } = resolveRunFile(q.get("run") ?? "", q.get("path") ?? "");
    return new Response(fs.readFileSync(file), { headers: { "content-type": type, "cache-control": "private, max-age=3600" } });
  } catch (e) {
    if (e instanceof RunPathError) return new Response(e.message, { status: 404 });
    throw e;
  }
}
