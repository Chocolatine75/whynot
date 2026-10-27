# Product spec

## One-liner

An AI creative team for Meta ads with a flight simulator built in: agents invent ad concepts from your market and your customers, build variants, test them in a simulated Instagram feed next to your competitors' real ads, hear *why not* from viewer agents built on real Meta audience data, and evolve them until they win — before you spend a cent on losers.

**The product is the loop.** Templates are the generator, the simulator is the judge, the agents evolve. Neither half is the product alone: a generator without a judge is one more AdCreative.ai; a judge without a generator is one more Kantar.

## The problem

- **The creative is the only lever left.** Meta automates targeting (Andromeda: "the creative is the targeting"), bidding and budgets. What the advertiser still decides is what the ad says and shows.
- **It is decided blind.** Advertisers guess, pay to find out (the learning phase is testing with real money), and even winners are unexplained. Meta's ranking predicts per-user response internally but doesn't explain it, and only after you spend.
- **Pre-testing is for big brands.** Kantar LINK AI from ~$4,500, System1 ~$11,000 per ad. They score an ad in isolation, don't fix it, and don't place it among the competition.
- **Variations don't help anymore.** Andromeda groups near-identical ads; small advertisers need genuinely different concepts every 2–3 weeks (ad fatigue) and can't produce them.

## Who it's for

Small and mid Meta advertisers who make their own creative, roughly $2k–$100k/month on Meta, no creative-strategy team:
- **Mobile apps** (subscription apps, install + in-app events). Design partner: a friend's mobile app, ~$20k MRR, wants to use it.
- **DTC / Shopify brands.** Design partner: a Shopify store (TBC).

## What they get

| Need | whynot |
|---|---|
| Know if an ad will work before paying | Score in a simulated feed vs real competitors, with a measured reliability |
| Know *why* | Viewer objections ("why not") + counterfactuals per element |
| New concepts, not variants | ~10 evidence-backed templates per account, evolved continuously |
| Less wasted budget | Only ads that win the simulation go to Meta; learning happens in simulation |
| Trust | Reliability published (backtest, humans, pre-registered predictions), real product pixels, capped spend |

Positioning: *your creative team and its flight simulator, for the price of an app.* Built **on** Meta (Muse models, Ad Library, Ads MCP), feeding Andromeda the diverse, good creative it needs.

## The loop

```
 Understand ──▶ Create templates ──▶ Compose variants ──▶ Simulate in the feed
     ▲             (concepts)          (code, ~free)          (viewer agents)
     │                                                              │
 Calibrate ◀── Launch on Meta ◀── Keep winners ◀── Evolve (mutate genes) ◀┘
 (real results)   (Ads MCP)
```

The simulator is also the diversity guard: two concepts viewers perceive the same way are merged. Evolution is guided by reasons (objections, counterfactuals), not random search.

1. **Understand.** Brand onboarding: store or App Store page, reviews, product footage (a short phone video), past ads. Competitors from the Ad Library: creatives (captured with Muse Spark computer use), copy, start date (longevity), EU reach split by age/gender/country. Muse Wonder writes the **strategy brief**: segments, angles that work, angles nobody uses, objections and how winners answer them.
2. **Personas.** Viewer personas built from real reach breakdowns × customer segments × objections (e.g. "F 25–34 FR, price-sensitive, doubts sizing").
3. **Templates (concepts).** ~10 distinct concepts, each tied to an objection/angle and backed by evidence. Each has a fixed core and a **genome** of mutable genes.
4. **Compose.** Deterministic assembly of statics and short videos from genes. Product/app screen = SAM 3.1 cutout, never generated. Scenes and first frames from Muse Image.
5. **Simulate.** A **feed** = the candidate + N real competitor ads from the same market. Viewer agents (Muse Spark Open, sees images/video + audio transcript) produce structured reactions per ad: hook noticed (first frame / first 2 s), message understood, believed, objection ("why not"), purchase intent (free text → SSR distribution), preferred ad in the feed. Aggregated per persona.
6. **Explain.** Counterfactuals: remove/swap one tracked element (face, product, text, first shot), re-simulate, report the delta (simulated).
7. **Evolve.** Creative agents read objections + counterfactuals, propose mutations, re-simulate. A diversity guard keeps concepts distinct. Stops on budget or plateau.
8. **Launch.** Winners pushed via Ads MCP / Marketing API, sandbox and dry-run by default, hard spend cap set by the advertiser.
9. **Calibrate.** Real metrics (hook rate, video thresholds, CTR, CPA) flow back; the simulator is re-weighted per account. A weekly concept drop keeps creative fresh.

## Template spec (concept + genome)

```yaml
id: size_fit_guarantee_v1
concept: "Fit guarantee: you can't get the size wrong"
objection: size_fit
evidence:
  reviews: [review_ids]            # customer quotes
  competitor_ads: [ad_ids]         # long-running ads using this angle
  behaviour: "38% of drop-offs opened the size guide"
fixed:
  brand: {logo, palette, font}
  product: {source: sam_3_1, asset_id}      # real pixels only
genes:                                       # what evolution may mutate
  format: [static_1080, reel_6s, reel_15s]
  hook: [question, before_after, face_to_camera, bold_claim]
  first_shot: [product_closeup, person_wearing, size_chart, ugc_frame]
  proof: [free_returns_badge, size_chart_snippet, review_quote]
  persona_focus: [persona_ids]
  cta: ["Find your size", "Free exchanges"]
guards: [product_pixels_unchanged, brand_palette, text_legible, policy_safe]
```

For an app: `product` = app screen recording cut out with SAM 3.1; objections like `price_of_subscription`, `does_it_work_for_me`, `time_commitment`.

## Surfaces

- **Arena (public):** paste a store or App Store link → agents propose 3 concepts with evidence, build them, test them in the feed vs real competitors, evolve them, and show the winners with their why not. Or upload an existing ad to see how it does and get it reworked. Viral entry point.
- **Workspace (design partners):** onboarding, templates, evolution runs, counterfactuals, launch, calibration, weekly concepts, agent log, cost counter.
- **Validation page (public):** the simulator's measured reliability and the pre-registered predictions vs real outcomes.

## How we prove it

1. **Backtest** on design partners' historical ads with real Meta metrics (consented, private, anonymised).
2. **Humans:** blind paired comparisons; agreement with the simulator; evolved vs original ad.
3. **Market:** simulator vs Ad Library longevity of competitor ads.
4. **Pre-registered public prediction:** rank a set of ads, publish it, then publish real results (only with an explicitly approved, capped budget).

## Out of scope for the hackathon

- Claiming per-second retention or scroll prediction.
- Non-Meta networks.
- Generated video (no Meta video generation model in scope; we edit real footage).
- Voice-over generation (Muse Voice Transcribe is speech-to-text only).
