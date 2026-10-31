import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "../fonts";

// A headline whose words rise in one after another.
export const Title: React.FC<{ text: string; color: string; size: number; boxed?: boolean; top: number }> = ({
  text, color, size, boxed, top,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = text.split(/\s+/).filter(Boolean);
  return (
    <div style={{ position: "absolute", top, left: 70, right: 70, display: "flex", justifyContent: "center" }}>
      <div
        style={{
          fontFamily, fontWeight: 800, fontSize: size, lineHeight: 1.1, letterSpacing: -1, color,
          textAlign: "center", padding: boxed ? "22px 34px" : 0, borderRadius: 30,
          background: boxed ? "rgba(0,0,0,0.62)" : "transparent",
          display: "flex", flexWrap: "wrap", justifyContent: "center", gap: `0 ${size * 0.26}px`,
        }}
      >
        {words.map((w, i) => {
          const s = spring({ frame: frame - i * 3, fps, config: { damping: 14, mass: 0.6 } });
          return (
            <span key={i} style={{ display: "inline-block", opacity: s,
              transform: `translateY(${interpolate(s, [0, 1], [size * 0.5, 0])}px)` }}>
              {w}
            </span>
          );
        })}
      </div>
    </div>
  );
};
