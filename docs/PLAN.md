# Plan

Two people. **A** = engine: research, simulator, validation, ML. **B** = agency product: creation pipeline, autopilot, Meta integration, UI, demo. Swap freely; update owners here.

Deadline: **Wed Nov 4, 9:00 PM ET = Thu Nov 5, 03:00 Paris.** Submit Wed Nov 4 evening Paris time, never at the last hour.

The bar is `TARGETS.md`. Each milestone ends with a gate. **The kill test (M1) decides whether we keep the idea.** The live pilot needs ads running by ~Oct 31 to have results before the deadline.

## M0 — Foundations + partner (Tue Oct 27 – Wed Oct 28)
- [ ] (B) **Design partner (mobile app, ~$20k MRR):** written consent; export of past ads (creatives) + real metrics per ad (hook rate / video thresholds, CTR, CPA); read-only account access. Agree the pilot: spend cap, autonomy level, which decisions he approves, start date. Data in `data/private/`, never committed. *Critical path for R1 and R4.*
- [ ] (B) Contact 5–10 more businesses/agencies (backtest data, Arena users); confirm the Shopify partner
- [ ] (both) Claim Meta credits + spend limit, Baseten, Modal
- [ ] (A) `costs` wrapper + smoke tests (incl. Muse Spark Open with image/video input on Baseten)
- [ ] (A) Ad Library ingest for the partner's market (tokens stripped) + creative capture
- [ ] (B) First build-in-public post

**Gate:** partner data in hand (or a firm date); pilot terms agreed; viewers can see an image and a video.

## M1 — Kill test (Thu Oct 29)
- [ ] (A) Viewer v0 (teacher, structured reactions + SSR) on a feed of competitor ads
- [ ] (A) Backtest v0 on the partner's history: pairwise accuracy vs real metric, with baselines
- [ ] (A) Longevity check v0 on ~40 Ad Library ads
- [ ] (both) 10 people × 6 pairs: quick human agreement check

**Gate (decide Oct 29 evening):** if ≥ 2 of {backtest beats baselines, longevity AUC > 0.55, human agreement > 60 %, someone new to the project finds the demo impressive} fail → change idea now. Otherwise go.

## M2 — Vertical slice + pilot launch (Fri Oct 30 – Sat Oct 31)
research → templates → composer (static + 6 s video) → guards → simulated feed → why not → one evolution step → publish (dry-run, then live with approval) → agent log + cost.
- [ ] (B) Templates v0 (3 hand-written), composer, SAM cutout, pixel guard
- [ ] (A) Simulated feed aggregated per persona; personas from reach breakdowns
- [ ] (B) Creative director: mutations from objections
- [ ] (B) Autopilot v0: autonomy levels, caps, publish via Ads MCP / Marketing API (sandbox first)
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
