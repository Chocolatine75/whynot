# Roadmap: Oct 29 → Nov 4

The full todo list to the deadline: **Wed Nov 4, 9:00 PM ET = Thu Nov 5, 03:00 Paris** (6.5 days from Oct 29). Two people, each driving Claude Code sessions non-stop, in parallel, without stepping on each other.

The bar is `TARGETS.md`. This file is how we get there. `PLAN.md` keeps the milestones; this file holds the tasks.

**The ambition:** the first ad agency whose judgement is measured. It makes the ads, tests them in a simulated feed against the real market, proves that the test predicts reality, then runs the campaign. Every claim on screen is backed by a number reproducible with one command. Nothing half-working ships: a feature without its tests and its measured result is not done.

---

## 0. Where we really are

### Update Oct 31 (read this first)
- **Priority order (Matteo):** the whole automated system and a striking demo first; model training and validation science after. Arena cut (E9-3), 80-voter page dropped (E9-5/P-5 deprioritised).
- **Video ads are now the core output (new epic E14, mostly done):** `whynot video RUN` makes trend-jacking ads (a viral format, then the app as the twist), with real UI cut out by SAM 3.1, Muse Image photos, a young creator voice plus native voices (dialogue), word-by-word captions, sound effects, music, rendered with Remotion. VietBuddy: 3 ads in ~5 min for ~$0.30.
- **Simulator validation (R3) failed twice** (v0, v1 on 44 advertisers with images and a judge baseline): nothing model-based beats chance; shorter copy does (0.62). Reported as a limit; E2-10 market-trained judge postponed after the demo work.
- **Partner (VietBuddy) available Monday Nov 2 only:** R1 backtest and pilot launch that day.
- **Next (in order):** E14-10 videos published to Meta (the daily loop's last missing link) → real footage (Pexels) and TikTok trends if Apify access → E9 platform showing the agency at work → partner Monday → demo video. Done since: E14-8 ads that sell, E8-2/E8-3 daily loop.

### Baseline (Oct 29)

What works:
- `whynot create`: App Store → Scout → Strategist → Director → composer → guards → simulated feed → evolution → plan → report. Tried on 4 real apps, $1.5–5.5 per run.
- Publishing on the real Meta API: images, campaign, ad sets and creatives are created; ads wait for Meta's review of the test account.
- Web platform: run list, agency room, Approve panel.
- 382 Python tests and 49 web tests. Coverage ≥ 90 %. CI is green.

What is weak, and what this roadmap fixes:
1. **The simulator has never been compared with reality.** We have no R1, R2 or R3 at scale. *Without this the product is a toy.*
2. **Our ads are judged on text only.** In `arena.our_item`, viewers never see the composed image. We claim a visual test we don't do.
3. **The "agents" are a fixed chain of single model calls.** They have no tools, no search, no self-correction loop, and no shared log of decisions.
4. **Tests check plumbing, not quality.** Almost every test runs against a scripted fake model. Nothing measures whether a strategy or an ad is good, or whether two runs agree.
5. **Evolution shows no progress.** Scores hit the ceiling at generation 0 because the feeds are too easy.
6. **Weak copy goes through.** Example: "A full loop, not just phrases". No critic, no human judgement.
7. **The landing page is static mock-ups** with grey rectangles. There is no real interactive component.
8. **No pilot, no partner data, no daily loop, no Arena, no validation page.**

---

## 1. How we work non-stop (read before starting any session)

### Lanes: who owns which files
Two lanes, so two people (and their Claude Code sessions) never edit the same files.

| Lane | Owns | Default owner |
|---|---|---|
| **A: engine** | `src/whynot/sim/`, `validate/`, `agents/`, `ingest/`, `models.py`, `costs.py`, `eval/` (new), `scripts/` for those | Tom (swap freely) |
| **B: product** | `src/whynot/create/`, `assets/`, `run/`, `agency/`, `cli.py`, `web/`, demo | Matteo |
| shared | `docs/`, `tests/fakes.py`, `tests/world.py`, `pyproject.toml`, CI | append-only, small PRs, rebase often |

Cross-lane changes: open a small PR and ping the other person. Never commit a drive-by edit.

### Claiming a task
1. Pick the highest unclaimed task in your lane for today's day block (§3). Tasks marked **★** come first.
2. Put your name and branch in the `STATUS.md` "In progress" table, then commit.
3. One task = one branch = one worktree = one PR. Branch name: `a/A-12-short-name` or `b/B-07-short-name`.
4. Done = every line of the task's **Done when** and **Tests** is true, `./scripts/check.sh` is green, the box below is ticked with the measured value, and a log line is in `STATUS.md`.
5. Blocked > 30 min: write the blocker in `STATUS.md` and switch tasks. Never wait.

### Prompt for a fresh Claude Code session
> Read CLAUDE.md, docs/STATUS.md, docs/ENGINEERING.md and docs/ROADMAP.md. Take task <ID>. Before coding, write the plan and the tests you will add. Done means every "Done when" and "Tests" line is true, check.sh is green, and the roadmap box is ticked with the measured value. Commit often. Stay inside your lane's files.

### The test bar (applies to every task)
Each task lists its tests. The kinds, from cheapest to most expensive:

| Kind | What it proves | Cost |
|---|---|---|
| **unit** | one function, edge cases | free |
| **property** (hypothesis) | invariants hold for any input: budgets, ids, ordering, fairness | free |
| **adversarial** | a lying or broken model is caught: invented quotes, wrong JSON, policy violations, prompt injection in reviews or ads | free |
| **contract** | our parser accepts **recorded real responses**: App Store, Ad Library, Meta models, Marketing API | free |
| **replay** (new, E0) | a whole stage reruns on recorded model answers and gives the same output | free |
| **e2e fake world** | the pipeline runs end to end on a fake world with known answers | free |
| **eval** (new, E1) | quality on real apps against thresholds: validity, grounding, stability, judged quality | $, capped |
| **validation** | the simulator against reality: R1, R2, R3, R6 | $, capped |
| **live smoke** (`--live`) | real APIs still answer as we expect | cents |
| **visual** (Playwright) | pages render: screenshots in light, dark and mobile, no layout shift, a11y | free |
| **security** | no token in any file or log, path confinement, injection, cap breaches impossible | free |
| **mutation** | the tests fail when the code is broken (mutmut on the critical modules) | free, slow |

Rules:
- A bug fixed = a regression test that failed before the fix.
- No test may call a paid API unless it is marked `live` or `eval`.
- Every new model prompt gets an adversarial test **and** a replay cassette.
- Any number that will appear in the demo gets a test that recomputes it from the logs.

### Spending rules for testing
- **Cassettes first.** Record real model answers once, replay them for free forever (E0-1).
- **Cache viewer answers** by hash of (persona, feed, model, prompt version). A view is never paid twice (E0-3).
- **Viewers on Muse Spark Open (Baseten credits)** with `reasoning_effort="low"`: $0.0034 per feed, measured. Use Muse Spark only for comparisons.
- **Hard cap per command.** Every `eval` / `validate` command estimates its cost first and refuses to start above `--max-usd` (default $5).
- **Budget to the deadline: $60 of Meta Model API** across both people. Track it in `STATUS.md` (`uv run whynot costs --since 2026-10-29`). Above $40, only ★ tasks may spend.

---

## 2. The todo list, by epic

Format: `- [ ] **ID** ★? title` · *Done when* · *Tests*. ★ = critical path.

### E0. Infrastructure for non-stop work (A + B, day 1)

- [ ] **E0-1** ★ Replay cassettes for model calls (A) — *code done Oct 30 (`cassette.py`): a whole fake-world `create` replays identically offline at $0. Left: record the real VietBuddy strategy cassette (needs `MODEL_API_KEY`).*
  - *Done when:* `ModelClient` gains `record` and `replay` modes (`WHYNOT_CASSETTE=record|replay|off`). Cassettes are keyed by hash of (model, messages, params) and stored in `tests/cassettes/`. Tokens and keys are stripped. Replay never touches the network: a missing cassette fails loudly.
  - *Tests:* unit (key stability, redaction); a replay of a recorded VietBuddy strategy gives byte-identical output; a test that the network is never called in replay mode.
- [ ] **E0-2** ★ Cost cap per command (A) — *code done Oct 30 (`budget.py`, used by `ModelClient`, R3 and bias scripts; property test). Left: `create` CLI printing an estimate (lane B), `eval`/`validate` commands when they exist.*
  - *Done when:* `Budget(max_usd)` with `estimate()` before running and a hard stop during the run. Used by `create`, `eval`, `validate`. The CLI prints the estimate and the actual cost.
  - *Tests:* property (spend never exceeds the cap + one call); unit (refuses when the estimate is above the cap).
- [x] **E0-3** ★ Viewer answer cache (A) — *Oct 30: second identical simulation = $0 and 0 calls; hits logged `source=cache`; on by default (`data/cache/viewers`).*
  - *Done when:* a disk cache keyed by (persona, feed items + order, model, prompt version, effort). Hits are counted in the cost log as $0. Cache size is reported.
  - *Tests:* unit (a different order means a different key); e2e (a second run of the same simulation costs $0).
- [x] **E0-4** `whynot costs` report (A) — *Oct 30: `uv run whynot costs --since 2026-10-29`.*
  - *Done when:* totals by day, module, model and run, plus remaining budget vs the $60 cap.
  - *Tests:* unit on a recorded log.
- [ ] **E0-5** Fast CI (both) — *Oct 30: `pytest -n auto` in `check.sh` (Python tests 96 s → 25 s locally, 3 runs green); replay tests run in CI; `live` skipped. Left: visual tests (lane B), CI time measured on GitHub.*
  - *Done when:* Python tests in parallel (`pytest -n auto`); CI < 4 min; replay and visual tests in CI; `live` and `eval` never run in CI.
  - *Tests:* the CI run itself.
- [ ] **E0-6** Mutation testing on the critical modules (A)
  - *Done when:* `mutmut` on `run/autopilot.py`, `run/publish.py`, `create/guards.py`, `sim/arena.py`, `validate/stats.py`. Mutation score ≥ 80 % on each, reported in `ENGINEERING.md`.
  - *Tests:* the score itself; surviving mutants are fixed or explained.
- [ ] **E0-7** Structured agent event log (A)
  - *Done when:* every agent step writes one `AgentEvent` (agent, step, inputs digest, outputs digest, tool calls, guard results, cost, duration, parent event) to `events.jsonl`. The web app reads it.
  - *Tests:* e2e (every stage of `create` emits events; costs in events sum to `costs.jsonl`); security (no token in events).

### E1. Evaluation bench: measure the agents, not just the plumbing (A)

- [ ] **E1-1** ★ Eval set of 20 real apps (A)
  - *Done when:* `eval/apps.yaml` lists 20 apps:
    - varied categories: language, fitness, finance, games, productivity, kids, health, travel, food;
    - varied storefronts: US, FR, DE, GB, ES, IT, BR, JP;
    - small and large apps, some with < 50 reviews, one with no reviews, one non-English-only;
    - why each app was picked;
    - licences for using public store data recorded in `DECISIONS.md`.
  - *Tests:* schema validation; every app id resolves (live smoke, cents).
- [ ] **E1-2** ★ `whynot eval agents` (A)
  - *Done when:* runs Scout → Strategist → Director (no viewers) on the eval set within `--max-usd`, and writes `eval/results/<date>/` with per app and per stage:
    - valid on first try / after repairs / failed;
    - quotes verified;
    - copy-rule violations caught;
    - accents and language correct;
    - policy hits;
    - cost and time.
  - *Tests:* replay e2e on 2 recorded apps (free); thresholds are asserted in the report.
  - *Targets:* ≥ 95 % of stages valid after repairs, 100 % of quotes verified, 0 wrong-language ads, cost ≤ $0.60 per app without viewers.
- [ ] **E1-3** Stability (A)
  - *Done when:* the Director is run 3× on the same cached strategy for 10 apps. We measure: overlap of chosen angles, embedding similarity of headlines, and how often the same objection is addressed.
  - *Tests:* the stats function (unit) + the report.
  - *Target:* the same top objections addressed in ≥ 2/3 runs.
- [ ] **E1-4** ★ Copy-quality judge, calibrated on humans (A)
  - *Done when:* a pairwise judge ("which ad would make you stop and want it?") is validated on ≥ 60 human pairwise labels from both of us and 3 friends. Report its agreement with humans with a CI. Used only as a regression signal, never shown as truth.
  - *Tests:* the agreement computation (unit); a position-bias check (A/B swap gives the same pick ≥ 90 %).
- [ ] **E1-5** Our ads vs real competitor ads, blind (A + B)
  - *Done when:* for 10 eval apps, we put 3 of our ads and 3 real long-running competitor ads in front of humans (≥ 5 people) and the judge, blind. We report how often ours are preferred.
  - *Tests:* the sampling is balanced (property); labels are stored without identities.
- [ ] **E1-6** Failure gallery (A)
  - *Done when:* the eval report lists the 10 worst outputs with the reason (judge, rule or human). Each one becomes a task or an adversarial test.
  - *Tests:* each listed failure has a linked test or task id.
- [ ] **E1-7** Eval dashboard in the web app (B)
  - *Done when:* `/eval` shows the latest eval run: per stage pass rates, cost, failure gallery, trend vs previous runs.
  - *Tests:* visual + unit on the data loader.

### E2. Validate the simulator against reality (A, ★ the technical hero)

- [ ] **E2-1** ★ R3 at scale: longevity (A) — *v0 measured Oct 30 (text-only, 130 GB ads, 24 advertisers, Muse Spark Open low, $0.88, `validate/results/r3-v0.json`): pooled AUC 0.49 [0.40, 0.58]; within advertiser 0.55 [0.44, 0.66] on 9 advertisers / 84 pairs. **No evidence yet.** Found: `select` does not balance per advertiser (Ling 24 long / 0 short), so the pooled AUC partly measures the brand. Left: only advertisers with both classes, ≥ 25 of them, images (E2-2), single-LLM judge baseline.* *v1 measured Oct 30 (`validate/results/r3-v1-apps-gb-v1.json`, `scripts/r3_v1.py`, ~$5.6 in all): 186 GB ads, 44 advertisers with both classes, 93 per class, real creatives (138 of 186 are videos, seen as their poster frame). Within-advertiser AUC: viewers text 0.52 [0.44, 0.60], viewers with images 0.41 [0.36, 0.47] (below chance), simple judge text 0.46, judge image 0.46, **shorter copy 0.62 [0.52, 0.73]**. Neither the simulator nor a plain LLM judge predicts longevity; a copy-length heuristic does better. R3 as designed fails its floor (> 0.55).*
  - *Done when:*
    - ≥ 200 ads from ≥ 15 advertisers in ≥ 4 categories, classes balanced per advertiser (long ≥ 60 days active, short ≤ 14 days stopped, pre-registered in `DECISIONS.md` on Oct 28);
    - viewers on Muse Spark Open, low effort;
    - AUC with bootstrap CI vs baselines: copy length, a single-LLM judge without feed or personas, random;
    - result in `validate/results/r3.json`, reproducible with `uv run whynot validate r3`.
  - *Tests:* the stratified split (property: no advertiser on both sides of a comparison); replay of a 20-ad subset.
  - *Target:* AUC ≥ 0.65; floor > 0.55; whatever it is, we publish it.
- [ ] **E2-2** ★ Images in the simulator (A + B)
  - *Done when:* viewers see **the composed image** of our ads and **the real creative** of competitor ads (snapshot capture, E2-3). Text-only mode stays available for comparison. R3 is re-run with images.
  - *Tests:* `our_item` includes the image (unit); a viewer cassette with images; cost per feed with images measured and reported.
- [x] **E2-3** Creative capture from Ad Library snapshots (A) — *Oct 30: `ingest/creatives.py`, 295/298 captured (99 %), video ads via poster frame, no URL or token stored.*
  - *Done when:* images (and video first frames) of competitor ads are fetched from snapshot pages without a token in any stored URL, ≥ 90 % success on 100 ads, licence notes in `DECISIONS.md`.
  - *Tests:* contract on recorded snapshot HTML; security (no `access_token` anywhere in the store).
- [ ] **E2-4** ★ R1 backtest on the partner's history (A, needs P-2) — *Oct 31: ready for Monday (`validate/backtest.py`, `scripts/r1_backtest.py`): Ads Manager CSV (EN/FR) or API read, protocol pre-registered in DECISIONS, blind by construction (tested), numbers-only summary, partner data under `data/private/`. Fake partner: a simulator with the right taste scores ≥ 0.75. Left: run it on his data.*
  - *Done when:*
    - pairwise accuracy of the simulator vs the real metric (CTR, CPA or hook rate) on all pairs of his past ads, blind to outcomes, with a CI;
    - baselines: random, single-LLM judge, longest copy, most recent;
    - anonymised summary in the repo; data stays in `data/private/`.
  - *Tests:* the pair builder (property: no pair with an outcome difference smaller than the noise threshold, pre-registered); a security test that no private file is tracked by git.
- [ ] **E2-5** ★ R2 human agreement (A + B)
  - *Done when:* a public, mobile-friendly blind test page (`/judge`): pairs of ads, "which one would you stop on?", no login, one vote per pair per browser, spam guard. ≥ 80 people × 6 pairs by Nov 3. Agreement with the simulator with a Wilson CI.
  - *Tests:* the randomisation (left/right balanced, property); dedup; the analysis script on synthetic votes with a known answer.
- [ ] **E2-10** Market-trained judge (A) — *added Oct 30 after R3 v1 failed; postponed Oct 31 (system and demo first)*
  - *Done when:* ads from the Ad Library (≥ 2,000, ≥ 150 advertisers with both classes) are embedded with Meta's Perception Encoder (open weights, local, $0) plus readable features (hook, price, social proof, format, length); a small head is trained to tell long-running from short-lived ads **within an advertiser**; tested on held-out advertisers only.
  - *Business metric:* among an advertiser's ads, the share that lasted in the model's top half vs at random ("ads we'd have launched").
  - *Decision rule (fixed before results):* if top-half survival beats random by **≥ 10 points** on held-out advertisers and the within-advertiser AUC beats shorter copy (0.62), it becomes the agency's gate and a demo number; otherwise it is reported as a limit and R2 + R1 carry the proof.
  - *Tests:* the advertiser split (property: no advertiser in both train and test); features extracted deterministically; the metric on synthetic data with a known answer.
- [ ] **E2-6** Bias suite (A) — *code done Oct 30 (`validate/bias.py`, `scripts/bias_suite.py`): brand, length, emoji, label leak, position (language via `translated`). Fake world, 40 seeds: planted biases caught ≥ 92 %, 3 % false alarms. Left: record a real run in cassettes and gate CI on it.*
  - *Done when:* automated checks run on every simulator change:
    - brand name (placebos);
    - position in the feed;
    - copy length;
    - language;
    - emoji density;
    - "our" ad label leakage.
    Each reports an effect size; any effect above threshold fails CI (replay mode).
  - *Tests:* each check detects a planted bias in the fake world (≥ 90 % detection) and stays quiet on a fair one (≤ 5 % false alarms).
- [ ] **E2-7** Persona fidelity check (A)
  - *Done when:* personas built from Ad Library reach (country × age × gender) are compared with the real reach mix of the ads they judge; the report shows the gap.
  - *Tests:* the allocation (property: sums to the reach shares within rounding).
- [ ] **E2-8** Predictive intent with SSR (A)
  - *Done when:* free-text intent is mapped to a Likert distribution (semantic similarity rating); compared with the 1–5 direct rating on R3; we keep whichever predicts better.
  - *Tests:* unit on anchor statements; the comparison report.
- [ ] **E2-9** `whynot validate all` (A)
  - *Done when:* one command recomputes R1, R2, R3 and R6 from stored inputs (cassettes and cached views): same numbers, $0.
  - *Tests:* run in CI on the stored inputs; numbers match `validate/results/*.json` exactly.

### E3. Harder, fairer simulated feeds so evolution can show progress (A)

- [x] **E3-1** ★ Hard feeds (A) — *Oct 30: `sim/relevance.py`, used by simulate + evolve. Fake world: a weak ad scores 1.7–1.85× chance vs the raw market, 0.05–0.4× in hard feeds.*
  - *Done when:* competitors in each feed are the **most relevant** ones (same category and language, long-running first), not random market ads. Our ads must beat ads that survived in the market.
  - *Tests:* relevance ranking (unit); a fake world where a weak ad loses to strong competitors.
- [ ] **E3-2** ★ Tournament mode (A) — *code done Oct 30 (`sim/tournament.py`): Kendall τ mean 0.92, ≥ 0.8 in 95 % of 20 seeds (6 variants, 9 games per pair). Left: call it from `simulate`/`evolve` and show it in the report (with E6-1).*
  - *Done when:* our variants face each other in round-robin feeds, which gives a ranking with a CI and no ceiling. The arena reports win rate vs competitors **and** Elo/Bradley-Terry among ours.
  - *Tests:* Bradley-Terry fit recovers a known ranking on the fake world (Kendall τ ≥ 0.8).
- [ ] **E3-3** Noise floor (A) — *code done Oct 30 (`validate/retest.py`): floor = 1.96·√2·SD(retest); 8 ads: 90 % of real gaps clear it, 9 % of equal-ad gaps do. Left: display it next to simulated differences in report and UI (lane B).*
  - *Done when:* the same feed is shown twice with a new seed. We measure test-retest agreement and use it as the minimum difference we report as real.
  - *Tests:* the stats (unit); the floor is displayed next to every simulated difference in the report and the UI.
- [ ] **E3-4** Viewer realism (A)
  - *Done when:* viewers get a scroll budget (they skip most ads, as people do). The prompt forbids knowing which ad is ours, and output includes "would scroll past" with a reason. Stop rates are compared with the 1–3 % CTR range of real feeds, as a sanity check only.
  - *Tests:* adversarial (the viewer is told an ad is "ours" in the copy: the placebo check catches the effect).
- [ ] **E3-5** Teacher on Baseten by default (A)
  - *Done when:* `VIEWER_BACKEND=baseten` is the default. Fallback to Muse Spark on errors is logged. Cost and latency per feed are reported.
  - *Tests:* live smoke (cents); unit on fallback.

### E4. Real agents: tools, loops and a shared log (A, kept only if E1 shows a gain)

Rule: each change is A/B tested on the eval set (E1-2) with the same budget. If quality doesn't improve, revert. We call them agents only where they really choose.

- [ ] **E4-1** ★ Scout with tools (A)
  - *Done when:* the Scout gets tools: `search_ads(terms, countries)`, `page_ads(page_id)`, `app_search(term)`, `lookup_app(id)`. It loops until it has ≥ 5 relevant long-running competitors or hits its step budget (≤ 8 tool calls), and logs each choice with its reason.
  - *Tests:* adversarial (tools return junk or injected text "ignore your instructions": it is ignored and logged); replay; on the eval set, relevant competitors per app vs the fixed-query Scout.
- [ ] **E4-2** Researcher agent (A)
  - *Done when:* it reads reviews (store + optional Reddit/Trustpilot when licensed), the app's own ads, and the website, then writes objections with verified quotes and frequency. It replaces the Strategist's review reading.
  - *Tests:* every quote is found verbatim in its source (unit + adversarial); frequency counts match on a fake corpus.
- [ ] **E4-3** Critic loop for copy (A)
  - *Done when:* after the Director, a critic scores each ad (E1-4 judge + rules) and sends the bottom third back once with the critique. Gain is measured on the eval set.
  - *Tests:* the loop stops (property: ≤ 1 round); replay; the gain report.
- [ ] **E4-4** Analyst agent (A)
  - *Done when:* it reads simulated reactions, groups the "why not" into themes, and proposes the mutations the Evolver applies. Every claim cites reaction ids.
  - *Tests:* cited ids exist (unit); adversarial (invented ids rejected).
- [ ] **E4-5** Orchestrator (A + B)
  - *Done when:* one orchestrator runs the agents over the `AgentEvent` log (E0-7), with a budget per agent, retries, and a resume from any event. `create` becomes a configuration of it.
  - *Tests:* e2e on the fake world; resume from every stage; budget per agent enforced (property).
- [ ] **E4-6** Account manager (B)
  - *Done when:* it writes the owner's report in their language from the event log, every number linked to its source event. It answers the owner's questions about the run from the log only.
  - *Tests:* every number in the report is found in the log (unit); adversarial (a question about data not in the log → "I don't know").

### E5. Ad quality: creative that a real business would ship (B)

- [ ] **E5-1** ★ Copy rules v2 (B)
  - *Done when:* headlines ≤ 6 words with a verb or a number, a concrete benefit, no abstract nouns ("loop", "journey", "solution"), and the objection named or answered. The rules come from E1-6 failures.
  - *Tests:* adversarial on 30 bad headlines from real runs (all rejected) and 30 good real ads (≥ 90 % pass).
- [ ] **E5-2** ★ 6 layout templates (B)
  - *Done when:*
    - layouts: split, rising, full-bleed screen, testimonial card (verified quote), before/after, big number;
    - formats: 1:1, 4:5, 9:16, each checked;
    - visual review: both of us rate ≥ 4/5 on a sheet of 24 ads.
  - *Tests:* golden image tests (pixel-perfect per template on fixed inputs); guards pass on all; text never overflows (property over random copy lengths and languages including DE and JP).
- [x] **E5-3** SAM cutouts as product assets (B) — *Oct 31: `assets/cutouts.py`, SAM 3.1 finds the phone screen (UI crop of the original pixels) and the mascot (mask decoded with Meta's `meta-sam-parser`, transparent PNG). Boxes and masks cached.*
  - *Done when:* the SAM 3.1 mask decoder works, the screen is cut out of store screenshots, the pixel guard compares against the cutout, and R8 = 0 px on 100 % of ads.
  - *Tests:* decoder on a known shape (unit); a recorded SAM response (contract); the guard fails on a 1-pixel change (property).
- [ ] **E5-4** Localised screenshots per storefront (B)
  - *Done when:* French ads use the FR App Store screenshots when they exist, with a fallback to the source language that is logged.
  - *Tests:* contract on recorded FR/US lookups.
- [x] **E5-5** Reels: video ads (B) — *superseded by E14: 12-18 s 9:16 ads rendered with Remotion.*
  - *Done when:* ffmpeg composes a 9:16 6 s video (hook frame, screen scroll, CTA) from the same genome, deterministically. Viewers see 3 key frames.
  - *Tests:* same genome → same bytes (hash); duration and resolution checked; guards on every key frame.
- [x] **E5-6** Muse Image scenes, never product pixels (B) — *Oct 31: photo prompts can never ask for a phone, screen, app, logo, sign or text (validated); cached by prompt.*
  - *Done when:* optional background scenes from Muse Image, with the product composited on top by code; the pixel guard proves the product area is untouched.
  - *Tests:* guard on composed output (property); cassette.
- [ ] **E5-7** Diversity guard R7 (B)
  - *Done when:* concept embeddings (copy + genome) with a pairwise threshold; near-duplicates are rejected and regenerated; the threshold is set on a labelled set of 40 pairs.
  - *Tests:* labelled pairs (≥ 90 % agreement); property (output has no pair above the threshold).
- [ ] **E5-8** Policy guard with a model (B)
  - *Done when:* rules v0 + a Muse Spark check on Meta's ad policies (health claims, before/after, personal attributes "Are you…?", etc.). It is precise on a labelled set of 50 ads.
  - *Tests:* the labelled set (precision ≥ 0.9, recall ≥ 0.8); adversarial.
- [ ] **E5-9** Android / Play Store and Shopify inputs (B)
  - *Done when:* `create` accepts a Play Store URL and a Shopify product URL with the same downstream pipeline.
  - *Tests:* contract on recorded pages; e2e on the fake world for each source.

### E6. Evolution that measurably improves ads (A + B, R6)

- [ ] **E6-1** ★ Evolution on hard feeds and tournaments (A)
  - *Done when:* generations are judged by E3-1 + E3-2. The report shows the score per generation with a CI and the noise floor. On ≥ 5 eval apps, gen 2 beats gen 0 by more than the noise floor (simulated), or we say it doesn't.
  - *Tests:* the fake world with a known better mutation: evolution finds it in ≥ 80 % of seeds.
- [ ] **E6-2** Counterfactuals (A)
  - *Done when:* remove or swap one element (headline, screen, CTA, badge) and re-test, which gives a contribution per element (simulated) shown in the report.
  - *Tests:* the fake world with a known element effect is recovered (sign correct ≥ 90 %).
- [ ] **E6-3** ★ R6 with humans (A + B)
  - *Done when:* evolved vs original pairs go into the `/judge` test (E2-5); humans prefer evolved ≥ 65 % with p < 0.05, or we report the real number.
  - *Tests:* the analysis on synthetic votes.

### E7. Student viewer: big model teaches, small serves (A, R10, open weights prize)

- [ ] **E7-1** Teacher dataset (A)
  - *Done when:* ≥ 3,000 teacher reactions (Muse Spark Open) on varied feeds, stored with prompt version; train / val / test split by advertiser.
  - *Tests:* no advertiser leak across splits (property).
- [ ] **E7-2** Student fine-tune (A)
  - *Done when:* a smaller open model is fine-tuned (Fireworks or Modal) on the teacher dataset. On the test set: agreement with the teacher ≥ 85 % on preference, at ≥ 10× lower cost per feed, measured.
  - *Tests:* the eval script on a stored test set; cost from the ledger.
- [ ] **E7-3** Student in production (A)
  - *Done when:* `VIEWER_BACKEND=student` for volume (evolution rounds); the teacher stays for final verdicts; agreement is monitored on 10 % of feeds.
  - *Tests:* unit on routing; monitoring alert when agreement < 80 %.

### E8. Running the campaign: publish, read, rotate, report (B, R4 R5 R9)

- [ ] **E8-1** ★ Finish real publishing (B)
  - *Done when:* the remaining `ads` step succeeds on a real account (Matteo's once Meta clears it, or the partner's, PAUSED, with consent). `META_APIS.md` lists every error seen and the fix.
  - *Tests:* `test_publish` gains the real error shapes we saw (1885183, 1341012, 1359188, 2490592) with clear messages.
- [x] **E8-2** ★ Read real metrics (B) — *Oct 31: `run/insights.py` (Insights API per ad and day, cursors not token URLs, junk numbers as 0, provisional recent days) + a labelled simulated account; property test on totals.*
  - *Done when:* `run/insights.py` reads the Insights API per ad and day (spend, impressions, clicks, CTR, installs, CPA), handles attribution delays, and never stores tokens.
  - *Tests:* contract on recorded insights responses; property (sums per day match totals).
- [x] **E8-3** ★ `whynot daily` (B) — *Oct 31: `agency/daily.py` + `agency/memory.py` + `agency/ideas.py`: results → pause losers/tired (decide + log) → ideas (exploit what sells in a new format, explore far away, never an idea twice, backups when one fails) → videos told past hooks → launch within cap/autonomy → report. Lock against concurrent runs; cap property over random results. Simulated week on VietBuddy: 4 days, 3 ads live, $0.57. Publishing videos to Meta still E14-10.*
  - *Done when:* metrics → autopilot rules (pause losers, keep winners, fatigue) → new variants from the evolution → simulate → publish within caps → daily report. Every action goes through `decide()` and is logged. It runs from cron or the web app.
  - *Tests:*
    - e2e on a fake Meta with 7 simulated days of metrics: losers paused, cap never exceeded (property over random metric series);
    - a cap breach is impossible, even under concurrent runs (lock test).
- [ ] **E8-4** ★ Predictions published before results (B + A, R5)
  - *Done when:* before the pilot launches, the simulator's ranking of the pilot's ads is committed with a hash and a timestamp (git commit + a public post). After N days it is compared with real metrics.
  - *Tests:* the comparison script on synthetic outcomes.
- [ ] **E8-5** Weekly report with approve / block (B)
  - *Done when:* an owner-facing report (web + email-ready HTML): what ran, what was paused and why, new concepts awaiting approval, spend vs cap. Approve and block buttons call the autopilot.
  - *Tests:* every number traced to the log (unit); the approve path is logged (e2e).
- [ ] **E8-6** Kill switch (B) — *Oct 31: `whynot stop RUN... --by NAME [--live]` (`run/killswitch.py`): campaigns first, then ad sets and ads in parallel; from publish.json (even partial) and the daily loop's memory; any autonomy level; logged; tested on the fake Graph. Button in the platform (Oct 31): "Pause everything now" in the publish panel, one confirmation with the owner's name, runs `whynot stop` without a shell and shows its result (`web/lib/stop.ts`, `/api/stop`). Left: a timed run against the sandbox.*
  - *Done when:* one command and one button pause everything whynot created on the account in < 10 s, logged.
  - *Tests:* e2e on the fake Graph (all objects PAUSED); it works even if publish.json is partial.
- [ ] **E8-7** Ads MCP path (B)
  - *Done when:* the same actions go through the Ads MCP where it supports them, with the Marketing API as fallback; both are tested on the fake.
  - *Tests:* contract per path.

### E9. Web platform: real interactive product, not mock-ups (B)

Rules: every component shows **real data from a real run**; no grey placeholder; every simulated number is labelled; motion only for feedback; light, dark and mobile; a11y AA.

- [ ] **E9-1** ★ Landing rebuilt on real data (B)
  - *Done when:* the landing uses a real run (VietBuddy, anonymised if needed), with:
    1. a **live feed** you can scroll: our ads among real competitor ads;
    2. tap an ad → what each simulated persona thought (hook, believed, why not), labelled simulated;
    3. a **persona switcher** that changes the feed verdicts;
    4. an **evolution scrubber**: parent → mutation → child, score delta with the noise floor;
    5. the **campaign plan** with editable budget and countries, recomputing the split live;
    6. the command bar starting a real run.
    Lighthouse ≥ 95 performance and a11y on mobile.
  - *Tests:* visual (light / dark / mobile screenshots, golden); interaction tests (Playwright: switch persona, scrub, edit budget); unit on data mappers; no mock data in the bundle (a test greps for placeholders).
- [ ] **E9-2** ★ Agency room v2 (B)
  - *Done when:* a live agent timeline from `events.jsonl` (E0-7): each step with its inputs, decision, cost, and guard results, expandable; cost counter; failures shown, not hidden.
  - *Tests:* visual; it streams a run in progress (e2e with a fake run writer).
- [ ] ~~**E9-3** ★ Arena public (B, R11 R12)~~ — *cut Oct 30: the product is the agency for a real client; R12 = real businesses on the agency*
  - *Done when:* no account; paste a link → 3 tested concepts in < 5 min (measured p50 and p90). Rate-limited, per-IP budget cap, queue with position, shareable result page. Abuse handling: the link must resolve to a real App Store / Play / Shopify page.
  - *Tests:* load test (10 concurrent runs within budget); the rate limiter (unit); a security test (SSRF: only allowed hosts are fetched).
- [ ] **E9-4** ★ Validation page (B + A)
  - *Done when:* `/validation` shows R1, R2, R3, R6 and R10 with CIs, baselines, sample sizes, the method in plain words, failures and limits, plus the one command to reproduce.
  - *Tests:* numbers read from `validate/results/*.json` (unit); visual.
- [ ] **E9-5** `/judge` human test page (B, feeds E2-5)
  - *Done when:* mobile-first, one tap per pair, progress, no login, privacy note.
  - *Tests:* see E2-5; visual.
- [ ] **E9-6** Approvals and owner settings (B)
  - *Done when:* the owner sets cap, autonomy level and countries; approves or blocks; sees the action log. Every change is logged.
  - *Tests:* e2e (Playwright) through the approve flow on the fake Graph; argument-injection tests on every field.
- [ ] **E9-7** Deploy (B)
  - *Done when:* the platform runs on a public URL (Arena, validation, judge); the engine runs on a small server with a job queue; secrets live in the host's secret store.
  - *Tests:* a smoke test against the public URL; a security headers check.

### E10. Partner pilot and real users (people tasks, both)

- [ ] **P-1** ★ Written consent from the partner (Matteo, today)
  - *Done when:* a message in writing covering: what we access, the cap, the autonomy level, the start date, anonymisation in the demo.
- [ ] **P-2** ★ Partner data (Matteo, by Oct 30)
  - *Done when:* an export of past ads + per-ad metrics in `data/private/partner/`, plus read access to his ad account (system user or partner token). Unblocks E2-4.
- [ ] **P-3** ★ Pilot launch (both, by Oct 31)
  - *Done when:* predictions published (E8-4), then first ads live on his account within his cap after his explicit approval.
- [ ] **P-4** 5 more businesses (both)
  - *Done when:* 5 businesses ran the Arena and gave a quote; 2 agreed to try the agency.
- [ ] **P-5** Human testers (both)
  - *Done when:* ≥ 80 people did the `/judge` test (friends, school, Discord, X).
- [ ] **P-6** Build in public (both)
  - *Done when:* one post a day with a real number.

### E11. Security, privacy, reliability (both, continuous)

- [ ] **S-1** Secret scanning in CI (gitleaks), plus a test that greps every output file for token patterns.
- [ ] **S-2** Path confinement and SSRF tests for every web route and fetcher.
- [ ] **S-3** Prompt-injection suite: injected text in reviews, ad copy, app descriptions and websites, across all agents; nothing changes behaviour or leaks.
- [ ] **S-4** Contributor tier is never used with partner data (a unit test on the routing + a log audit).
- [ ] **S-5** Chaos tests: kill the process at every stage of `create` and `publish`, resume, no duplicate and no corruption (property over random kill points).
- [ ] **S-6** Rate-limit and timeout behaviour for every external API (recorded 429/5xx responses).

### E12. Demo, docs, submission (both, Nov 3–4)

- [ ] **D-1** One command reproduces every number in the demo (`uv run whynot reproduce`), $0 from cassettes and caches.
- [ ] **D-2** README final: what it is, what was built during the event, an architecture diagram, how to run, results with links.
- [ ] **D-3** 3-minute video per `DEMO.md`, plus a 30 s cut for X.
- [ ] **D-4** Go through `TARGETS.md` line by line with measured values.
- [ ] **D-5** Submit on Cerebral Valley Wed Nov 4 evening Paris time; flag open weights.

---

### E14. Video ads that hold a thumb (B, the core output since Oct 30)

Method inspired by VoodRadar (ideas only: no licence, hackathon rule), rebuilt on Meta models.

- [x] **E14-1** Deconstruct competitor ads (Muse Spark vision): hook, visual, overlays, CTA, pitch, style, promise, audience, viral format; palette by code; cached by ad id + prompt version (`agents/deconstruct.py`).
- [x] **E14-2** Archetypes scored on Ad Library signals (staying power, reach, reuse, breadth), Muse Spark picks what fits the app (`agents/archetypes.py`).
- [x] **E14-3** Viral format library (12 formats) + "trending now" from competitor start dates (`create/trends.py`). *On VietBuddy's market no competitor ad matched a format: formats picked on fit.*
- [x] **E14-4** Trend briefs: 8-14 shots of 0.6-2.2 s, trend (≥ 50 %) → twist with the real app → CTA; copy rules; creator tone guide, course/ad words refused, tone critic with one rewrite (`agents/trend_brief.py`).
- [x] **E14-5** Dialogue with native voices: "me" (young creator) and "them" (a local, in their language, native ElevenLabs voice by accent); each line voiced on its own, checked by Muse Voice Transcribe in its language (`audio/voices.py`, `agency/trend_video.py`).
- [x] **E14-6** Remotion compositions (`video/`): hard cuts, native caption bubbles, word-by-word captions (natives in yellow), punch-in / shake / whip, sound effects on cuts, ducked music, end card; Pillow fallback without Node.
- [x] **E14-7** Robustness: model requests time out (3 min), videos made in parallel, a failed run never overwrites the last scripts, `--rerender` renders the same scripts again.
- [x] **E14-8** ★ Make it sell (Oct 31, `Selling` in `agents/trend_brief.py`): demo of the app in action (≥ 25 % of the time, ≥ 2 real screens), proof (a verified review quote), transformation shot, offer from the store page ("free to start"), the app named in the voice. Enforced by the validator.
- [ ] **E14-9** Reference ads: the client's best videos (MP4 with consent, `data/private/`) deconstructed into a house style the briefs follow.
- [ ] **E14-10** Videos in the campaign plan and in publishing (Marketing API video upload, PAUSED).
- [ ] **E14-11** Critic on keyframes vs the best competitor ads before the final render.
- [x] **E14-12** Captions: Vietnamese words in English captions keep their accents (seen: "ca phe sua"). — *Oct 31: the prompt example had no accents; the prompt now asks for them and the validator refuses known unaccented Vietnamese words in English lines and on-screen text, naming the correct spelling.* *The creator's own Vietnamese now has its own line and caption (set apart by language).*

Tests: `test_deconstruct`, `test_archetypes`, `test_brief`, `test_trends` (formats, trend briefs, tone, dialogue, cut-outs, props, never losing scripts), `test_audio` (voice, music, SFX, dialogue guard, captions), `test_remotion` (props + a real render when Node is installed), `test_video`, `test_video_pipeline`.

## 3. Day by day (gates are hard)

| Day | Lane A (engine) | Lane B (product) | People | Gate (evening) |
|---|---|---|---|---|
| **Thu Oct 29** | E0-1, E0-2, E0-3, E1-1 | E9-1 starts, E0-5 | P-1 consent, P-2 asked | cassettes + cost cap + cache merged |
| **Fri Oct 30** | E2-1 R3, E3-1, E3-2, E1-2 | E9-1 done, E5-1, E8-2 | P-2 data in hand, Fireworks workshop | **R3 measured** at any value; landing on real data |
| **Sat Oct 31** | review PR #2/#3; E14-12; E2-4 R1 script ready on partner-shaped fake data | E14 trend ads with sound + dialogue (done); **E14-8 selling structure** | — | 3 VietBuddy trend ads that sell |
| **Sun Nov 1** | E14-11 critic; E1-2 eval of the video pipeline on 5 apps (cheap) | **E9 platform: the agency at work** (pipeline live, Remotion Player, approve), E14-10 videos in the plan | find 2-3 more apps whose founders agree | a stranger sees the agency make ads live |
| **Mon Nov 2** | **E2-4 R1 on the partner's history, same day** | **Partner day:** consent, data, E14-9 his best videos as reference, predictions committed, pilot launched PAUSED→ACTIVE with his approval; E9-7 deploy | partner | R1 measured; pilot live |
| **Tue Nov 3** | E2-9 reproduce; validation page with honest limits (R3) | first pilot metrics (1 day, shown as a start), D-2 README, D-3 video draft | pilot day 2 | demo video drafted |
| **Wed Nov 4** | D-1, D-4 | D-3 video, D-5 submit | post | **submitted before 22:00 Paris** |

If a gate fails: write it in `STATUS.md`, take the next item from the cut list, and never lower a target silently.

### Gate log

- **Sat Oct 31, daily loop (E8-2, E8-3) done** on a simulated account: memory, idea planner (exploit/explore, never twice), backups. Found on the real run: a failed idea was retried every day (fixed: recorded as failed, backups fill the slot) and 34 % exploit rounded to 0 with one slot (fixed).
- **Sat Oct 31, E14-8 done:** ads go trend → twist → demo (≥ 25 %, ≥ 2 real screens, a tap) → a verified 4-5★ App Store review quoted word for word → transformation → offer from the store page ("Free to download"); the creator names the app. Voice guard taught spoken forms (wanna, lowkey, fifty/50, VietBuddy/Viet buddy) after it dropped a correct voice.
- **Sat Oct 31:** trend video ads with voice, dialogue and native voices done (E14-1..7); harsh sound effects removed, transitions fixed. Matteo: "much better, but it doesn't sell yet" → E14-8 next.
- **Fri Oct 30, replan:** the partner is only available Mon Nov 2. R1 (needs only his past ads) moves to Monday, same day; the pilot launches Monday and shows 1–2 days of results, presented as a start with predictions published before. R3 failed (v0, v1), so validation rests on E2-10 (market-trained judge), R2 (humans) and R1. Arena (E9-3) cut: the product is the agency for a real client.
- **Fri Oct 30, R3 v1 (balanced, 44 advertisers, images, judge baseline): negative.** Nothing model-based beats chance within advertiser; viewers with images are below it (0.41); shorter copy reaches 0.62. Decision needed: R1 (partner's real metrics) and R2 (humans) become the main proofs; R3 is reported as a limit. See DECISIONS.
- **Fri Oct 30, R3 v0 measured (gate met, result negative):** text-only simulator does not separate long-running from short-lived ads (pooled 0.49, within-advertiser 0.55, CIs include 0.5). Next: balanced-per-advertiser selection, more advertisers, images in the feed, judge baseline — then re-run.
- **Thu Oct 29 gate (cassettes + cost cap + cache): met Oct 30** (branch `a/lane-a-oct30`): E0-1, E0-2 code done, E0-3 done; a fake-world `create` replays offline at $0. Real cassettes wait for `MODEL_API_KEY`.
- **Fri Oct 30, lane A:** E3-1 done (hard feeds wired into simulate + evolve); E3-2 and E3-3 code done (tournament τ 0.92, noise floor); E2-6 code done (bias suite); E0-4 done; E0-5 tests 96 s → 25 s. **R3 not measured yet** (E2-1 needs model keys and credits): first task once keys are in `.env`.

## 4. Cut list (in order) and never-cut list

Cut, in order:
1. E5-9 Android / Shopify
2. E5-5 reels
3. E7-3 student in production (keep E7-2's measured agreement)
4. E4-6 account manager Q&A
5. E8-7 Ads MCP path
6. E2-8 SSR
7. E4-2 Researcher

Never cut:
- E0-1, E0-2;
- E2-1, E2-2, E2-4, E2-5 (validation);
- E3-1, E3-2;
- E8-1, E8-3, E8-4;
- E9-1, E9-3, E9-4;
- P-1 to P-3;
- D-1, D-3, D-5.

## 5. Definition of done for the whole project

- [ ] Every ★ task ticked with its measured value.
- [ ] `uv run whynot reproduce` regenerates every number in the demo, $0, from a clean clone.
- [ ] `TARGETS.md` reviewed line by line; every ❌ is explained on the validation page.
- [ ] The pilot ran ≥ 3 days with 0 cap breaches, every action logged.
- [ ] A stranger used the Arena without help.
- [ ] No secret, partner data or token anywhere in the repo or its history (gitleaks clean).
