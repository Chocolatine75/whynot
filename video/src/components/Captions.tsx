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
  if (current < 0 && (t < words[0].start || t > words[words.length - 1].end + 0.6)) return null;
  // between two words: the last word said. After the last word there is no "next" word, and the old
  // `findIndex(...) - 1` gave -2, which showed the FIRST words again over the last shot (seen on WhatsApp, Nov 2)
  const next = words.findIndex((w) => w.start > t);
  const at = current >= 0 ? current : next < 0 ? words.length - 1 : Math.max(next - 1, 0);
  // up to 4 words, never mixing two speakers: a line said by someone else starts a new caption
  const i0 = Math.max(at, 0);
  const sameLine = (a: number, b: number) =>
    (words[a].speaker ?? "me") === (words[b].speaker ?? "me") && !!words[a].native === !!words[b].native;
  let lineStart = i0;
  while (lineStart > 0 && sameLine(lineStart - 1, i0)) lineStart--;
  const start = lineStart + Math.floor((i0 - lineStart) / 4) * 4;
  let stop = start;
  while (stop < words.length && stop - start < 4 && sameLine(stop, start)) stop++;
  const chunk = words.slice(start, stop);
  const native = !!words[start]?.native;
  return (
    // safe zone: at 65-72 % of the height, below the phone of app shots, above the feed's own interface
    <div style={{ position: "absolute", left: 60, right: 60, top: 1250, display: "flex", flexWrap: "wrap",
      justifyContent: "center", gap: "10px 18px", fontFamily, fontWeight: 800, fontSize: 64,
      textTransform: "uppercase", letterSpacing: -0.5 }}>
      {chunk.map((w, i) => {
        const lit = start + i === at;
        return (
          <span key={i} style={{ padding: "4px 18px", borderRadius: 18, textTransform: native ? "none" : "uppercase",
            color: native ? (lit ? "#111111" : "#FFE15A") : lit ? look.onAccent : "#FFFFFF",
            background: lit ? (native ? "#FFE15A" : look.accent) : "transparent",
            textShadow: lit ? "none" : "0 4px 18px rgba(0,0,0,0.75), 0 0 2px rgba(0,0,0,0.9)" }}>
            {w.text}
          </span>
        );
      })}
    </div>
  );
};
