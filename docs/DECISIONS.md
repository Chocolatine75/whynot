# Decision log

One line per decision: date — decision — why. Newer lines can supersede older ones; the current direction is the last block.

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
- 2026-10-27 — Positioning = the loop (templates generate, simulator judges, agents evolve), not "a simulator" — a judge alone is a Kantar, a generator alone an AdCreative; Arena starts from a link, not only an uploaded ad.
- 2026-10-27 — **Current direction: whynot = AI ad agency for small businesses on Meta** (research → strategy → concepts → test in the simulated feed → evolve → publish, rotate, report; owner only checks). The simulator is the agency's quality gate, not the pitch — the design partner (~$20k MRR app) asked for a tool that runs the whole campaign without him; the simulator is what makes that autonomy trustworthy and separates us from Meta's assistant.
- 2026-10-27 — Personalise by customer profile (persona), not by person — Meta audiences need hundreds of people and Meta controls delivery.
- 2026-10-27 — Manage creative and rotation only; leave bidding and delivery to Meta (Advantage+) — don't rebuild what Meta does well.
- 2026-10-27 — Autonomy levels dry_run (default) → propose → autopilot, hard spend caps, owner approval before the first live launch — we'd be spending a real client's money.
- 2026-10-27 — Live pilot on the design partner's account replaces the separate "public bet": predictions published before the pilot's results — real business, real proof, one setup.
- 2026-10-27 — All docs in English — public repo, international judges.
- 2026-10-27 — VoodRadar (Voodoo × Anthropic Hack 2026 winner) studied for ideas only; no code, prompts, data or assets reused — hackathon rule (new work only) and the repo has no licence. Ideas taken and our differences in `PRIOR_ART.md`; disclosed in the README.
- 2026-10-27 — Python engine managed with uv, `src/whynot` layout; one `ModelClient` (OpenAI SDK) for both the Meta Model API and Baseten, logging every call to a JSONL cost ledger — both APIs are OpenAI-compatible; one wrapper keeps the cost counter real.

## Data & asset rights

| Asset | Source | Licence / consent | Status |
|---|---|---|---|
| Design partner (mobile app) ad history, creatives, metrics | partner | written consent; `data/private/` only, never committed; anonymised in demo | ☐ |
| Design partner ad account (pilot) | partner | written consent for read access; separate written consent + cap + approval for live actions | ☐ |
| Design partner app screens / footage | partner | written consent | ☐ |
| Shopify partner catalog & images (if confirmed) | partner | written consent | ☐ |
| Competitor ads (copy, creatives, reach) | Meta Ad Library API | Meta terms (public transparency data) | ☐ check terms for capturing creatives and showing them in the Arena / demo |
| Criteo uplift dataset | Criteo AI Lab | CC BY-NC-SA 4.0, cite Diemert et al. 2018 (AdKDD) | not used in the current plan |
| SSR library | pymc-labs/semantic-similarity-rating | open source (repo shows both Apache-2.0 and MIT) | ☐ |
| Human test answers | our form | participant consent line in form | ☐ |
