import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "../fonts";

// The native caption bubble of TikTok / Reels: white box, black bold text. Pops in on the cut.
export const Bubble: React.FC<{ text: string; top?: number; big?: boolean }> = ({ text, top = 520, big }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (!text) return null;
  const s = spring({ frame, fps, config: { damping: 12, mass: 0.5, stiffness: 220 } });
  return (
    <div style={{ position: "absolute", top, left: 60, right: 60, display: "flex", justifyContent: "center",
      transform: `scale(${interpolate(s, [0, 1], [0.7, 1])})`, opacity: s }}>
      <div style={{ background: "#FFFFFF", color: "#111111", fontFamily, fontWeight: 800,
        fontSize: big ? 76 : 60, lineHeight: 1.18, padding: big ? "18px 30px" : "14px 26px", borderRadius: 18,
        textAlign: "center", boxShadow: "0 8px 30px rgba(0,0,0,0.25)", maxWidth: 940 }}>
        {text}
      </div>
    </div>
  );
};
