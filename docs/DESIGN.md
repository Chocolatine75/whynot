# Design

whynot looks like a premium Apple app: macOS / iOS design language with **Liquid Glass used with restraint**. Content sits on solid, quiet surfaces; glass is reserved for what floats above content. Neutral palette, one accent, almost no motion. Tokens live in `web/app/globals.css`.

## Principles

1. **Content first.** The ad, the quote, the number. The interface frames them and steps back.
2. **Glass only where something floats.** Toolbar, command bar, segmented tabs, inspectors over content. Never on every card: glass over a flat background means nothing.
3. **One accent.** System blue for actions and the current state. Semantic tints (green, orange, red, indigo for "Simulated") are quiet fills, never large areas.
4. **Depth from light, not lines.** Hairline separators (0.5 px), soft layered shadows, a specular top edge on glass.
5. **Calm type.** SF Pro (system stack), semibold display, negative tracking on large sizes, balanced headings.
6. **Restrained motion.** Press feedback and colour transitions only. No entrance animations, no pulsing, no parallax.
7. **Honest.** Simulated numbers are tagged; illustrations are labelled; nothing looks live unless it is.

Avoid: neon or multi-colour gradients, dark "hero" sections with glows, big stat cards, uppercase eyebrows on every section, generic SaaS feature grids.

## Tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--canvas` | `#F5F5F7` | `#000000` | page background |
| `--surface` / `--surface-2` | `#FFFFFF` / `#F2F2F4` | `#1C1C1E` / `#2C2C2E` | content cards, sidebars |
| `--fill` / `--fill-2` | grey 12 % / 8 % | grey 24 % / 16 % | inputs, secondary buttons, rows on hover |
| `--text` / `--text-2` / `--text-3` | `#1D1D1F` / `#6E6E73` / `#86868B` | `#F5F5F7` / `#A1A1A6` / `#8E8E93` | |
| `--separator` | 12 % | 60 % | hairlines (0.5 px) |
| `--accent` | `#0071E3` | `#0A84FF` | actions, focus |
| semantic | positive, warning, negative, sim (indigo) | | tints at 10–16 % |
| radius | 10 · 14 · 22 · 999 (pills) | | |
| shadow | `--shadow-1` hairline lift · `--shadow-2` floating · `--shadow-3` window | | |

**Glass material (`.glass`):** `rgba(255,255,255,.62)` (dark: `rgba(40,40,44,.58)`), `backdrop-filter: blur(24px) saturate(180%)`, a 1 px luminous border, a specular inner top edge (`inset 0 1px 0 rgba(255,255,255,.9)`), a 0.5 px outer edge and `--shadow-2`. Falls back to a solid surface with `prefers-reduced-transparency`, gets a visible border with `prefers-contrast: more`.

**Type:** body 17/1.47, tracking −0.022 em; display semibold 600, 64 → 28 px with −0.035 → −0.025 em; labels 13 px medium; numbers tabular.

## Motion

From the design-engineering skills (`emil-design-eng`, `apple-design`, `animate` from emilkowalski/skill, MIT; pinned in `skills-lock.json`, restore with `npx skills experimental_install`):

- Buttons: `scale(0.97)` on press, 150 ms, `cubic-bezier(0.23, 1, 0.32, 1)`; colour transitions 150 ms. Nothing else moves.
- `prefers-reduced-motion`: press scaling and transitions off.

## Landing page

- A centred, calm headline and one sentence; the glass command bar (paste the App Store link → Start the campaign).
- The product itself as a static macOS window: sidebar of agency steps, an ad in a feed, a glass inspector floating over the ad with the simulated result. Brand-free and captioned **Illustration**; partner data never appears there.
- "How it works" as one inset list (like System Settings), three short commitments, then the campaigns.

## Ads (composer)

Implemented in `src/whynot/create/composer.py`, checked by `create/guards.py`.

- Colours come from the app's icon (`assets/brand.py`): a near-white background and a light surface (gradient ends), a near-black text colour, the brand accent for the button. Contrast is guaranteed (text ≥ 12:1, button ≥ 4.6:1).
- Large bold headline, balanced lines (no lone last word); one small proof line; one pill button.
- The real app screen, big, with rounded corners and a soft shadow. Never generated, never drawn over.
- Two layouts: **split** (text left, full screen right) and **rising** (headline on top, the screen rising from the bottom edge).
- No emoji or pictograms, no ALL CAPS, accents and punctuation of the ad's language.

Next: a 4:5 feed format (1080×1350) and localized screenshots per storefront.
