import React from "react";
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "../fonts";
import { AdProps, Look } from "../types";

export const EndCard: React.FC<{ card: AdProps["endCard"] & { offer?: string }; look: Look }> = ({ card, look }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // everything lands in about half a second (a slow fade on a white card read as the video being over)
  const icon = spring({ frame, fps, config: { damping: 10, stiffness: 260, mass: 0.5 } });
  const text = spring({ frame: frame - 3, fps, config: { damping: 16, stiffness: 240 } });
  const button = spring({ frame: frame - 6, fps, config: { damping: 11, stiffness: 260 } });
  const pulse = 1 + 0.045 * Math.sin(Math.max(0, frame - 14) / 4);
  return (
    <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 38%, ${look.surface} 0%, ${look.bg} 70%)`,
      justifyContent: "center", alignItems: "center", fontFamily, color: look.fg, gap: 44 }}>
      {card.icon ? (
        <Img src={staticFile(card.icon)} style={{ width: 300, height: 300, borderRadius: 68,
          boxShadow: "0 30px 70px rgba(0,0,0,0.22)",
          transform: `scale(${interpolate(icon, [0, 1], [0.6, 1])}) rotate(${interpolate(icon, [0, 1], [-8, 0])}deg)` }} />
      ) : null}
      <div style={{ textAlign: "center", opacity: text, transform: `translateY(${interpolate(text, [0, 1], [30, 0])}px)` }}>
        <div style={{ fontWeight: 800, fontSize: 92, letterSpacing: -2 }}>{card.appName}</div>
        <div style={{ fontWeight: 600, fontSize: 44, opacity: 0.75, marginTop: 10 }}>{card.offer || card.rating}</div>
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
