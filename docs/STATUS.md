# Status — session handoff

**Read this at the start of every session (human or agent). Update it at the end.**
It answers: where are we, who is on what, what's next, what's blocking. Details live in the other docs; this file stays short.

Last updated: 2026-10-27

## Where we are

Team: Matteo Atkinson, Tom Angles. Day 2 of 10. Direction settled: **whynot = AI ad agency for small businesses on Meta**, with a simulated feed as its quality gate (see `PRODUCT.md`, `TARGETS.md`). All docs aligned, in English. Code so far (`src/whynot/`, `scripts/`, 45 tests passing, no network): cost ledger + model client + smoke tests; Ad Library ingest (tokens stripped, reach breakdown, longevity); validation statistics. Nothing run against real APIs yet: no `.env` keys.

Done:
- Accepted to the hackathon (Indie track, *Build for Your World*).
- Ad Library API access works (identity verified, Business app, `ads_read` token; FR reach breakdowns confirmed).
- Docs checked against official Meta sources (`META_APIS.md`).
- Market research (Meta's 2026 features, pre-testing, synthetic research, Andromeda) → `RESEARCH.md`, `COMPETITION.md`.
- First design partner: a friend's mobile app (~$20k MRR). He wants the agency to run his whole Meta campaign; he only checks.

## In progress

| Who | Task | Branch / files | Notes |
|---|---|---|---|
| — | — | — | — |

## Next up (M0, see `PLAN.md`)

1. **Design partner:** written consent; export of past ads + real metrics per ad → `data/private/`; read-only account access; agree the pilot (cap, autonomy level, approvals, start ~Oct 31). Critical path for R1 and R4.
2. Contact 5–10 more businesses/agencies; confirm the Shopify partner.
3. Both: claim Meta credits + spend limit; request Baseten and Modal credits (Baseten: first 2,000 participants).
4. Fill `.env` (MODEL_API_KEY, BASETEN_API_KEY, FB_TOKEN), run `uv run python scripts/smoke_models.py`, record results in `META_APIS.md`.
5. With `FB_TOKEN`: `scripts/fetch_competitors.py` on the partner's competitors; confirm the reach breakdown format. Then creative capture.
6. Next code without keys: template schema (concept + genome), deterministic composer + pixel guard, autopilot safety rules — all with tests.
7. First build-in-public post.

## Blockers / open questions

- Partner data: which metrics per ad, how many ads, export vs read-only access.
- Ads MCP capabilities for pausing ads and budgets; write access for the pilot.
- Does Muse Spark Open on Baseten accept images/video? Token cost per frame?
- Baseten model: `meta-models/muse-spark-open` (official) or `...-1026` (guide)? Smoke test decides.
- SAM 3.1 mask → full-resolution mapping; video tracking format.
- Ad Library terms for capturing and showing competitor creatives.
- Finals top 5 or top 10? Ask on Discord.

## Session log

Newest first. One entry per working session: date, who, what changed, what's next.

- 2026-10-27 — Matteo + Claude — VoodRadar logged as prior art (ideas only). Python project set up (uv); `costs.py` ledger, `models.py` client (Spark, Wonder, Image, SAM, Spark Open), `sam.py` parser, smoke-test script, 14 tests. Next: keys in `.env`, run smoke tests.
- 2026-10-27 — Matteo + Claude — Validation stats (R1–R3, R6) and Ad Library ingest + fetch script, 45 tests. Next: template schema, composer + pixel guard, autopilot rules.

- 2026-10-27 — Matteo + Claude — Settled the direction (AI ad agency, simulator as quality gate, live pilot with the app partner); rewrote and aligned all docs in English. Next: M0, partner data and pilot terms first.
- 2026-10-27 — Matteo + Claude — Pivot from objection retargeting to the create–test–evolve loop; market research.
- 2026-10-27 — Matteo + Claude — Wrote `TARGETS.md`; gated plan.
- 2026-10-27 — Matteo + Claude — Checked all docs against official sources; rewrote `META_APIS.md`.
- 2026-10-27 — Matteo + Claude — Added `STATUS.md` handoff file.
