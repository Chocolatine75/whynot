# Design

whynot is a Meta-flavoured product: **Meta blue, the cool Meta greys, Geist type, quiet surfaces and hairlines.** The ads, the quotes and the numbers carry the colour; the frame steps back. The blue→violet gradient of Meta AI appears in three places only: the brand mark, the search ring on the home page and one phrase of its headline. Tokens live in `web/app/globals.css`. (Until Nov 3 the platform followed an Apple / Liquid Glass language; replaced at Tom's request, see DECISIONS.)

## Principles

1. **One thing per screen.** The home page is one search bar: paste the App Store link. Everything else lives behind it.
2. **Content first.** Ads are shown as feed posts, videos in a phone, competitor ads as Ad Library cards, objections as quotes with their source.
3. **One accent.** Meta blue for actions, the current state and positive bars. Semantic tints (green, amber, red, violet for "Simulated") stay small.
4. **Honest.** Every simulated number carries the violet "Simulated" tag; failures are shown, not hidden.
5. **Restrained motion.** Press feedback, a pulsing dot on the running step, a sliding bar while a stage works. Nothing else moves; `prefers-reduced-motion` turns it off.

## Tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#F5F7FA` | `#0A0D11` | page |
| `--surface` / `-2` / `-3` | `#FFF` / `#F1F4F7` / `#E8EDF2` | `#11161C` / `#171D25` / `#202833` | cards, wells, tracks |
| `--line` / `--line-strong` | `#1C2B33` at 9 % / 16 % | `#E8EDF2` at 8 % / 15 % | 1 px hairlines |
| `--text` / `-2` / `-3` | `#1C2B33` / `#5A6B77` / `#8696A2` | `#E8EDF2` / `#9AA7B3` / `#6D7B87` | |
| `--blue` | `#0064E0` (Meta blue) | `#2E8BFF` | actions, focus, bars |
| `--grad` | `#0064E0 → #0A8CFF → #7A5CFF → #C74AE0` | same | brand mark, search ring, one headline phrase |
| semantic | green, amber, red, violet (simulated) | | tints at 10–16 % |
| radius | 6 · 10 · 14 · 20 · 28 · pill | | |

**Type:** Geist (Google Fonts, `next/font`), Geist Mono for money and measures. Body 15/1.55; headings semibold with negative tracking (−0.045 em at 56 px, −0.016 em at 17 px); labels 12–13 px.

## Pages

- **Home `/`**: the headline, one sentence, the search bar with a gradient ring, chips for countries and the daily cap, three "Try" examples. Nothing else.
- **Campaigns `/runs`**: one row per app (icon, name, what was made, AI cost, status).
- **Campaign `/runs/<id>`**: a sticky side navigation (a status dot per stage, counts) over one page: Overview (status, five numbers, the pipeline, positioning) · Market (competitors' ads, longest-running first) · Strategy (profiles, objections with quotes, angles) · Ads (feed posts per audience) · Videos (phones that play) · Simulated test · Evolution (strength per generation with CIs, lineage) · Launch (plan, approval, kill switch). On mobile the navigation becomes a scrolling bar under the top bar.
- **Validation `/validation`**: every experiment with its interval, baselines, method and limits.

## Ads (composer)

Implemented in `src/whynot/create/composer.py`, checked by `create/guards.py`.

- Colours come from the app's icon (`assets/brand.py`): a near-white background and a light surface (gradient ends), a near-black text colour, the brand accent for the button. Contrast is guaranteed (text ≥ 12:1, button ≥ 4.6:1).
- Large bold headline, balanced lines (no lone last word); one small proof line; one pill button.
- The real app screen, big, with rounded corners and a soft shadow. Never generated, never drawn over.
- Two layouts: **split** (text left, full screen right) and **rising** (headline on top, the screen rising from the bottom edge).
- No emoji or pictograms, no ALL CAPS, accents and punctuation of the ad's language.

Next: a 4:5 feed format (1080×1350) and localized screenshots per storefront.
