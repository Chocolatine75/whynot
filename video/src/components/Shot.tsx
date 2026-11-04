import React from "react";
import { AbsoluteFill, Img, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "../fonts";
import { Look, ShotProps } from "../types";
import { AppShot } from "./AppShot";
import { Bubble } from "./Bubble";
import { ReviewCard } from "./Proof";

// One shot: a full-bleed visual that never stops moving, the caption bubble, a flash on hard cuts.
export const Shot: React.FC<{ shot: ShotProps; look: Look; caption: string; index: number; first: boolean;
  pop?: string; theme?: number }> = ({ shot, look, caption, index, first, pop, theme = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = shot.durationInFrames;
  const p = frame / n;
  const hit = spring({ frame, fps, config: { damping: 15, stiffness: 260, mass: 0.6 } });
  let scale = 1 + 0.06 * p; // always drifting: a still frame is a scroll
  let x = 0;
  let y = 0;
  let rot = 0;
  if (shot.move === "punch_in") scale = interpolate(hit, [0, 1], [1.28, 1.04]) + 0.05 * p;
  if (shot.move === "pop") scale = interpolate(hit, [0, 1], [0.82, 1]) + 0.04 * p;
  // a whip: the new image is already on screen, slightly zoomed so its edges never show, and settles in
  if (shot.move === "slide") {
    x = interpolate(hit, [0, 1], [220, 0]);
    scale = 1.18 - 0.12 * hit + 0.04 * p;
  }
  // a reframe of the same photo: close on the faces (they sit in the upper third of a phone photo), punched in
  let origin = "50% 50%";
  if (shot.move === "close") {
    scale = interpolate(hit, [0, 1], [1.62, 1.42]) + 0.05 * p;
    origin = "50% 30%";
  }
  // a slow sideways move across the picture, zoomed so no edge ever shows
  if (shot.move === "pan") {
    scale = 1.24 + 0.03 * p;
    x = interpolate(p, [0, 1], [-70, 70]);
  }
  if (shot.move === "still") scale = 1.02;
  if (shot.move === "shake") scale = Math.max(scale, 1.1); // zoomed enough that the shake never shows an edge
  if (shot.move === "shake" && frame < 12) {
    x = (random(`x${index}-${frame}`) - 0.5) * 36;
    y = (random(`y${index}-${frame}`) - 0.5) * 36;
    rot = (random(`r${index}-${frame}`) - 0.5) * 2.5;
  }
  const transform = `translate(${x}px, ${y}px) scale(${scale}) rotate(${rot}deg)`;
  // a light flash on whoosh cuts only: a full white frame is aggressive
  const flash = shot.sfx === "whoosh";
  const flashOpacity = flash ? interpolate(frame, [0, 2], [0.3, 0], { extrapolateRight: "clamp" }) : 0;

  let visual: React.ReactNode = null;
  if (shot.visual === "screen") {
    visual = <AppShot shot={shot} look={look} pop={pop} theme={theme} />;
  } else if (shot.visual === "photo") {
    visual = (
      <Img src={staticFile(shot.src ?? "")} style={{ width: "100%", height: "100%", objectFit: "cover",
        objectPosition: "50% 50%", transform, transformOrigin: origin }} />
    );
  } else if (shot.visual === "review") {
    visual = <ReviewCard quote={shot.quote ?? ""} stars={shot.stars ?? 5} look={look} />;
  } else if (shot.visual === "mascot") {
    visual = (
      <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 60%, ${look.accent} 0%, ${look.fg} 85%)`,
        justifyContent: "center", alignItems: "center" }}>
        <Img src={staticFile(shot.src ?? "")} style={{ height: 1150, objectFit: "contain",
          filter: "drop-shadow(0 0 0 #fff) drop-shadow(6px 0 0 #fff) drop-shadow(-6px 0 0 #fff) drop-shadow(0 6px 0 #fff) drop-shadow(0 -6px 0 #fff) drop-shadow(0 30px 40px rgba(0,0,0,0.45))",
          transform: `${transform} rotate(${-3 + 6 * p}deg)` }} />
      </AbsoluteFill>
    );
  } else {
    const words = (shot.text ?? "").split(/\s+/);
    const dark = index % 2 === 0;
    visual = (
      <AbsoluteFill style={{ background: dark ? "#0E0E10" : look.accent, justifyContent: "center",
        alignItems: "center", padding: 80 }}>
        <div style={{ fontFamily, fontWeight: 800, fontSize: 132, lineHeight: 1.02, letterSpacing: -3,
          textAlign: "center", color: dark ? "#FFFFFF" : look.onAccent, transform }}>
          {words.map((w, i) => {
            // the call to action is read at once: a word fading in on the last card looked unfinished ("Free" half
            // transparent on the end, seen on WhatsApp)
            const s = shot.beat === "cta" ? 1 : spring({ frame: frame - i * 2, fps, config: { damping: 11, stiffness: 240 } });
            return <span key={i} style={{ display: "inline-block", marginRight: 30, opacity: s,
              transform: `translateY(${interpolate(s, [0, 1], [60, 0])}px)` }}>{w}</span>;
          })}
        </div>
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{ background: "#000", overflow: "hidden" }}>
      {visual}
      {shot.visual === "photo" ? (
        <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0) 40%)" }} />
      ) : null}
      {/* one text layer on the app and the review: the spoken captions; the bubble would cover the proof */}
      {shot.visual === "screen" || shot.visual === "review" || shot.hook ? null : (
        <Bubble text={caption} top={first ? 430 : 480} big={first} />
      )}
      <AbsoluteFill style={{ background: "#FFFFFF", opacity: flashOpacity }} />
    </AbsoluteFill>
  );
};
