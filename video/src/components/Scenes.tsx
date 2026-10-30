import React from "react";
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Look, SceneProps } from "../types";
import { Title } from "./Title";
import { fontFamily } from "../fonts";

const ease = (frame: number, total: number) =>
  interpolate(frame, [0, total], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

// The app's REAL screenshot as a big rounded card: it is only scaled and moved, never redrawn.
export const ScreenScene: React.FC<{ scene: SceneProps; look: Look; title: string; first: boolean }> = ({
  scene, look, title, first,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: scene.motion === "pop" ? 9 : 16 } });
  const p = ease(frame, scene.durationInFrames);
  const zoom = scene.motion === "zoom_in" ? 1 + 0.06 * p : scene.motion === "zoom_out" ? 1.06 - 0.06 * p : 1;
  const dy = scene.motion === "scroll" || scene.motion === "pan" ? -110 * p : 0;
  return (
    <AbsoluteFill style={{ background: `linear-gradient(180deg, ${look.bg} 0%, ${look.surface} 100%)` }}>
      <div style={{ position: "absolute", width: 900, height: 900, borderRadius: 450, left: 90, top: 700,
        background: look.accent, opacity: 0.16, filter: "blur(120px)" }} />
      <Title text={title} color={look.fg} size={first ? 92 : 72} top={first ? 170 : 200} />
      <div style={{ position: "absolute", left: 0, right: 0, top: first ? 560 : 500, display: "flex",
        justifyContent: "center",
        transform: `translateY(${interpolate(enter, [0, 1], [260, dy])}px) scale(${interpolate(enter, [0, 1], [0.86, zoom])})` }}>
        <Img src={staticFile(scene.src ?? "")} style={{ height: 1240, borderRadius: 46,
          boxShadow: "0 40px 90px rgba(0,0,0,0.28)" }} />
      </div>
    </AbsoluteFill>
  );
};

// A generated photo (never the product) with a slow camera move.
export const PhotoScene: React.FC<{ scene: SceneProps; title: string; first: boolean }> = ({ scene, title, first }) => {
  const frame = useCurrentFrame();
  const p = ease(frame, scene.durationInFrames);
  const scale = scene.motion === "zoom_out" ? 1.14 - 0.1 * p : 1.04 + 0.1 * p;
  const x = scene.motion === "pan" ? interpolate(p, [0, 1], [-40, 40]) : 0;
  const y = scene.motion === "scroll" ? interpolate(p, [0, 1], [40, -40]) : 0;
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <Img src={staticFile(scene.src ?? "")} style={{ width: "100%", height: "100%", objectFit: "cover",
        transform: `scale(${scale}) translate(${x}px, ${y}px)` }} />
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 38%, rgba(0,0,0,0) 62%, rgba(0,0,0,0.55) 100%)" }} />
      <Title text={title} color="#FFFFFF" size={first ? 92 : 74} top={first ? 170 : 200} boxed />
    </AbsoluteFill>
  );
};

// A full-screen statement in the brand colour, words popping in.
export const TextScene: React.FC<{ scene: SceneProps; look: Look; title: string }> = ({ scene, look, title }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = (scene.text ?? scene.overlay).split(/\s+/);
  return (
    <AbsoluteFill style={{ background: look.accent, justifyContent: "center", alignItems: "center" }}>
      <Title text={title} color={look.onAccent} size={60} top={210} />
      <div style={{ fontFamily, fontWeight: 800, fontSize: 128, lineHeight: 1.04, letterSpacing: -3,
        color: look.onAccent, textAlign: "center", padding: "0 80px", display: "flex", flexWrap: "wrap",
        justifyContent: "center", gap: "0 34px" }}>
        {words.map((w, i) => {
          const s = spring({ frame: frame - 6 - i * 4, fps, config: { damping: 10, mass: 0.7 } });
          return <span key={i} style={{ display: "inline-block", opacity: s,
            transform: `scale(${interpolate(s, [0, 1], [0.6, 1])})` }}>{w}</span>;
        })}
      </div>
    </AbsoluteFill>
  );
};
