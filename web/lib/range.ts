/**
 * One HTTP byte range inside a file of `size` bytes: the range to send, null when it can't be satisfied (416), or
 * "ignore" when the header is malformed or asks for several ranges (the whole file is then sent, as HTTP says).
 */
export function byteRange(header: string, size: number, maxChunk = 4 * 1024 * 1024): { start: number; end: number } | null | "ignore" {
  const m = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
  if (!m || (m[1] === "" && m[2] === "")) return "ignore";
  let start: number;
  let end: number;
  if (m[1] === "") {
    if (Number(m[2]) === 0 || size === 0) return null;
    start = Math.max(0, size - Number(m[2]));
    end = size - 1;
  } else {
    start = Number(m[1]);
    end = m[2] === "" ? Math.max(start, size - 1) : Number(m[2]);
    if (end < start) return "ignore";
    if (start >= size) return null;
    end = Math.min(end, size - 1);
  }
  return { start, end: Math.min(end, start + maxChunk - 1) }; // a seek never pulls more than a chunk
}
