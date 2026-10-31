import React from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile, useVideoConfig } from "remotion";
import { Captions } from "./components/Captions";
import { EndCard } from "./components/EndCard";
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
          <Shot shot={s} look={props.look} index={i} first={i === 0}
            caption={i === 0 ? props.hook : s.caption} />
        </Sequence>
      ))}
      <Sequence from={endStart} durationInFrames={props.endCard.durationInFrames}>
        <EndCard card={props.endCard} look={props.look} />
      </Sequence>
      {voice ? <Captions words={voice.words} look={props.look} until={endStart} /> : null}
      {props.shots.map((s, i) =>
        s.sfx !== "none" && props.sfx[s.sfx] ? (
          <Sequence key={`fx${i}`} from={starts[i]}>
            <Audio src={staticFile(props.sfx[s.sfx])} volume={0.32} />
          </Sequence>
        ) : null,
      )}
      {voice ? <Audio src={staticFile(voice.src)} /> : null}
      {music ? <Audio src={staticFile(music.src)} volume={musicVolume} /> : null}
    </AbsoluteFill>
  );
};
