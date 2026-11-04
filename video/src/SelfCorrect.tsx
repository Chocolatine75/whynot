import React from "react";
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "./fonts";
import { SelfCorrectProps } from "./types";

// The demo's one idea, in ~22 s (16:9): an ad sits in a simulated feed between real competitor ads (blurred), a
// simulated customer says why not, Muse Spark changes ONE gene to answer it, the new version wins head to head
// beyond the measured noise, the owner approves, it goes to Meta. Every word and number comes from the run's own
// files (passed as props); the simulated parts are labelled as such on screen.

const BLUE = "#0866FF";
const INK = "#1C2B33";
const MUTED = "#65676B";
const BG = "#F0F2F5";

const ease = (frame: number, from: number, to: number) =>
  interpolate(frame, [from, to], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

const Step: React.FC<{ n: number; title: string; sub: string; at: number; until: number }> = ({ n, title, sub, at, until }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - at, fps, config: { damping: 14 } });
  const out = 1 - ease(frame, until - 8, until);
  if (frame < at || frame > until) return null;
  return (
    <div style={{ position: "absolute", left: 110, top: 160, width: 820, opacity: s * out,
      transform: `translateY(${interpolate(s, [0, 1], [30, 0])}px)` }}>
      <div style={{ fontSize: 30, fontWeight: 800, color: BLUE, letterSpacing: 1 }}>STEP {n}</div>
      <div style={{ fontSize: 68, fontWeight: 800, color: INK, lineHeight: 1.05, marginTop: 14, letterSpacing: -1.5 }}>{title}</div>
      <div style={{ fontSize: 30, fontWeight: 600, color: MUTED, marginTop: 22, lineHeight: 1.35 }}>{sub}</div>
    </div>
  );
};

const Tag: React.FC<{ text: string; color?: string }> = ({ text, color = "#6E3FF3" }) => (
  <span style={{ background: `${color}1A`, color, fontWeight: 800, fontSize: 22, padding: "8px 16px",
    borderRadius: 999, letterSpacing: 0.5 }}>{text}</span>
);

const Card: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ background: "white", borderRadius: 18, boxShadow: "0 10px 40px rgba(0,0,0,0.12)", overflow: "hidden",
    ...style }}>{children}</div>
);

const Competitor: React.FC<{ src: string; name: string }> = ({ src, name }) => (
  <Card style={{ width: 620, height: 160, position: "relative" }}>
    <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover", filter: "blur(14px)",
      transform: "scale(1.15)" }} />
    <div style={{ position: "absolute", left: 20, top: 18, background: "rgba(255,255,255,0.92)", borderRadius: 10,
      padding: "8px 14px", fontSize: 22, fontWeight: 800, color: INK }}>{name} · real ad, Meta Ad Library</div>
  </Card>
);

const OurAd: React.FC<{ p: SelfCorrectProps; fix: number }> = ({ p, fix }) => {
  const frame = useCurrentFrame();
  const typed = Math.round(interpolate(frame, [fix + 20, fix + 80], [0, p.newSentence.length],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const strike = ease(frame, fix, fix + 18);
  const swapped = frame >= fix + 20;
  const glow = frame >= fix ? 1 - ease(frame, fix + 90, fix + 130) : 0;
  return (
    <Card style={{ width: 620, boxShadow: `0 10px 40px rgba(0,0,0,0.12), 0 0 0 ${6 * glow}px ${BLUE}` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "18px 20px 8px" }}>
        <div style={{ width: 48, height: 48, borderRadius: 24, background: "#E7F0FF" }} />
        <div>
          <div style={{ fontSize: 24, fontWeight: 800, color: INK }}>{p.brand}</div>
          <div style={{ fontSize: 18, color: MUTED, fontWeight: 600 }}>Sponsored</div>
        </div>
      </div>
      <div style={{ padding: "4px 20px 14px", fontSize: 21, lineHeight: 1.35, color: INK, fontWeight: 600, minHeight: 112 }}>
        {p.keptText}{" "}
        {!swapped ? (
          <span style={{ position: "relative", color: strike > 0 ? "#B42318" : INK }}>
            {p.oldSentence}
            <span style={{ position: "absolute", left: 0, top: "50%", height: 3, width: `${strike * 100}%`,
              background: "#B42318" }} />
          </span>
        ) : (
          <span style={{ background: "#E7F0FF", color: BLUE }}>{p.newSentence.slice(0, typed)}</span>
        )}
      </div>
      <Img src={staticFile(p.image)} style={{ width: 620, height: 300, objectFit: "cover", objectPosition: "top" }} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 20px",
        background: "#F7F8FA" }}>
        <div style={{ fontSize: 22, fontWeight: 800, color: INK }}>{p.title}</div>
        <div style={{ background: "#E4E6EB", borderRadius: 8, padding: "10px 18px", fontSize: 20, fontWeight: 800 }}>{p.cta}</div>
      </div>
    </Card>
  );
};

const Bubble: React.FC<{ p: SelfCorrectProps; at: number; until: number }> = ({ p, at, until }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (frame < at || frame > until) return null;
  const s = spring({ frame: frame - at, fps, config: { damping: 12 } });
  const chars = Math.round(interpolate(frame, [at + 8, at + 70], [0, p.objection.length],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  return (
    <div style={{ position: "absolute", left: 110, top: 520, width: 820, opacity: s * (1 - ease(frame, until - 8, until)),
      transform: `scale(${interpolate(s, [0, 1], [0.9, 1])})`, transformOrigin: "left top" }}>
      <div style={{ fontSize: 24, fontWeight: 800, color: MUTED, marginBottom: 12 }}>
        {p.persona} · simulated viewer
      </div>
      <div style={{ background: "white", borderRadius: 28, padding: "30px 36px", fontSize: 40, lineHeight: 1.25,
        fontWeight: 700, color: INK, boxShadow: "0 10px 40px rgba(0,0,0,0.10)", borderLeft: `8px solid #6E3FF3` }}>
        “{p.objection.slice(0, chars)}”
      </div>
    </div>
  );
};

const Duel: React.FC<{ p: SelfCorrectProps; at: number; until: number }> = ({ p, at, until }) => {
  const frame = useCurrentFrame();
  if (frame < at || frame > until) return null;
  const grow = ease(frame, at + 10, at + 55);
  const scale = 110; // px per strength point
  const floorW = p.noiseFloor * scale;
  const verdict = ease(frame, at + 60, at + 75);
  return (
    <div style={{ position: "absolute", left: 110, top: 540, width: 820, opacity: 1 - ease(frame, until - 8, until) }}>
      <div style={{ fontSize: 26, fontWeight: 700, color: MUTED, marginBottom: 18 }}>New version vs original, same simulated feeds</div>
      <div style={{ position: "relative", height: 90, background: "white", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ position: "absolute", left: 40, top: 0, bottom: 0, width: floorW, background: "#E4E6EB" }} />
        <div style={{ position: "absolute", left: 40 + floorW - 4, top: 0, bottom: 0, width: 4, background: MUTED }} />
        <div style={{ position: "absolute", left: 40, top: 26, height: 38, borderRadius: 8, background: BLUE,
          width: grow * p.difference * scale }} />
        <div style={{ position: "absolute", left: 40 + grow * p.difference * scale + 16, top: 22, fontSize: 38,
          fontWeight: 800, color: BLUE }}>+{(grow * p.difference).toFixed(2)}</div>
      </div>
      <div style={{ fontSize: 24, color: MUTED, fontWeight: 600, marginTop: 12 }}>
        grey = measured noise (±{p.noiseFloor.toFixed(2)}, from a retest of the same feeds)
      </div>
      <div style={{ marginTop: 30, opacity: verdict, fontSize: 44, fontWeight: 800, color: "#067647" }}>
        ✓ Better, beyond the noise
        <div style={{ fontSize: 26, color: MUTED, fontWeight: 700, marginTop: 8 }}>retest +{p.retest.toFixed(2)} · Bradley-Terry, head to head</div>
      </div>
    </div>
  );
};

const Launch: React.FC<{ p: SelfCorrectProps; at: number }> = ({ p, at }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (frame < at) return null;
  const click = spring({ frame: frame - at - 25, fps, config: { damping: 9 } });
  const live = spring({ frame: frame - at - 45, fps, config: { damping: 12 } });
  return (
    <div style={{ position: "absolute", left: 110, top: 540, width: 820 }}>
      <div style={{ display: "inline-block", background: frame > at + 25 ? "#067647" : BLUE, color: "white", fontSize: 40,
        fontWeight: 800, padding: "22px 44px", borderRadius: 18, transform: `scale(${1 - 0.06 * Math.sin(click * Math.PI)})` }}>
        {frame > at + 25 ? "✓ Approved by the owner" : "Approve"}
      </div>
      <div style={{ marginTop: 34, opacity: live, transform: `translateY(${interpolate(live, [0, 1], [20, 0])}px)` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 40, fontWeight: 800, color: INK }}>
          <span style={{ width: 22, height: 22, borderRadius: 11, background: "#12B76A", display: "inline-block" }} />
          {p.liveLine}
        </div>
        <div style={{ fontSize: 26, fontWeight: 600, color: MUTED, marginTop: 12 }}>{p.liveSub}</div>
      </div>
    </div>
  );
};

export const SelfCorrect: React.FC<SelfCorrectProps> = (p) => {
  const frame = useCurrentFrame();
  const FIX = 255;
  const DUEL = 390;
  const LAUNCH = 510;
  const feedIn = ease(frame, 0, 35);
  return (
    <AbsoluteFill style={{ background: BG, fontFamily }}>
      <Step n={1} title="Tested before a cent is spent" sub="Your ad, in a simulated feed, between your competitors' real ads." at={0} until={250} />
      <Bubble p={p} at={110} until={250} />
      <Step n={2} title="It fixes itself" sub={`Muse Spark changes one thing, the text, to answer that objection.`} at={FIX} until={385} />
      <Step n={3} title="Kept only if it wins" sub="Head to head against the original, beyond the measured noise." at={DUEL} until={505} />
      <Duel p={p} at={DUEL} until={505} />
      <Step n={4} title="You approve. It goes live." sub="Published on Meta, within your cap. Meta keeps bidding and delivery." at={LAUNCH} until={9999} />
      <Launch p={p} at={LAUNCH} />

      <div style={{ position: "absolute", right: 110, top: 0, bottom: 0, width: 660, display: "flex", flexDirection: "column",
        justifyContent: "center", gap: 18, alignItems: "center",
        transform: `translateY(${interpolate(feedIn, [0, 1], [180, 0])}px)`, opacity: feedIn }}>
        <Competitor src={p.competitors[0]} name={p.competitorNames[0]} />
        <OurAd p={p} fix={FIX} />
        <Competitor src={p.competitors[1]} name={p.competitorNames[1]} />
      </div>
      <div style={{ position: "absolute", left: 110, top: 70 }}><Tag text="SIMULATED VIEWERS · NOT REAL PEOPLE" /></div>
      <div style={{ position: "absolute", left: 110, bottom: 50, fontSize: 30, fontWeight: 800, color: INK }}>
        whynot <span style={{ color: MUTED, fontWeight: 600, fontSize: 24 }}>· {p.footnote}</span>
      </div>
    </AbsoluteFill>
  );
};
