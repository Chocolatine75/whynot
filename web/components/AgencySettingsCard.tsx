"use client";
import { useEffect, useState } from "react";
import { type AgencySettings, DEFAULT_SETTINGS, MODES, type Mode, loadSettings, saveSettings } from "@/lib/agencySettings";

/** How far the agency may go on the account, and where the ads send people: used by the home page's search bar. */
export default function AgencySettingsCard() {
  const [s, setS] = useState<AgencySettings>(DEFAULT_SETTINGS);
  const [saved, setSaved] = useState(false);
  useEffect(() => setS(loadSettings()), []);
  const update = (next: AgencySettings) => { setS(next); saveSettings(next); setSaved(true); };
  return (
    <div className="card stack" style={{ gap: 14 }}>
      <div className="spread">
        <h3 className="h4">What the agency may do</h3>
        {saved && <span className="tag ok">Saved</span>}
      </div>
      <label className="stack small" style={{ gap: 6 }}>
        <span className="label">On this account</span>
        <select className="select" value={s.mode} onChange={(e) => update({ ...s, mode: e.target.value as Mode })}>
          {(Object.keys(MODES) as Mode[]).map((m) => <option key={m} value={m}>{MODES[m].label}</option>)}
        </select>
      </label>
      <label className="stack small" style={{ gap: 6 }}>
        <span className="label">Website the ads link to (when the app is not registered with Meta)</span>
        <input className="input" placeholder="https://… (empty: the website on the App Store page)" value={s.website}
               onChange={(e) => setS({ ...s, website: e.target.value })} onBlur={() => update(s)} inputMode="url" spellCheck={false} />
      </label>
      <p className="xsmall faint">Every new campaign from the home page uses these. The engine checks the level and your cap again.</p>
    </div>
  );
}
