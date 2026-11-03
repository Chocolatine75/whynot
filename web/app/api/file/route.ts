import fs from "node:fs";
import { Readable } from "node:stream";
import { RunPathError, resolveRunFile } from "@/lib/runs";
import { byteRange } from "@/lib/range";

export const dynamic = "force-dynamic";

/** Streamed, never read whole into memory: a run's videos weigh 7–27 MB each. */
const stream = (file: string, start?: number, end?: number) => Readable.toWeb(fs.createReadStream(file, { start, end })) as ReadableStream;

export async function GET(req: Request) {
  const q = new URL(req.url).searchParams;
  try {
    const { file, type } = resolveRunFile(q.get("run") ?? "", q.get("path") ?? "");
    const st = fs.statSync(file);
    const etag = `"${st.size}-${Math.trunc(st.mtimeMs)}"`;
    const headers = { "content-type": type, "cache-control": "private, max-age=3600", "accept-ranges": "bytes", etag,
      "last-modified": st.mtime.toUTCString() };
    const header = req.headers.get("range");
    const ifRange = req.headers.get("if-range");
    const r = header === null || (ifRange && ifRange !== etag) ? "ignore" : byteRange(header, st.size);
    if (r === "ignore") return new Response(stream(file), { headers: { ...headers, "content-length": String(st.size) } });
    if (!r) return new Response(null, { status: 416, headers: { ...headers, "content-range": `bytes */${st.size}` } });
    return new Response(stream(file, r.start, r.end), { status: 206, headers: { ...headers,
      "content-length": String(r.end - r.start + 1), "content-range": `bytes ${r.start}-${r.end}/${st.size}` } });
  } catch (e) {
    if (e instanceof RunPathError) return new Response(e.message, { status: 404 });
    throw e;
  }
}
