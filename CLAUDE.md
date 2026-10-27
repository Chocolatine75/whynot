# CLAUDE.md

Context for Claude Code (and any coding agent) working in this repo. Read this first, then the docs it points to.

## What we're building

**whynot**: an autonomous growth marketer for Shopify stores. It infers *why* each visitor didn't buy (their objection), generates a personalized ad answering that objection from reusable templates, pre-tests ads on a synthetic consumer panel, targets only persuadable visitors (uplift), launches on Meta via the Marketing API, and proves causal sales with a holdout.

Full spec: `docs/PRODUCT.md`. Architecture: `docs/ARCHITECTURE.md`. Plan: `docs/PLAN.md`.

**Start every session by reading `docs/STATUS.md`** (where we are, who is on what, what's next). Update it before ending the session.

## Hard constraints (hackathon rules)

- **All code is written during the hackathon (from Oct 26, 2026).** Never paste in code from outside projects, including the authors' own earlier repos. Open-source libraries are fine.
- **The repo is public.** Never commit secrets. Tokens live in `.env` (gitignored). `.env.example` lists the variables.
- **Only use data and assets we have rights to.** Product images come from the partner store with written consent. Check dataset licences before use and record them in `docs/DECISIONS.md`.
- **Must use Meta models** (Meta Model API and/or Meta open weights). This is the core of the project, not decoration.
- Submission deadline: **Wed Nov 4, 9:00 PM ET (Thu Nov 5, 03:00 Paris)**.

## Security gotchas

- Meta Ad Library API responses embed the access token inside every `ad_snapshot_url`. **Strip `access_token` from URLs before storing, logging or displaying them.**
- Never log full API responses that contain tokens.
- The Muse Spark *Contributor* tier is cheaper but may allow Meta to use the data. Use it only for synthetic personas, never for real visitor data.
- Any action that spends money on Meta (creating active campaigns) must go through an explicit budget cap and a dry-run / sandbox mode by default.

## Meta APIs: quick reference

See `docs/META_APIS.md` for details.

- Meta Model API: base URL `https://api.meta.ai/v1`, OpenAI- and Anthropic-compatible, key in `MODEL_API_KEY`. Model IDs: `muse-spark-1.3`, `muse-spark-1.3-contributor`, `muse-wonder-1.0`, `muse-image-1.0`, `sam-3.1`, `muse-voice-transcribe-1.0`. Verify IDs against the model list before relying on them.
- Muse Spark Open on Baseten: model `meta-models/muse-spark-open-1026` (not the name in Baseten's docs).
- Ad Library: `GET https://graph.facebook.com/v26.0/ads_archive`, token in `FB_TOKEN`. Commercial ads only returned for EU/UK-delivered ads. Useful fields: `ad_creative_bodies, ad_creative_link_titles, ad_delivery_start_time, ad_snapshot_url, eu_total_reach, age_country_gender_reach_breakdown, target_ages, target_gender, page_name`.

## Engineering principles

- **Big model teaches, small model serves.** Muse labels a sample; cheap classifiers run per visitor. Don't call an LLM per visitor in the hot path.
- **Deterministic where possible.** Composition of ads from templates is code, not generation. Product pixels are never generated.
- **Every number shown in the demo is measured**, logged, and reproducible. If something is simulated, label it as simulated in the UI.
- **Track cost.** Every model call goes through one client wrapper that records tokens, images and $ cost, so the demo's cost counter is real.
- Small, testable modules. Each pipeline stage reads and writes files/rows that can be inspected.

## Working conventions

- Python for pipeline/ML, TypeScript for the web app (adjust in `docs/DECISIONS.md` if we change this).
- Write decisions to `docs/DECISIONS.md` (one line + why).
- Update the status checkboxes in `docs/PLAN.md` when a task is done.
- At the end of a session, update `docs/STATUS.md` (in progress, next up, blockers, one log line).
- Commit often with clear messages: the history proves the work was done during the event.
