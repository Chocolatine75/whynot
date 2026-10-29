/** The hero's product picture, drawn in HTML (no real brand): an ad in a feed, the agency at work, a viewer's
 * objection and the evolved answer. Pure CSS motion, staggered once on load; off with reduced motion. */
const STEPS = [
  ["Your reviews and your competitors’ ads", "Research"],
  ["Audiences and objections, all quoted", "Strategy"],
  ["Ads from your real screens", "Create"],
  ["Tested next to competitors", "Simulate"],
  ["v2 answers “I don’t see the price”", "Evolve"],
];

export default function HeroDemo() {
  return (
    <div className="demo" aria-hidden>
      <span className="illustration demo-label">Illustration</span>
      <div className="demo-phone">
        <div className="demo-notch" />
        <div className="demo-post">
          <div className="demo-head"><span className="demo-avatar">Y</span><div><b>YourApp</b><small>Sponsored</small></div></div>
          <p className="demo-copy">Five minutes a day, on your commute. Start free.</p>
          <div className="demo-creative">
            <div className="demo-creative-text">Speak it before you read it</div>
            <div className="demo-screen"><i /><i /><i /><i /></div>
          </div>
          <div className="demo-cta"><span>Learn the way it sounds</span><em>Install</em></div>
        </div>
      </div>
      <div className="demo-panel">
        <div className="demo-panel-title"><span className="demo-live" />The agency is working</div>
        <ol className="demo-steps">
          {STEPS.map(([text, label], i) => (
            <li key={label} style={{ "--i": i } as React.CSSProperties}>
              <span className="demo-check">✓</span>
              <span><small>{label}</small>{text}</span>
            </li>
          ))}
        </ol>
        <div className="demo-bubble" style={{ "--i": 5 } as React.CSSProperties}>
          <small>Simulated viewer</small>“Looks nice, but I don’t see the price.”
        </div>
        <div className="demo-score" style={{ "--i": 6 } as React.CSSProperties}>
          <span className="tag sim">Simulated</span> v2 beats a competitor ad shown under your name <b>+1.8</b>
        </div>
      </div>
    </div>
  );
}
