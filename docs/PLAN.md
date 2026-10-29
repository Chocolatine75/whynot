# Plan

Two people. **A** = engine: research, simulator, validation, ML. **B** = agency product: creation pipeline, autopilot, Meta integration, UI, demo. Swap freely; update owners here.

Deadline: **Wed Nov 4, 9:00 PM ET = Thu Nov 5, 03:00 Paris.** Submit Wed Nov 4 evening Paris time, never at the last hour.

The bar is `TARGETS.md`. Each milestone ends with a gate. **The kill test (M1) decides whether we keep the idea.** The live pilot needs ads running by ~Oct 31 to have results before the deadline.

## M0 — Foundations + partner (Tue Oct 27 – Wed Oct 28)
- [ ] (B) **Design partner (mobile app, ~$20k MRR):** written consent; export of past ads (creatives) + real metrics per ad (hook rate / video thresholds, CTR, CPA); read-only account access. Agree the pilot: spend cap, autonomy level, which decisions he approves, start date. Data in `data/private/`, never committed. *Critical path for R1 and R4.*
- [ ] (B) Contact 5–10 more businesses/agencies (backtest data, Arena users); confirm the Shopify partner
- [ ] (both) Claim Meta credits + spend limit, Baseten, Modal
- [x] (A) `costs` wrapper + `ModelClient` + unit tests (`src/whynot/costs.py`, `models.py`)
- [x] (A) Smoke tests on the Meta API: all models pass; findings in `META_APIS.md` (reasoning tokens, inline images, SAM mask geometry)
- [ ] (A) Smoke tests on Baseten (Muse Spark Open) once credits arrive; add a video input check
- [x] (A) Ad Library ingest code: search by page ids/terms, cursor pagination, tokens stripped, reach breakdown, longevity (`ingest/adlibrary.py`, `scripts/fetch_competitors.py`, tested on fake responses)
- [x] (A) Real calls work with `FB_TOKEN`; breakdown format confirmed; long-running filter added (`--active ACTIVE --started-before-days 60`)
- [ ] (A) Run it on the partner's competitors (need their page ids)
- [ ] (B) SAM mask decoder (base85 `~`) + mapping into the box, checked on a known shape
- [ ] (A) Creative capture from snapshot pages (Muse Spark computer use)
- [x] (A) Validation statistics for R1–R3, R6: pairwise accuracy, AUC, bootstrap CIs, Wilson, binomial test (`validate/stats.py`)
- [ ] (B) First build-in-public post

**Gate:** partner data in hand (or a firm date); pilot terms agreed; viewers can see an image and a video.

## M1 — Kill test (Thu Oct 29)
- [x] (A) Viewer v0: personas from real reach, market/candidate feeds, viewer agent with strict JSON + retry, per-ad scores (`sim/`); runs on Muse Spark via `VIEWER_BACKEND=meta` until Baseten. Text-only feeds; intent as 1–5 (SSR later)
- [x] (A) Longevity pipeline (`validate/longevity.py`, `scripts/longevity_check.py`): tiny real run on Lacoste (10 ads, 0 failures, $0.10) — too small to conclude
- [ ] (A) R3 v0 at scale: ≥ 20 ads per class across several advertisers of the partner's market; compare reasoning effort low vs minimal
- [ ] (A) Backtest v0 on the partner's history: pairwise accuracy vs real metric, with baselines
- [ ] (both) 10 people × 6 pairs: quick human agreement check

**Gate (decide Oct 29 evening):** if ≥ 2 of {backtest beats baselines, longevity AUC > 0.55, human agreement > 60 %, someone new to the project finds the demo impressive} fail → change idea now. Otherwise go.

## M2 — Vertical slice + pilot launch (Fri Oct 30 – Sat Oct 31)
research → templates → composer (static + 6 s video) → guards → simulated feed → why not → one evolution step → publish (dry-run, then live with approval) → agent log + cost.
- [x] (B) Template schema + validation, genome sampling/mutation, deterministic variant ids (`templates.py`); 1 example template (`templates/examples/`)
- [x] (B) Composer v0 (`static_1080`, Pillow) + guards: exact product-pixel check, WCAG contrast, palette, missing glyphs (`composer.py`, `guards.py`)
- [ ] (B) 2 more hand-written templates; SAM cutout as the product asset; reels (ffmpeg); policy guard (model)
- [ ] (A) Simulated feed aggregated per persona; personas from reach breakdowns
- [x] (B) Evolver: one-element mutations from simulated objections, generations with placebo-checked re-tests, lineage in the report
- [x] (B) Autopilot rules v0: autonomy levels, daily cap, first-live approval, guard gate, loser/fatigue review, action log (`autopilot.py`, no Meta calls)
- [x] (A+B) `whynot create`: App Store ingest, Scout, Strategist (verified quotes), Creative director (verified copy), brand palette, policy guard v0, campaign plan (Marketing API shape), report; end-to-end, adversarial, contract and live tests
- [ ] (B) `whynot daily`: real metrics → pause/scale/rotate → new variants → simulate → publish within caps → daily report
- [x] (B) Publishing via the Marketing API: `whynot publish` + Approve panel, sandbox first, autopilot-gated, resumable (tested on a fake Graph API)
- [ ] (B) First real sandbox publish (needs sandbox account + token + page id)
- [ ] (both) **Pilot:** publish the predicted ranking (timestamped), then launch the first live ads on the partner's account with his explicit approval
- [ ] (both) Launch the blind human test (R2, R6) — collection runs until Nov 3
- [ ] (A) Fireworks workshop (Oct 30): distillation / fine-tuning path

**Gate:** the loop runs end to end with no manual step; first live ads running within caps; R8 holds.

## M3 — Depth (Sun Nov 1 – Mon Nov 2)
- [ ] (A) Strategy (Wonder) → templates generated with evidence
- [ ] (A) Counterfactuals with SAM-tracked elements (image + video)
- [ ] (A) Student viewer distilled; agreement + cost measured (R10)
- [ ] (A) R1, R3 final with CIs
- [ ] (B) Evolution loop multi-generation + diversity guard (R7)
- [ ] (B) Autopilot daily loop: metrics, fatigue/loser rules, rotation; weekly report with approve/block
- [x] (B) Client platform v0 (`web/`): start a campaign, live agency room, results
- [ ] (B) **Arena public** (R11), shared with businesses (R12)

**Gate:** a stranger runs the Arena on their own link without help; R1–R3 measured; pilot running with daily logs.

## M4 — Ship (Tue Nov 3 – Wed Nov 4)
- [ ] R2, R6 analysed; pilot results (R4, R5) published, whatever they are
- [ ] Validation page; go through `TARGETS.md` line by line
- [ ] One command reproduces every number
- [ ] README final, architecture diagram, what-was-built list
- [ ] Record the 3-min video (see `DEMO.md`) + 30 s cut for X
- [ ] Submit on Cerebral Valley (repo public, video public, both members listed); flag open weights
- [ ] Post on X

## Cut list if late (in order)
1. Calibration on real metrics (keep the design, show one example)
2. Weekly concept refresh (show one cycle)
3. Video counterfactuals (keep image counterfactuals)
4. Student viewer fine-tune (keep a prompt-distilled smaller model)
5. Live pilot (fall back to dry-run on the partner's account + sandbox publishing)

Never cut: the validation (R1–R3), the simulated feed with real competitor ads, the create → test → evolve loop, publishing (at least sandbox), the agent log, the cost counter, the Arena.
