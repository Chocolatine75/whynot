# Targets — the product we ship and the bar it must clear

This is the reference we loop on. Every few days, and before submitting, go through each line and mark it ✅ / 🟡 / ❌ with the measured value. If a criterion is ❌ two days before the deadline, cut scope elsewhere; never lower the bar silently. Changing a target = one line in `DECISIONS.md` with why.

The bar: **an agency that really runs a business's Meta ads, whose quality gate is measured.** Not an ad generator, not a pre-test tool, not a wrapper around Meta. A Meta judge must think "I'd want this in our ecosystem"; a small business owner must think "I'd hand my ads to this".

Our estimate (gut, not a calculation): ~10 % chance of Indie top 5 with the simulator validated, ~20 % if the levers in §5 land, ~5 % if the simulator isn't validated.

---

## 1. The final product (what exists on Nov 4)

### A. The agency, running for the design partner (mobile app, ~$20k MRR)
- Onboarded from his App Store link and ad account; cap and autonomy level set by him.
- Research, strategy, personas and ~10 templates with evidence.
- Ads created, tested in the simulated feed, evolved, then **published and run for several days** (after his explicit approval), with rotation and pauses.
- Agency room (live agent log, running ads, test results, cost counter) and a weekly report with approve/block.

### B. Arena — public, no account
Paste a store or App Store link (or upload an existing ad) → in a few minutes:
- the agents' **3 concepts** with their evidence;
- the variants **inside a simulated feed** next to real competitor ads;
- reactions per persona: hook, understood, believed, **why not**, intent, preferred ad;
- one evolution round with the reasons, score before / after (simulated);
- the winners, downloadable; a link to the Validation page.

### C. Validation page — public
Backtest, human agreement, Ad Library longevity, student-vs-teacher agreement, live pilot predictions vs outcomes.

---

## 2. Results (measured, shown in the demo)

Target = what we aim for. Floor = below this we don't present it as a win; we show it honestly as a limit.

| # | Result | How we measure | Target | Floor |
|---|---|---|---|---|
| R1 | **The quality gate predicts real performance** | Backtest on the partner's past ads: pairwise ranking accuracy vs a real metric (hook rate, CTR or CPA), blind to outcomes | ≥ 65 %, CI excludes 50 %, beats baselines (random, single-LLM judge without feed/personas, simple heuristics) | > 55 % |
| R2 | **It agrees with humans** | Blind paired comparisons, same pairs through the simulator | ≥ 75 % agreement, n ≥ 80 people | ≥ 65 % |
| R3 | **It reads the market** | Tells long-running (> 60 days) competitor ads from short-lived ones | AUC ≥ 0.65 | > 0.55 |
| R4 | **The agency really runs an account** | Live pilot on the partner's account (approved, capped) | ≥ 5 days live, every action logged and explained, 0 cap breaches, results reported vs his previous ads whatever they are | ≥ 3 days |
| R5 | **Predictions before results** | Before launch, publish (timestamped) the simulator's ranking of the pilot's ads; compare with real metrics | Published before and after | published |
| R6 | **Evolution makes ads better** | Evolved vs original: humans (blind) and pilot metrics | Humans prefer evolved ≥ 65 %, p < 0.05 | > 55 % |
| R7 | **Real new concepts** | Pairwise similarity of shipped concepts (our metric) + viewer-perceived distinctness | All pairs under threshold | — |
| R8 | **Product / app never invented** | Pixel diff on the product region vs SAM cutout | 0 px on 100 % of ads | hard rule |
| R9 | **Owner time near zero** | Partner's time per week (onboarding excluded) | < 10 min/week (report + approvals) | < 30 min |
| R10 | **Cheap** | `costs` log | Agency < $20 of model cost per business per week; Arena run < $0.50; student ≥ 10× cheaper than teacher with ≥ 85 % agreement | — |
| R11 | **Fast** | Wall clock | Arena: link → 3 tested concepts < 5 min | < 10 min |
| R12 | **People want it** | Real businesses | ≥ 30 Arena runs, ≥ 2 businesses on the agency, ≥ 5 quotes | ≥ 10 runs |

---

## 3. Criteria — the bar per judging criterion

### Impact (30 %)
- [ ] The problem lands in 10 s: "small businesses can't run Meta ads well, and pay Meta to find out their ads are bad".
- [ ] A real business with real revenue hands its ads to whynot (R4) and says so.
- [ ] R9 and R12 reached.
- [ ] Clear economics: model cost per business per week vs an agency's monthly fee vs $4.5k–$11k per traditional pre-test.
- [ ] Why Meta wants it: real new creative for Andromeda, small advertisers who succeed and stay, built on Muse + Ad Library + Ads MCP.

### Use of Meta models (25 %)
- [ ] Each model does something only it can do here (see README), one sentence each.
- [ ] **Surprise:** viewer agents that *watch* a feed of real competitor ads; Ad Library reach data as persona ground truth; SAM-tracked counterfactuals.
- [ ] Open weights on the critical path (viewers) **and** distilled/trained (student viewer) — Best Open Weights prize.
- [ ] Contributor tier never touches partner data.

### Technical depth (20 %)
- [ ] Validation is the technical hero: R1–R3 with baselines and confidence intervals.
- [ ] A real agent team: roles, tools, guards, autonomy levels, caps, retries, verifiable log (Agents 102).
- [ ] Teacher → student distillation measured (R10).
- [ ] One command reproduces every number.
- [ ] Clean modules, tests on the core (composer, guards, SSR, autopilot rules, validation stats).

### Demo (25 %)
- [ ] Hook in 15 s: a founder who wants his ads done for him; the agency takes over.
- [ ] The loop on screen: research → concepts → simulated feed → why not → evolution → published.
- [ ] Days of autopilot compressed: the report, the pauses, the new concepts, real numbers.
- [ ] Proof on screen: R1/R2/R3, the predictions vs reality.
- [ ] Live, no manual step; simulated numbers labelled.
- [ ] A judge can paste their own link in the Arena.
- [ ] 30 s cut for X that stands alone.

---

## 4. Anti-goals

- Claiming per-person ads, or scroll / retention prediction.
- Unlabelled simulated numbers; reliability claims without `validate/` behind them.
- An ad generator with a score bolted on, or a scoring tool with no generator.
- Variations sold as concepts.
- Re-implementing Meta's bidding or delivery.
- Partner data in the repo or visible un-anonymised.
- Generated product / app pixels.
- Any live spend without written consent, a hard cap and explicit approval.

---

## 5. Levers from ~10 % to ~20 % (in order)

1. **Backtest on the partner's history (R1)** — get his data today. Critical path.
2. **Live pilot + predictions published before results (R4, R5)** — first live ads by ~Oct 31 to have results by Nov 3–4.
3. **Distilled student viewer on open weights (R10)** — Fireworks workshop Oct 30.
4. **Real users (R12)** — Arena public by Nov 2.
5. **Build in public** — daily X posts; daily presence at Meta office hours.
6. **Live interactive finale** — "give us a brand, the agency starts on it now".
