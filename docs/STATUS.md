# Status — session handoff

**Read this at the start of every session (human or agent). Update it at the end.**
It answers: where are we, who is on what, what's next, what's blocking. Details live in the other docs; this file stays short.

Last updated: 2026-10-27

## Where we are

Team: Matteo Atkinson, Tom Angles. Day 2 of 10. Direction settled: **whynot = AI ad agency for small businesses on Meta**, with a simulated feed as its quality gate (see `PRODUCT.md`, `TARGETS.md`). All docs aligned, in English. **No code yet.**

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
3. Both: claim Meta credits + spend limit, Baseten, Modal.
4. `costs` wrapper + smoke tests (Muse Spark Open with image/video input).
5. Ad Library ingest for the partner's market + creative capture.
6. First build-in-public post.

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

- 2026-10-27 — Matteo + Claude — Settled the direction (AI ad agency, simulator as quality gate, live pilot with the app partner); rewrote and aligned all docs in English. Next: M0, partner data and pilot terms first.
- 2026-10-27 — Matteo + Claude — Pivot from objection retargeting to the create–test–evolve loop; market research.
- 2026-10-27 — Matteo + Claude — Wrote `TARGETS.md`; gated plan.
- 2026-10-27 — Matteo + Claude — Checked all docs against official sources; rewrote `META_APIS.md`.
- 2026-10-27 — Matteo + Claude — Added `STATUS.md` handoff file.
