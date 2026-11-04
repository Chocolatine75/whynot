import React from "react";
import { Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "../fonts";
import { Look } from "../types";

// The call to action shown once in the middle (around 4-5 s), not only on the end card: practitioners report
// mid-content CTAs convert better. A small pill with the app icon, below the captions and above the zone the
// feed's own interface covers; it slides in, holds, and leaves.
export const MidCta: React.FC<{ text: string; icon?: string; look: Look; frames: number }> = ({ text, icon, look, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const inn = spring({ frame, fps, config: { damping: 13, stiffness: 240, mass: 0.6 } });
  const out = interpolate(frame, [frames - 8, frames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const k = inn * out;
  return (
    <div style={{ position: "absolute", left: 0, right: 0, top: 1450, display: "flex", justifyContent: "center",
      opacity: k, transform: `translateY(${interpolate(k, [0, 1], [60, 0])}px) scale(${interpolate(k, [0, 1], [0.9, 1])})` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18, background: look.accent, color: look.onAccent,
        borderRadius: 999, padding: "16px 34px 16px 18px", fontFamily, fontWeight: 800, fontSize: 44,
        boxShadow: "0 16px 40px rgba(0,0,0,0.35)" }}>
        {icon ? <Img src={staticFile(icon)} style={{ width: 62, height: 62, borderRadius: 16 }} /> : null}
        {text}
      </div>
    </div>
  );
};
