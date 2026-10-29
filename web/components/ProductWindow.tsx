/** The landing's picture of the product: the agency room as a macOS window. Static, brand-free, labelled. */
const STEPS = ["App Store page", "Competitors", "Strategy", "Ads", "Simulated feed", "Evolution", "Campaign"];

export default function ProductWindow() {
  return (
    <figure className="stage" style={{ margin: "64px auto 0" }}>
      <div className="window" role="img" aria-label="Illustration of a whynot campaign: an ad in a feed, with its simulated test results">
        <div className="window-bar">
          <span className="lights"><i /><i /><i /></span>
          <span className="window-title">YourApp — Campaign</span>
        </div>
        <div className="window-body">
          <aside className="sidebar">
            <span className="sidebar-title">Agency</span>
            {STEPS.map((s, i) => (
              <span key={s} className={`side-item ${s === "Ads" ? "active" : ""}`}>
                <span className={`tick ${i > 5 ? "todo" : ""}`}>{i > 5 ? "" : "✓"}</span>{s}
              </span>
            ))}
          </aside>
          <div className="content">
            <article className="post" style={{ maxWidth: 340 }}>
              <div className="post-head">
                <span className="avatar">Y</span>
                <div><div className="name">YourApp</div><div className="sponsored">Sponsored</div></div>
              </div>
              <p className="post-text">Five minutes a day, on your commute. Start free.</p>
              <div className="mock-creative">
                <b>Speak it before you read it</b>
                <div className="mock-screen"><i /><i /><i /><i /></div>
              </div>
              <div className="post-cta"><span className="title">Learn the way it sounds</span><span className="cta">Install</span></div>
            </article>

            <div className="stack inspector-col" style={{ gap: 14 }}>
              <div className="glass inspector floating">
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <h4>Version 2</h4><span className="tag sim">Simulated</span>
                </div>
                <div className="kv"><span>Against a competitor ad under your name</span><span className="num">+1.8</span></div>
                <div className="kv"><span>Purchase intent</span><span className="num">4.1 / 5</span></div>
                <div className="kv"><span>Views</span><span className="num">18</span></div>
                <div className="hr" />
                <div className="kv"><span>Changed</span><span>Proof line</span></div>
                <p className="small muted">Answers the most frequent objection from version 1:</p>
                <blockquote className="quote">“Looks nice, but I don’t see the price.”</blockquote>
              </div>
              <div className="card tight" style={{ boxShadow: "none", background: "var(--surface)" }}>
                <div className="kv"><span>Ad set</span><span>US · 25–44</span></div>
                <div className="kv" style={{ marginTop: 6 }}><span>Daily budget</span><span className="num">€6.66 of €20</span></div>
                <div className="kv" style={{ marginTop: 6 }}><span>Status</span><span className="tag warn">Waiting for your approval</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <figcaption className="caption">Illustration. Real campaigns use your App Store screens and your competitors’ real ads.</figcaption>
    </figure>
  );
}
