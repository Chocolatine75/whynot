import type { MarketAd, PlanAd, Score, Variant } from "@/lib/runs";
import AppIcon from "@/components/AppIcon";
import { fileUrl } from "@/lib/format";

/*
 * Three static 3D scenes, drawn with CSS transforms (no WebGL, nothing loops). Each shows one idea at a glance:
 *  - MarketDeck: competitors' real ads fanned out like a hand of cards, the longest-running one in front;
 *  - ExplodedFeed: the simulated feed taken apart in layers, our ad lifted out between two real competitor ads;
 *  - GenerationStack: an ad's generations stacked in depth, the original at the back, the winner in front.
 */

const initials = (s: string) => s.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

export function MarketDeck({ ads }: { ads: MarketAd[] }) {
  // the longest runner in the middle, the next ones alternating outwards
  const top = ads.filter((a) => a.body && a.days !== null).slice(0, 7);
  const order: MarketAd[] = [];
  top.forEach((a, i) => (i % 2 ? order.push(a) : order.unshift(a)));
  const mid = (order.length - 1) / 2;
  const longest = Math.max(1, ...top.map((a) => a.days ?? 0));
  if (top.length < 3) return null;
  return (
    <figure className="scene deck" aria-label="The longest-running competitor ads">
      <div className="deck-stage">
        {order.map((a, i) => {
          const k = i - mid;
          const style = { transform: `translateX(${k * 128}px) translateZ(${-Math.abs(k) * 70}px) rotateY(${k * -14}deg)`, zIndex: 10 - Math.abs(Math.round(k)) };
          return (
            <article key={a.id} className={`deck-card${k === 0 ? " front" : ""}`} style={style}>
              <div className="dc-head"><span className="avatar sm">{initials(a.pageName)}</span><b>{a.pageName}</b></div>
              <p>{a.body}</p>
              <div className="dc-life"><i style={{ width: `${((a.days ?? 0) / longest) * 100}%` }} /></div>
              <span className="dc-days">{a.days} days running</span>
            </article>
          );
        })}
      </div>
      <figcaption>Real ads from the Meta Ad Library, the longest-running in front</figcaption>
    </figure>
  );
}

export function ExplodedFeed({ run, icon, brand, ad, score, competitors }: {
  run: string; icon: string | null; brand: string; ad: PlanAd; score?: Score; competitors: MarketAd[];
}) {
  const Comp = ({ a, z, y }: { a: MarketAd; z: number; y: number }) => (
    <div className="layer comp" style={{ transform: `translate3d(0, ${y}px, ${z}px)` }}>
      <div className="ly-head"><span className="avatar sm">{initials(a.pageName)}</span><b>{a.pageName}</b><i>real ad</i></div>
      <p>{a.body}</p>
    </div>
  );
  return (
    <figure className="scene exploded" aria-label="The simulated feed, taken apart: our ad between two real competitor ads">
      <div className="iso">
        <div className="slab" />
        {competitors[0] && <Comp a={competitors[0]} z={14} y={18} />}
        <div className="layer ours" style={{ transform: "translate3d(0, 172px, 92px)" }}>
          <div className="ly-head"><AppIcon run={run} icon={icon} name={brand} size="sm" /><b>{brand}</b><i>our ad</i></div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={fileUrl(run, ad.image_path)} alt={ad.headline_on_image} />
        </div>
        <div className="drop" style={{ transform: "translate3d(0, 172px, 1px)" }} />
        {competitors[1] && <Comp a={competitors[1]} z={14} y={440} />}
      </div>
      {score && (
        <div className="callout">
          <span className="eyebrow">Viewer agent · simulated</span>
          <p>{score.top_why_not[0] ? `“${score.top_why_not[0]}”` : "Picked this ad."}</p>
          <div className="callout-nums">
            <span><b>{score.lift.toFixed(1)}×</b> picked vs chance</span>
            <span><b>{score.intent.toFixed(1)}</b>/5 would install</span>
          </div>
        </div>
      )}
    </figure>
  );
}

export function GenerationStack({ run, chain }: { run: string; chain: Variant[] }) {
  const n = chain.length;
  return (
    <figure className="scene gens" aria-label="The ad's generations, from the original at the back to the winner in front">
      <div className="gens-stage" style={{ width: 240 + (n - 1) * 70, height: 246 + (n - 1) * 18 }}>
        {chain.map((v, i) => (
          <div key={v.variant_id} className={`gen-card${i === n - 1 ? " winner" : ""}`}
               style={{ transform: `translate3d(${i * 70}px, ${(n - 1 - i) * -18}px, ${i * 60}px) rotateY(-22deg)`, zIndex: i }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {v.image && <img src={fileUrl(run, v.image)} alt={v.texts?.hook ?? ""} loading="lazy" />}
            <span className="gen-tag">{i === 0 ? "Original" : i === n - 1 ? `Winner · gen ${v.generation}` : `Gen ${v.generation}`}</span>
          </div>
        ))}
      </div>
    </figure>
  );
}
