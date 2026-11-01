# Status — session handoff

**Read this at the start of every session (human or agent). Update it at the end.**
It answers: where are we, who is on what, what's next, what's blocking. Details live in the other docs; this file stays short.

Last updated: 2026-11-01

## Where we are

Team: Matteo Atkinson, Tom Angles (Tom drives both lanes while Matteo has no Claude credits). Deadline Wed Nov 4,
22:00 Paris. **whynot = AI ad agency for small businesses on Meta**: research → strategy → ads (statics and trend
videos with voice) → simulated feed → evolution → plan → publish → daily loop → report, all logged and capped.
Partner (VietBuddy) day: **Monday Nov 2** (`docs/PILOT.md`).

Works today (`master`, 723 Python + 65 web tests):
- `whynot create`, `whynot video` (trend ads with Remotion + ElevenLabs), `whynot daily` (results, pauses, new ideas,
  video ads published to Meta), `whynot publish` / `stop` (kill switch, CLI + button), `whynot predict` (frozen,
  hashed predictions), `whynot costs`; `/validation` page; R1 backtest ready for the partner's data.
- Keys (Tom): Meta Model API with credits, Baseten, ElevenLabs, FB_TOKEN (identity verified). Smoke test green
  (Nov 1, $0.025); Ad Library live test green.
- Fresh VietBuddy run `outputs/runs/20261101-014653-id6796837982`: 127 competitor ads (Falou, Pimsleur…), 4 audiences,
  24 variants simulated in hard feeds + 2 evolution rounds, 12 ads in 4 ad sets, €20/day PAUSED, **$1.78**.
- Bias suite on that run (**$1.06**): brand-name bias −0.47 and emoji −0.30 flagged (see ROADMAP E2-6, DECISIONS).
- Validation so far: R3 failed twice (reported as a limit); R1, R5 wait for the partner.

## In progress

| Who | Task | Branch / files | Notes |
|---|---|---|---|
| Matteo + Claude | E0-7 event log + E4-5 orchestrator (`whynot connect`, `whynot agency`); honest trend videos, no repeated copy | `b/E4-5-orchestrator` (PR #12) | done, CI green; next: tournament + noise floor in evolution (E3-2/E3-3/E6-1) |

## Next up

1. **Sandbox rehearsal** (Tom): set `META_SANDBOX_AD_ACCOUNT_ID`, `META_SANDBOX_TOKEN`, `META_PAGE_ID`, then on the
   Nov 1 run: `whynot publish` → `whynot predict` → `whynot stop` (button too). Never run against a real account yet.
2. **Monday (partner):** consent, data, R1, predictions frozen + posted, publish PAUSED, activate on his OK
   (`docs/PILOT.md`).
3. Gen-0 scores still reach the ceiling (max lift over placebo 4.0 in hard feeds): judge the evolution with the
   tournament (`sim/tournament.py`, E3-2/E6-1) instead of lift.
4. README, demo video, `TARGETS.md` review (Nov 3–4).

## Blockers / open questions

- Sandbox ids and a Facebook Page for publishing (Tom's `.env`).
- Partner: written consent, cap, autonomy level, naming in the demo (yes/no), data format.
- Baseten rate limits drop ~15 % of viewer calls on big batches (not billed; a rerun fills them from the cache).
- Finals top 5 or top 10? Ask on Discord.

## Session log

Newest first. One entry per working session: date, who, what changed, what's next.

- 2026-11-01 (3) — Matteo + Claude — **No repeated lines, no unbacked promises** (PR #12): the prompt's own tone examples ("kept talking", "so cooked"…) are refused (all four videos reused them); a 4-word phrase said in an earlier ad is refused, and videos made in one batch see each other's lines; promise words (instant, perfect, fluent, guaranteed, accurate…) are allowed only when the store page or a verified claim says them, in static copy and video captions; from the demo on, captions speak for the brand (no "I/my": testimonials had moved to the captions); any "link…" line is refused. VietBuddy, two batches of 4 videos: 8/8 made ($0.55, $0.58), every voice different, captions in the brand's voice.

- 2026-11-01 (2) — Matteo + Claude — **Trend briefs succeed far more often** (PR #12): the validator sends every rule problem back in one message with the timeline (it used to stop at the first, so each repair fixed one rule and hit the next), repairs say how to fix (seconds of trend/demo to add, the twist shot to write, the verified numbers allowed), one more attempt, and an invalid tone rewrite now keeps the valid first take instead of throwing the idea away. VietBuddy: before 2 of 7 ideas became videos (days 1–2), after 6 of 7 (day 3: 2/3, the failure was the rewrite bug since fixed; `whynot video -n 4`: 4/4, $0.55). Still open: the four voices reuse the same lines ("she just kept talking… i was so cooked"); a caption claimed instant feedback the store page doesn't promise (non-number claims are not checked).

- 2026-11-01 — Matteo + Claude — **Honest ads, no pasted copy** (PR #12), found on two real `whynot agency --sim` runs on VietBuddy ($2.53, $3.10): trend videos no longer make an invented creator vouch for the app (the creator is a skit character, never names the app or claims a use or result; the app is named on screen in the brand's voice; enforced by the validator); the director refuses a 4-word phrase shared by more than 2 concepts and hook options that say the same thing; the strategist caps angles per objection at a third. Also: a directive repair for a too-short trend, 4 API retries, the daily studio captures competitors' creatives (a fresh run had deconstructed 0 ads). Second run: no testimonial, angles spread (max 2 per objection), 4 audiences funded; 2 of 4 video ideas failed on the trend share before the new repair message.

- 2026-10-31 (night) — Matteo + Claude — **The agency in one command** (PR #12): `whynot connect` (owner's Meta login → ad account + Page found and checked, saved in `data/private/connections/`, token never in argv or a run folder) and `whynot agency <App Store link> --countries FR --daily-cap 20 --connection <file>`: connect → create → publish → daily, resumable, budget per step, one ad cap for static + video ads, approvals waited for and remembered (E4-5); shared `events.jsonl` with parents and digests (E0-7). Not yet run on a real ad account (the sandbox token had expired). **Tom:** the Connect Meta button can pipe the token to `whynot connect --token-stdin`; the agency room can read `events.jsonl` and `agency/state.json`.

- 2026-11-01 — Tom + Claude — Keys live (smoke $0.025, Ad Library live test green). Merged the five pending branches into master (E14-10, E8-4, E9-4, stop button, macOS private-path fix); STATUS rewritten to today's state. Fresh VietBuddy `create` ($1.78, cassettes recorded privately) and the first real bias suite ($1.06): brand-name −0.47 and emoji −0.30 flagged. Next: sandbox rehearsal, then the partner on Monday.

- 2026-10-31 (evening) — Tom + Claude — Four PRs, new files where possible to stay clear of Matteo: E14-10 the daily loop publishes its videos to Meta (`b/E14-10-video-publish`), E8-4 `whynot predict` frozen + hashed predictions and `scripts/compare_predictions.py` (`a/E8-4-predictions`), E9-4 `/validation` page (`b/E9-4-validation-page`), kill switch button (`b/E8-6-stop-button`). The four merge cleanly together and with `fix/private-path-macos`: 723 Python + 65 web tests green. No model spend. Not yet run against a real account: video upload, Insights comparison, the button. Next: keys → smoke test → sandbox rehearsal (publish, predict, stop) before Monday.

- 2026-10-31 — Tom + Claude — Tom takes over both lanes (Matteo out of Claude credits). Reviewed #4/#5: fixed the daily loop saving memory only at the end (a crash after a real launch would launch the same ad again) and `--days` on a real account (would launch tomorrow's ads today), with regression tests. Remotion installed, real render test green. E14-12 accents in captions (`b/E14-12-accents`), E2-4 R1 ready for Monday, protocol pre-registered (`a/E2-4-r1`), E8-6 `whynot stop` + `docs/PILOT.md` (`b/E8-6-kill-switch`). All stacked on `b/daily-loop`. No model spend. **To merge in order: #4, #5, then the three branches.** Waiting: Tom's Meta credits + `MODEL_API_KEY`, Facebook identity check. Next: smoke test, sandbox rehearsal of publish + stop, E14-10 videos to Meta.

- 2026-10-31 — Matteo + Claude — **Daily loop** (branch `b/daily-loop`): `whynot daily RUN [--sim --days N]`. Results (Meta Insights or a labelled simulated account) → memory of every ad and its idea → pause losers/tired ads within the cap → new ideas (exploit what sells in a new format, explore far from everything tried, never twice, backups) → videos that avoid past hooks → launch → daily report in `<run>/agency/reports/`. VietBuddy simulated week: 4 days, $0.57. 660 tests. Missing: publishing videos to Meta (E14-10), platform. Apify (TikTok trends) maybe; Pexels footage next.

- 2026-10-31 — Matteo + Claude — **E14-8 ads that sell** (branch `b/E14-8-sell`): demo with a tap on the real screens, verified review card (stars + verbatim quote, ≥ 4★ only), transformation shot, offer from the store page on the end card, the app named by the creator; trend share 40 %, videos up to 24 s. Fixes: capitals lowercased in captions/cards (a brief failed 4× on 'THIS or THAT'), 'link in bio' refused, captions set apart by language, voice guard understands spoken forms/numbers/compounds. VietBuddy: 3 ads, $0.38. 628 tests. Next: E9 platform (the agency at work), partner Monday.

- 2026-10-31 — Matteo + Claude — Trend ads: creator tone (guide, course words refused, tone critic), eleven_v3 young voice, **dialogue with native Vietnamese voices** (Southern/Northern) checked line by line by Muse Voice Transcribe, mascot cut out with SAM masks (`meta-sam-parser`), videos in parallel, request timeouts, `--rerender`, harsh SFX (record scratch, bass drop) removed, whip/shake without black edges. Lost one set of scripts to a failed re-render → now never overwritten (test). Branch `b/video-ads` (PR #3, stacked on #2). Next: E14-8 selling structure, platform, partner Monday. **Tom: run `cd video && npm install` once for Remotion; `uv run --group capture` for creative capture; ElevenLabs key needed for sound (or `--silent`).**

- 2026-10-30 — Matteo + Claude — **Trend ads with sound** (branch `b/video-ads`): Remotion compositions (`video/`), ElevenLabs voice + music + sound effects, word-by-word captions, voice guard by Muse Voice Transcribe (WER ≤ 0.2), viral format library + 'trending now' from Ad Library dates, trend shot lists (trend → twist with the real app → CTA), SAM 3.1 crops the real UI from store screenshots. VietBuddy: 3 trend ads (POV, Day in the life, This or that), 15-17 s, voice checked (WER 0.10-0.19), **$0.69**. 587 tests. Known: first shot repeats the hook, bubbles can cover UI text, mascot not found ('cartoon mascot'), no competitor ad matched a format. Next: fix those, critic pass, platform.

- 2026-10-30 — Matteo + Claude — **Video ads** (branch `b/video-ads`): `whynot video RUN` = capture competitor creatives → Muse Spark deconstructs each ad (typed, cached) → archetypes scored on Ad Library signals → Muse Spark picks 3 that fit (persona + angle) → briefs checked like any copy → Muse Image scenes → 9:16 MP4 rendered by code with real screenshots and an end card. VietBuddy: 89 ads deconstructed, 3 videos of 17 s, **$0.52**. 543 tests. Next: audio (music + voice-over), video in the campaign plan and publishing, the platform showing it.

- 2026-10-30 — Matteo + Claude — **R3 v1** (branch `a/E2-1-r3-v1`): paired selection per advertiser, within-advertiser AUC with advertiser bootstrap, real competitor creatives (`ingest/creatives.py`, 99 % captured), simple-judge baseline (`validate/judge.py`). 186 GB ads, 44 advertisers, ~$5.6. **Result: no model-based condition beats chance (viewers text 0.52, with images 0.41, judge 0.46); shorter copy 0.62.** Bugs fixed with tests: JSONL split on U+2028, judge cost of failed attempts, video ads had no `<img>`. Next: decide the proof strategy (R1 partner metrics, R2 humans), test new viewer designs only on held-out advertisers.

- 2026-10-30 — Matteo + Claude — Reviewed lane A; fixed cassette key ignoring viewer draws (retest replayed the first answer). **R3 v0 on real data** (130 GB ads, 24 app advertisers, text only, $0.88): pooled AUC 0.49 [0.40, 0.58], within advertiser 0.55 [0.44, 0.66] → no evidence yet that the simulator predicts longevity. Found the selection doesn't balance per advertiser. `longevity_check.py` now queries ≤ 10 page ids per call. Next (A): balanced selection + ≥ 25 advertisers + judge baseline; (A+B) images in feeds (E2-2), then R3 v1.

- 2026-10-30 — Tom + Claude — Lane A, branch `a/lane-a-oct30`: E0-1 cassettes (`WHYNOT_CASSETTE=record|replay`, a whole fake-world `create` replays identically offline, $0), E0-2 `Budget` (estimate refused before running, hard stop during), E0-3 viewer cache (a view is never paid twice), E0-4 `whynot costs`, E3-1 hard feeds (same language, long-running, on-topic; wired into simulate + evolve), E3-2 tournament + Bradley-Terry (τ 0.92 on the fake world), E3-3 noise floor (1.96·√2·SD retest), E2-6 bias suite (≥ 92 % detection, 3 % false alarms). 471 tests, 95 %. No model spend. Next: with `MODEL_API_KEY`, record the VietBuddy cassette and run `scripts/bias_suite.py` on a real run; lane B: show the noise floor and the tournament in report/UI.

- 2026-10-29 — Matteo + Claude — `ROADMAP.md`: honest baseline (simulator never validated against reality, our ads judged on text only, agents are a fixed chain, tests check plumbing not quality, landing = mock-ups), 13 epics with ids, lanes A/B by files, test bar per task, $60 model budget with cassettes + viewer cache + Baseten, day-by-day gates to Nov 4. Next: claim tasks from the Thu Oct 29 row.

- 2026-10-29 — Matteo + Claude — First real publishes. Sandbox (act 2319100775624921): 10 images, campaign, 3 ad sets created; creatives refused (sandbox test user can't post as a New Pages Experience Page). Matteo's own ad account, PAUSED, €0 spent: images, campaign, 3 ad sets **and a creative** created; `ads` needs a payment method, then Meta put the new account under review (status 100). Findings in `META_APIS.md`. Next: resume `whynot publish outputs/runs/<run>-own-account --live --objective=traffic --approve=Matteo` once Meta clears the account (only `ads` left), or validate `ads` on the partner's account, PAUSED, with his consent.

- 2026-10-29 — Matteo + Claude — Publishing to Meta: `run/meta.py` (Marketing API client, retries, token redaction), `run/publish.py` (autopilot-gated, PAUSED, resumable, logged), `whynot publish`, Approve panel in the platform (readiness without exposing values, sandbox default). Tested on a fake Graph API (order, approval, cap, resume without duplicates, rate limits, token errors, leaks) + mutation check. **Not yet run against a real sandbox: needs META_SANDBOX_AD_ACCOUNT_ID, META_SANDBOX_TOKEN, META_PAGE_ID (setup in META_APIS.md).**
- 2026-10-29 — Matteo + Claude — Interface v3: premium Apple design with restrained Liquid Glass (glass only on toolbar, command bar, tabs, inspector over content), neutral palette, one accent, no motion beyond press feedback; landing = calm headline + command bar + static macOS product window + settings-style list. Checked light/dark/mobile.
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
