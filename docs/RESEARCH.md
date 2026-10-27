# Research behind the product

Each design choice is grounded in published work or market data. Sources at the bottom. Market figures from vendor or agency blogs are marked as such.

## 1. The creative is the last lever — and it's blind

- Under Meta's Andromeda retrieval and GEM ranking, detailed targeting is a suggestion; practitioners summarise it as **"the creative is the targeting"** (agency blogs).
- Andromeda groups near-identical ads (industry calls it "Entity ID"); variations compete with each other. Practitioners recommend **concept-level diversity** (pain point, persona, awareness level, format), not cosmetic variants. No official similarity threshold is published.
- A Common Thread Collective analysis: well under 1 % of ads drive most spend.
- Creative fatigue window fell to 2–3 weeks (2026, from 4–6 weeks in 2024); brands testing 20+ new ads per month see higher ROAS (CTC, 170+ brands).

→ **whynot generates distinct concepts and checks diversity before shipping.**

## 2. Meta automates everything else

- Advantage+ end-to-end solutions at a $75B+ annual run-rate (Meta Q2 2026); ~10M advertisers used a gen-AI creative tool in Q3 2026, mostly SMBs.
- Business AI assistant (testing, Oct 2026) plans campaigns, generates creative, adjusts budgets; Ads MCP open to partners; Brand Memory; Creative Studio.
- Main advertiser complaint: black box, no explanation of what works (AdExchanger, Mediaweek).

→ **whynot builds on Meta (Muse, Ad Library, Ads MCP) and adds what the platform can't: pre-spend, explained, measured.**

## 3. LLM synthetic consumers work — if asked the right way

"LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings" (arXiv 2510.08338, PyMC Labs & Colgate-Palmolive): direct 1–5 scores are unrealistic; free text mapped to a Likert distribution by embedding similarity (**SSR**) reaches ~90 % of human test–retest reliability on 57 concepts / 9,300 responses. Open source: `pymc-labs/semantic-similarity-rating`.

Limit: this validates **purchase intent on concepts**, not scroll-stopping or attention.

→ **Viewer agents output free text → SSR; we simulate cognitive reactions and validate them ourselves.**

## 4. Context changes attention

AdGazer (University of Maryland & Tilburg, 2026): attention to an ad depends on the surrounding content; tested on 3,500+ ads with eye tracking. Attention-prediction tools trained on eye-tracking exist (Amplified AttentionAI, May 2026).

→ **We judge ads inside a feed of real competitor ads, not in isolation, and we don't compete on pixel-level attention.**

## 5. Learning from performance beats imitation

Meta's AdLlama (arXiv 2507.21983): RL from performance feedback (historical CTR as reward) raised CTR by 6.7 % vs supervised imitation in a 10-week A/B test across ~35,000 advertisers.

→ **The simulator is the pre-spend reward; real metrics recalibrate it; the student viewer can be trained on both.**

## 6. Pre-testing is expensive; synthetic research is hot

- Kantar LINK AI self-serve from ~$4,500 (US), System1 Pro ~$11,250 per ad (comparison blogs).
- Synthetic research raised $1.5B+; Simile $100M (Index, Feb 2026); Qualtrics added synthetic respondents (market-map blogs).

→ **A validated, cheap, competitive-context pre-test for SMBs is open.**

## 7. Ad Library as ground truth

Under the DSA, EU-delivered ads expose start dates, EU reach and reach by age/gender/country; no spend or engagement for commercial ads. Long-running ads are a common practitioner proxy for "this ad pays" — a noisy one.

→ **Reach breakdowns ground the personas; longevity is one validation signal (R3), not the only one.**

## 8. Uplift and retargeting (kept as background)

Ghost Ads (Johnson, Lewis, Nubbemeyer): retargeting lifts purchases +10.5 % with a proper control group, less than attribution suggests. Criteo uplift dataset (CC BY-NC-SA 4.0). Not core to the current product; holdouts stay the right way to measure real outcomes later.

## Sources

- Andromeda & creative diversity: https://jetfuel.agency/metas-2026-algorithm-update-what-andromeda-changed-and-how-to-adapt-your-ads/ , https://www.exposure.com.au/blog/meta-andromeda-creative-targeting , https://nikhil.pro/meta-ads-creative-similarity-explained/ , https://www.precis.com/resources/meta-andromeda-and-creative-strategy-what-actually-changed-and-what-didnt
- Meta updates: https://adsuploader.com/blog/meta-ads-updates , https://www.socialsamosa.com/industry-updates/meta-ai-advertising-tools-cannes-lions-12065586 , https://www.fool.com/earnings/call-transcripts/2026/10/21/meta-meta-q3-2026-earnings-call-transcript/
- Black box: https://www.adexchanger.com/commerce/more-performance-less-transparency-inside-metas-advantage-shopping-black-box/
- SSR: https://www.emergentmind.com/papers/2510.08338 , https://github.com/pymc-labs/semantic-similarity-rating
- AdGazer: https://techxplore.com/news/2026-02-ad-ai-attention-content-context.html ; Amplified: https://itbrief.asia/story/amplified-launches-attentionai-to-predict-ad-attention
- AdLlama / RLPF: https://arxiv.org/abs/2507.21983
- Pre-testing prices: https://www.koji.so/blog/best-ad-testing-software-2026
- Synthetic research: https://fish.dog/news/synthetic-research-platforms-the-2026-market-map
- Ad Library data: https://adlibrary.com/posts/ad-transparency-data-landscape
- Fatigue / volume: https://rocketium.ai/academy/all/ad-fatigue-statistics , https://jetfuel.agency/meta-ads-strategy-for-dtc-ecommerce-brands-in-2026-the-andromeda-playbook/
- Ghost Ads: https://conference.nber.org/confer/2016/EoDs16/Johnson_Lewis_Nubbemeyer.pdf ; Criteo uplift: https://ailab.criteo.com/?p=859
- McKinsey agents for growth: https://www.mckinsey.com/capabilities/growth-marketing-and-sales/our-insights/agents-for-growth-turning-ai-promise-into-impact ; BCG creativity: https://www.bcg.com/publications/2024/genais-influence-on-future-creativity-in-marketing
