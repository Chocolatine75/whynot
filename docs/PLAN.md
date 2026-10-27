# Plan

Two people. **A** = simulator / ML / validation. **B** = product / agents / composer / UI / demo. Swap freely; update owners here.

Deadline: **Wed Nov 4, 9:00 PM ET = Thu Nov 5, 03:00 Paris.** Submit Wed Nov 4 evening Paris time, never at the last hour.

The bar is `TARGETS.md`. Each milestone ends with a gate. **The kill test (M1) decides whether we keep the idea.**

## M0 — Foundations + partner data (Oct 27–28)
- [ ] (both) Claim Meta credits + spend limit, Baseten, Modal
- [ ] (B) **Design partner (mobile app, ~$20k MRR):** written consent; export of past ads (creatives) + real metrics per ad (hook rate / video thresholds, CTR, CPA); read-only access if possible. Stored in `data/private/`, never committed. *Critical path for R1.*
- [ ] (B) Contact 5–10 more brands/agencies for backtest data; confirm the Shopify partner
- [ ] (A) `costs` wrapper + smoke tests (incl. Muse Spark Open with image/video input on Baseten)
- [ ] (A) Ad Library ingest for the partner's market (tokens stripped) + creative capture
- [ ] (both) Decide the capped budget for the public prediction (R4) — or decide not to
- [ ] (B) First "building in public" post

**Gate:** partner data in hand (or a date for it); viewers can see an image and a video.

## M1 — Kill test (Oct 29)
- [ ] (A) Viewer v0 (teacher, structured reactions + SSR) on a feed of competitor ads
- [ ] (A) Backtest v0 on the partner's history: pairwise accuracy vs real metric, with baselines
- [ ] (A) Longevity check v0 on ~40 Ad Library ads
- [ ] (both) 10 people × 6 pairs: quick human agreement check

**Gate (decide Oct 29 evening):** if ≥ 2 of {backtest > baselines, longevity AUC > 0.55, human agreement > 60 %, a cold viewer finds the demo impressive} fail → change idea now. Otherwise go.

## M2 — Vertical slice (Oct 30–31)
template → composer (static + 6 s video) → guards → SimFeed → why not → one evolution step → UI with agent log + cost.
- [ ] (B) Templates v0 (3 hand-written), composer, SAM cutout, pixel guard
- [ ] (A) SimFeed aggregation per persona; personas from reach breakdowns
- [ ] (B) Creative director agent: mutation from objections
- [ ] (both) Launch the blind human test (R2, R5) — collection runs until Nov 3
- [ ] (B) If R4 approved: launch 8–12 variants, publish the predicted ranking (timestamped)
- [ ] (A) Fireworks workshop (Oct 30): distillation / fine-tuning path

**Gate:** two-ads-in-a-feed hook runs live end to end; R7 holds.

## M3 — Depth (Nov 1–2)
- [ ] (A) Strategy brief (Wonder) → templates generated, with evidence
- [ ] (A) Counterfactuals with SAM-tracked elements (image + video)
- [ ] (A) Student viewer distilled; agreement + cost measured (R8)
- [ ] (A) R1, R3 final with CIs
- [ ] (B) Evolution loop multi-generation + diversity guard (R6)
- [ ] (B) Launch via Ads MCP / Marketing API, sandbox default, caps
- [ ] (B) **Arena public** (R9), shared with advertisers (R10)

**Gate:** a stranger runs the Arena on their own ad without help; R1–R3 measured.

## M4 — Ship (Nov 3–4)
- [ ] R2, R5 analysed; R4 results published
- [ ] Validation page; go through `TARGETS.md` line by line
- [ ] One command reproduces every number
- [ ] README final, architecture diagram, what-was-built list
- [ ] Record the 3-min video (see `DEMO.md`) + 30 s cut for X
- [ ] Submit on Cerebral Valley (repo public, video public, both members listed); flag open weights
- [ ] Post on X

## Cut list if late (in order)
1. Calibration loop on real metrics (keep the design, show one example)
2. Live launch (fall back to export; R4 only if already running)
3. Weekly concept drop
4. Video counterfactuals (keep image counterfactuals)
5. Student viewer fine-tune (keep prompt-distilled smaller model)

Never cut: the validation (R1–R3), the feed simulation with real competitor ads, why not + one evolution step, the Arena, the agent log, the cost counter.
