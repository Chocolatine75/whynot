# Architecture

Principle: **agents decide, code composes, the simulator judges, reality calibrates.** Big models do research, strategy and simulation; deterministic code does assembly; a distilled viewer serves volume; every reliability claim comes from the validation module; every live action goes through caps and the owner's autonomy level.

```
┌──────────── RESEARCH & STRATEGY (onboarding, then weekly) ───────────────────────┐
│ Ad Library ─▶ competitor ads (copy, dates, EU reach) ─▶ creatives captured        │
│               (Muse Spark computer use) ─▶ transcripts (Voice Transcribe)         │
│ Business: store / App Store page, reviews, past ads + metrics, product footage    │
│        ─▶ SAM 3.1 cutouts (image + video)                                         │
│ Muse Wonder (1M ctx, cached) ─▶ strategy ─▶ personas ─▶ ~10 templates             │
└──────────────────────────────────────────────────────────────────────────────────┘
┌──────────── CREATE & TEST (per run) ─────────────────────────────────────────────┐
│ templates ─▶ composer (code; Muse Image scenes) ─▶ guards (pixel diff, policy…)   │
│   ─▶ simulated feed: candidate + N competitor ads ─▶ viewer agents (Spark Open    │
│      teacher / distilled student) ─▶ reactions ─▶ SSR intent, preference, why not │
│   ─▶ counterfactuals (SAM-tracked element removed/swapped, re-test)               │
│   ─▶ creative director mutates genes ─▶ diversity guard ─▶ next generation        │
└──────────────────────────────────────────────────────────────────────────────────┘
┌──────────── RUN, REPORT, LEARN ──────────────────────────────────────────────────┐
│ winners ─▶ autopilot (autonomy level + caps) ─▶ Ads MCP / Marketing API           │
│ daily: metrics ─▶ fatigue / losers paused / winners kept; weekly: new concepts    │
│ weekly report ─▶ owner approves / blocks                                          │
│ real metrics ─▶ calibration per business                                          │
│ validate: backtest · humans · Ad Library longevity · live pilot                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Agent team

| Agent | Does | Model / tools |
|---|---|---|
| Scout | Finds competitors, pulls and captures their ads | Ad Library API, Muse Spark computer use, Voice Transcribe |
| Researcher | Customer truth: reviews, pages, past ads and metrics, objections | Muse Spark |
| Strategist | Strategy and personas over the whole corpus | Muse Wonder |
| Creative director | Writes templates (concepts + genomes), decides mutations | Muse Spark |
| Producer | Builds variants via the composer, asks Muse Image for scenes | code, Muse Image, SAM 3.1 |
| Audience | Viewer agents in the simulated feed | Muse Spark Open (teacher), distilled student |
| Analyst | Reads reactions, runs counterfactuals, explains why | Muse Spark, SAM 3.1 |
| Media buyer | Publishes, monitors, pauses, rotates — within caps | Ads MCP / Marketing API |
| Account manager | Weekly report, approvals, owner questions | Muse Spark |
| Auditor | Guards, spend limits, autonomy rules, validation | code |

An orchestrator runs the agents over a shared, inspectable log (`AgentEvent`). Every action is a tool call with inputs, outputs, guard results and cost. Live actions pass through the Auditor (cap + autonomy level) before reaching Meta.

## Modules

Code layout, rules and definition of done: `ENGINEERING.md`.

| Module | Responsibility | Models / tools |
|---|---|---|
| `costs` | Single model-call wrapper; logs tokens, images, $ | code |
| `agents` | Orchestrator, roles, shared log | Muse Spark |
| `ingest/adlibrary` | Competitor ads, reach breakdowns, start dates; tokens stripped | Graph API v26 |
| `ingest/creatives` | Capture images/videos from snapshot pages; transcripts | Muse Spark computer use, Voice Transcribe |
| `ingest/appstore` | App Store page, reviews (objections), real screenshots, competitor apps | iTunes lookup/RSS/search |
| `ingest/history` | Partner's past ads + real metrics (read-only, private) | Marketing API / Ads MCP |
| `agents/scout` | Search terms, Ad Library collection, competitor filter, market corpus | Muse Spark, Ad Library |
| `agents/strategist` | Personas, objections, angles, claims; every quote verified in its source | Muse Wonder |
| `agents/director` | Templates + copy per angle; numbers only from claims; policy; diversity | Muse Spark |
| `agency/create` | `whynot create`: the pipeline, run folder, resume, budget, report | — |
| `create/templates` | Concepts + genomes (YAML), validation, sampling, one-gene mutation, variant ids | Muse Spark (writes them) |
| `assets/sam` (+ `assets/cutout` next) | SAM 3.1 output parsing; product / app-screen cutouts, element tracks in video | SAM 3.1 |
| `assets/scenes` | Scenes, first frames | Muse Image |
| `create/composer` | Deterministic statics (v0: `static_1080`) and short videos from genes | Pillow, ffmpeg |
| `create/policy` | Rule-based Meta ad-policy checks (v0) | code |
| `assets/brand` | Brand palette from the app icon, legible by construction | Pillow |
| `run/campaign` | Campaign plan (Marketing API shape), validation, launch through the autopilot | — |
| `create/guards` | Exact product-pixel check, palette, WCAG legibility, ad-policy (not yet); all mandatory | code (+ Muse Spark for policy) |
| `sim/personas` | Personas allocated from real reach cells (country × age × gender) | — |
| `sim/feed` | Market feeds (exposure balanced ±1, least-shown first) and candidate feeds; per-viewer order | — |
| `sim/viewer` | Viewer prompt, strict JSON parsing, retry, parallel runs; backend via `VIEWER_BACKEND` | Muse Spark (now), Muse Spark Open (Baseten); student later |
| `sim/scores` | Per-ad scores: preference lift vs chance (primary), intent, stop/understood/believed rates, why-not | — |
| `ssr` | Free-text intent → Likert distribution | embeddings, SSR library |
| `counterfactual` | Element removal/swap + re-test deltas | SAM 3.1, composer, simfeed |
| `evolve` | Mutations, selection, diversity guard | Muse Spark, embeddings |
| `run/autopilot` | Autonomy levels, caps, fatigue/loser rules, action log; publishing and rotation next | Ads MCP / Marketing API |
| `report` | Weekly report, approvals | Muse Spark |
| `calibrate` | Per-business re-weighting from real metrics | code |
| `validate` | Stats (`stats.py`), longevity R3 (`longevity.py`); backtest, humans, live pilot next | code |
| `web` | Onboarding, Agency room, Report, Arena, Validation page | Next.js |

## Data contracts (sketch)

- `Business {id, kind: app|store, links[], autonomy_level, spend_cap, account_ref (private)}`
- `CompetitorAd {id, page_name, bodies[], titles[], start_date, last_seen, reach_total, reach_breakdown[], creative_paths[], transcript, snapshot_url_clean}`
- `Persona {id, age_band, gender, country, segment, objections[], source_refs[]}`
- `Template {id, concept, persona_id, objection, evidence{}, fixed{}, genes{}, guards[]}`
- `Variant {id, template_id, genome{}, asset_path, guard_results{}, generation}`
- `Feed {id, market, slots[ad_ref], candidate_slot}`
- `Reaction {variant_id, feed_id, persona_id, viewer_model, hook_noticed, understood, believed, objection_text, intent_text, intent_pmf[5], preferred_ad_id}`
- `Counterfactual {variant_id, element, operation, delta{metric: value}}` — always labelled simulated
- `LiveAction {ts, business_id, kind: publish|pause|rotate|budget, ad_ref, reason, autonomy_level, approved_by, spend_after}`
- `RealMetrics {ad_ref, business (anonymised), impressions, hook_rate, p25..p95, ctr, cpa, period}`
- `ValidationResult {kind: backtest|humans|longevity|pilot, n, metric, value, ci, baseline}`
- `AgentEvent {ts, agent, tool, input_refs, output_ref, guards, cost_usd}`
- `CostEvent {ts, module, model, input_tokens, output_tokens, images, usd}`

## Cost design

- Research/strategy: Wonder reads a cached corpus (cached input 20× cheaper). Muse Image $0.01/image. SAM 3.1 $2.50/1k images.
- Test: analyse each creative **once** (frames + transcript), then viewer reactions per persona on that analysis plus key frames. Volume on the distilled student; the teacher audits a sample.
- Evolve: composition is code; only new scenes cost Muse Image calls.
- Run: metric pulls and rules are code; the report is one Muse Spark call per week.
- Every call logged in `costs`; the cost counter is real.

## Open questions

- Muse Spark Open on Baseten: image/video input via chat completions? Tokens per frame? → smoke test when credits arrive.
- SSR needs an embedding model; the Meta API lists none. Options: an open-source embedding model run locally, or Muse Spark Open embeddings if the host offers them. Until then viewers give a 1–5 intent score plus free text (kept for SSR).
- SAM 3.1 video tracking output and mask → frame mapping → test on real footage.
- Ad Library creative capture reliability with computer use.
- Partner account: which metrics per ad, how many past ads, Ads MCP vs Marketing API access, write permissions.
- Fatigue and pause rules (thresholds on frequency, CTR trend, CPA) → set with the partner.
- Distillation path: Muse Glimmer size and serving; fine-tuning Spark Open on Fireworks/Modal (workshop Oct 30).
