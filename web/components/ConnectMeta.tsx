"use client";
import { useCallback, useEffect, useState } from "react";
import type { Connection } from "@/lib/meta";

/** What Facebook Login must ask for: publish and read ads, on a Page the owner manages. */
const SCOPES = "ads_management,ads_read,pages_show_list,pages_read_engagement,pages_manage_ads,business_management";

interface FBLoginResponse { authResponse?: { accessToken: string } | null; status?: string }
interface FBSdk {
  init(o: { appId: string; version: string; cookie?: boolean; xfbml?: boolean }): void;
  login(cb: (r: FBLoginResponse) => void, o: { scope: string; return_scopes?: boolean; auth_type?: string }): void;
}
declare global { interface Window { FB?: FBSdk; fbAsyncInit?: () => void } }

/** Load Meta's JavaScript SDK once (only on this page, only when an app id is set). */
function loadSdk(appId: string): Promise<FBSdk> {
  return new Promise((resolve, reject) => {
    if (window.FB) { resolve(window.FB); return; }
    window.fbAsyncInit = () => { window.FB!.init({ appId, version: "v26.0", cookie: false, xfbml: false }); resolve(window.FB!); };
    const s = document.createElement("script");
    s.src = "https://connect.facebook.net/en_US/sdk.js";
    s.async = true;
    s.crossOrigin = "anonymous";
    s.onerror = () => reject(new Error("Meta's login could not load (blocked by the browser?)."));
    document.body.appendChild(s);
  });
}

export function useConnections() {
  const [state, setState] = useState<{ appId: string | null; connections: Connection[] } | null>(null);
  const reload = useCallback(async () => {
    try {
      const res = await fetch("/api/meta", { cache: "no-store" });
      setState(res.ok ? await res.json() : { appId: null, connections: [] });
    } catch { setState({ appId: null, connections: [] }); }
  }, []);
  useEffect(() => { void reload(); }, [reload]);
  return { ...(state ?? { appId: null, connections: [] }), loaded: state !== null, reload };
}

function expiry(c: Connection): [string, string] {
  if (c.daysLeft === null) return ["neutral", "login expiry unknown"];
  if (c.daysLeft < 0) return ["bad", "login expired: connect again"];
  if (c.daysLeft < 7) return ["warn", `login ends in ${c.daysLeft} days`];
  return ["ok", `login valid ${c.daysLeft} more days, renewed by itself`];
}

export function ConnectionCard({ c }: { c: Connection }) {
  const [tag, text] = expiry(c);
  return (
    <div className="card stack" style={{ gap: 10 }}>
      <div className="spread">
        <div>
          <h3 className="h4">{c.accountName || c.act}</h3>
          <p className="xsmall faint num">{c.act} · {c.currency}{c.sandbox ? " · sandbox (never spends)" : ""}</p>
        </div>
        <span className={`tag dot ${c.canPublish ? "ok" : "warn"}`}>{c.canPublish ? "Connected" : "Cannot publish"}</span>
      </div>
      <p className="small muted">
        Ads speak as <strong>{c.pageName ?? "no Page"}</strong>
        {c.appId ? <> · app installs on (Meta app {c.appId})</> : <> · ads send people to the app&apos;s website</>}
      </p>
      <span className={`tag ${tag}`} style={{ alignSelf: "flex-start" }}>{text}</span>
      {c.warnings.length > 0 && <ul className="xsmall faint notes">{c.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
    </div>
  );
}

/** Connect the owner's Meta ad account once: Facebook Login (or a pasted token), then the engine checks it. */
export default function ConnectMeta({ onConnected }: { onConnected?: (c: Connection) => void }) {
  const { appId, connections, loaded, reload } = useConnections();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paste, setPaste] = useState(false);
  const [token, setToken] = useState("");
  const [account, setAccount] = useState("");

  async function send(accessToken: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/meta", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ token: accessToken, account: account.trim() || undefined }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) { setError(body.error ?? "Meta refused the connection."); return; }
      setToken("");
      setPaste(false);
      await reload();
      onConnected?.(body as Connection);
    } catch {
      setError("Network error: nothing was saved.");
    } finally {
      setBusy(false);
    }
  }

  async function facebook() {
    if (!appId) return;
    setError(null);
    try {
      const FB = await loadSdk(appId);
      FB.login((r) => {
        if (r.authResponse?.accessToken) void send(r.authResponse.accessToken);
        else setError("Login cancelled: nothing was connected.");
      }, { scope: SCOPES, return_scopes: true, auth_type: "rerequest" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Meta's login could not load.");
    }
  }

  return (
    <div className="stack" style={{ gap: 16 }}>
      {connections.map((c) => <ConnectionCard key={c.act} c={c} />)}
      <div className="card stack" style={{ gap: 14 }}>
        <div>
          <h3 className="h4">{connections.length ? "Connect another account" : "Connect your Meta ad account"}</h3>
          <p className="small muted">Once. whynot keeps a 60-day login, renews it by itself, and only acts within the cap and
            autonomy you choose. Your login never leaves this machine.</p>
        </div>
        <div className="row" style={{ gap: 10 }}>
          <button type="button" className="btn" onClick={facebook} disabled={busy || !appId}
                  title={appId ? undefined : "Set WHYNOT_META_APP_ID in .env"}>
            {busy ? "Checking with Meta…" : "Continue with Facebook"}
          </button>
          <button type="button" className="btn secondary" onClick={() => setPaste((p) => !p)} disabled={busy} aria-expanded={paste}>
            Paste a token instead
          </button>
        </div>
        {loaded && !appId && <p className="xsmall faint">Facebook Login needs whynot&apos;s app id (WHYNOT_META_APP_ID in .env).</p>}
        {paste && (
          <form className="stack" style={{ gap: 10 }} onSubmit={(e) => { e.preventDefault(); void send(token); }}>
            <input type="password" className="input" aria-label="Meta user token" placeholder="User token (Graph API Explorer)"
                   value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off" spellCheck={false} />
            <div className="row" style={{ gap: 10 }}>
              <input className="input" aria-label="Ad account id (optional)" placeholder="Ad account id, if you have several"
                     value={account} onChange={(e) => setAccount(e.target.value)} style={{ flex: 1, minWidth: 160 }} />
              <button className="btn" disabled={busy || token.trim().length < 20}>{busy ? "Checking…" : "Connect"}</button>
            </div>
          </form>
        )}
        {error && <p className="error-text small" role="alert">{error}</p>}
      </div>
    </div>
  );
}
