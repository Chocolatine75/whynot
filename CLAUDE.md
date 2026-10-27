# CLAUDE.md

Context for Claude Code (and any coding agent) working in this repo. Read this first, then the docs it points to.

## What we're building

**whynot**: a flight simulator for Meta ads. Agents read the market (Meta Ad Library) and the customer (reviews, behaviour), invent ad concepts as templates with a mutable "genome", compose variants deterministically (real product pixels via SAM 3.1), drop them into a **simulated feed next to competitors' real ads**, where multimodal viewer agents (Muse Spark Open) react and say *why not*. Agents evolve the ads until they win, explain why with counterfactuals, launch winners on Meta (capped), and recalibrate on real results. The simulator's reliability is **measured** (backtest on design partners' ad history, humans, Ad Library longevity, public pre-registered predictions).

Users: small and mid Meta advertisers who make their own creative — DTC/Shopify brands and mobile apps. Design partners: a friend's mobile app (~$20k MRR) and a Shopify store (TBC).

Full spec: `docs/PRODUCT.md`. Architecture: `docs/ARCHITECTURE.md`. Plan: `docs/PLAN.md`.

**The bar is `docs/TARGETS.md`**: final product, measured results (R1–R10), per-criterion checklist. Check work against it.

**Start every session by reading `docs/STATUS.md`** (where we are, who is on what, what's next). Update it before ending the session.

## Hard constraints (hackathon rules)

- **All code is written during the hackathon (from Oct 26, 2026).** Never paste in code from outside projects, including the authors' own earlier repos. Open-source libraries are fine.
- **The repo is public.** Never commit secrets. Tokens live in `.env` (gitignored). `.env.example` lists the variables.
- **Only use data and assets we have rights to.** Design partners' assets and ad history only with written consent; their data lives in `data/private/` (gitignored), never in the repo, and is anonymised in the demo. Check dataset licences before use and record them in `docs/DECISIONS.md`.
- **Must use Meta models** (Meta Model API and/or Meta open weights). This is the core of the project, not decoration.
- Submission deadline: **Wed Nov 4, 9:00 PM ET (Thu Nov 5, 03:00 Paris)**.

## Security gotchas

- Meta Ad Library API responses embed the access token inside every `ad_snapshot_url`. **Strip `access_token` from URLs before storing, logging or displaying them.**
- Never log full API responses that contain tokens.
- The Muse Spark *Contributor* tier is cheaper but Meta trains on the data (confirmed in the pricing docs). Use it only for synthetic personas, never for real visitor data.
- Any action that spends money on Meta (creating active campaigns) must go through an explicit budget cap and a dry-run / sandbox mode by default.

## Meta APIs: quick reference

See `docs/META_APIS.md` for details.

- Meta Model API: base URL `https://api.meta.ai/v1`, OpenAI- and Anthropic-compatible, key in `MODEL_API_KEY`. Model IDs: `muse-spark-1.3`, `muse-spark-1.3-contributor`, `muse-wonder-1.0`, `muse-image-1.0`, `sam-3.1`, `muse-voice-transcribe-1.0`. Verify IDs against the model list before relying on them.
- Muse Spark Open on Baseten: `base_url=https://inference.baseten.co/v1`. Official docs say model `meta-models/muse-spark-open`; the hackathon guide said `meta-models/muse-spark-open-1026`. The smoke test decides; read it from `BASETEN_MODEL`.
- SAM 3.1 returns streamed special-token text (boxes + base85 masks), not JSON. Muse Image edits do not support masks. Details in `docs/META_APIS.md`.
- Marketing API / Ads MCP: launch + read real metrics (video thresholds p25–p95, CTR, CPA). Design partners' accounts: read-only unless they approve otherwise.
- Ad Library: `GET https://graph.facebook.com/v26.0/ads_archive`, token in `FB_TOKEN`. Commercial ads only returned for EU/UK-delivered ads. Useful fields: `ad_creative_bodies, ad_creative_link_titles, ad_delivery_start_time, ad_snapshot_url, eu_total_reach, age_country_gender_reach_breakdown, target_ages, target_gender, page_name`.

## Engineering principles

- **The simulator is a measured proxy, not an oracle.** Viewer agents simulate *cognitive* reactions (noticed the hook, understood, believed, objection, purchase intent, preference vs competitors). Never claim to predict millisecond scroll behaviour or exact retention curves. Every simulated number is labelled "simulated"; every claim about reliability comes from `validate/`.
- **Big model teaches, small model serves.** Muse Spark Open is the teacher viewer; a distilled student (Muse Glimmer or fine-tuned Spark Open) serves volume. Its agreement with the teacher is measured.
- **Concepts, not variations.** A template is a distinct concept with a genome; the diversity guard rejects near-duplicates.
- **Deterministic where possible.** Composition is code, not generation. Product / app-screen pixels are never generated (pixel-diff guard).
- **Every number shown in the demo is measured**, logged, and reproducible with one command.
- **Track cost.** Every model call goes through one client wrapper that records tokens, images and $ cost, so the demo's cost counter is real.
- **Agents are verifiable.** Every agent action (tool call, input refs, output, guard results, cost) goes to an inspectable log.
- Small, testable modules. Each stage reads and writes files/rows that can be inspected.

## Working conventions

- Python for pipeline/ML, TypeScript for the web app (adjust in `docs/DECISIONS.md` if we change this).
- Write decisions to `docs/DECISIONS.md` (one line + why).
- Update the status checkboxes in `docs/PLAN.md` when a task is done.
- At the end of a session, update `docs/STATUS.md` (in progress, next up, blockers, one log line).
- Commit often with clear messages: the history proves the work was done during the event.
