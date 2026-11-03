"use client";
import { useEffect } from "react";

/**
 * The site's response to the mouse, with one set of delegated listeners (no per-component wiring):
 *  - the page background (aurora + spotlight) follows the cursor through --mx / --my on <html>;
 *  - `.spot` elements light up where the cursor is (--x / --y on the element);
 *  - `.tilt` elements lean towards the cursor in 3D;
 *  - `.magnetic` buttons are pulled a few pixels towards it;
 *  - `.reveal` elements rise in when they enter the screen.
 * Everything stops under prefers-reduced-motion and on touch screens (no hover).
 */
export default function Interactions() {
  useEffect(() => {
    const root = document.documentElement;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const hover = matchMedia("(hover: hover) and (pointer: fine)").matches;

    const seen = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); seen.unobserve(e.target); }
    }, { rootMargin: "0px 0px -8% 0px" });
    const watch = () => document.querySelectorAll(".reveal:not(.in)").forEach((el) => (still ? el.classList.add("in") : seen.observe(el)));
    watch();
    const added = new MutationObserver(watch);
    added.observe(document.body, { childList: true, subtree: true });

    if (still || !hover) return () => { seen.disconnect(); added.disconnect(); };

    let frame = 0;
    let last: PointerEvent | null = null;
    let tilted: HTMLElement | null = null;
    let pulled: HTMLElement | null = null;
    const apply = () => {
      frame = 0;
      const e = last;
      if (!e) return;
      root.style.setProperty("--mx", `${e.clientX}px`);
      root.style.setProperty("--my", `${e.clientY}px`);
      root.style.setProperty("--px", `${(e.clientX / innerWidth - 0.5).toFixed(3)}`);
      root.style.setProperty("--py", `${(e.clientY / innerHeight - 0.5).toFixed(3)}`);
      const t = e.target instanceof Element ? e.target : null;
      const spot = t?.closest<HTMLElement>(".spot");
      if (spot) {
        const r = spot.getBoundingClientRect();
        spot.style.setProperty("--x", `${e.clientX - r.left}px`);
        spot.style.setProperty("--y", `${e.clientY - r.top}px`);
      }
      const tilt = t?.closest<HTMLElement>(".tilt") ?? null;
      if (tilted && tilted !== tilt) tilted.style.transform = "";
      tilted = tilt;
      if (tilt) {
        const r = tilt.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - 0.5;
        const y = (e.clientY - r.top) / r.height - 0.5;
        const k = Number(tilt.dataset.tilt ?? 8);
        tilt.style.transform = `perspective(900px) rotateX(${(-y * k).toFixed(2)}deg) rotateY(${(x * k).toFixed(2)}deg) translateZ(0)`;
      }
      const mag = t?.closest<HTMLElement>(".magnetic") ?? null;
      if (pulled && pulled !== mag) pulled.style.translate = "";
      pulled = mag;
      if (mag) {
        const r = mag.getBoundingClientRect();
        mag.style.translate = `${((e.clientX - r.left - r.width / 2) * 0.18).toFixed(1)}px ${((e.clientY - r.top - r.height / 2) * 0.28).toFixed(1)}px`;
      }
    };
    const move = (e: PointerEvent) => { last = e; if (!frame) frame = requestAnimationFrame(apply); };
    const leave = () => { if (tilted) tilted.style.transform = ""; if (pulled) pulled.style.translate = ""; tilted = pulled = null; };
    addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerleave", leave);
    return () => {
      removeEventListener("pointermove", move);
      document.removeEventListener("pointerleave", leave);
      cancelAnimationFrame(frame);
      seen.disconnect();
      added.disconnect();
    };
  }, []);
  return null;
}
