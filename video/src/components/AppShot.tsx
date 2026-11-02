import React from "react";
import { AbsoluteFill, Audio, Img, interpolate, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Look, ShotProps } from "../types";
import { Tap } from "./Proof";

// The app's REAL interface (a crop of its store screenshot), shown the way ads show products: inside a phone,
// on the brand's moving background, and animated so it reads as the app working, not as a frozen screenshot.
// Every pixel inside the phone is the app's own; only the frame, the background and the motion are drawn here.
//
// Motions (`shot.ui`):
//   rows   the screen fills from the top, row by row: messages or chats arriving
//   grid   the screen is cut into tiles that pop in one by one (a call filling with faces), a pop sound each
//   zoom   the phone pushes into the focus region, which a ring points at
//   scroll the interface scrolls to the focus region, like a thumb flicking
//   float  the phone settles and floats (default)
// Layout: the phone lives in the top 63 % of the frame; captions sit below it (never over the interface) and
// above the zone the TikTok / Reels interface covers.

export const PHONE = { w: 560, h: 1080, top: 120, radius: 64, bezel: 14 };
const FOCUS_Y: Record<string, number> = { top: 0.18, middle: 0.5, bottom: 0.82, full: 0.5 };

const Background: React.FC<{ look: Look }> = ({ look }) => {
  const frame = useCurrentFrame();
  const a = Math.sin(frame / 40) * 60;
  const b = Math.cos(frame / 55) * 80;
  return (
    <AbsoluteFill style={{ background: `linear-gradient(170deg, ${look.fg} 0%, #0b0b0d 100%)`, overflow: "hidden" }}>
      <div style={{ position: "absolute", width: 900, height: 900, borderRadius: 450, left: -260 + a, top: -180,
        background: look.accent, opacity: 0.38, filter: "blur(140px)" }} />
      <div style={{ position: "absolute", width: 800, height: 800, borderRadius: 400, right: -300 + b, bottom: 200,
        background: look.accent, opacity: 0.22, filter: "blur(160px)" }} />
    </AbsoluteFill>
  );
};

const Tiles: React.FC<{ src: string; cols: number; rows: number; w: number; h: number; pop?: string }> = ({
  src, cols, rows, w, h, pop,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const tw = w / cols;
  const th = h / rows;
  const tiles = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const k = r * cols + c;
      const delay = 6 + k * 5;
      const s = spring({ frame: frame - delay, fps, config: { damping: 11, stiffness: 240, mass: 0.6 } });
      tiles.push(
        <div key={k} style={{ position: "absolute", left: c * tw, top: r * th, width: tw, height: th,
          backgroundImage: `url(${staticFile(src)})`, backgroundSize: `${w}px ${h}px`,
          backgroundPosition: `${-c * tw}px ${-r * th}px`, transform: `scale(${s})`, opacity: s,
          borderRadius: 18 * (1 - s) }} />,
      );
      if (pop) {
        tiles.push(<Sequence key={`p${k}`} from={delay}><Audio src={staticFile(pop)} volume={0.5} /></Sequence>);
      }
    }
  }
  return <>{tiles}</>;
};

export const AppShot: React.FC<{ shot: ShotProps; look: Look; pop?: string }> = ({ shot, look, pop }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = shot.durationInFrames;
  const enter = spring({ frame, fps, config: { damping: 16, stiffness: 150, mass: 0.8 } });
  const float = Math.sin(frame / 18) * 6;
  const ui = shot.ui ?? "float";
  const fy = FOCUS_Y[shot.focus ?? "full"];
  const inner = { w: PHONE.w - 2 * PHONE.bezel, h: PHONE.h - 2 * PHONE.bezel };

  let push = 1;
  let originY = 50;
  if (ui === "zoom") {
    push = interpolate(spring({ frame: frame - 10, fps, config: { damping: 18, stiffness: 120 } }), [0, 1], [1, 1.35]);
    originY = fy * 100;
  }
  const scrollY = ui === "scroll"
    ? interpolate(spring({ frame: frame - 6, fps, config: { damping: 20, stiffness: 90 } }), [0, 1], [0, fy * 100])
    : fy * 100;

  // rows: the visible part grows from the top in steps, each step springing open
  let reveal = 100;
  if (ui === "rows") {
    const steps = 5;
    let shown = 0;
    for (let i = 0; i < steps; i++) {
      shown += spring({ frame: frame - 4 - i * Math.max(3, Math.floor(n / (steps + 2))), fps,
        config: { damping: 14, stiffness: 200 } }) / steps;
    }
    reveal = shown * 100;
  }

  const screen = ui === "grid" ? (
    <Tiles src={shot.src ?? ""} cols={shot.grid?.[0] ?? 2} rows={shot.grid?.[1] ?? 3} w={inner.w} h={inner.h} pop={pop} />
  ) : (
    <Img src={staticFile(shot.src ?? "")} style={{ width: "100%", height: "100%", objectFit: "cover",
      objectPosition: `50% ${scrollY}%`, clipPath: `inset(0 0 ${100 - reveal}% 0)` }} />
  );

  const ring = ui === "zoom" ? interpolate(frame, [18, 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) : 0;
  return (
    <AbsoluteFill>
      <Background look={look} />
      <AbsoluteFill style={{ perspective: 1800 }}>
        <div style={{ position: "absolute", left: (1080 - PHONE.w) / 2, top: PHONE.top + float, width: PHONE.w,
          height: PHONE.h, borderRadius: PHONE.radius, background: "#0a0a0a", padding: PHONE.bezel,
          boxShadow: "0 60px 120px rgba(0,0,0,0.55), inset 0 0 0 3px rgba(255,255,255,0.08)",
          transformOrigin: `50% ${originY}%`,
          transform: `translateY(${interpolate(enter, [0, 1], [380, 0])}px) rotateX(${interpolate(enter, [0, 1], [24, 0])}deg) scale(${push})`,
          opacity: interpolate(enter, [0, 0.3], [0, 1], { extrapolateRight: "clamp" }) }}>
          <div style={{ position: "relative", width: "100%", height: "100%", borderRadius: PHONE.radius - PHONE.bezel,
            overflow: "hidden", background: ui === "grid" ? "#111" : "#fff" }}>
            {screen}
            {ring > 0 ? (
              <div style={{ position: "absolute", left: 24, right: 24, top: `${fy * 100 - 9}%`, height: "18%",
                borderRadius: 28, border: `8px solid ${look.accent}`, opacity: ring,
                transform: `scale(${interpolate(ring, [0, 1], [1.15, 1])})` }} />
            ) : null}
          </div>
        </div>
      </AbsoluteFill>
      {shot.tap ? <Tap y={PHONE.top + PHONE.bezel + fy * inner.h} /> : null}
    </AbsoluteFill>
  );
};
