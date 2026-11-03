import fs from "node:fs";
import { RunPathError, resolveRunFile } from "@/lib/runs";
import { byteRange } from "@/lib/range";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const q = new URL(req.url).searchParams;
  try {
    const { file, type } = resolveRunFile(q.get("run") ?? "", q.get("path") ?? "");
    const size = fs.statSync(file).size;
    const headers = { "content-type": type, "cache-control": "private, max-age=3600", "accept-ranges": "bytes" };
    const range = req.headers.get("range");
    if (range === null) return new Response(fs.readFileSync(file), { headers: { ...headers, "content-length": String(size) } });
    // videos are read in ranges: the browser seeks without downloading the whole file
    const r = byteRange(range, size);
    if (!r) return new Response(null, { status: 416, headers: { "content-range": `bytes */${size}` } });
    const buf = Buffer.alloc(r.end - r.start + 1);
    const fd = fs.openSync(file, "r");
    try { fs.readSync(fd, buf, 0, buf.length, r.start); } finally { fs.closeSync(fd); }
    return new Response(buf, { status: 206, headers: { ...headers, "content-length": String(buf.length), "content-range": `bytes ${r.start}-${r.end}/${size}` } });
  } catch (e) {
    if (e instanceof RunPathError) return new Response(e.message, { status: 404 });
    throw e;
  }
}
