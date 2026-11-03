import React from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile, useVideoConfig } from "remotion";
import { Captions } from "./components/Captions";
import { EndCard } from "./components/EndCard";
import { HookTitle } from "./components/HookTitle";
import { Shot } from "./components/Shot";
import { TrendProps } from "./types";

// A trend ad: hard cuts every second or so, sound effects on the cuts, voice + captions, music under it.
export const TrendAd: React.FC<TrendProps> = (props) => {
  const { fps } = useVideoConfig();
  const starts: number[] = [];
  let t = 0;
  for (const s of props.shots) {
    starts.push(t);
    t += s.durationInFrames;
  }
  const endStart = t;
  // the hook title spans the first shot and its reframes (older props: the first shot only)
  let hookFrames = 0;
  for (const s of props.shots) {
    if (!s.hook) break;
    hookFrames += s.durationInFrames;
  }
  if (hookFrames === 0) hookFrames = props.shots[0]?.durationInFrames ?? 0;
  const voice = props.voice;
  const music = props.music;
  const musicVolume = (f: number) => {
    if (!music) return 0;
    const fadeOut = interpolate(f, [props.durationInFrames - 15, props.durationInFrames], [1, 0], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    if (!voice || voice.words.length === 0) return music.volume * fadeOut;
    const s = f / fps;
    const speaking = s >= voice.words[0].start - 0.15 && s <= voice.words[voice.words.length - 1].end + 0.15;
    return (speaking ? music.volume * 0.4 : music.volume) * fadeOut;
  };
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {props.shots.map((s, i) => (
        <Sequence key={i} from={starts[i]} durationInFrames={s.durationInFrames}>
          <Shot shot={{ ...s, hook: i === 0 || s.hook }} look={props.look} index={i} first={i === 0}
            caption={voice ? "" : s.caption} pop={props.sfx.pop} />
        </Sequence>
      ))}
      <Sequence from={endStart} durationInFrames={props.endCard.durationInFrames}>
        <EndCard card={props.endCard} look={props.look} />
      </Sequence>
      {/* one text layer: with a voice, its captions are the text (a bubble saying the same thing on top doubled
          it); the hook bubble owns the first shot, the spoken captions start after it */}
      {/* a first shot that is a text card already says the hook: no second copy of it on top */}
      {props.shots[0]?.visual !== "text" ? (
        <Sequence from={0} durationInFrames={hookFrames}>
          <HookTitle text={props.hook} />
        </Sequence>
      ) : null}
      {voice ? <Captions words={voice.words} look={props.look} from={hookFrames}
        until={endStart} cuts={starts.map((f) => f / fps)} /> : null}
      {props.shots.map((s, i) =>
        s.sfx !== "none" && props.sfx[s.sfx] ? (
          <Sequence key={`fx${i}`} from={starts[i]}>
            <Audio src={staticFile(props.sfx[s.sfx])} volume={0.55} />
          </Sequence>
        ) : null,
      )}
      {voice ? <Audio src={staticFile(voice.src)} /> : null}
      {music ? <Audio src={staticFile(music.src)} volume={musicVolume} /> : null}
    </AbsoluteFill>
  );
};
