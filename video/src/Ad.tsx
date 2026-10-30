import React from "react";
import { AbsoluteFill, Audio, interpolate, staticFile, useVideoConfig } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { Captions } from "./components/Captions";
import { EndCard } from "./components/EndCard";
import { PhotoScene, ScreenScene, TextScene } from "./components/Scenes";
import { AdProps } from "./types";

export const Ad: React.FC<AdProps> = (props) => {
  const { fps } = useVideoConfig();
  const { scenes, look, transitionFrames: tf } = props;
  const endStart = props.durationInFrames - props.endCard.durationInFrames;
  const voice = props.voice;
  const music = props.music;
  // the music steps back while the voice speaks
  const musicVolume = (f: number) => {
    if (!music) return 0;
    if (!voice || voice.words.length === 0) return music.volume;
    const t = f / fps;
    const speaking = t >= voice.words[0].start - 0.2 && t <= voice.words[voice.words.length - 1].end + 0.2;
    const fadeOut = interpolate(f, [props.durationInFrames - 20, props.durationInFrames], [1, 0], {
      extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return (speaking ? music.volume * 0.35 : music.volume) * fadeOut;
  };
  return (
    <AbsoluteFill style={{ background: look.bg }}>
      <TransitionSeries>
        {scenes.flatMap((s, i) => {
          const title = i === 0 ? props.hook : s.overlay;
          const body =
            s.kind === "screen" ? <ScreenScene scene={s} look={look} title={title} first={i === 0} />
            : s.kind === "scene" ? <PhotoScene scene={s} title={title} first={i === 0} />
            : <TextScene scene={s} look={look} title={title} />;
          const items = [
            <TransitionSeries.Sequence key={`s${i}`} durationInFrames={s.durationInFrames}>{body}</TransitionSeries.Sequence>,
          ];
          items.push(
            <TransitionSeries.Transition key={`t${i}`} timing={linearTiming({ durationInFrames: tf })}
              presentation={i % 2 === 0 ? slide({ direction: "from-right" }) : fade()} />,
          );
          return items;
        })}
        <TransitionSeries.Sequence durationInFrames={props.endCard.durationInFrames}>
          <EndCard card={props.endCard} look={look} />
        </TransitionSeries.Sequence>
      </TransitionSeries>
      {voice ? <Captions words={voice.words} look={look} until={endStart} /> : null}
      {voice ? <Audio src={staticFile(voice.src)} /> : null}
      {music ? <Audio src={staticFile(music.src)} volume={musicVolume} /> : null}
    </AbsoluteFill>
  );
};
