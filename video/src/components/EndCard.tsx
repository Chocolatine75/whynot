import React from "react";
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "../fonts";
import { AdProps, Look } from "../types";

export const EndCard: React.FC<{ card: AdProps["endCard"]; look: Look }> = ({ card, look }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const icon = spring({ frame, fps, config: { damping: 9 } });
  const text = spring({ frame: frame - 6, fps, config: { damping: 18 } });
  const button = spring({ frame: frame - 12, fps, config: { damping: 12 } });
  const pulse = 1 + 0.035 * Math.sin(Math.max(0, frame - 25) / 6);
  return (
    <AbsoluteFill style={{ background: `linear-gradient(180deg, ${look.bg} 0%, ${look.surface} 100%)`,
      justifyContent: "center", alignItems: "center", fontFamily, color: look.fg, gap: 44 }}>
      {card.icon ? (
        <Img src={staticFile(card.icon)} style={{ width: 300, height: 300, borderRadius: 68,
          boxShadow: "0 30px 70px rgba(0,0,0,0.22)", transform: `scale(${interpolate(icon, [0, 1], [0.5, 1])})` }} />
      ) : null}
      <div style={{ textAlign: "center", opacity: text, transform: `translateY(${interpolate(text, [0, 1], [30, 0])}px)` }}>
        <div style={{ fontWeight: 800, fontSize: 92, letterSpacing: -2 }}>{card.appName}</div>
        <div style={{ fontWeight: 600, fontSize: 44, opacity: 0.75, marginTop: 10 }}>{card.rating}</div>
      </div>
      <div style={{ background: look.accent, color: look.onAccent, fontWeight: 800, fontSize: 64,
        padding: "34px 80px", borderRadius: 999, opacity: button,
        transform: `scale(${interpolate(button, [0, 1], [0.7, 1]) * pulse})`,
        boxShadow: "0 24px 50px rgba(0,0,0,0.18)" }}>
        {card.cta}
      </div>
    </AbsoluteFill>
  );
};
