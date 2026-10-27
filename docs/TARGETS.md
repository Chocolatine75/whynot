# Targets — the product we ship and the bar it must clear

This is the reference we loop on. Every few days, and before submitting, go through each line and mark it ✅ / 🟡 / ❌ with the measured value. If a criterion is ❌ two days before the deadline, cut scope elsewhere; never lower the bar silently. Changing a target = one line in `DECISIONS.md` with why.

The bar: **not a wrapper, not an ad generator.** A Meta judge must think "I'd want this in our ecosystem", and an advertiser must want to drop their own ad in.

Our honest estimate (gut, not a calculation): ~10% chance of Indie top 5 with the simulator validated, ~20% if the levers in §5 land, ~5% if the simulator isn't validated.

---

## 1. The final product (what exists on Nov 4)

### A. Arena — public, no install
Upload an ad (image or ≤ 30 s video) or pick one, choose a market → in under 2 minutes:
- the ad **inside a simulated feed** next to real competitor ads from the Ad Library;
- reactions per persona: hook, understood, believed, **why not**, intent, preferred ad;
- the 3 fixes that would help most (from counterfactuals, labelled simulated);
- the simulator's reliability, linked to the Validation page.

### B. Workspace — design partners (mobile app ~$20k MRR; Shopify store TBC)
- Onboarding from store/App Store page, reviews, product footage, past ads.
- Strategy brief, personas, ~10 templates with evidence.
- **Evolution runs** v1 → vN, with counterfactuals and the diversity guard.
- Launch to Meta (sandbox / capped) and real-metric calibration.
- Weekly concept drop. Agent log + cost counter on every screen.

### C. Validation page — public
Backtest, human agreement, Ad Library longevity, distilled-vs-teacher agreement, and the pre-registered public prediction with its real outcome.

---

## 2. Results (measured, shown in the demo)

Target = what we aim for. Floor = below this we don't show it as a win; we show it honestly as a limit and fix the system.

| # | Result | How we measure | Target | Floor |
|---|---|---|---|---|
| R1 | **Simulator predicts real performance** | Backtest on design partners' past ads: pairwise ranking accuracy vs a real metric (hook rate, CTR or CPA), blind to outcomes | ≥ 65 %, CI excludes 50 %, beats baselines (random, single-LLM judge without feed/personas, simple heuristics) | > 55 % |
| R2 | **Simulator agrees with humans** | Blind paired comparisons, same pairs through the simulator | ≥ 75 % agreement, n ≥ 80 people | ≥ 65 % |
| R3 | **Simulator reads the market** | Tells long-running (> 60 days) competitor ads from short-lived ones | AUC ≥ 0.65 | > 0.55 |
| R4 | **Public pre-registered prediction** *(needs approved, capped spend)* | Rank 8–12 live variants, publish timestamped, publish real results | Published before and after, whatever the outcome | published |
| R5 | **Evolution makes ads better** | Final vs original variant: humans (blind) and, if R4 runs, real metrics | Humans prefer evolved ≥ 65 %, p < 0.05 | > 55 % |
| R6 | **Concepts, not variations** | Pairwise similarity of shipped concepts (our embedding metric) + viewer-perceived distinctness | All pairs under threshold | — |
| R7 | **Product / app never invented** | Pixel diff on product region vs SAM cutout | 0 px on 100 % of ads | hard rule |
| R8 | **Cheap** | `costs` log | Arena run < $0.50; evolution run (5 gens) < $5; student ≥ 10× cheaper than teacher with ≥ 85 % agreement | — |
| R9 | **Fast** | Wall clock | Arena < 2 min | < 4 min |
| R10 | **People use it** | Real advertisers | ≥ 30 Arena runs by real advertisers, ≥ 2 partners in Workspace, ≥ 5 quotes, ≥ 1 ad changed because of whynot | ≥ 10 runs |

---

## 3. Criteria — the bar per judging criterion

### Impact (30 %)
- [ ] The problem lands in 10 s: "you pay Meta to find out your ad is bad".
- [ ] A design partner with real revenue uses it and says so on camera / in a quote.
- [ ] R10 reached.
- [ ] Clear economics: cost per run vs $4.5k–$11k per traditional pre-test; budget not wasted on losers.
- [ ] Why Meta wants it: better ads in the feed for users, SMB advertisers succeed and stay, built on Muse + Ads MCP.

### Use of Meta models (25 %)
- [ ] Each model does something only it can do here (see README table), one sentence each.
- [ ] **Surprise:** viewer agents that *watch* a feed of real competitor ads; SAM-tracked counterfactuals in video; Ad Library reach data as persona ground truth.
- [ ] Open weights on the critical path (viewers) **and** trained/distilled (student viewer) — Best Open Weights prize.
- [ ] Contributor tier never touches partner data.

### Technical depth (20 %)
- [ ] Validation is the technical hero: R1–R3 with baselines and confidence intervals.
- [ ] It's an agent system: roles, tools, guards, budget, retries, verifiable log (Agents 102).
- [ ] Teacher → student distillation measured (R8).
- [ ] One command reproduces every number.
- [ ] Clean modules, tests on core (composer, guards, SSR, validation stats).

### Demo (25 %)
- [ ] Hook in 15 s: an ad dropped into a fake Instagram feed among real competitors; viewers say why not.
- [ ] Evolution v1 → vN live, score rising vs competitors, with the reasons.
- [ ] A counterfactual moment: "without this shot, −X % (simulated)".
- [ ] Proof on screen: R1/R2/R3 numbers, the public bet.
- [ ] Live, no manual step; simulated numbers labelled.
- [ ] A judge can drop their own ad in the Arena.
- [ ] 30 s cut for X that stands alone.

---

## 4. Anti-goals

- Claiming per-second scroll or retention prediction.
- Unlabelled simulated numbers; reliability claims without `validate/` behind them.
- An ad generator with a score bolted on.
- Variations sold as concepts.
- Partner data in the repo or visible un-anonymised.
- Generated product / app pixels.
- Spending on Meta without an explicit cap and our explicit OK.

---

## 5. Levers to go from ~10 % to ~20 % (in order)

1. **Backtest on real history (R1)** — start partner data collection today. Critical path.
2. **Public pre-registered prediction (R4)** — needs a launch by ~Oct 31 to have results by Nov 3–4.
3. **Distilled student viewer on open weights (R8)** — Fireworks workshop Oct 30.
4. **Real users (R10)** — Arena public by Nov 2.
5. **Build in public** — daily X posts from day 2; daily presence at Meta office hours.
6. **Live interactive finale** — "give us a brand, we drop its ad in the feed".
