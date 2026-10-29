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
- 2026-10-28 — Viewers run on Muse Spark via the Meta API until Baseten credits arrive (`VIEWER_BACKEND`), never on the Contributor tier — don't block on inference credits; feeds can contain partner ads.
- 2026-10-28 — R3 design fixed before results: long = still active ≥ 60 days, short = stopped ≤ 14 days; one ad per (advertiser, copy); classes balanced across advertisers; primary metric = AUC of preference lift, intent secondary, copy length as baseline — avoid choosing the metric after seeing the data.
- 2026-10-28 — Viewer reasoning effort defaults to `low` in experiments (≈2× cheaper than default, `minimal` ≈4×); quality per effort to be compared on R3 — reasoning tokens are ~85 % of viewer cost.
- 2026-10-28 — Build the generic product first, specialise for the design partner after. Partner = VietBuddy (Vietnamese-learning iOS app) advertising mainly in the US; the Ad Library API only exposes EU/UK commercial ads, so competitor research and the R3 test use EU/UK ads, and the partner's own US history comes from his ad account (with consent).
- 2026-10-28 — Pillow + PyYAML for templates and the composer: deterministic, no model in the composition path.
- 2026-10-28 — Pixel guard = exact equality of every fully opaque product pixel with the asset after the composer's single declared resize (LANCZOS). The resize is the only allowed transform; anything drawn over or generated fails.
- 2026-10-28 — A guard that wasn't run (e.g. policy, which needs a model) counts as not passed: an ad is publishable only if every guard of its template passed.
- 2026-10-28 — Autopilot rules: the cap applies to the sum of daily budgets of running ads; lowering spend (pause, budget cut) is always allowed; the first live publish needs the owner's approval even in autopilot; losers = CPA > 2× account median after €20 spent; fatigue = CTR down ≥30 % between the first and last 3 days. Thresholds are defaults, to tune with the partner.
- 2026-10-28 — Quality bar: ruff + mypy + pytest with branch coverage ≥ 90 % in one command (`scripts/check.sh`) and in CI on every push/PR; Hypothesis property tests for invariants; one regression test per bug. Rules in `ENGINEERING.md`.
- 2026-10-28 — Package split along the loop: `create/` (templates, composer, guards), `assets/` (SAM), `run/` (autopilot), next to `ingest/`, `sim/`, `validate/`.
- 2026-10-28 — Market feeds now take the least-shown ads first: exposure differs by at most one between ads (the old round-robin with random top-ups gave 7 vs 4 views on small sets, found by a property test).
- 2026-10-28 — All guards are mandatory whatever the template lists; a template with `guards: []` was publishable before.
- 2026-10-28 — Transcription cost rounds up to the second (billing granularity undocumented; never under-count).
- 2026-10-28 — Ad Library calls retry with exponential backoff on network errors, 5xx and rate-limit codes (2, 4, 17, 341, 613); never on token errors.
- 2026-10-28 — The product's entry point is `whynot create <app>`: research → strategy → ads → simulation → campaign plan → report. The simulator is one stage (quality gate), not the product; a daily loop (`whynot daily`) comes next.
- 2026-10-28 — Every agent answer is validated by code and repaired with the exact error (max 2 repairs), never guessed. Strategy quotes must appear verbatim in the cited review, ad or store page; ads may only state numbers found in verified claims; competitor names are banned from copy.
- 2026-10-28 — Research countries are EU/UK (Ad Library limit) even when the campaign targets elsewhere (e.g. the US partner): the EU/UK market is the proxy.
- 2026-10-28 — Campaign plan: one ad set per persona, budget split evenly under the cap (simulated scores rank ads but don't move money before real results), €5/day minimum per ad set, 2–6 ads per set, ≤ 2 variants per template, everything PAUSED, launch through the autopilot.
- 2026-10-28 — Brand palette from the app icon; the accent is darkened/lightened (same hue) until button text reaches 4.6:1 — a red icon made every ad fail the legibility guard (found by the end-to-end test).
- 2026-10-28 — Viewers compare text with text (our copy + image text vs competitors' copy) until competitor creatives are captured, so the comparison stays fair.
- 2026-10-28 — Policy guard v0 is rule-based (personal attributes, absolute claims, engagement bait, shouting); model-based review planned.
- 2026-10-29 — Baseten model string is `meta-models/muse-spark-open-1026` (the hackathon guide's name): with our key `meta-models/muse-spark-open` returns 403. Default updated in config and `.env.example`.
- 2026-10-29 — `create` tested on 3 real apps in 3 categories (VietBuddy/language, Finch/wellbeing, Flighty/travel): all complete; it is generic for iOS apps. Not covered yet: Android, Shopify/web stores.
- 2026-10-29 — One set of ads per language (create/locale.py): each ad set targets only the countries of its language. Found on Flighty: France would have received English ads.
- 2026-10-29 — Ads are drawn with a font covering every Latin language (create/fonts.py: WHYNOT_FONT → assets/fonts → Arial/DejaVu); Pillow's default font can't draw "é", which pushed the model to strip accents. Director refuses accented-language copy with no accent at all (the model drops them intermittently).
- 2026-10-29 — Ad set names are neutral ("Profile 1 · US · 18-34"): persona labels can contain sensitive words ("ADHD", seen on Finch) and names live in the ad account.
- 2026-10-29 — Strategist gets 3 repairs (2 of 3 real runs needed all 3 attempts); every refused attempt's errors are saved in the run (`strategy.raw.json`, `creative.json`).
- 2026-10-29 — `--redo-from <stage>` recomputes a stage and the later ones, reusing earlier results (no re-billing).
- 2026-10-29 — Simulator bias diagnosed with placebos (`scripts/sim_bias_check.py`, VietBuddy): the same competitor ads scored 0.50× under their own page name and 3.50× under "VietBuddy: Learn Vietnamese". The advertiser name drove preference; removing objections from viewer traits changed nothing; purchase intent still separated our ads from placebos.
- 2026-10-29 — Fair feeds (`sim/arena.py`): ads shown under the page-style brand name; every feed has two candidate slots (our variants or placebos = real competitor ads dressed as ours) plus competitors, so name bias cancels head-to-head; ranking metric = lift minus placebo lift (a ratio blew up when placebos never won). An audience is flagged biased when placebo lift > 1.5× (midpoint between fair 1.0 and fully name-driven feed_size/2). Defaults 3 placebos × 3 appearances: on a scripted test world, 27/30 biased audiences caught, 1/30 false alarm (2 appearances: 23/30, 2/30).
- 2026-10-29 — Viewers get who they are and what they want, never the objections the ads answer (objections are measured, not injected).

## Data & asset rights

| Asset | Source | Licence / consent | Status |
|---|---|---|---|
| Design partner (mobile app) ad history, creatives, metrics | partner | written consent; `data/private/` only, never committed; anonymised in demo | ☐ |
| Design partner ad account (pilot) | partner | written consent for read access; separate written consent + cap + approval for live actions | ☐ |
| Design partner app screens / footage | partner | written consent | ☐ |
| Shopify partner catalog & images (if confirmed) | partner | written consent | ☐ |
| App Store pages, reviews, screenshots | Apple public endpoints | the owner's own app for the owner's own campaign; competitor apps: metadata only; reviewer names dropped; test fixtures from a large public app (Duolingo), trimmed | ☐ check Apple terms for screenshots in ads (owner's own assets) |
| Competitor ads (copy, creatives, reach) | Meta Ad Library API | Meta terms (public transparency data) | ☐ check terms for capturing creatives and showing them in the Arena / demo |
| Criteo uplift dataset | Criteo AI Lab | CC BY-NC-SA 4.0, cite Diemert et al. 2018 (AdKDD) | not used in the current plan |
| SSR library | pymc-labs/semantic-similarity-rating | open source (repo shows both Apache-2.0 and MIT) | ☐ |
| Human test answers | our form | participant consent line in form | ☐ |
