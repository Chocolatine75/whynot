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

## Next up (from `PLAN.md`, Day 1–2)

1. Both: claim Meta credits + spend limit, Baseten, Modal.
2. `costs` wrapper: one client for every model call, logs tokens / images / $.
3. Smoke tests for each Meta model; record real IDs and prices in `META_APIS.md`.
4. Ad Library ingest: competitor page IDs → ads + reach breakdowns, **tokens stripped**.
5. Partner store: written consent, export catalog / pages / reviews / media.
6. Sessions source: partner traffic and/or public dataset (licence in `DECISIONS.md`).

## Blockers / open questions

- Partner store not yet confirmed in writing.
- Muse Image and SAM 3.1 API formats unknown → check docs.
- Marketing API sandbox account setup time unknown.
- Teammate name / GitHub handle to add in `README.md` and the table above.

## Session log

Newest first. One entry per working session: date, who, what changed, what's next.

- 2026-10-27 — Matteo + Claude — Added `STATUS.md` handoff file; folded remaining brainstorm details into docs. Next: Day 1–2 foundations.
