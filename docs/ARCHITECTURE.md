# Architecture

Principle: **the big model teaches, small models serve, code composes.** Muse models do the work only they can do (understanding, writing, image generation, simulating consumers). Everything that runs per visitor is cheap and deterministic.

```
                ┌──────────────── ONBOARDING (once per store, a few $) ────────────────┐
Shopify store ──▶ ingest ──▶ store profile (catalog, pages, reviews)                    │
Meta Ad Library ─▶ competitor ads ─▶ snapshots read by Muse Spark (computer use) ──┐     │
                                                                                   ▼     │
                                         Muse Wonder (1M ctx, cached) ─▶ strategy brief  │
                                                                                   │     │
                         product media ─▶ SAM 3.1 cutouts                          ▼     │
                                         Muse Image ─▶ scene assets ─▶ ~10 ad templates │
                └─────────────────────────────────────────────────────────────────────────┘

                ┌──────────────── PER VISITOR (near-zero cost) ──────────────────────────┐
browsing events ─▶ objection classifier (distilled from Muse Spark labels)              │
                ─▶ uplift model (gradient boosting, T-/X-learner)                       │
                ─▶ template pick + slot fill ─▶ composer (code) ─▶ guards (pixel diff…)  │
                └─────────────────────────────────────────────────────────────────────────┘

                ┌──────────────── PRE-TEST & LAUNCH ─────────────────────────────────────┐
variants ─▶ synthetic panel (Muse Spark Open on Baseten, SSR scoring) ─▶ top-k          │
top-k ─▶ Meta Marketing API (sandbox by default, budget cap) ─▶ campaigns / audiences   │
performance ─▶ learner (bandit over templates × objections) ─▶ refresh loop             │
holdout ─▶ causal lift report + store fix recommendations                               │
                └─────────────────────────────────────────────────────────────────────────┘
```

## Modules

| Module | Responsibility | Models / tools |
|---|---|---|
| `ingest/shopify` | Catalog, pages, reviews, browsing events (Shopify API or demo dataset) | — |
| `ingest/adlibrary` | Pull competitor ads, strip tokens from URLs, store reach breakdowns | Graph API v26 |
| `ingest/snapshots` | Open ad snapshot pages, capture and describe visuals | Muse Spark computer use / vision |
| `brief` | Market strategy brief from all competitor ads + reviews | Muse Wonder (prompt caching) |
| `objections/label` | Label a sample of sessions with objections | Muse Spark |
| `objections/classifier` | Small classifier trained on labels, runs per visitor | scikit-learn / LightGBM |
| `uplift` | Persuadable scoring; evaluated on Criteo uplift data | scikit-uplift / causalml |
| `assets/cutout` | Product cutout, used as exact pixels | SAM 3.1 |
| `assets/scenes` | Scene backgrounds per template | Muse Image |
| `templates` | Template specs (YAML) generated from the brief | Muse Spark |
| `composer` | Deterministic ad rendering from template + slots | Pillow / Satori |
| `guards` | Pixel diff on product region, palette, legibility | code |
| `panel` | Synthetic consumers + Semantic Similarity Rating | Muse Spark Open (Baseten), embeddings |
| `launch` | Campaigns, audiences, ads via Marketing API, sandbox + caps | Graph API |
| `learner` | Bandit over (template, objection), fatigue detection | code |
| `report` | Weekly report + store fixes | Muse Spark |
| `costs` | Single model-call wrapper logging tokens, images, $ | code |
| `web` | Merchant dashboard + demo UI | Next.js |

## Data contracts (sketch)

- `Session {visitor_id, events[{type, url, ts, product_id?}], converted: bool}`
- `Objection {visitor_id, label, confidence, source: muse|classifier}`
- `CompetitorAd {id, page_name, bodies[], titles[], start_date, reach_total, reach_breakdown[], snapshot_url_clean, visual_description}`
- `Template {id, objection, angle, evidence[], fixed{}, slots{}, rules[], guards[]}`
- `Variant {id, template_id, slot_values{}, image_path, guard_results{}}`
- `PanelScore {variant_id, persona_id, free_text, pmf[5], mean}`
- `CostEvent {ts, module, model, input_tokens, output_tokens, images, usd}`

## Cost design

- Onboarding: Wonder brief reuses a cached corpus (cache reads ~20× cheaper than fresh input). Muse Image ~$0.01/image, ~10–30 scene assets per store.
- Per visitor: classifier + uplift + composition, no LLM call.
- Order of magnitude: one generated ad per visitor ≈ $10k per million visitors; templates generated once + code composition ≈ a few $ per store.
- Panel: open-weight model on partner credits, not Meta API credits.
- Every call logged in `costs`, so the UI's cost counter is real.

## Open questions

- ~~Muse Image API surface~~ → checked: generations + edits with up to 10 reference images, no mask (see META_APIS.md).
- SAM 3.1 output is special-token text with base85 masks smaller than the frame → verify how to map a mask back to full resolution on a real image.
- Marketing API sandbox ad account setup time.
- Source of browsing sessions if partner store traffic is low (public e-commerce event dataset, licence to check).
