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

## Data & asset rights

| Asset | Source | Licence / consent | Status |
|---|---|---|---|
| Partner store catalog & images | partner | written consent | ☐ |
| Competitor ads | Meta Ad Library API | Meta terms (public transparency data) | ☐ check terms for display in demo |
| Criteo uplift dataset | Criteo AI Lab | CC BY-NC-SA 4.0: OK for a non-commercial evaluation, cite Diemert et al. 2018 (AdKDD); not for the commercial product | ☐ confirm hackathon use counts as non-commercial |
| SSR library | pymc-labs/semantic-similarity-rating | open source (repo shows both Apache-2.0 and MIT) | ☐ |
| Browsing sessions dataset | TBD | TBD | ☐ |
| Human test answers | our form | participant consent line in form | ☐ |
