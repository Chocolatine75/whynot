import { fileUrl } from "@/lib/format";

/** The app's own icon (from its store page), or its initial on a quiet tile. */
export default function AppIcon({ run, icon, name, size = "" }: { run: string; icon: string | null; name: string; size?: "" | "sm" | "lg" }) {
  const cls = `app-icon${size ? ` ${size}` : ""}`;
  // eslint-disable-next-line @next/next/no-img-element
  return icon ? <img className={cls} src={fileUrl(run, icon)} alt="" /> : <span className={cls} aria-hidden>{name.slice(0, 1).toUpperCase()}</span>;
}
