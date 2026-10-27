# Targets — the product we ship and the bar it must clear

This is the reference we loop on. Every few days, and before submitting, go through each criterion and mark it ✅ / 🟡 / ❌ with the measured value. If a criterion is ❌ two days before the deadline, cut scope elsewhere, never lower the bar silently. Changing a target = one line in `DECISIONS.md` with why.

The bar: **not a wrapper around Meta APIs.** A judge must leave thinking "this is a product I'd install", and a merchant must want to try it on their own store.

---

## 1. The final product (what exists on Nov 4)

Three surfaces, one engine.

### A. Public "why not?" teardown — anyone, no install
Paste a Shopify store URL → in about a minute:
- the store's likely **objection map** (what is probably stopping visitors: slow shipping vs competitors, no size guide, few reviews, price vs market…), each one backed by evidence from the store pages and competitors' ads;
- the **competitor angles** that work in this market (long-running Ad Library ads, who they actually reach);
- **3 ready-to-use ads**, each answering one objection, built with the store's real product pixels;
- **store fixes** ranked by impact.

This is the viral, community-vote and "people actually use it" surface. Product images of third-party stores are shown only to that user, never in our own demo or posts (rights).

### B. Merchant dashboard — connected store (partner store in the demo)
- Objection map from **real browsing behaviour**, per visitor.
- Templates per objection, variants, panel scores, guards.
- **Agent log**: every decision, tool call, guard result and $ cost, readable by the merchant.
- Launch to Meta (sandbox / capped budget) or export ready-to-upload campaigns.
- Weekly report + store fixes.

### C. On-site answer — free proof channel
A banner or cart message on the partner store that answers the visitor's objection live (and the abandoned-cart email). This is where we measure real behaviour without ad spend.

### The engine (shared)
Objection inference → template choice → deterministic composition with the SAM cutout → guards → synthetic panel that **looks at the final image** → agent decides what ships, within a budget and with every action logged.

---

## 2. Results we want (measured, shown in the demo)

Every number below is measured on our data, logged, and reproducible from the repo. Target = what we aim for. Floor = below this we don't show the number, we fix the system.

| # | Result | How we measure | Target | Floor |
|---|---|---|---|---|
| R1 | **Objections are right** | Top-1 accuracy vs ground truth from an exit question on the partner store ("What stopped you?") and the human-test scenarios | ≥ 70 % on 6 classes, and **≥ +10 pts over the rule baseline** | beats rules |
| R2 | **Personalized ads convince more** | Blind paired human test, generic vs objection ad, same product | n ≥ 80, preferred ≥ 65 %, p < 0.01 | n ≥ 50, p < 0.05 |
| R3 | **The panel predicts humans** | Agreement of panel ranking vs human ranking on the same pairs | ≥ 75 % pairwise agreement | ≥ 65 % |
| R4 | **The panel predicts the market** | Panel score vs Ad Library longevity: does it tell long-running (> 60 days) competitor ads from short-lived ones? | AUC ≥ 0.65 | AUC > 0.55 |
| R5 | **Product never invented** | Pixel diff on the product region vs SAM cutout, all shipped ads | 0 px, 100 % of ads | — (hard rule) |
| R6 | **Cheap at scale** | `costs` log | Teardown < $0.50 / store · onboarding < $5 / store · **0 LLM calls per visitor**, < 50 ms | — |
| R7 | **Fast** | Wall clock, public teardown | < 90 s URL → 3 ads | < 3 min |
| R8 | **Real behaviour moves** | Partner store A/B, generic vs objection banner/email | Measured CTR / add-to-cart lift with a confidence interval, whatever the sign | test running ≥ 4 days |
| R9 | **People want it** | Real merchants who ran the teardown on their own store | ≥ 20 stores, ≥ 5 quotes, ≥ 3 "I'd install it" | ≥ 10 stores |
| R10 | **Real Meta signal** *(optional, needs our OK to spend)* | Meta A/B test (split test) via Marketing API, generic vs objection ad, hard cap ~€100 | CTR / cost per click difference with CI | — |

### What Meta data gives us (replaces Criteo as the main proof)
- **Ad Library = free ground truth on the market.** We can't see competitors' clicks, but longevity and EU reach are a real proxy of "this ad pays". R4 checks the panel against it. The age/gender reach breakdown tells us who each angle really reaches → personas for the panel.
- **Marketing API insights** (impressions, clicks, CTR, CPC, conversions) only exist for ads we run. A small capped split test (R10) gives a real Meta number; never without explicit approval.
- **Meta Conversion Lift studies** need much more spend and account eligibility → out of reach; the holdout stays a product feature, shown as such.
- Uplift / persuadables: kept as a product mechanism (holdout design, explained), Criteo only as a small optional side check. Not a pillar.

---

## 3. Criteria — the bar per judging criterion

Each line is pass/fail. "Excellent" means all ✅.

### Impact (30 %)
- [ ] A merchant understands the value in **10 seconds** from the landing page.
- [ ] The public teardown works on **any** Shopify store, not just ours.
- [ ] R9 reached: real merchants used it and said so, with quotes we can show.
- [ ] The output is actionable the same day: ads downloadable, fixes concrete.
- [ ] The business case is in numbers: wasted budget avoided, cost per store, outcome-based pricing.

### Use of Meta models (25 %)
- [ ] Each Meta model does something **only it could do here**, and we can say why in one sentence (Wonder: whole market in one cached call · Spark computer use: reads ad snapshots and/or browses the store as shoppers · Spark Open: multimodal panel judging the real image · Image: scenes consistent across a series · SAM: pixel-exact product).
- [ ] At least **one use that surprises Meta** (candidates: synthetic shoppers browsing the store with computer use; panel that sees the ad and is validated against humans and Ad Library longevity).
- [ ] Open-weights model is on the critical path, not a side demo (Best Open Weights prize).
- [ ] Contributor tier never touches real visitor or store data.

### Technical depth (20 %)
- [ ] It's an **agent**, not a pipeline: it plans, calls tools, checks guards, retries, and stays inside a budget. Every action is logged and **verifiable** (Agents 102).
- [ ] Big model teaches, small model serves — and the small model is **measured** against the big one and against ground truth (R1).
- [ ] Deterministic composition, pixel guard, cost wrapper: tested.
- [ ] One command reproduces every number in the demo from the repo.
- [ ] Clean repo: modules with clear inputs/outputs, tests on the core, README that a judge can follow.

### Demo (25 %)
- [ ] The hook lands in 20 s: same jacket, two visitors, two different ads.
- [ ] **Live**, no manual step, no mock screen (or labelled "simulated").
- [ ] At least one moment where the viewer goes "wow" (an agent visibly working; the ad assembling; the panel reacting; the cost counter at a few cents).
- [ ] The three proof numbers (R1, R2, R3) on screen, real.
- [ ] A judge can open the public URL and run it on their own store.
- [ ] X post with a 30-second cut that stands on its own (Most Viral, Community Vote).

---

## 4. Anti-goals

- A dashboard that only displays Meta API responses.
- An LLM call per visitor.
- Generated product pixels.
- Numbers we can't reproduce, or simulated numbers not labelled.
- Features shown in the demo that don't work live.
- Spending money on Meta without an explicit cap and our explicit OK.
