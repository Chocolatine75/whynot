# CLAUDE.md

Context for Claude Code (and any coding agent) working in this repo. Read this first, then the docs it points to.

## What we're building

**whynot: an AI ad agency for small businesses on Meta.** Agents research the market (Meta Ad Library) and the customers (reviews, pages, past ads), write a strategy (Muse Wonder), create ad concepts as templates with a mutable "genome", produce variants deterministically (real product pixels via SAM 3.1), **test every ad in a simulated feed next to competitors' real ads** (viewer agents on Muse Spark Open), evolve them, then publish, rotate and report on Meta within the owner's caps. The owner only checks and approves.

The engine is a loop: **templates generate, the simulator judges, the agents evolve.** The simulator is the agency's quality gate; its reliability is measured (backtest, humans, Ad Library longevity, live pilot).

Users: small businesses advertising on Meta without a marketing team — mobile apps and DTC/Shopify brands. First design partner: a friend's mobile app (~$20k MRR) who wants the full autopilot.

Docs: `docs/PRODUCT.md` (spec), `docs/ARCHITECTURE.md`, `docs/PLAN.md`.

**The bar is `docs/TARGETS.md`**: final product, measured results, per-criterion checklist. Check work against it.

**Start every session by reading `docs/STATUS.md`** (where we are, who is on what, what's next). Update it before ending the session.

## Hard constraints (hackathon rules)

- **All code is written during the hackathon (from Oct 26, 2026).** Never paste in code from outside projects, including the authors' own earlier repos. Open-source libraries are fine.
- **The repo is public.** Never commit secrets. Tokens live in `.env` (gitignored). `.env.example` lists the variables.
- **Only use data and assets we have rights to.** Design partners' assets, ad history and account access only with written consent; their data lives in `data/private/` (gitignored), never in the repo, and is anonymised in the demo. Record every dataset/asset licence in `docs/DECISIONS.md`.
- **Must use Meta models** (Meta Model API and/or Meta open weights). This is the core of the project, not decoration.
- Submission deadline: **Wed Nov 4, 9:00 PM ET (Thu Nov 5, 03:00 Paris)**.

## Spending and autonomy rules

- The agency runs in **dry-run by default**. Live actions on a real ad account need: the owner's written consent, a hard spend cap set by the owner, and the owner's explicit approval before the first live launch.
- Autonomy levels: `dry_run` (default) → `propose` (owner approves each action) → `autopilot` (acts within caps, owner can block; every action reported).
- whynot manages creative and its rotation; it does not override Meta's bidding or delivery.
- Every agent action is logged with its inputs, outputs, guard results and cost.

## Security gotchas

- Meta Ad Library API responses embed the access token inside every `ad_snapshot_url` and paging URL. **Strip `access_token` from URLs before storing, logging or displaying them.**
- Never log full API responses that contain tokens.
- The Muse Spark *Contributor* tier is cheaper but Meta trains on the data (confirmed in the pricing docs). Use it only for synthetic content, never for partner or customer data.

## Meta APIs: quick reference

Details and sources in `docs/META_APIS.md`.

- Meta Model API: base URL `https://api.meta.ai/v1`, OpenAI- and Anthropic-compatible, key in `MODEL_API_KEY`. Model IDs: `muse-spark-1.3`, `muse-spark-1.3-contributor`, `muse-wonder-1.0`, `muse-image-1.0`, `sam-3.1`, `muse-voice-transcribe-1.0`.
- Muse Spark Open on Baseten: `base_url=https://inference.baseten.co/v1`. Official docs say model `meta-models/muse-spark-open`; the hackathon guide said `meta-models/muse-spark-open-1026`. The smoke test decides; read it from `BASETEN_MODEL`.
- SAM 3.1 returns streamed special-token text (boxes + base85 masks), not JSON. Muse Image edits do not support masks.
- Ad Library: `GET https://graph.facebook.com/v26.0/ads_archive`, token in `FB_TOKEN`. Commercial ads only for EU/UK-delivered ads. Key fields: `ad_creative_bodies, ad_creative_link_titles, ad_delivery_start_time, ad_snapshot_url, eu_total_reach, age_country_gender_reach_breakdown, page_name`.
- Ads MCP / Marketing API: publishing and real metrics. Sandbox account for tests; partner accounts read-only unless the owner approves otherwise.

## Engineering principles

- **The simulator is a measured proxy, not an oracle.** Viewer agents simulate *cognitive* reactions (noticed the hook, understood, believed, objection, purchase intent, preference vs competitors). Never claim to predict scroll behaviour or exact retention curves. Every simulated number is labelled "simulated"; every reliability claim comes from `validate/`.
- **Personas, not individuals.** Ads are made per customer profile; Meta handles delivery to people.
- **Concepts, not variations.** A template is a distinct concept with a genome; the diversity guard rejects near-duplicates.
- **Big model teaches, small model serves.** Muse Spark Open is the teacher viewer; a distilled student serves volume; their agreement is measured.
- **Deterministic where possible.** Composition is code, not generation. Product / app-screen pixels are never generated (pixel-diff guard).
- **Every number shown in the demo is measured**, logged, and reproducible with one command.
- **Track cost.** Every model call goes through one client wrapper that records tokens, images and $ cost, so the cost counter is real.
- Small, testable modules. Each stage reads and writes files/rows that can be inspected.

## Working conventions

- Python for the engine (agents, simulator, ML), TypeScript for the web app (record changes in `docs/DECISIONS.md`).
- Docs and code comments in English.
- Write decisions to `docs/DECISIONS.md` (one line + why).
- Update the checkboxes in `docs/PLAN.md` when a task is done.
- At the end of a session, update `docs/STATUS.md` (in progress, next up, blockers, one log line).
- Commit often with clear messages: the history proves the work was done during the event.
