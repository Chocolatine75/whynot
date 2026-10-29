# Design

whynot looks like it belongs between Apple and Meta: Apple's calm (white space, large type, soft depth, rounded geometry) with Meta's product language (Meta blue for action, pill buttons, feed-native cards). One system for the web app and for the ads we generate.

## Principles

1. **Content first.** The app's real screen, the ad, the number: the interface frames them and gets out of the way.
2. **One accent.** Meta blue for every primary action and live state. Everything else is neutral.
3. **Soft depth, no borders.** Separate surfaces with background tone and a soft shadow, not lines.
4. **Large, calm type.** Few sizes, generous line height, sentence case. No ALL CAPS, no exclamation marks.
5. **Honest by design.** Anything simulated carries a "Simulated" tag; nothing looks live unless it is.

## Tokens (web app)

| Token | Value | Use |
|---|---|---|
| `--accent` | `#0064E0` (Meta blue) | primary buttons, links, live state |
| `--accent-hover` | `#0866FF` | hover / focus ring |
| `--bg` | `#FFFFFF` | page |
| `--surface` | `#F5F5F7` (Apple grey) | cards, panels |
| `--text` | `#1D1D1F` | body and headings |
| `--text-2` | `#6E6E73` | secondary text, labels |
| `--positive` | `#1E8E3E` | gains, passed checks |
| `--warning` | `#B26A00` | bias flags, needs approval |
| `--negative` | `#D93025` | refused, failed checks |
| `--simulated` | `#5E5CE6` on `#EFEFFD` | "Simulated" tag |
| radius | 12 (inputs) · 20 (cards) · 999 (pills) | |
| shadow | `0 8px 30px rgba(0,0,0,.08)` | raised cards only |
| spacing | 4-pt grid: 8 · 12 · 16 · 24 · 32 · 48 · 64 | |

Dark mode: `--bg #000`, `--surface #1C1C1E`, `--text #F5F5F7`, `--text-2 #98989D`, accent unchanged.

**Type:** system stack `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", Roboto, sans-serif`. Sizes 13 · 15 · 17 (body) · 22 · 28 · 40 · 56 (hero). Weights 400 / 600 / 700. Numbers tabular (`font-variant-numeric: tabular-nums`) in tables and counters.

**Components:** pill buttons (primary = accent fill, white text; secondary = surface fill); cards on `--surface` with radius 20; ads always shown in a phone-width feed frame (≤ 420 px) like Instagram, with "Sponsored" under the brand name; a cost counter in tabular numbers; the agent log as a calm vertical timeline.

## Ads (composer)

Implemented in `src/whynot/create/composer.py`, checked by `create/guards.py`.

- Colours come from the app's icon (`assets/brand.py`): a near-white background and a light surface (gradient ends), a near-black text colour, the brand accent for the button. Contrast is guaranteed (text ≥ 12:1, button ≥ 4.6:1).
- Large bold headline, balanced lines (no lone last word); one small proof line; one pill button.
- The real app screen, big, with rounded corners and a soft shadow. Never generated, never drawn over.
- Two layouts: **split** (text left, full screen right) and **rising** (headline on top, the screen rising from the bottom edge).
- No emoji or pictograms, no ALL CAPS, accents and punctuation of the ad's language.

Next: a 4:5 feed format (1080×1350) and localized screenshots per storefront.
