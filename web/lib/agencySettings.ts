/**
 * What the agency may do on the connected Meta account, chosen once on the Meta account page and used by the
 * search bar. Kept in this browser only (a convenience); the engine enforces the level and the cap again.
 */
export const MODES = {
  paused: { label: "Test on Meta, paused", level: "autopilot", paused: true },
  dry_run: { label: "Prepare only", level: "dry_run", paused: false },
  propose: { label: "Ask me before each action", level: "propose", paused: false },
  autopilot: { label: "Autopilot within my cap", level: "autopilot", paused: false },
} as const;
export type Mode = keyof typeof MODES;

export interface AgencySettings { mode: Mode; website: string }

const KEY = "whynot.agency";
export const DEFAULT_SETTINGS: AgencySettings = { mode: "paused", website: "" };

export function parseSettings(raw: string | null): AgencySettings {
  try {
    const o = JSON.parse(raw ?? "{}") as Partial<AgencySettings>;
    const mode = typeof o.mode === "string" && o.mode in MODES ? (o.mode as Mode) : DEFAULT_SETTINGS.mode;
    const website = typeof o.website === "string" && /^https?:\/\/\S{3,300}$/.test(o.website.trim()) ? o.website.trim() : "";
    return { mode, website };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function loadSettings(): AgencySettings {
  try { return parseSettings(localStorage.getItem(KEY)); } catch { return DEFAULT_SETTINGS; }
}

export function saveSettings(s: AgencySettings): void {
  try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* private window: the defaults apply */ }
}
