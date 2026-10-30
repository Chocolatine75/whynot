import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "../fonts";
import { Look, Word } from "../types";

// Word-by-word captions synced to the voice (most Reels are watched muted): the spoken word is lit.
export const Captions: React.FC<{ words: Word[]; look: Look; until: number }> = ({ words, look, until }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  if (frame >= until || words.length === 0) return null;
  const current = words.findIndex((w) => t >= w.start && t < w.end + 0.15);
  if (current < 0 && (t < words[0].start || t > words[words.length - 1].end + 0.3)) return null;
  const at = current < 0 ? words.findIndex((w) => w.start > t) - 1 : current;
  const start = Math.max(0, Math.floor(Math.max(at, 0) / 4) * 4);
  const chunk = words.slice(start, start + 4);
  return (
    <div style={{ position: "absolute", left: 60, right: 60, bottom: 250, display: "flex", flexWrap: "wrap",
      justifyContent: "center", gap: "10px 18px", fontFamily, fontWeight: 800, fontSize: 64,
      textTransform: "uppercase", letterSpacing: -0.5 }}>
      {chunk.map((w, i) => {
        const lit = start + i === at;
        return (
          <span key={i} style={{ padding: "4px 18px", borderRadius: 18,
            color: lit ? look.onAccent : "#FFFFFF", background: lit ? look.accent : "transparent",
            textShadow: lit ? "none" : "0 4px 18px rgba(0,0,0,0.75), 0 0 2px rgba(0,0,0,0.9)" }}>
            {w.text}
          </span>
        );
      })}
    </div>
  );
};
