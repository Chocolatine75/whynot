import { useId } from "react";

/**
 * The whynot mark: a feed comment bubble with the question mark cut out of it. It is the "why not?" every ad has
 * to answer, asked where people answer ads: in the comments. Meta's blue→violet→pink, with a glass highlight.
 */
export function Mark({ size = 28, className }: { size?: number; className?: string }) {
  const id = useId().replace(/:/g, "");
  const bubble = "M30 7H70A23 23 0 0 1 93 30V56A23 23 0 0 1 70 79H44L21 95L26 78.2A23 23 0 0 1 7 56V30A23 23 0 0 1 30 7Z";
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" className={className} aria-hidden>
      <defs>
        <linearGradient id={`f${id}`} x1="8" y1="6" x2="92" y2="94" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#0A7CFF" />
          <stop offset="0.38" stopColor="#0064E0" />
          <stop offset="0.7" stopColor="#7A5CFF" />
          <stop offset="1" stopColor="#E042C4" />
        </linearGradient>
        <linearGradient id={`h${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.45" />
          <stop offset="0.5" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
        <mask id={`m${id}`}>
          <path d={bubble} fill="#fff" />
          <path d="M37.5 33.5C37.5 21.5 62.5 20.5 62.5 33.5C62.5 43 50 43.5 50 53" fill="none" stroke="#000" strokeWidth="9.5" strokeLinecap="round" />
          <circle cx="50" cy="65.5" r="6" fill="#000" />
        </mask>
      </defs>
      <g mask={`url(#m${id})`}>
        <path d={bubble} fill={`url(#f${id})`} />
        <path d={bubble} fill={`url(#h${id})`} />
      </g>
    </svg>
  );
}

export function Wordmark({ size = 19 }: { size?: number }) {
  return <span className="wordmark" style={{ fontSize: size }}>whynot</span>;
}
