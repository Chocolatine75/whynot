/** One HTTP byte range ("bytes=0-", "bytes=100-199", "bytes=-500") inside a file of `size` bytes, or null if unsatisfiable. */
export function byteRange(header: string, size: number, maxChunk = 4 * 1024 * 1024): { start: number; end: number } | null {
  const m = /^bytes=(\d*)-(\d*)$/.exec(header.trim());
  if (!m || (m[1] === "" && m[2] === "") || size === 0) return null;
  let start: number;
  let end: number;
  if (m[1] === "") {
    start = Math.max(0, size - Number(m[2]));
    end = size - 1;
  } else {
    start = Number(m[1]);
    end = m[2] === "" ? size - 1 : Math.min(Number(m[2]), size - 1);
  }
  if (start >= size || end < start) return null;
  return { start, end: Math.min(end, start + maxChunk - 1) }; // never more than a chunk in memory
}
