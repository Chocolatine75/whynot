# Product spec

## One-liner

An autonomous growth marketer for Shopify stores: it finds out why each visitor didn't buy, answers that reason with an ad built for them, spends only where the ad changes the outcome, and proves it.

## Who it's for

Small and mid-size Shopify merchants spending on Meta ads, with no in-house marketing team and no budget for an agency. They need 20+ fresh creatives a month to keep up with ad fatigue and can't produce them.

## What the merchant buys

| Need | What whynot delivers |
|---|---|
| More sales | Ads that answer each visitor's real objection, refreshed fast enough to never wear out |
| Zero time spent | The agent handles strategy, creatives, launch and monitoring; the merchant approves once and reads a weekly report |
| No wasted budget | No spend on sure buyers; weak ads filtered before they cost anything |
| Trust | Measured causal sales, real product pixels, budget hard-capped by the merchant |
| Understand customers | Objections turned into concrete fixes for the store |

Positioning: *the marketing team of a €50M brand, for the price of a Shopify app.*

## The loop

1. **Connect**: merchant installs the Shopify app. We read catalog, browsing events, orders, store pages (size guide, shipping, returns, reviews).
2. **Understand the market**: Muse Wonder reads competitors' long-running ads from the Meta Ad Library (text, visuals via snapshots, reach split by age and gender) plus the store's reviews, and writes a **strategy brief**: segments, angles that work, angles competitors miss, how competitors answer each objection.
3. **Infer objections**: each non-buying visitor gets a likely objection from their path:
   - viewed size guide → `size_fit`
   - viewed shipping page then left → `shipping_cost_or_delay`
   - read low-star reviews → `quality_trust`
   - abandoned at cart total → `price`
   - multiple product comparisons → `choice_overload`
   - unknown → `generic`
4. **Templates**: ~10 ad templates per store, each tied to one objection and one angle from the brief. A template is a spec (see below), not an image.
5. **Personalize**: per visitor or micro-segment, pick the template and fill the variable slots. Mostly deterministic composition in code; Muse Image only regenerates a slot when it adds value.
6. **Pre-test**: every variant is scored by a synthetic consumer panel (personas built from real visitor segments, Semantic Similarity Rating). Only top variants ship.
7. **Target**: an uplift model scores each visitor as persuadable / sure thing / lost cause. Budget goes to persuadables.
8. **Launch**: campaigns, custom audiences per objection, ads and budgets created via the Meta Marketing API, inside merchant-set limits. Sandbox by default.
9. **Learn**: daily, pull performance, detect fatigue, kill losers, generate replacements, update which templates win for which objections in *this* store.
10. **Prove**: a random holdout of persuadables sees no ad; the difference in purchases is the causal lift.
11. **Fix the store**: "40% of drop-offs doubt sizing → move the size guide above the fold, show free returns on the product page."

## Ad template spec

```yaml
id: size_fit_reassurance_v1
objection: size_fit
angle: "fit guarantee"          # from the strategy brief
evidence: [competitor_ad_ids]   # long-running competitor ads using this angle
layout: square_1080             # fixed
fixed:
  brand: {logo, palette, font}
  background_scene: muse_image_asset_id   # generated once, reused
slots:
  headline:   {type: text, max_chars: 40, generator: muse_spark}
  product:    {type: product_cutout, source: sam_3_1}   # real pixels only
  proof:      {type: one_of, options: [free_returns_badge, size_chart_snippet, review_quote]}
  cta:        {type: text, options: ["Find your size", "Free exchanges"]}
rules:
  - if visitor.price_sensitive: proof = free_returns_badge
guards:
  - product_pixels_unchanged     # pixel diff vs SAM cutout must be 0
  - brand_palette_respected
  - text_legible
```

## Surfaces

Public teardown (any Shopify URL), merchant dashboard, on-site answer. Defined in `TARGETS.md`.

## Channels

- **Primary**: Meta (Facebook / Instagram) via Marketing API.
- **Free proof channels** (for validation without ad spend): on-site banner on the partner store, personalized abandoned-cart email.

## How we prove it works (no ad spend)

1. **Blind human test**: 50–100 people, each picks a realistic hesitation scenario for the partner's real product, compares generic vs personalized ad blind, rates purchase intent. Paired design, so a small sample gives a clear result.
2. **Synthetic panel validated against humans**: same scenarios through the panel; we report how well its ranking matches the humans.
3. **Partner store A/B**: on-site banner and cart email, generic vs objection-specific.
4. **Panel vs market**: panel scores vs Ad Library longevity of competitor ads (R4).
5. *(optional)* Criteo uplift side check; capped Meta split test with explicit approval.

## Out of scope for the hackathon

- Real multi-week ad spend and real causal lift on a live store (we show the mechanism; numbers come from public data and the human test).
- Non-Shopify platforms, non-Meta ad networks.
- Video ads.
