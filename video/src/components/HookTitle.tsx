import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "../fonts";

// The hook, the line that has to stop the thumb: it lands at once (the first word on frame 0), then word by word,
// each one springing in, in the native white caption box. It stays over every reframe of the first shot.
export const HookTitle: React.FC<{ text: string; top?: number }> = ({ text, top = 400 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (!text) return null;
  const words = text.split(/\s+/);
  const box = spring({ frame, fps, config: { damping: 11, mass: 0.45, stiffness: 260 } });
  return (
    <div style={{ position: "absolute", top, left: 56, right: 56, display: "flex", justifyContent: "center",
      transform: `scale(${interpolate(box, [0, 1], [0.86, 1])}) rotate(${interpolate(box, [0, 1], [-2, 0])}deg)` }}>
      <div style={{ background: "#FFFFFF", color: "#111111", fontFamily, fontWeight: 800, fontSize: 80,
        lineHeight: 1.14, padding: "20px 32px", borderRadius: 20, textAlign: "center",
        boxShadow: "0 10px 36px rgba(0,0,0,0.3)", maxWidth: 960 }}>
        {words.map((w, i) => {
          const s = spring({ frame: frame - i * 3, fps, config: { damping: 12, stiffness: 300, mass: 0.4 } });
          return (
            <span key={i} style={{ display: "inline-block", marginRight: i < words.length - 1 ? 18 : 0,
              opacity: i === 0 ? 1 : s, transform: `translateY(${interpolate(s, [0, 1], [28, 0])}px)` }}>{w}</span>
          );
        })}
      </div>
    </div>
  );
};
