import type { Metadata } from "next";
import { type Experiment, type Verdict, readValidation } from "@/lib/validation";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Validation — whynot", description: "Is the simulator right? Every number, with its method and limits." };

const VERDICT_TAG: Record<Verdict, string> = { "meets target": "ok", "above floor": "info", "no evidence": "warn", "below chance": "bad" };

function ci(r: { ci: [number, number] | null }) {
  return r.ci ? `[${r.ci[0].toFixed(2)}, ${r.ci[1].toFixed(2)}]` : "—";
}

function ExperimentCard({ e }: { e: Experiment }) {
  return (
    <article className="card pad-lg exp" aria-labelledby={`exp-${e.id}`}>
      <div className="spread">
        <h3 id={`exp-${e.id}`}>{e.title}</h3>
        <span className={`tag dot ${VERDICT_TAG[e.verdict]}`}>{e.verdict}</span>
      </div>
      <p className="positioning" style={{ fontSize: 18 }}>{e.question}</p>
      <p className="small muted">
        {e.sample} · {e.date}{e.usd !== null && <> · model cost ${e.usd.toFixed(2)}</>} · target ≥ {e.target.toFixed(2)},
        floor &gt; {e.floor.toFixed(2)} · <span className="tag sim">simulated predictions</span>
      </p>
      <div className="card flush scroll-x"><table className="table">
        <thead><tr><th scope="col">{e.metric}</th><th scope="col">value</th><th scope="col">95 % CI</th><th scope="col" /></tr></thead>
        <tbody>
          {e.rows.map((r) => (
            <tr key={r.name}>
              <td>{r.primary ? <strong>{r.name}</strong> : r.name}{r.baseline && <span className="small muted"> · baseline</span>}</td>
              <td className="num mono">{r.value.toFixed(2)}</td>
              <td className="num mono">{ci(r)}</td>
              <td className="small muted">{r.primary ? "primary" : r.note ?? ""}</td>
            </tr>
          ))}
          <tr><td className="muted">chance</td><td className="num mono muted">0.50</td><td /><td /></tr>
        </tbody>
      </table></div>
      <details>
        <summary className="small">Method, limits and how to reproduce</summary>
        <div className="stack small" style={{ gap: 8, marginTop: 10 }}>
          <p>{e.method}</p>
          <ul>{e.limits.map((l) => <li key={l}>{l}</li>)}</ul>
          <p className="muted">Reproduce: <code>{e.command}</code> · data: <code>{e.file}</code></p>
        </div>
      </details>
    </article>
  );
}

export default function ValidationPage() {
  const { experiments, unread } = readValidation();
  return (
    <main className="page narrow">
      <div className="page-head">
        <div>
          <span className="eyebrow">Validation</span>
          <h1 style={{ marginTop: 6 }}>Is the simulator right?</h1>
          <p>
            Ads are tested in a simulated feed before anyone spends. That is only useful if the simulation agrees
            with reality, so we measure it and publish every result, good or bad, with its confidence interval and
            simple baselines. A result counts only when its interval excludes chance.
          </p>
        </div>
      </div>
      {experiments.length === 0 && <p className="muted">No validation result yet.</p>}
      <div className="stack" style={{ gap: 20 }}>
        {experiments.map((e) => <ExperimentCard key={e.file} e={e} />)}
      </div>
      {unread.length > 0 && (
        <p className="small muted" style={{ marginTop: 20 }}>Not shown (format not recognised): {unread.join(", ")}</p>
      )}
    </main>
  );
}
