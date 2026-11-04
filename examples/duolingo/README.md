# Example: one real agency run, every file it wrote

This folder is a **real whynot run**, copied as it came out of the engine on Nov 4, 2026 (`outputs/runs/web/20261104-145009-id570060128`), with `scripts/export_example.py`: tokens, the owner's ad account, Page id and home path are redacted; the store screenshots and the videos are left out (the app owner's assets, and size). Nothing else was edited. The ads are **concept ads made from Duolingo's public App Store page, not official Duolingo ads**. Every reaction, preference and score below is **simulated**.

It was started from the site's search bar, on a real Meta ad account, at autonomy level `autopilot` with `paused_only` on: whynot prepared everything and **published nothing** (the first live launch needs the owner's approval, see `publish.json`).

## Read it in this order

| File | Stage · model | What is in it |
|---|---|---|
| [`app.json`](app.json) | App Store | The store page and **150 reviews** the agents read |
| [`market.json`](market.json), [`market_ads.jsonl`](market_ads.jsonl) | Research · Ad Library + Muse Spark | 118 advertisers found, **23 real competitors** kept, **66 of their running ads** (copy, start date, reach), each deconstructed |
| [`strategy.json`](strategy.json) | Strategy · **Muse Wonder** | Positioning, **4 customer profiles, 6 objections, 9 angles**; every objection backed by verbatim review quotes (`evidence[].quote`) |
| [`templates/`](templates/) | Concepts · **Muse Spark** (director) | 6 concepts, each a template with fixed facts and mutable genes |
| [`variants.json`](variants.json) | Production · code + **SAM 3.1** | **36 ads**, each with its genome, its texts and the result of the 4 guards (`product_pixels_unchanged`, `text_legible`, `brand_palette`, `policy_safe`): 36/36 pass |
| [`simulation.json`](simulation.json) | Simulated feed · viewer agents | 56 feeds with the competitors' real creatives; per ad: preference vs chance, intent, **the viewers' own "why not"** (`scores[].top_why_not`), placebo check per audience |
| [`evolution.json`](evolution.json) | Evolution · **Muse Spark** (evolver) + tournaments | Per audience: each generation's Bradley-Terry strengths with 95 % intervals, the retest, the **noise floor**, the verdict |
| [`plan.json`](plan.json), [`meta_api_payloads.json`](meta_api_payloads.json), [`launch.json`](launch.json) | Plan | 2 ad sets, 6 ads, €10/day; the exact Marketing API v26.0 payloads (all `PAUSED`); the launch decision per ad set |
| [`publish.json`](publish.json), [`agency/`](agency/) | Run on Meta | `needs_approval` → nothing created; the agency's state, actions and daily report |
| [`report.md`](report.md) | Report | What the owner reads: summary, reliability of the simulation, how the ads evolved |
| [`events.jsonl`](events.jsonl), [`costs.jsonl`](costs.jsonl) | Logs | Every stage with inputs/outputs digests; **every model call with its cost** (615 calls, $4.71, of which $3.93 Muse Spark, $0.66 Muse Wonder) |
| [`ads/`](ads/) | Pictures | The planned ads and the ads the report shows, feed (4:5 or 1:1) and story (9:16) |

## One thread to follow, from a review to a better ad

1. **A real objection.** In `simulation.json`, viewers playing the *heritage family reconnector* say about the original ad `talk_with_abuela_en_v1-b1746ff3`:
   > "that freezing up part is so me but I've been burned by apps before so I'm not sure it would really work"
2. **One change that answers it.** In `report.md` (and `evolution.json`), the evolver changes one gene, the **layout**, to `review_card`: it "answers 'I've been burned by apps before…' by quoting a real App Store review to build trust" → `ads/talk_with_abuela_en_v1-602774dc.png`.
3. **Kept only if it wins beyond the noise.** Generation 1 beats generation 0 by **+1.12** head-to-head; the retest of the same feeds gives +0.82 and a **noise floor of 0.99**, so the verdict is *better, beyond the noise* (simulated).
4. **And when it doesn't.** For the *busy travel, school and career beginner*, +0.64 against a floor of 1.31: *within noise, no difference we can claim*. Evolution stopped there, at that audience's budget ($0.41), and the report says so.

Check any number here against the files: they are the files.
