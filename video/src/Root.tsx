import React from "react";
import { Composition } from "remotion";
import { Ad } from "./Ad";
import { SelfCorrect } from "./SelfCorrect";
import { StaticMotion } from "./StaticMotion";
import { TrendAd } from "./TrendAd";
import { AdProps, MotionProps, SelfCorrectProps, TrendProps } from "./types";

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

const motionSample: MotionProps = {
  fps: 30, durationInFrames: 210, layout: "split", headline: "No time to learn Vietnamese?", keyWords: 1,
  proof: "Rated 4.8 on the App Store", cta: "Start free", base: "#FFF8EE", ink: "#1B1B1F", look: sample.look,
  screen: "screen.png", content: {},
};


// Defaults = the VietBuddy run of Nov 3 (outputs/runs/web/20261103-125927-id6796837982): report.md, simulation.json.
const selfCorrectSample: SelfCorrectProps = {
  brand: "VietBuddy: Learn Vietnamese", title: "Warm Phrases For Family", cta: "Learn more", image: "after.png",
  keptText: "Walking in with your partner, you want kindness more than polish.",
  oldSentence: "Rehearse a gentle greeting and voice handy phrases aloud at an easy tempo.",
  newSentence: "Practice real situations such as talking with family and speak useful phrases out loud at your own pace.",
  persona: "Partner and in-law confidence builder",
  objection: "I like the sound of it but I'm wary it'll just be another paid app that doesn't really help me speak",
  difference: 2.98, noiseFloor: 1.63, retest: 2.64,
  competitors: ["comp1.jpg", "comp2.jpg"], competitorNames: ["Ling", "Competitor"],
  liveLine: "Launched on Meta · Nov 4", liveSub: "This exact ad, on Instagram and Facebook, €5/day cap",
  footnote: "simulated scores; the launch is real",
};

export const Root: React.FC = () => (
  <>
    <Composition id="Ad" component={Ad} width={1080} height={1920} fps={30} durationInFrames={300}
      defaultProps={sample}
      calculateMetadata={({ props }) => ({ durationInFrames: props.durationInFrames, fps: props.fps })} />
    <Composition id="Trend" component={TrendAd} width={1080} height={1920} fps={30} durationInFrames={180}
      defaultProps={trendSample}
      calculateMetadata={({ props }) => ({ durationInFrames: props.durationInFrames, fps: props.fps })} />
    <Composition id="StaticMotion" component={StaticMotion} width={1080} height={1920} fps={30} durationInFrames={210}
      defaultProps={motionSample}
      calculateMetadata={({ props }) => ({ durationInFrames: props.durationInFrames, fps: props.fps })} />
    <Composition id="SelfCorrect" component={SelfCorrect} width={1920} height={1080} fps={30} durationInFrames={660}
      defaultProps={selfCorrectSample} />
  </>
);
