/** The few line icons the platform uses (24 px grid, 1.75 stroke, currentColor). */
type P = { className?: string };
const base = { width: 24, height: 24, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.75, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export const LinkIcon = ({ className }: P) => (
  <svg {...base} className={className}><path d="M10 14a4.5 4.5 0 0 0 6.36 0l3-3a4.5 4.5 0 0 0-6.36-6.36l-1 1" /><path d="M14 10a4.5 4.5 0 0 0-6.36 0l-3 3a4.5 4.5 0 0 0 6.36 6.36l1-1" /></svg>
);
export const ArrowUp = ({ className }: P) => (
  <svg {...base} strokeWidth={2.2} className={className}><path d="M12 19V5" /><path d="m5 12 7-7 7 7" /></svg>
);
export const ArrowRight = ({ className }: P) => (
  <svg {...base} className={className}><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></svg>
);
export const Shield = ({ className }: P) => (
  <svg {...base} className={className}><path d="M12 3 5 6v5c0 4.5 3 8.3 7 10 4-1.7 7-5.5 7-10V6l-7-3Z" /><path d="m9 12 2 2 4-4" /></svg>
);
export const Alert = ({ className }: P) => (
  <svg {...base} className={className}><circle cx="12" cy="12" r="9" /><path d="M12 8v5" /><path d="M12 16.5v.01" /></svg>
);
export const Chevron = ({ className }: P) => (
  <svg {...base} width={16} height={16} className={className}><path d="m9 6 6 6-6 6" /></svg>
);
