# Architecture

Principle: **agents decide, code composes, the simulator judges, reality calibrates.** Big models do understanding, strategy and simulation; deterministic code does assembly; a distilled viewer serves volume; every claim of reliability comes from the validation module.

```
┌───────────── UNDERSTAND (once per account, then weekly) ─────────────────────────┐
│ Ad Library ─▶ competitor ads (copy, dates, EU reach) ─▶ creatives captured        │
│               (Muse Spark computer use) ─▶ video transcripts (Voice Transcribe)   │
│ Brand: store / App Store page, reviews, behaviour, product footage, past ads      │
│        ─▶ SAM 3.1 cutouts (image + video)                                         │
│ Muse Wonder (1M ctx, cached) ─▶ strategy brief ─▶ personas ─▶ ~10 templates       │
└──────────────────────────────────────────────────────────────────────────────────┘
┌───────────── EVOLVE (per run) ───────────────────────────────────────────────────┐
│ templates ─▶ composer (code; Muse Image scenes) ─▶ guards (pixel diff, policy…)   │
│   ─▶ SimFeed: candidate + N competitor ads ─▶ viewer agents (Spark Open teacher / │
│      distilled student) ─▶ reactions ─▶ SSR intent + preference + objections      │
│   ─▶ counterfactuals (SAM-tracked element removed/swapped, re-sim)                │
│   ─▶ creative agents mutate genes ─▶ diversity guard ─▶ next generation           │
└──────────────────────────────────────────────────────────────────────────────────┘
┌───────────── LAUNCH, CALIBRATE, VALIDATE ────────────────────────────────────────┐
│ winners ─▶ Ads MCP / Marketing API (sandbox default, hard cap) ─▶ real metrics    │
│ real metrics ─▶ calibration per account                                           │
│ validate: backtest (partner history) · humans · Ad Library longevity · public bet │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Agent roles

| Agent | Does | Model / tools |
|---|---|---|
| Scout | Finds competitors, pulls and captures their ads | Ad Library API, Muse Spark computer use, Voice Transcribe |
| Researcher | Customer truth: reviews, behaviour, objections | Muse Spark |
| Strategist | Strategy brief over the whole corpus | Muse Wonder |
| Creative director | Writes templates (concepts + genomes), decides mutations | Muse Spark |
| Producer | Builds variants via the composer, asks Muse Image for scenes | code, Muse Image, SAM 3.1 |
| Audience | Viewer agents in the simulated feed | Muse Spark Open (teacher), distilled student |
| Analyst | Reads reactions, runs counterfactuals, reports why | Muse Spark, SAM 3.1 |
| Media buyer | Launch within caps, pull metrics | Ads MCP / Marketing API |
| Auditor | Guards, validation, cost and spend limits | code |

An orchestrator runs the agents with a shared, inspectable log (`AgentEvent`). Every agent action is a tool call with inputs, outputs, guard results and cost.

## Modules

| Module | Responsibility | Models / tools |
|---|---|---|
| `costs` | Single model-call wrapper; logs tokens, images, $ | code |
| `ingest/adlibrary` | Competitor ads, reach breakdowns, start dates; tokens stripped | Graph API v26 |
| `ingest/creatives` | Capture images/videos from snapshot pages; transcripts | Muse Spark computer use, Voice Transcribe |
| `ingest/brand` | Store/App Store page, reviews, product footage | — |
| `ingest/history` | Partner ad history + real metrics (read-only, private) | Marketing API / Ads MCP |
| `brief` | Strategy brief | Muse Wonder (prompt caching) |
| `personas` | Personas from reach breakdowns × segments × objections | Muse Spark |
| `templates` | Concepts + genomes (YAML) | Muse Spark |
| `assets/cutout` | Product / app-screen cutouts, element tracks in video | SAM 3.1 |
| `assets/scenes` | Scenes, first frames | Muse Image |
| `composer` | Deterministic statics and short videos from genes | Pillow, ffmpeg |
| `guards` | Pixel diff, palette, legibility, ad-policy checks | code (+ Muse Spark for policy) |
| `simfeed` | Assemble feeds; run viewers; aggregate | — |
| `viewers` | Teacher viewer prompts + structured output; student model | Muse Spark Open (Baseten); Glimmer / fine-tune |
| `ssr` | Free-text intent → Likert distribution | embeddings, SSR library |
| `counterfactual` | Element removal/swap + re-sim deltas | SAM 3.1, composer, simfeed |
| `evolve` | Mutation proposals, selection, diversity guard | Muse Spark, embeddings |
| `validate` | Backtest, humans, longevity, public predictions | code |
| `launch` | Campaigns/ads, caps, dry-run default | Ads MCP / Marketing API |
| `calibrate` | Per-account re-weighting from real metrics | code |
| `web` | Arena, Workspace, Validation page, agent log, cost counter | Next.js |

## Data contracts (sketch)

- `CompetitorAd {id, page_name, bodies[], titles[], start_date, last_seen, reach_total, reach_breakdown[], creative_paths[], transcript, snapshot_url_clean}`
- `Persona {id, age_band, gender, country, segment, objections[], source_refs[]}`
- `Template {id, concept, objection, evidence{}, fixed{}, genes{}, guards[]}`
- `Variant {id, template_id, genome{}, asset_path, guard_results{}, generation}`
- `Feed {id, market, slots[ad_ref], candidate_slot}`
- `Reaction {variant_id, feed_id, persona_id, viewer_model, hook_noticed, understood, believed, objection_text, intent_text, intent_pmf[5], preferred_ad_id}`
- `Counterfactual {variant_id, element, operation, delta{metric: value}}` — always labelled simulated
- `RealMetrics {ad_id, account (anonymised), impressions, hook_rate, p25..p95, ctr, cpa, period}`
- `ValidationResult {kind: backtest|humans|longevity|public, n, metric, value, ci, baseline}`
- `AgentEvent {ts, agent, tool, input_refs, output_ref, guards, cost_usd}`
- `CostEvent {ts, module, model, input_tokens, output_tokens, images, usd}`

## Cost design

- Understand: Wonder reads a cached corpus (cached input 20× cheaper). Muse Image $0.01/image. SAM 3.1 $2.50/1k images.
- Simulate: analyse each creative **once** (frames + transcript), then viewer reactions per persona on that analysis plus key frames. Volume runs on the distilled student; the teacher audits a sample.
- Evolve: composition is code; only new scenes cost Muse Image calls.
- Every call logged in `costs`; the UI counter is real.

## Open questions

- Muse Spark Open on Baseten: image/video input via chat completions? Tokens per frame? → smoke test.
- SAM 3.1 video tracking output and mask → frame mapping → test on real footage.
- Ad Library creative capture: snapshot pages render video; capture reliability with computer use.
- Partner history: which metrics are available per ad (video thresholds, CTR, CPA), for how many ads.
- Distillation path: Muse Glimmer size and serving; fine-tuning Spark Open on Fireworks/Modal (workshop Oct 30).
