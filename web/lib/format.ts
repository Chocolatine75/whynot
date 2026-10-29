export const fileUrl = (run: string, rel: string) => `/api/file?run=${encodeURIComponent(run)}&path=${encodeURIComponent(rel)}`;
export const runUrl = (id: string) => `/runs/${id.split("/").map(encodeURIComponent).join("/")}`;
export const usd = (n: number) => `$${n.toFixed(2)}`;
export const eur = (n: number) => `€${n % 1 === 0 ? n.toFixed(0) : n.toFixed(2)}`;
export const signed = (n: number) => `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(2)}`;
export function ago(iso: string | null, now = Date.now()): string {
  if (!iso) return "";
  const m = Math.round((now - Date.parse(iso)) / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  return h < 24 ? `${h} h ago` : `${Math.round(h / 24)} d ago`;
}
export const STATUS_TAG: Record<string, [string, string]> = {
  running: ["info", "Working"], done: ["ok", "Ready"], failed: ["bad", "Stopped on an error"], stopped: ["warn", "Interrupted"],
};

/** "a." + "b" → "a · b": phrases without their final full stop, joined calmly. */
export function joinPhrases(items: string[]): string {
  return items.map((t) => t.trim().replace(/[.;]+$/, "")).filter(Boolean).join(" · ");
}
