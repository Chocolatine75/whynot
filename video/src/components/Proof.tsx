import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "../fonts";
import { Look } from "../types";

const Star: React.FC<{ on: boolean; size: number; delay: number }> = ({ on, size, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - delay, fps, config: { damping: 9, stiffness: 220 } });
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ transform: `scale(${s})` }}>
      <path d="M12 2l2.9 6.6 7.1.6-5.4 4.7 1.6 7L12 17.3 5.8 20.9l1.6-7L2 9.2l7.1-.6z"
        fill={on ? "#FFB800" : "#D9D9D9"} />
    </svg>
  );
};

// A verified App Store review: its stars and the quote, word for word.
export const ReviewCard: React.FC<{ quote: string; stars: number; look: Look }> = ({ quote, stars, look }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 14, stiffness: 180 } });
  return (
    <AbsoluteFill style={{ background: `linear-gradient(160deg, ${look.accent} 0%, ${look.fg} 100%)`,
      justifyContent: "center", alignItems: "center", padding: 70 }}>
      <div style={{ background: "#FFFFFF", borderRadius: 44, padding: "60px 56px", width: 900,
        boxShadow: "0 40px 90px rgba(0,0,0,0.35)", fontFamily,
        transform: `translateY(${interpolate(enter, [0, 1], [160, 0])}px) rotate(${interpolate(enter, [0, 1], [-4, -1.5])}deg)`,
        opacity: enter }}>
        <div style={{ display: "flex", gap: 10 }}>
          {[0, 1, 2, 3, 4].map((i) => <Star key={i} on={i < stars} size={70} delay={6 + i * 3} />)}
        </div>
        <div style={{ fontWeight: 800, fontSize: 62, lineHeight: 1.18, color: "#111111", marginTop: 34,
          letterSpacing: -1 }}>
          “{quote}”
        </div>
        <div style={{ fontWeight: 600, fontSize: 36, color: "#6B6B6B", marginTop: 30 }}>App Store review</div>
      </div>
    </AbsoluteFill>
  );
};

// A finger tap on the demo screen: a ring that presses in, then ripples out, at the focus region.
export const Tap: React.FC<{ y: number }> = ({ y }) => {
  const frame = useCurrentFrame();
  const t = frame - 14; // after the shot settles
  if (t < 0) return null;
  const press = interpolate(t, [0, 5, 10], [1.3, 0.85, 1], { extrapolateRight: "clamp" });
  const ripple = interpolate(t % 30, [6, 26], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: 540 - 70, top: y - 70, width: 140, height: 140 }}>
      <div style={{ position: "absolute", inset: 0, borderRadius: 70, border: "8px solid rgba(255,255,255,0.9)",
        transform: `scale(${1 + ripple * 1.6})`, opacity: 1 - ripple }} />
      <div style={{ position: "absolute", inset: 22, borderRadius: 48, background: "rgba(255,255,255,0.85)",
        boxShadow: "0 0 0 6px rgba(0,0,0,0.15)", transform: `scale(${press})` }} />
    </div>
  );
};
