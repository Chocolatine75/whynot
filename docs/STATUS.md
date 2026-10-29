# Status — session handoff

**Read this at the start of every session (human or agent). Update it at the end.**
It answers: where are we, who is on what, what's next, what's blocking. Details live in the other docs; this file stays short.

Last updated: 2026-10-28

## Where we are

Team: Matteo Atkinson, Tom Angles. Day 2 of 10. Direction settled: **whynot = AI ad agency for small businesses on Meta**, with a simulated feed as its quality gate (see `PRODUCT.md`, `TARGETS.md`). All docs aligned, in English. Code so far (`src/whynot/`, `scripts/`, 85 tests passing, no network): simulated feed v0 (personas from reach, feeds, viewer agents, scores) and the R3 longevity experiment; cost ledger + model client + smoke tests; Ad Library ingest (tokens stripped, reach breakdown, longevity); validation statistics. Real calls: Ad Library works (format confirmed, long-running filter); every Meta model passes its smoke test. Baseten, Modal and Fireworks credits requested (pending); viewers run on Muse Spark meanwhile.

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
4. When Baseten credits arrive: `BASETEN_API_KEY` in `.env`, then `uv run python scripts/smoke_models.py --only open_text open_vision`.
5. Get the partner's competitors (Facebook page ids) and run `scripts/fetch_competitors.py --active ACTIVE --started-before-days 60` on them. Then creative capture.
6. R3 at scale: pick 4–6 advertisers in the partner's market (page ids), run `scripts/longevity_check.py` with ≥ 20 ads per class, compare reasoning effort low vs minimal.
7. Next code: SAM mask decoder → cutout as the composer's product asset; viewers see composed images (candidate feeds); one evolution step (objections → mutate one gene → re-test); creative capture; publishing via Marketing API sandbox.
8. First build-in-public post.

## Blockers / open questions

- Partner data: which metrics per ad, how many ads, export vs read-only access.
- Ads MCP capabilities for pausing ads and budgets; write access for the pilot.
- Baseten (credits pending): does Muse Spark Open accept images/video? Model string `meta-models/muse-spark-open` or `...-1026`?
- SAM 3.1: mask covers the box (observed once); write and verify the base85 decoder; video tracking format.
- Ad Library terms for capturing and showing competitor creatives.
- Finals top 5 or top 10? Ask on Discord.

## Session log

Newest first. One entry per working session: date, who, what changed, what's next.

- 2026-10-29 — Matteo + Claude — Landing page v2 (minitap × Meta Muse): dark hero with command bar, illustrated agency demo, measured results card, Muse-style feature sections, control section; motion rules from Emil Kowalski's skills; checked desktop/mobile/dark. Note: never run `npm run build` while `npm run dev` runs (shared `.next`, breaks the dev server).
- 2026-10-29 — Matteo + Claude — Client platform (`web/`, Next.js): home (paste an App Store link → the agency starts), campaign list, agency room (live stages + AI spend, personas, objections with quotes, ads in an Instagram-style feed with simulated scores, evolution lineage, campaign table with launch decisions, market). Apple × Meta tokens, dark mode, mobile. Security tests found a symlink escape (fixed). 38 web tests; CI builds the web app. Next: harder feeds, Meta publishing (Approve button).
- 2026-10-29 — Matteo + Claude — Evolution loop + Apple × Meta design. `agents/evolver.py` + stage `evolve` (one-element mutations answering simulated objections, re-tested with placebos, lineage in report). Composer v1 (split/rising layouts, big rounded screen with shadow, bold balanced headline, gradient, pill CTA), `docs/DESIGN.md` for the web app. Bugs fixed: `Template.to_dict` leaked internal lists (mutations changed parents); cost line counted every redo as this run. Real VietBuddy run: evolution $1.10, 3 audiences × 2 generations. **Finding: scores hit the ceiling (+4.0 = always picked) at gen 0 in 2 of 3 audiences, so progress can't show; the research market includes ads for other languages, which our ads beat too easily.** Next: harder feeds (most relevant competitors / tournament between our variants), then the web UI. 370 tests.
- 2026-10-29 — Matteo + Claude — Simulator bias fixed. Placebo test showed the advertiser name alone won the feed (0.50× → 3.50×). New `sim/arena.py`: brand name as on Facebook, head-to-head slots, placebos + bias flag (90% detection / 3% false alarms on the test world). VietBuddy re-run: variants now spread 0–4× (were all 4.0×), placebos ~0×, $0.61. Also: CI fixed (pictograms banned by Unicode category, not by font). 347 tests.
- 2026-10-29 — Matteo + Claude — `create` run on 3 real apps (VietBuddy, Finch, Flighty): all complete, $1–1.7 per app. Fixed what they revealed: ads per language (France got English ads), real font for accents (Pillow's default can't draw é → the model stripped accents), accent check in the director, neutral ad set names ("ADHD" in a name), strategist repairs 3 + refused attempts logged, `--redo-from`. 331 tests. Still open: simulator bias (lift saturates), screenshots per storefront language, Android/Shopify.
- 2026-10-28 — Matteo + Claude — `whynot create` built: App Store ingest, Scout, Strategist (Wonder, verified quotes), Creative director (verified copy), brand palette, policy guard v0, campaign plan (Marketing API shape, PAUSED), report, CLI. Tests: contract (recorded Apple data), adversarial (lying model), end-to-end on a fake world, live (`--live`). 315 tests. **Real run on VietBuddy (US campaign, GB research): $1.09**, 6 competitors kept of 40 checked, 6 objections from real reviews, 24/24 ads pass guards, 3 ad sets €19.98/day. **Finding: every variant scored the max simulated preference (4.0×, 4 views each) → the simulator does not discriminate in this setup** (viewer traits contain the objections the ads answer; our item is persona-tailored, competitors' aren't). Next: fix that bias, then `whynot daily`.
- 2026-10-28 — Matteo + Claude — Quality pass: ENGINEERING.md (layout, rules, definition of done), ruff + mypy + coverage ≥ 90 % in `scripts/check.sh` and GitHub CI, packages split along the loop (`create/`, `assets/`, `run/`). Review fixed 11 bugs, each with a regression test (NaN budget passed the cap, guards skippable, pixel guard missed 1-level changes, unbalanced feeds, duplicate personas skewed scores, unpriced model calls unlogged, SAM payload cut on `|>`…). Property tests on invariants. 180 tests, 96 % coverage.
- 2026-10-28 — Matteo + Claude — Partner identified: VietBuddy (US ads → we focus on EU for him). Built generic product pieces: templates (schema, genome, mutation, variant ids), composer v0 (static 1080), guards (exact product pixels, contrast, palette, missing glyphs), autopilot rules (levels, cap, first-live approval, loser/fatigue review, action log). 120 tests. Next: SAM cutout as asset, viewers see composed images, evolution step.

- 2026-10-27 — Matteo + Claude — VoodRadar logged as prior art (ideas only). Python project set up (uv); `costs.py` ledger, `models.py` client (Spark, Wonder, Image, SAM, Spark Open), `sam.py` parser, smoke-test script, 14 tests. Next: keys in `.env`, run smoke tests.
- 2026-10-27 — Matteo + Claude — Validation stats (R1–R3, R6) and Ad Library ingest + fetch script, 45 tests. Next: template schema, composer + pixel guard, autopilot rules.
- 2026-10-27 — Matteo + Claude — First real Ad Library calls: token works, breakdown format confirmed, results are newest-first → added long-running filter; Lacoste test (17 ads, median 118 days). 47 tests.
- 2026-10-27 — Matteo + Claude — Meta model smoke tests all pass (~$0.02). Fixed silent empty answers (reasoning tokens eat max_tokens → `TruncatedOutput`), images sent inline, SAM mask covers the box. 51 tests.
- 2026-10-28 — Matteo + Claude — Simulated feed v0: personas from real reach, feeds, viewer agents (strict JSON, retry, parallel), per-ad scores; R3 longevity pipeline. Tiny real run on Lacoste: 8/8 viewers valid, realistic why-nots, $0.10. Reasoning = 85 % of cost; `low` effort ≈2× cheaper. 85 tests.

- 2026-10-27 — Matteo + Claude — Settled the direction (AI ad agency, simulator as quality gate, live pilot with the app partner); rewrote and aligned all docs in English. Next: M0, partner data and pilot terms first.
- 2026-10-27 — Matteo + Claude — Pivot from objection retargeting to the create–test–evolve loop; market research.
- 2026-10-27 — Matteo + Claude — Wrote `TARGETS.md`; gated plan.
- 2026-10-27 — Matteo + Claude — Checked all docs against official sources; rewrote `META_APIS.md`.
- 2026-10-27 — Matteo + Claude — Added `STATUS.md` handoff file.
