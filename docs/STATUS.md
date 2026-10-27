# Status — session handoff

**Read this at the start of every session (human or agent). Update it at the end.**
It answers: where are we, who is on what, what's next, what's blocking. Details live in the other docs; this file stays short.

Last updated: 2026-10-27

## Where we are

Day 2 of 10. Docs and project context written. **No pipeline code yet.**

Done before / at kickoff:
- Accepted to the hackathon (Indie track, *Build for Your World*).
- Ad Library API access works: identity verified, Business dev app, `ads_read` token. First calls on FR-delivered ads confirmed text, dates, reach, targeting and age/gender/country breakdowns are returned (see `META_APIS.md`).
- Public repo `whynot` with full docs (product, architecture, research, plan, demo, decisions).

## In progress

| Who | Task | Branch / files | Notes |
|---|---|---|---|
| — | — | — | — |

## Next up (from `PLAN.md`, M0)

1. Both: claim Meta credits + spend limit, Baseten, Modal.
2. **Partner store confirmed in writing**, then tracking + exit question live (ground truth for R1).
3. `costs` wrapper + smoke tests of every model.
4. Ad Library ingest, one market end to end (tokens stripped).
5. App skeleton: run a job, show agent log + cost.

## Blockers / open questions

- Partner store not yet confirmed in writing.
- Baseten model: `meta-models/muse-spark-open` (official) or `...-1026` (guide)? Smoke test decides.
- SAM 3.1 mask → full-resolution mapping not documented; test on a real image.
- Finals top 5 or top 10? Ask on Discord.
- Marketing API sandbox account setup time unknown.
- Teammate name / GitHub handle to add in `README.md` and the table above.

## Session log

Newest first. One entry per working session: date, who, what changed, what's next.

- 2026-10-27 — Matteo + Claude — Wrote `TARGETS.md` (final product, R1–R10, criteria); PLAN reorganised into gated milestones M0–M4; Criteo demoted. Next: M0.
- 2026-10-27 — Matteo + Claude — Checked all docs against official sources. Rewrote `META_APIS.md` (real prices, rate limits, Muse Image and SAM 3.1 formats). Baseten model string conflict noted. Criteo licence = CC BY-NC-SA. Next: costs wrapper + smoke tests.

- 2026-10-27 — Matteo + Claude — Added `STATUS.md` handoff file; folded remaining brainstorm details into docs. Next: Day 1–2 foundations.
