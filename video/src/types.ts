// The props a video brief becomes (built by src/whynot/create/remotion.py). Times are in frames at `fps`.

export type Motion = "zoom_in" | "zoom_out" | "scroll" | "pan" | "pop" | "still";

export type SceneProps = {
  kind: "screen" | "scene" | "text";
  durationInFrames: number;
  overlay: string;
  motion: Motion;
  src?: string; // file in the public dir: the real screenshot (screen) or the generated photo (scene)
  text?: string; // the card's text (text)
};

export type Word = { text: string; start: number; end: number; speaker?: "me" | "them"; native?: boolean }; // seconds

export type Look = {
  bg: string;
  fg: string;
  accent: string;
  surface: string;
  onAccent: string; // readable text colour on the accent
};

export type AdProps = {
  fps: number;
  durationInFrames: number;
  transitionFrames: number;
  hook: string;
  scenes: SceneProps[];
  endCard: { durationInFrames: number; appName: string; icon?: string; rating: string; cta: string };
  look: Look;
  voice: { src: string; words: Word[] } | null;
  music: { src: string; volume: number } | null;
};

// --- trend ads: fast shot list (built by src/whynot/create/trend_render.py) ---

export type ShotProps = {
  visual: "text" | "photo" | "screen" | "mascot";
  durationInFrames: number;
  caption: string;
  move: "punch_in" | "slow_zoom" | "shake" | "slide" | "pop" | "still";
  sfx: string; // a key of `sfx`, or "none"
  beat: "trend" | "twist" | "cta";
  src?: string; // photo, real UI crop, or mascot sticker (files in the public dir)
  focus?: "top" | "middle" | "bottom" | "full";
  text?: string;
};

export type TrendProps = {
  fps: number;
  durationInFrames: number;
  hook: string;
  shots: ShotProps[];
  endCard: { durationInFrames: number; appName: string; icon?: string; rating: string; cta: string };
  look: Look;
  voice: { src: string; words: Word[] } | null;
  music: { src: string; volume: number } | null;
  sfx: Record<string, string>; // name -> file
};
