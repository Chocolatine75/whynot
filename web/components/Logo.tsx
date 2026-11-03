import { useId } from "react";

/**
 * The whynot mark: a question mark drawn as one ribbon (the "why not?" every ad has to answer), in Meta's
 * blue→violet. Two strokes give the ribbon its fold, like Meta's own mark; the dot is the answer landing.
 */
export function Mark({ size = 28, animated = false, className }: { size?: number; animated?: boolean; className?: string }) {
  const id = useId().replace(/:/g, "");
  const hook = "M30 36 C30 16 70 14 72 36 C73.5 52 52 52 51 68";
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" className={`${className ?? ""}${animated ? " mark-anim" : ""}`} aria-hidden>
      <defs>
        <linearGradient id={`g${id}`} x1="20" y1="10" x2="85" y2="95" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#0064E0" />
          <stop offset="0.45" stopColor="#0A8CFF" />
          <stop offset="0.8" stopColor="#7A5CFF" />
          <stop offset="1" stopColor="#C74AE0" />
        </linearGradient>
        <linearGradient id={`s${id}`} x1="30" y1="20" x2="72" y2="70" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#003E8F" />
          <stop offset="1" stopColor="#4B2FB8" />
        </linearGradient>
      </defs>
      {/* the fold: a darker ribbon under the front one */}
      <path d={hook} fill="none" stroke={`url(#s${id})`} strokeWidth="17" strokeLinecap="round" transform="translate(2.5 3)" opacity="0.55" className="mark-fold" />
      <path d={hook} fill="none" stroke={`url(#g${id})`} strokeWidth="15" strokeLinecap="round" pathLength={100} className="mark-hook" />
      <circle cx="51" cy="86" r="8.5" fill={`url(#g${id})`} className="mark-dot" />
    </svg>
  );
}

export function Wordmark({ size = 17 }: { size?: number }) {
  return (
    <span className="wordmark" style={{ fontSize: size }}>
      why<span>not</span>
    </span>
  );
}
