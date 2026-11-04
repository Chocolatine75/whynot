import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "../fonts";
import { Look } from "../types";

// The hook, the line that has to stop the thumb: it lands at once (the first word on frame 0), then word by word,
// each one springing in, in the native white caption box. It stays over every reframe of the first shot.
// themes: 0 the native white box, 1 the brand colour box, 2 big white words with a heavy shadow (no box)
export const HookTitle: React.FC<{ text: string; top?: number; theme?: number; look?: Look }> = ({ text, top = 400,
  theme = 0, look }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (!text) return null;
  const words = text.split(/\s+/);
  const box = spring({ frame, fps, config: { damping: 11, mass: 0.45, stiffness: 260 } });
  return (
    <div style={{ position: "absolute", top, left: 56, right: 56, display: "flex", justifyContent: "center",
      transform: `scale(${interpolate(box, [0, 1], [0.86, 1])}) rotate(${interpolate(box, [0, 1], [-2, 0])}deg)` }}>
      <div style={{ background: theme === 2 ? "transparent" : theme === 1 && look ? look.accent : "#FFFFFF",
        color: theme === 2 ? "#FFFFFF" : theme === 1 && look ? look.onAccent : "#111111", fontFamily, fontWeight: 800,
        fontSize: theme === 2 ? 96 : 80, lineHeight: 1.14, padding: "20px 32px", borderRadius: 20, textAlign: "center",
        textShadow: theme === 2 ? "0 6px 26px rgba(0,0,0,0.85), 0 0 3px rgba(0,0,0,0.9)" : "none",
        boxShadow: theme === 2 ? "none" : "0 10px 36px rgba(0,0,0,0.3)", maxWidth: 960 }}>
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
