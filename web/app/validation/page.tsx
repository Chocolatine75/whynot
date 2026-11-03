import type { Metadata } from "next";
import { type ClaimStatus, type Experiment, type Verdict, readClaims, readValidation } from "@/lib/validation";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Validation — whynot", description: "Is the simulator right? Every number, with its method and limits." };

const VERDICT_TAG: Record<Verdict, string> = { "meets target": "ok", "above floor": "info", "no evidence": "warn", "below chance": "bad" };
const CLAIM_TAG: Record<ClaimStatus, string> = { passed: "ok", failed: "bad", "not yet run": "neutral" };

function ci(r: { ci: [number, number] | null }) {
  return r.ci ? `[${r.ci[0].toFixed(2)}, ${r.ci[1].toFixed(2)}]` : "—";
}

/** Each row's value and interval on one 0–1 axis, chance at 0.5: the eye compares them at once. */
function Forest({ e }: { e: Experiment }) {
  const W = 560, row = 26, L = 170, R = 20, H = e.rows.length * row + 26;
  const x = (v: number) => L + v * (W - L - R);
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${e.metric} per method with 95 % intervals`}>
      <line x1={x(0.5)} x2={x(0.5)} y1={4} y2={H - 18} stroke="currentColor" strokeDasharray="3 4" opacity={0.35} />
      {e.rows.map((r, i) => {
        const y = 14 + i * row;
        const c = r.primary ? "var(--blue)" : "var(--text-3)";
        return (
          <g key={`${i}-${r.name}`}>
            <text x={L - 10} y={y + 4} textAnchor="end" style={{ fill: r.primary ? "var(--text)" : undefined }}>{r.name}</text>
            {r.ci && <line x1={x(r.ci[0])} x2={x(r.ci[1])} y1={y} y2={y} stroke={c} strokeWidth={2} />}
            <circle cx={x(r.value)} cy={y} r={4.5} fill={c}><title>{`${r.name}: ${r.value.toFixed(2)} ${ci(r)}`}</title></circle>
          </g>
        );
      })}
      {[0, 0.5, 1].map((v) => <text key={v} x={x(v)} y={H - 4} textAnchor="middle">{v === 0.5 ? "chance" : v}</text>)}
    </svg>
  );
}

function ExperimentCard({ e }: { e: Experiment }) {
  const p = e.rows.find((r) => r.primary);
  return (
    <article className="card pad-lg exp" aria-labelledby={`exp-${e.id}`}>
      <div className="spread">
        <h2 id={`exp-${e.id}`}>{e.title}</h2>
        <span className={`tag dot ${VERDICT_TAG[e.verdict]}`}>{e.verdict}</span>
      </div>
      <p className="muted">{e.question}</p>
      <Forest e={e} />
      {p && <p className="small">{e.verdict === "meets target" || e.verdict === "above floor"
        ? `Primary result ${p.value.toFixed(2)} ${ci(p)}: the interval excludes chance.`
        : `Primary result ${p.value.toFixed(2)} ${ci(p)}: no evidence it beats chance, so we don't rely on it for this.`}</p>}
      <details>
        <summary>Method, numbers and limits</summary>
        <div className="stack small" style={{ gap: 10, marginTop: 10 }}>
          <p className="muted">{e.sample} · {e.date}{e.usd !== null && <> · model cost ${e.usd.toFixed(2)}</>} · target ≥ {e.target.toFixed(2)} · <span className="tag sim">simulated predictions</span></p>
          <div className="card flush scroll-x"><table className="table">
            <thead><tr><th scope="col">{e.metric}</th><th scope="col">value</th><th scope="col">95 % CI</th><th scope="col" /></tr></thead>
            <tbody>
              {e.rows.map((r, i) => (
                <tr key={`${i}-${r.name}`}>
                  <td>{r.primary ? <strong>{r.name}</strong> : r.name}{r.baseline && <span className="small muted"> · baseline</span>}</td>
                  <td className="num mono">{r.value.toFixed(2)}</td>
                  <td className="num mono">{ci(r)}</td>
                  <td className="small muted">{r.primary ? "primary" : r.note ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
          <p>{e.method}</p>
          <ul>{e.limits.map((l, i) => <li key={`${i}-${l}`}>{l}</li>)}</ul>
          <p className="muted">Reproduce: <code>{e.command}</code> · data: <code>{e.file}</code></p>
        </div>
      </details>
    </article>
  );
}

export default function ValidationPage() {
  const view = readValidation();
  const claims = readClaims(view);
  const count = (s: ClaimStatus) => claims.filter((c) => c.status === s).length;
  return (
    <main className="page narrow" id="content">
      <div className="page-head">
        <div>
          <span className="eyebrow">Validation</span>
          <h1 style={{ marginTop: 8 }}>Is the simulator right?</h1>
          <p>We measure it and publish every result, including the failures. Today: {count("passed")} pass, {count("failed")} fail, {count("not yet run")} not yet run.</p>
        </div>
      </div>
      <div className="card flush claims">
        {claims.map((c) => (
          <div key={c.what} className="claim">
            <span className="what">{c.what}</span>
            <span className="row" style={{ gap: 10 }}><span className="val faint">{c.value}</span><span className={`tag dot ${CLAIM_TAG[c.status]}`}>{c.status}</span></span>
            <span className="how">{c.how}</span>
          </div>
        ))}
      </div>
      <h2 className="sub-title" style={{ marginTop: 48 }}>Experiments</h2>
      {view.experiments.length === 0 && <p className="muted">No validation result yet.</p>}
      <div className="stack" style={{ gap: 20 }}>
        {view.experiments.map((e) => <ExperimentCard key={e.file} e={e} />)}
      </div>
      {view.unread.length > 0 && <p className="small muted" style={{ marginTop: 20 }}>Not shown (format not recognised): {view.unread.join(", ")}</p>}
    </main>
  );
}
