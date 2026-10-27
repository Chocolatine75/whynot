# Status — session handoff

**Read this at the start of every session (human or agent). Update it at the end.**
It answers: where are we, who is on what, what's next, what's blocking. Details live in the other docs; this file stays short.

Last updated: 2026-10-27

## Where we are

Day 2 of 10. **Pivoted** to whynot = flight simulator for Meta ads (see `PRODUCT.md`, `TARGETS.md`). All docs rewritten for it. **No pipeline code yet.**

Done:
- Accepted to the hackathon (Indie track, *Build for Your World*).
- Ad Library API access works (identity verified, Business app, `ads_read` token; FR reach breakdowns confirmed).
- Docs checked against official Meta sources (`META_APIS.md`).
- Market research done (Meta's 2026 features, pre-testing, synthetic research, Andromeda) → `RESEARCH.md`, `COMPETITION.md`.
- First design partner found: a friend's mobile app (~$20k MRR), keen to use the product.

## In progress

| Who | Task | Branch / files | Notes |
|---|---|---|---|
| — | — | — | — |

## Next up (M0, see `PLAN.md`)

1. **Design partner data**: written consent + export of past ads and real metrics per ad → `data/private/`. Critical path for the backtest (R1).
2. Contact 5–10 more brands/agencies for backtest data; confirm the Shopify partner.
3. Both: claim Meta credits + spend limit, Baseten, Modal.
4. `costs` wrapper + smoke tests (Muse Spark Open with image/video input).
5. Ad Library ingest for the partner's market + creative capture.
6. Decide the capped budget for the public prediction (R4), or not.
7. First build-in-public post.

## Blockers / open questions

- Partner ad history: which metrics per ad, how many ads, how we get them (export vs read-only access).
- Does Muse Spark Open on Baseten accept images/video? Token cost per frame?
- Baseten model: `meta-models/muse-spark-open` (official) or `...-1026` (guide)? Smoke test decides.
- SAM 3.1 mask → full-resolution mapping; video tracking format.
- Ad Library terms for capturing and showing competitor creatives.
- Finals top 5 or top 10? Ask on Discord.
- Teammate name / GitHub handle to add in `README.md`.

## Session log

Newest first. One entry per working session: date, who, what changed, what's next.

- 2026-10-27 — Matteo + Claude — Pivot to the ad flight simulator; rewrote README, CLAUDE.md, PRODUCT, ARCHITECTURE, TARGETS, PLAN, DEMO, COMPETITION, RESEARCH; logged decisions; mobile-app design partner added. Next: M0, partner data first.
- 2026-10-27 — Matteo + Claude — Wrote `TARGETS.md`; PLAN reorganised into gated milestones; Criteo demoted.
- 2026-10-27 — Matteo + Claude — Checked all docs against official sources; rewrote `META_APIS.md`.
- 2026-10-27 — Matteo + Claude — Added `STATUS.md` handoff file; folded brainstorm details into docs.
