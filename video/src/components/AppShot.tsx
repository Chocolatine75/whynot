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

// The call fills with faces: the REAL tiles of the call screen (found in its pixels by the engine) pop in one by
// one, each from its own centre, over the dimmed screen. Picture and tiles share one geometry (the same cover fit
// as an <img>), so every tile lands exactly where it is in the screenshot.
const Tiles: React.FC<{ src: string; tiles: number[][]; size: number[]; w: number; h: number; fy: number;
  pop?: string; frames: number }> = ({ src, tiles, size, w, h, fy, pop, frames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const [iw, ih] = size;
  const k = Math.max(w / iw, h / ih);
  const dw = iw * k;
  const dh = ih * k;
  const dx = (w - dw) / 2;
  const dy = (h - dh) * fy;
  const picture = (left: number, top: number): React.CSSProperties => ({
    backgroundImage: `url(${staticFile(src)})`, backgroundSize: `${dw}px ${dh}px`,
    backgroundPosition: `${dx - left}px ${dy - top}px`, backgroundRepeat: "no-repeat",
  });
  // every tile has popped and settled (≈8 frames) before the cut, whatever the shot's length
  const gap = Math.max(1, Math.min(5, Math.floor((frames - 12) / Math.max(1, tiles.length))));
  return (
    <>
      <div style={{ position: "absolute", inset: 0, ...picture(0, 0), opacity: 0.18, filter: "blur(2px)" }} />
      {tiles.map(([x0, y0, x1, y1], i) => {
        const left = dx + x0 * dw;
        const top = dy + y0 * dh;
        const delay = 2 + i * gap;
        const s = spring({ frame: frame - delay, fps, config: { damping: 13, stiffness: 210, mass: 0.7 } });
        return (
          <React.Fragment key={i}>
            <div style={{ position: "absolute", left, top, width: (x1 - x0) * dw, height: (y1 - y0) * dh,
              ...picture(left, top), opacity: Math.min(1, s * 1.4),
              transform: `scale(${interpolate(s, [0, 1], [0.55, 1])})`, borderRadius: 22 * (1 - s) }} />
            {pop ? <Sequence from={delay}><Audio src={staticFile(pop)} volume={0.45} /></Sequence> : null}
          </React.Fragment>
        );
      })}
    </>
  );
};

export const AppShot: React.FC<{ shot: ShotProps; look: Look; pop?: string }> = ({ shot, look, pop }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const n = shot.durationInFrames;
  // the phone flies in on the first app shot only; the next ones keep it in place and change what it shows
  // (re-entering on every 1 s shot made the phone vanish and come back four times in 3 s, Nov 2)
  const enter = shot.continues ? 1 : spring({ frame, fps, config: { damping: 16, stiffness: 150, mass: 0.8 } });
  // a cut inside the phone, never a fade from black (a dark frame showed between two app shots)
  const swap = 1;
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
    reveal = 18 + shown * 82;
  }

  const picture = (style: React.CSSProperties) => (
    <Img src={staticFile(shot.src ?? "")} style={{ position: "absolute", inset: 0, width: "100%", height: "100%",
      objectFit: "cover", objectPosition: `50% ${scrollY}%`, ...style }} />
  );
  const screen = ui === "grid" && shot.tiles && shot.imageSize ? (
    <Tiles src={shot.src ?? ""} tiles={shot.tiles} size={shot.imageSize} w={inner.w} h={inner.h} fy={0} pop={pop}
      frames={n} />
  ) : ui === "rows" ? (
    // the screen is there, dimmed, and its rows light up from the top: never a blank phone
    <>
      {picture({ opacity: 0.22, filter: "blur(1.5px)" })}
      {picture({ clipPath: `inset(0 0 ${100 - reveal}% 0)` })}
    </>
  ) : (
    picture({})
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
            overflow: "hidden", background: ui === "grid" ? "#111" : "#fff", opacity: swap }}>
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
