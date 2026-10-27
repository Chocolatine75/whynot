# Meta APIs — working notes

Checked against official docs on 2026-10-27 (sources at the bottom). Items marked *unverified* have not been confirmed by an official page or by our own calls. Our smoke tests should confirm everything here; update this file with what we actually observe.

Smoke test: `uv run python scripts/smoke_models.py` (results in `outputs/smoke.json`). Checks: model list, Spark text + vision, Contributor text, Wonder text, Muse Image, SAM 3.1 on a test image, Spark Open on Baseten text + vision. Last run: *not yet run — no keys in `.env`*.

## Meta Model API

- Base URL: `https://api.meta.ai/v1`. Auth: `Authorization: Bearer $MODEL_API_KEY`.
- OpenAI SDK compatible (Chat Completions, Responses) and Anthropic SDK compatible (Messages). Anthropic-format base `https://api.meta.ai` is *unverified*.
- Model list endpoint: `GET /v1/models` (see API reference "list models").
- Reasoning depth: `reasoning_effort` from `minimal` to `xhigh`. Reasoning tokens are billed as output.
- Credits: $150 per person (participant guide); card required; set a spend limit on Billing.

### Models, prices and rate limits (official pricing page)

Prices per 1M tokens unless noted. Rate limits are **per team, per model**, not per key.

| Model ID | Use | Input | Cached in | Output | RPM / TPM |
|---|---|---|---|---|---|
| `muse-spark-1.3` (also `-1.2`, `-1.1`) | Reasoning, tools, vision, computer use. 1M ctx | $1.25 | $0.15 | $4.25 | 3,000 / 4M |
| `muse-spark-1.3-contributor` (also `-1.2-contributor`) | Cheap bulk text. **Synthetic data only** | $0.10 | $0.002 | $0.20 | 150 / 3M |
| `muse-wonder-1.0` | 1M ctx (1,048,576), long-context reading. Preview | $4.00 | $0.20 | $20.00 | 3,000 / 4M |
| `muse-image-1.0` | Image generation & editing | $0.01 / image returned | | | 150 RPM |
| `sam-3.1` | Segmentation (image, video) | $2.50 / 1k images, $0.20 / 1k video frames (min 50 frames per video request) | | | 3,000 RPM |
| `muse-voice-transcribe-1.0` | Speech to text | $0.18 / hour of audio | | | 256 concurrent streams |

- Web search grounding: $2.50 / 1k queries on top of tokens.
- **Contributor mode is confirmed to grant Meta the right to train on prompts, files and responses.** Only Muse Spark 1.3 / 1.2. Never send partner or customer data to it.
- Background (async) responses capped at 600 submissions / min / team.

### Prompt caching

- **Automatic**: the stable prefix is cached, no flag or `cache_control`. Optional `prompt_cache_key` raises hit rates.
- Responses API only: `prompt_cache_retention: "24h"` asks for longer retention (a hint, not a guarantee).
- Cached tokens reported in `usage.prompt_tokens_details.cached_tokens` (Chat Completions) or `usage.input_tokens_details.cached_tokens` (Responses). They are a subset of input tokens.
- No documented minimum length or default TTL. → Put the big stable corpus first, the variable question last.
- Wonder: cached input is 20× cheaper than fresh input ($0.20 vs $4.00). Confirmed.

### Muse Image (`muse-image-1.0`)

- `POST /v1/images/generations` (text → image), `POST /v1/images/edits` (image(s) → image), or `POST /v1/responses` with the `image_generation` tool (multi-turn refinement).
- Params: `prompt`, `n` 1–10, `size` `"WxH"` (sets **aspect ratio**, not exact pixels; `"auto"` default), `response_format` `b64_json` (default) or `url` (temporary signed URL), `output_format` `webp` (default) / `png` / `jpeg`.
- Meta extensions via `extra_body`: `reasoning_strength` (`high` default / `low`), `tool_enablement` (`enable_image_search`, `enable_web_search`, `enable_shell`; all default on in the Responses tool).
- Edits: 1–10 reference images (multipart `image`, or JSON `images[]` with `image_url` or `file_id`). Good for series consistency.
- ⚠️ **No `mask`** on edits (400 `unsupported_parameter`). No `moderation` param. Output background is always opaque.
- ⚠️ Unknown top-level JSON fields → 400. Safety block → 400 `content_policy_violation`. Retryable failure → 503.
- Billed only for images actually returned.
- Implication for us: scenes come from Muse Image, the product is composited in code on top. Never ask Muse Image to redraw the product.

### SAM 3.1 (`sam-3.1`)

- Called through `POST /v1/responses` with a user message: `input_text` (short concept prompt, e.g. `"jacket"`) + `input_image` (`image_url`). Local files via `POST /v1/files`. Box and point prompts: see "segmenting prompts" page. Video supported.
- Output is **streamed special-token text**, one box + one mask per match:
  - Box: `<|box;x1=..;y1=..;x2=..;y2=..;w=<frameW>;h=<frameH>[;c=<conf>]|>`, corners in source pixels.
  - Mask: `<|mask;x=0;y=0[;c=<conf>];data=<H>,<W>,<enc><payload>|>`. Payload is **base85**; `~` = lossless (default), `!` = one-bit. Mask raster H×W is smaller than the frame.
  - Confidence only with `include_confidence: "true"`. Encoding via `metadata.mask_encoding`.
- ⚠️ Docs don't say how the H×W mask maps back to the frame. Official decoder is in client libraries (`decodeMaskToRaster`). → Must verify on a real image in the smoke test before building `assets/cutout`.

### Computer use / vision

- Cookbook: "computer use" (look-act-look loop) and "vision input". Used to read Ad Library snapshot pages.

## Open weights

- **Muse Spark Open**: 816B total / ~42B active MoE, 1M ctx, text+image+audio+video in, text out. Muse Model License + Acceptable Use Policy.
- Hosted model string per Meta's deploy page: Baseten / Together / Groq / Nebius `meta-models/muse-spark-open`; Fireworks `accounts/fireworks/models/muse-spark-open`.
- **Baseten**: OpenAI-compatible, `base_url=https://inference.baseten.co/v1`, model `meta-models/muse-spark-open`. Public price $1.25 in / $0.15 cached / $4.25 out per 1M. Reported: no JSON mode / structured output, `n>1` → 400 (*unverified*, from search summary). Hackathon guide mentioned `meta-models/muse-spark-open-1026`, which no official page lists → **the smoke test decides; keep the model string in `BASETEN_MODEL`.**
- **Muse Glimmer**: open weights, Apache 2.0.
- Qualifies for "Best Build on Meta Open Weight Models" when served on own hardware or partner inference (participant guide).

## Ad Library API

- Free. Requires identity verification at facebook.com/ID (done for Matteo), a developer app (type Business), and a user token (Graph API Explorer, `ads_read`). Extend to long-lived (~60 days) via the Access Token Debugger.
- Graph API **v26.0** is the latest version (released 2026-07-29; no v27 found).
- Endpoint: `GET https://graph.facebook.com/v26.0/ads_archive`
- Required: `access_token`, `ad_reached_countries` (e.g. `['FR']`), and `search_terms` or `search_page_ids`.
- Commercial ads are only available for ads delivered in the EU/UK.
- Useful params: `ad_type=ALL`, `ad_active_status=ACTIVE|ALL`, `ad_delivery_date_max=YYYY-MM-DD` (long-running ads), `search_type=KEYWORD_EXACT_PHRASE`, `limit`, cursor pagination via `after`.
- Useful fields: `id, page_name, ad_creative_bodies, ad_creative_link_titles, ad_delivery_start_time, ad_snapshot_url, publisher_platforms, eu_total_reach, target_ages, target_gender, target_locations, age_country_gender_reach_breakdown`.
- ⚠️ `ad_snapshot_url` and paging `next` URLs contain the access token. Strip it.
- ⚠️ No creative image/video files: only the snapshot page.
- ⚠️ A missing token returns `OAuthException code 1 "unknown error"`, not an auth error.
- *Unverified (our parser assumes it):* `age_country_gender_reach_breakdown` = `[{country, age_gender_breakdowns: [{age_range, male, female, unknown}]}]`. Confirm on the first real call (`scripts/fetch_competitors.py`).
- Observed: keyword search is noisy ("baskets" matched a coaching ad). Prefer `search_page_ids` for known competitors.
- Observed: two Lacoste ads active for ~4 months, one reaching ~195k people in France, mostly 25–44, roughly 50/50 men/women. Long-running = proxy for "this ad works".
- Observed: most advertisers target 18–65 broadly; `age_country_gender_reach_breakdown` reflects who the algorithm actually delivered to, which is the useful signal.

## Marketing API / Ads MCP

Used by the agency's media buyer to publish, monitor and rotate ads, and by `ingest/history` to read past ads and metrics.

- **Ads MCP server** (Oct 2026): creative uploads, ad previews, performance tracking; partners include Triple Whale, Snowflake, Databricks, Perplexity. Preferred publishing + metrics channel; exact capabilities (pausing ads, budgets) to verify.
- Real metrics we need per ad for backtest/calibration: impressions, 3-s plays / hook rate, video thresholds (p25/p50/p75/p95 watched actions — *unverified field names*), ThruPlay, CTR, CPA. Ad-level per-second retention curves are *not confirmed* for ads (the per-timestamp retention metric documented is for Reels video insights).
- Create campaigns, ad sets, custom audiences, ads. Needs `ads_management`, `ads_read`, a business setup, and possibly App Review for non-dev users. Use a **sandbox ad account** to test without spending. Partner accounts: read-only first; write access only with the owner's written consent, a hard cap and approval before the first live launch.
- v26.0 changes that affect us: new or copied ad sets with constrained targeting must set `advantage_audience` explicitly (1 or 0); Instagram Explore Feed placement removed; poll ads blocked. Several restrictions apply to all versions from 2026-10-27.

## Sources

- Meta Model API docs: https://dev.meta.ai/docs/ — pricing & rate limits: https://dev.meta.ai/docs/pricing-rate-limits
- Muse Image: https://dev.meta.ai/docs/image-generation
- SAM 3.1: https://dev.meta.ai/docs/media-segmentation , https://dev.meta.ai/docs/sam/reading-segmentation
- Prompt caching: https://dev.meta.ai/docs/prompt-caching
- Muse Spark launch post: https://dev.meta.ai/resources/blog/build-with-muse-spark
- Muse Spark Open: https://dev.meta.ai/docs/muse-spark-open , https://dev.meta.ai/docs/muse-spark-open/deploy , https://www.baseten.co/library/muse-spark-open/
- Graph API v26.0: https://developers.facebook.com/docs/graph-api/changelog/version26.0
