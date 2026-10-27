# Decision log

One line per decision: date — decision — why.

- 2026-10-24 — Target Shopify merchants; ads delivered on Meta via Marketing API — native fit with a Meta hackathon, Shopify gives catalog + behaviour data.
- 2026-10-24 — Indie Developer track, theme Build for Your World — two students; e-commerce growth is a problem we can show firsthand.
- 2026-10-24 — Personalise on the visitor's objection, not their profile — the gap left by Advantage+, Criteo and creative tools.
- 2026-10-24 — Optimise for sales caused (uplift + holdout), not attributed conversions — the real waste in retargeting.
- 2026-10-24 — Prove value without ad spend: blind human test, panel-vs-human validation, partner store on-site/email A/B, Criteo uplift data.
- 2026-10-27 — Synthetic panel on Muse Spark Open via Baseten — saves Meta API credits, qualifies for the open-weights bonus prize.
- 2026-10-27 — Product pixels are never generated: SAM 3.1 cutout composited, pixel-diff guard.
- 2026-10-27 — Repo name `whynot`.
- 2026-10-27 — Docs checked against official Meta docs; Baseten model string read from env (`meta-models/muse-spark-open` vs guide's `-1026`) — official sources disagree with the hackathon guide.

- 2026-10-27 — Added `TARGETS.md` as the bar (final product, R1–R10, per-criterion checklist) — loop on it instead of on features.
- 2026-10-27 — Plan reorganised into gated milestones, vertical slice by Oct 30 — avoid layers that never connect.
- 2026-10-27 — Criteo uplift demoted to optional side check; main proofs = exit-question ground truth, human test, panel vs humans, panel vs Ad Library longevity — Criteo is unrelated data and costly to integrate.
- 2026-10-27 — Add a public teardown (any Shopify URL) — impact, viral and community vote need something people can try.
- 2026-10-27 — **Pivot: whynot = flight simulator for Meta ads** (simulated feed with real competitor ads, viewer agents, why not, evolving concept templates, measured reliability) — objection retargeting was a "Criteo bis", the agency idea overlaps Meta's business AI assistant; pre-spend, explained, validated creative judgement is what Meta can't do alone.
- 2026-10-27 — Simulate cognitive reactions only (understood, believed, objection, intent, preference); never claim scroll/retention prediction — LLMs can't credibly predict sub-second perceptual behaviour; SSR validates intent.
- 2026-10-27 — Validation is the technical hero (backtest on partner history, humans, Ad Library longevity, public pre-registered prediction) — without it the simulator is a toy.
- 2026-10-27 — Target Meta advertisers who make their own creative: mobile apps and DTC/Shopify brands, not Shopify only — first design partner is a mobile app (~$20k MRR) with ad history.
- 2026-10-27 — Templates = concepts with a mutable genome, not slot-filled images — Andromeda groups near-duplicates.
- 2026-10-27 — Teacher viewer on Muse Spark Open, distilled student on open weights — volume cost + Best Open Weights prize.
- 2026-10-27 — Superseded: per-visitor objection retargeting, uplift targeting and Criteo as product pillars (objections survive as personas and concept axes).

## Data & asset rights

| Asset | Source | Licence / consent | Status |
|---|---|---|---|
| Design partner (mobile app) ad history, creatives, metrics | partner | written consent; `data/private/` only, never committed; anonymised in demo | ☐ |
| Design partner app screens / footage | partner | written consent | ☐ |
| Partner store catalog & images | partner | written consent | ☐ |
| Competitor ads (copy, creatives, reach) | Meta Ad Library API | Meta terms (public transparency data) | ☐ check terms for capturing creatives and showing them in the Arena / demo |
| Criteo uplift dataset | Criteo AI Lab | CC BY-NC-SA 4.0: OK for a non-commercial evaluation, cite Diemert et al. 2018 (AdKDD); not for the commercial product | ☐ confirm hackathon use counts as non-commercial |
| SSR library | pymc-labs/semantic-similarity-rating | open source (repo shows both Apache-2.0 and MIT) | ☐ |
| Browsing sessions dataset | TBD | TBD | ☐ |
| Human test answers | our form | participant consent line in form | ☐ |
