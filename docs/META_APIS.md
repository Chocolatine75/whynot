# Meta APIs — working notes

Update this file with what we actually observe (model IDs, prices, quirks). Items marked *unverified* come from third-party sources before the event.

## Meta Model API
- Base URL: `https://api.meta.ai/v1` (Anthropic-format harnesses: `https://api.meta.ai`)
- Auth: `Authorization: Bearer $MODEL_API_KEY`
- Compatible with OpenAI SDK (Responses, Chat Completions) and Anthropic SDK (Messages).
- Credits: $150 per person; card required; set a spend limit on Billing.

| Model ID | Use | Price (*unverified*) |
|---|---|---|
| `muse-spark-1.3` | Reasoning, tools, vision, computer use | ~$1.25 / M input |
| `muse-spark-1.3-contributor` | Cheap bulk text — **synthetic data only** | $0.10 in / $0.20 out / M |
| `muse-wonder-1.0` | 1M context, text+image+video+audio in | $4 in / $20 out / $0.20 cached / M |
| `muse-image-1.0` | Image generation & editing, reference images, text in image | $0.01 / image |
| `sam-3.1` | Segmentation | ? |
| `muse-voice-transcribe-1.0` | Speech to text | ? |

Computer use reference: Meta cookbook "Building a computer-use agent with Muse Spark" (OpenCode + Cua MCP, look-act-look loop).

## Open weights
- **Muse Spark Open** (MoE, ~42B active). On Baseten use model `meta-models/muse-spark-open-1026`.
- Muse Glimmer.
- Qualifies for "Best Build on Meta Open Weight Models" when served on own hardware or partner inference.

## Ad Library API
- Free. Requires identity verification at facebook.com/ID (done for Matteo), a developer app (type Business), and a user token (Graph API Explorer, `ads_read`). Extend to long-lived (~60 days) via the Access Token Debugger.
- Endpoint: `GET https://graph.facebook.com/v26.0/ads_archive`
- Required: `access_token`, `ad_reached_countries` (e.g. `['FR']`), and `search_terms` or `search_page_ids`.
- Commercial ads are only available for ads delivered in the EU/UK.
- Useful params: `ad_type=ALL`, `ad_active_status=ACTIVE|ALL`, `ad_delivery_date_max=YYYY-MM-DD` (long-running ads), `search_type=KEYWORD_EXACT_PHRASE`, `limit`, cursor pagination via `after`.
- Useful fields: `id, page_name, ad_creative_bodies, ad_creative_link_titles, ad_delivery_start_time, ad_snapshot_url, publisher_platforms, eu_total_reach, target_ages, target_gender, target_locations, age_country_gender_reach_breakdown`.
- ⚠️ `ad_snapshot_url` and paging `next` URLs contain the access token. Strip it.
- ⚠️ No creative image/video files: only the snapshot page.
- ⚠️ A missing token returns `OAuthException code 1 "unknown error"`, not an auth error.
- Observed: keyword search is noisy ("baskets" matched a coaching ad). Prefer `search_page_ids` for known competitors.
- Observed: two Lacoste ads active for ~4 months, one reaching ~195k people in France, mostly 25–44, roughly 50/50 men/women. Long-running = proxy for "this ad works".
- Observed: most advertisers target 18–65 broadly; `age_country_gender_reach_breakdown` reflects who the algorithm actually delivered to, which is the useful signal.

## Marketing API
- Create campaigns, ad sets, custom audiences, ads. Needs `ads_management`, `ads_read`, a business setup, and possibly App Review for non-dev users. Use a **sandbox ad account** to test without spending.
