# 10-day plan

Two people. **A** = pipeline / ML / data. **B** = product / integrations / UI / demo. Swap freely; update owners here.

Deadline: **Wed Nov 4, 9:00 PM ET = Thu Nov 5, 03:00 Paris.** Aim to submit Wed Nov 4 evening Paris time, never at the last hour.

## Day 1–2 (Oct 27–28): foundations
- [ ] (both) Claim Meta credits, Baseten, Modal; spend limits set
- [ ] (B) Repo, CI, `.env`, `costs` wrapper around every model call
- [ ] (A) Smoke tests: Muse Spark, Muse Wonder, Muse Image, SAM 3.1, Muse Spark Open on Baseten. Record real model IDs and pricing in `docs/META_APIS.md`
- [ ] (A) Ad Library ingest: competitor list → ads + reach breakdowns, tokens stripped
- [ ] (B) Partner store: confirm consent in writing, export catalog, pages, reviews, product media
- [ ] (B) Sessions source: partner traffic and/or public e-commerce events dataset (licence checked)

## Day 3–4 (Oct 29–30): understanding
- [ ] (A) Snapshot reading (visual descriptions of competitor ads)
- [ ] (A) Strategy brief with Muse Wonder (cached corpus)
- [ ] (A) Objection labelling on a session sample, then distilled classifier + eval
- [ ] (B) SAM 3.1 product cutouts; Muse Image scene assets
- [ ] (B) Template spec format + generation of ~10 templates from the brief

## Day 5–6 (Oct 31–Nov 1): generation & proof
- [ ] (B) Deterministic composer + guards (product pixel diff = 0, palette, legibility)
- [ ] (A) Synthetic panel with SSR on Muse Spark Open; score all variants
- [ ] (A) Uplift model on Criteo data: uplift curve vs response model
- [ ] (both) **Launch the blind human test** (form + links), collect over the weekend

## Day 7–8 (Nov 2–3): autonomy
- [ ] (B) Marketing API: sandbox account, campaign/audience/ad creation, budget caps, dry-run default
- [ ] (A) Learner loop on simulated performance (labelled as simulated), fatigue detection, refresh
- [ ] (A) Holdout lift report + store-fix recommendations
- [ ] (B) Merchant dashboard: onboarding, objections map, templates, variants + panel scores, launch, cost counter
- [ ] (both) Analyse human test; validate panel vs humans

## Day 9 (Nov 3): polish
- [ ] End-to-end run on partner store, no manual steps
- [ ] README final, architecture diagram, what-was-built list
- [ ] Record 3-minute video (see DEMO.md)

## Day 10 (Nov 4): ship
- [ ] Submit on Cerebral Valley (repo public, video public, both members listed)
- [ ] Post on X, submit link for Most Viral
- [ ] Flag for Best Open Weight Model build

## Cut list if late (in order)
1. Learner loop on simulated performance
2. Snapshot reading via computer use (fall back to text-only ads)
3. Live Marketing API launch (fall back to export of ready-to-upload campaigns)
Never cut: objection inference, templates + composer + guards, panel, cost counter, human test result.
