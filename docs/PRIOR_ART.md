# Prior art we learned from

We read related projects for ideas. **No code, prompts, data or assets from them are in this repository** — hackathon rule: new work only. Everything here is re-implemented from scratch during the event.

## VoodRadar — Voodoo × Anthropic Hack 2026, 1st place (Track 3, Market Intelligence)

Repo: https://github.com/edouardfoussier/voodoo-anthropic-hack-winner (no licence: all rights reserved, so nothing can be reused beyond ideas).

What it does: a mobile-game name → a competitive creative dossier (competitor ads deconstructed, clustered into archetypes, scored for the game) → briefs → rendered video ads, in minutes. Built on SensorTower, Gemini, Claude, Scenario and Kling.

Ideas we take (re-implemented with Meta models):
- **Structured deconstruction of every competitor ad**: hook (first seconds), scene flow, text overlays, CTA, palette, emotional pitch, audience proxy — typed output, never prose. For us: Muse Spark / Wonder, feeding the strategist and the viewer agents.
- **Persistent analysis cache keyed by ad id**: each ad is analysed once, then read from disk. Big cost saver across runs and businesses.
- **Briefs with explicit audio direction** and first/last-frame chaining into a branded end card.
- **Presentation**: one user story at the top of the README; numbered, auditable steps.

What it lacks and we add:
- **A judge.** Its winner score uses hand-picked weights it says should be calibrated against historical winners. Our simulated feed is a judge whose reliability is measured (backtest on real performance, humans, Ad Library longevity).
- **Running the account**: publishing, rotation and reporting on Meta within the owner's caps.
- **Meta-native data and models**: Ad Library reach breakdowns, Muse models, Ads MCP.
