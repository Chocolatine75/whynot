import React from "react";
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { fontFamily } from "./fonts";
import { MotionProps } from "./types";

// A static ad brought to life for Reels and Stories (9:16, ~7 s): the headline lands word by word, the REAL app
// screen rises and scrolls in a phone, the layout's verified fact gets its own beat (a real review with its stars,
// verified benefits ticked one by one, a verified number counting up, the customer's objection struck out), then
// the call to action. All drawn in code from the ad's own copy and screens: nothing generated.
// Text stays inside the zone Stories / Reels leave free (y 250 to 1580).

const SAFE_TOP = 250;

const Words: React.FC<{ text: string; keyWords: number; accent: string; color: string; size: number;
  delay?: number }> = ({ text, keyWords, accent, color, size, delay = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = text.split(/\s+/);
  const firstKey = words.length - keyWords;
  return (
    <div style={{ fontFamily, fontWeight: 800, fontSize: size, lineHeight: 1.04, letterSpacing: -2, color }}>
      {words.map((w, i) => {
        const s = spring({ frame: frame - delay - i * 3, fps, config: { damping: 13, stiffness: 260, mass: 0.5 } });
        return (
          <span key={i} style={{ display: "inline-block", marginRight: size * 0.24, opacity: s,
            color: keyWords && i >= firstKey ? accent : color,
            transform: `translateY(${interpolate(s, [0, 1], [size * 0.5, 0])}px)` }}>{w}</span>
        );
      })}
    </div>
  );
};

const Stars: React.FC<{ n: number; color: string; delay: number }> = ({ n, color, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <div style={{ display: "flex", gap: 10 }}>
      {Array.from({ length: n }).map((_, i) => {
        const s = spring({ frame: frame - delay - i * 3, fps, config: { damping: 10, stiffness: 280 } });
        return <svg key={i} width={54} height={54} viewBox="0 0 24 24" style={{ transform: `scale(${s})` }}>
          <path fill={color} d="M12 2l2.9 6.6 7.1.6-5.4 4.7 1.6 7L12 17.3 5.8 20.9l1.6-7L2 9.2l7.1-.6z" />
        </svg>;
      })}
    </div>
  );
};

export const StaticMotion: React.FC<MotionProps> = (p) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { look } = p;
  const fact = p.layout === "review_card" && p.content.review ? "review"
    : p.layout === "benefits" && p.content.benefits?.length ? "benefits"
    : p.layout === "big_number" && p.content.number ? "number"
    : (p.layout === "before_after" || p.layout === "comparison") && p.content.objection ? "objection" : null;
  const factAt = 70; // the fact takes the headline's place from here
  const ctaAt = p.durationInFrames - 60;

  // the phone rises from below, then the real screen scrolls slowly, like a thumb reading it
  const rise = spring({ frame: frame - 10, fps, config: { damping: 16, stiffness: 140, mass: 0.8 } });
  const scroll = interpolate(frame, [30, p.durationInFrames], [0, 38], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const float = Math.sin(frame / 20) * 8;
  const phoneW = 600;
  const phoneTop = 860;
  const second = p.second ? spring({ frame: frame - 26, fps, config: { damping: 16, stiffness: 140 } }) : 0;

  // the headline leaves when the fact arrives, and comes back over the call to action
  const out = fact ? spring({ frame: frame - factAt, fps, config: { damping: 18, stiffness: 200 } }) : 0;
  const back = fact ? spring({ frame: frame - ctaAt, fps, config: { damping: 18, stiffness: 200 } }) : 0;
  const headlineShown = fact ? 1 - out + back : 1;
  const factIn = fact ? spring({ frame: frame - factAt - 4, fps, config: { damping: 14, stiffness: 220 } }) * (1 - back) : 0;
  const cta = spring({ frame: frame - ctaAt, fps, config: { damping: 11, stiffness: 260 } });
  const pulse = 1 + 0.04 * Math.sin(Math.max(0, frame - ctaAt - 12) / 4);
  const blob = Math.sin(frame / 30) * 50;

  const phone = (src: string, left: number, top: number, w: number, k: number, key: string) => (
    <div key={key} style={{ position: "absolute", left, top: top + float + interpolate(k, [0, 1], [900, 0]), width: w,
      height: w * 2.05, borderRadius: 64, background: "#0b0b0d", padding: 14,
      boxShadow: "0 60px 120px rgba(0,0,0,0.45)" }}>
      <div style={{ width: "100%", height: "100%", borderRadius: 50, overflow: "hidden", background: "#fff" }}>
        <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover",
          objectPosition: `50% ${scroll}%` }} />
      </div>
    </div>
  );

  return (
    <AbsoluteFill style={{ background: p.base, overflow: "hidden" }}>
      <div style={{ position: "absolute", width: 1100, height: 1100, borderRadius: 550, left: -100 + blob,
        top: 900, background: look.accent, opacity: 0.22, filter: "blur(120px)" }} />
      {p.second ? phone(p.second, 560, phoneTop + 120, 470, second, "b") : null}
      {phone(p.screen, p.second ? 60 : (1080 - phoneW) / 2, phoneTop, p.second ? 470 : phoneW, rise, "a")}

      <div style={{ position: "absolute", left: 72, right: 72, top: SAFE_TOP + 40, opacity: headlineShown,
        transform: `translateY(${interpolate(headlineShown, [0, 1], [-60, 0])}px)` }}>
        <Words text={p.headline} keyWords={p.keyWords} accent={look.accent} color={p.ink} size={104} />
        {p.proof && !fact ? (
          <div style={{ fontFamily, fontWeight: 600, fontSize: 40, color: p.ink, opacity: interpolate(frame, [40, 52], [0, 0.85],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }), marginTop: 26 }}>{p.proof}</div>
        ) : null}
      </div>

      {fact ? (
        <div style={{ position: "absolute", left: 72, right: 72, top: SAFE_TOP + 30, opacity: factIn,
          transform: `translateY(${interpolate(factIn, [0, 1], [70, 0])}px)` }}>
          {fact === "review" ? (
            <div style={{ background: "#fff", borderRadius: 36, padding: "36px 40px", boxShadow: "0 30px 60px rgba(0,0,0,0.2)" }}>
              <Stars n={p.content.review!.rating} color={look.accent} delay={factAt + 6} />
              <div style={{ fontFamily, fontWeight: 800, fontSize: 52, lineHeight: 1.15, color: "#111", marginTop: 18 }}>
                “{p.content.review!.text}”</div>
              <div style={{ fontFamily, fontWeight: 600, fontSize: 30, color: "#666", marginTop: 16 }}>App Store review</div>
            </div>
          ) : fact === "benefits" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
              {p.content.benefits!.slice(0, 3).map((b, i) => {
                const s = spring({ frame: frame - factAt - 6 - i * 12, fps, config: { damping: 12, stiffness: 240 } });
                return (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 26, opacity: s,
                    transform: `translateX(${interpolate(s, [0, 1], [-80, 0])}px)` }}>
                    <div style={{ width: 72, height: 72, borderRadius: 36, background: look.accent, display: "flex",
                      alignItems: "center", justifyContent: "center", flex: "none", transform: `scale(${s})` }}>
                      <svg width={40} height={40} viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" stroke={look.onAccent}
                        strokeWidth={3.2} fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
                    </div>
                    <div style={{ fontFamily, fontWeight: 800, fontSize: 54, lineHeight: 1.1, color: p.ink }}>{b}</div>
                  </div>
                );
              })}
            </div>
          ) : fact === "number" ? (
            <div style={{ textAlign: "center" }}>
              <div style={{ fontFamily, fontWeight: 800, fontSize: 260, lineHeight: 1, color: look.accent, letterSpacing: -6 }}>
                {countUp(p.content.number!.value, interpolate(frame, [factAt, factAt + 30], [0, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" }))}
              </div>
              <div style={{ fontFamily, fontWeight: 600, fontSize: 46, color: p.ink, marginTop: 10 }}>{p.content.number!.label}</div>
            </div>
          ) : (
            <div>
              <div style={{ position: "relative", display: "inline-block", fontFamily, fontWeight: 800, fontSize: 70,
                lineHeight: 1.1, color: p.ink, opacity: 0.75 }}>
                {p.content.objection!.text}
                <div style={{ position: "absolute", left: -8, top: "52%", height: 10, background: look.accent, borderRadius: 5,
                  width: `${interpolate(frame, [factAt + 18, factAt + 34], [0, 104], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}%` }} />
              </div>
              <div style={{ marginTop: 36 }}>
                <Words text={p.headline} keyWords={p.keyWords} accent={look.accent} color={p.ink} size={80} delay={factAt + 36} />
              </div>
            </div>
          )}
        </div>
      ) : null}

      <div style={{ position: "absolute", left: 0, right: 0, top: 1440, display: "flex", justifyContent: "center",
        opacity: cta, transform: `scale(${interpolate(cta, [0, 1], [0.6, 1]) * pulse})` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 22, background: look.accent, color: look.onAccent,
          borderRadius: 999, padding: "26px 54px", fontFamily, fontWeight: 800, fontSize: 56,
          boxShadow: "0 24px 50px rgba(0,0,0,0.25)" }}>
          {p.icon ? <Img src={staticFile(p.icon)} style={{ width: 70, height: 70, borderRadius: 18 }} /> : null}
          {p.cta}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// "4.8" → "0.0" … "4.8"; "50%" → "0%" … "50%"; anything else as it is
function countUp(value: string, k: number): string {
  const m = value.match(/^(\d+)([.,](\d+))?(.*)$/);
  if (!m) return value;
  const decimals = m[3]?.length ?? 0;
  const n = parseFloat(`${m[1]}.${m[3] ?? "0"}`) * k;
  return `${n.toFixed(decimals).replace(".", m[2]?.[0] ?? ".")}${m[4]}`;
}
