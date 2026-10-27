# Product spec

## One-liner

whynot is an AI ad agency for small businesses on Meta: agents research the market and the customers, create ads for each customer profile, test every ad in a simulated feed before spending, then publish, steer and report. The owner just checks.

## The problem

- **Small businesses can't afford an agency and can't keep up alone.** Under Andromeda, ads wear out in 2–3 weeks and only genuinely different concepts get distinct delivery (near-duplicates are grouped). A founder can't produce, test and rotate new concepts every week.
- **Meta automates delivery, not creation.** Targeting, bidding and budgets are automated: the creative is the last lever. Advantage+ tweaks existing assets (backgrounds, text variants, video from a still); it doesn't create a new concept. Meta's business AI assistant (testing since Oct 2026) plans and adjusts campaigns, but learns by spending.
- **Testing costs real money and explains nothing.** The learning phase is testing with the advertiser's budget. Pre-tests from Kantar or System1 cost $4,500–$11,000 per ad and score an ad in isolation.

## Who it's for

Small businesses that advertise on Meta without a marketing team, roughly $2k–$100k/month of ad spend:
- **Mobile apps** (subscriptions, installs). First design partner: a friend's app, ~$20k MRR. His ask, in his words: a tool that runs the whole ad campaign without him — creates, posts and adjusts the ads — so he only checks.
- **DTC / Shopify brands.** Second design partner: a Shopify store (TBC).

## What the owner gets

| Need | whynot |
|---|---|
| Ads done without them | Research, strategy, creation, publishing, rotation and reporting by agents |
| Real new ads, not tweaks | ~10 evidence-backed concepts per business, refreshed weekly |
| No budget wasted on bad ads | Every ad tested in a simulated feed vs real competitors before it runs |
| Understand what works | Every ad comes with its concept, evidence and the reasons it won |
| Control | Hard spend caps, autonomy level chosen by the owner, approve/block from the weekly report |

Positioning: *the marketing team of a much bigger brand, for the price of an app.* Built **on** Meta (Muse models, Ad Library, Ads MCP): it feeds Andromeda the diverse, good creative it needs and leaves bidding and delivery to Meta.

## The engine: a loop

```
 Research ──▶ Strategy ──▶ Create templates ──▶ Produce variants ──▶ Test in the simulated feed
    ▲                        (concepts)          (code, ~free)          (viewer agents)
    │                                                                         │
 Learn ◀── Report ◀── Run on Meta ◀── Keep winners ◀── Evolve (mutate genes) ◀┘
 (real results)  (owner checks)  (Ads MCP, caps)
```

**Templates generate, the simulator judges, the agents evolve.** A generator without a judge is one more AdCreative.ai; a judge without a generator is one more Kantar. The simulator is also the diversity guard: two concepts that viewers perceive the same way are merged. Evolution is guided by reasons (objections, counterfactuals), not random search.

## Step by step

1. **Onboard.** The owner pastes a store or App Store link, connects the ad account (read-only first), sets a spend cap and an autonomy level, optionally uploads a short product video.
2. **Research.** Scout: competitors' ads from the Ad Library — copy, creatives (captured with Muse Spark computer use), transcripts, start date (longevity), EU reach by age/gender/country. Researcher: reviews, pages, past ads and their metrics → why people buy and *why not*.
3. **Strategy.** Muse Wonder reads everything in one cached call: customer profiles (personas), angles that work, angles nobody uses, objections and how the winners answer them.
4. **Personas.** Built from real reach breakdowns × customer segments × objections (e.g. "F 25–34 FR, short on time, doubts it works for her").
5. **Create.** ~10 templates: distinct concepts, each tied to a persona/objection and backed by evidence, each with a genome.
6. **Produce.** Deterministic assembly of statics and short videos from genes. Product/app screen = SAM 3.1 cutout, never generated. Scenes and first frames from Muse Image.
7. **Test.** A feed = the candidate + N real competitor ads from the same market. Viewer agents (Muse Spark Open, sees images/video + transcript) react per ad: hook noticed (first frame / first 2 s), message understood, believed, objection ("why not"), purchase intent (free text → SSR distribution), preferred ad in the feed. Aggregated per persona.
8. **Explain.** Counterfactuals: remove/swap one tracked element (face, product, text, first shot), re-simulate, report the delta (simulated).
9. **Evolve.** The creative director reads objections and counterfactuals, mutates genes, re-tests, until the ad wins its feed or the budget is spent.
10. **Run.** Winners published through the Ads MCP / Marketing API within caps. Daily: pull metrics, detect fatigue, pause losers, keep winners. Weekly: new concepts. Meta handles bidding and delivery.
11. **Report.** Weekly report in plain language: what shipped, what was paused and why, what's next; approve/block buttons.
12. **Learn.** Real metrics (hook rate, video thresholds, CTR, CPA) recalibrate the simulator for that business and tell which concepts work for whom.

## Template spec (concept + genome)

```yaml
id: five_minutes_a_day_v1
concept: "Five minutes a day is enough"
persona: f25_34_short_on_time
objection: no_time
evidence:
  reviews: [review_ids]            # customers saying it
  competitor_ads: [ad_ids]         # long-running ads using this angle
  metrics: "past ads with time-based hooks: hook rate +X% (partner history)"
fixed:
  brand: {logo, palette, font}
  product: {source: sam_3_1, asset_id}      # real app screens only
genes:                                       # what evolution may mutate
  format: [static_1080, reel_6s, reel_15s]
  hook: [question, before_after, face_to_camera, bold_claim]
  first_shot: [app_screen, person_using, result_card, ugc_frame]
  proof: [rating_badge, review_quote, streak_counter]
  cta: ["Start free", "Try 5 minutes"]
guards: [product_pixels_unchanged, brand_palette, text_legible, policy_safe]
```

For a store: `product` = product photo/video cutout; objections like `size_fit`, `shipping`, `price`, `trust`.

## Personalisation: by profile, not by person

Meta audiences need at least ~100 people (practically ~1,000) and Meta chooses who sees what. whynot makes different concepts for different personas; Meta delivers each concept to the people who respond to it. Per-person personalisation is out of scope on Meta.

## Autonomy and control

| Level | What the agency does | Owner |
|---|---|---|
| `dry_run` (default) | Everything except publishing; shows what it would do | Reads |
| `propose` | Prepares each action, waits | Approves each action |
| `autopilot` | Acts within caps, reports every action | Can block; reads the weekly report |

Hard rules: spend never exceeds the owner's cap; first live launch always needs explicit approval; every action is logged and explained.

## Surfaces

- **Onboarding:** link + account + cap + autonomy level.
- **Agency room:** live agent log, running ads, test results in the simulated feed, next concepts, cost counter.
- **Weekly report:** actions, results, reasons, approve/block.
- **Arena (public, no account):** paste a link → the agents create 3 concepts, test them in the simulated feed vs real competitors, evolve them, show the winners and the why not. Or upload an existing ad. Viral entry point; nothing is published.
- **Validation page (public):** the simulator's measured reliability and the live pilot results.

## How we prove it

1. **Backtest:** the simulator ranks the design partner's past ads blind; compared with their real metrics.
2. **Humans:** blind paired comparisons; agreement with the simulator; evolved vs original ad.
3. **Market:** simulator vs Ad Library longevity of competitor ads.
4. **Live pilot:** the agency runs the design partner's account for several days within caps; predictions published before results; real outcomes reported, good or bad.

## Out of scope for the hackathon

- Per-person ads on Meta.
- Bidding and delivery optimisation (Meta's job).
- Claiming scroll or per-second retention prediction.
- Non-Meta networks.
- Generated video (we edit real footage) and voice-over generation (Muse Voice Transcribe is speech-to-text only).
