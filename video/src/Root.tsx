import React from "react";
import { Composition } from "remotion";
import { Ad } from "./Ad";
import { TrendAd } from "./TrendAd";
import { AdProps, TrendProps } from "./types";

const sample: AdProps = {
  fps: 30, durationInFrames: 30 * 10, transitionFrames: 10, hook: "Your ads, made for you",
  scenes: [
    { kind: "text", durationInFrames: 120, overlay: "whynot", motion: "pop", text: "Tested before you spend" },
    { kind: "text", durationInFrames: 120, overlay: "Then published", motion: "pop", text: "You approve" },
  ],
  endCard: { durationInFrames: 80, appName: "whynot", rating: "On the App Store", cta: "Start" },
  look: { bg: "#FDFAF9", fg: "#261412", accent: "#FF7A6B", surface: "#F7E5E3", onAccent: "#261412" },
  voice: null, music: null,
};

const trendSample: TrendProps = {
  fps: 30, durationInFrames: 30 * 6, hook: "Tell me you're learning Vietnamese",
  shots: [
    { visual: "text", durationInFrames: 45, caption: "", move: "punch_in", sfx: "none", beat: "trend", text: "Ma ma ma ma" },
    { visual: "text", durationInFrames: 45, caption: "six meanings", move: "shake", sfx: "none", beat: "trend", text: "Six tones" },
  ],
  endCard: { durationInFrames: 90, appName: "whynot", rating: "On the App Store", cta: "Start" },
  look: sample.look, voice: null, music: null, sfx: {},
};

export const Root: React.FC = () => (
  <>
    <Composition id="Ad" component={Ad} width={1080} height={1920} fps={30} durationInFrames={300}
      defaultProps={sample}
      calculateMetadata={({ props }) => ({ durationInFrames: props.durationInFrames, fps: props.fps })} />
    <Composition id="Trend" component={TrendAd} width={1080} height={1920} fps={30} durationInFrames={180}
      defaultProps={trendSample}
      calculateMetadata={({ props }) => ({ durationInFrames: props.durationInFrames, fps: props.fps })} />
  </>
);
