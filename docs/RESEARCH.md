# Research behind the product

Each design choice is grounded in published work or market data. Sources at the bottom.

## 1. Retargeting pays for sales that would have happened anyway

Uplift modelling splits customers into sure things, lost causes, sleeping dogs and **persuadables**. Only persuadables generate incremental sales, and classic response models mostly target sure things because they can't tell them apart.

Retargeting does work, but less than attribution suggests: the "Ghost Ads" field study (Johnson, Lewis, Nubbemeyer) measured **+10.5% purchases and +17.2% site visits** with a proper control group. Meta's default attribution also credits view-through purchases that may have happened anyway.

→ **whynot targets persuadables and measures lift with a holdout.**
→ Public data to prove it: Criteo's large-scale uplift datasets from randomised ad experiments (Diemert et al.). Check licence before use.

## 2. Training generation on performance beats imitation

Meta's AdLlama paper (arXiv 2507.21983): post-training an ad text model with **reinforcement learning from performance feedback (RLPF)**, using historical CTR as reward, raised CTR by **6.7%** vs a supervised imitation model, in a 10-week A/B test across ~35,000 advertisers and 640,000 variations.

→ **whynot closes the loop**: performance (and, before launch, the synthetic panel) is the reward signal that decides which templates and slots survive.

## 3. LLM synthetic consumers work, if you ask them the right way

"LLMs Reproduce Human Purchase Intent via Semantic Similarity Elicitation of Likert Ratings" (arXiv 2510.08338, PyMC Labs & Colgate-Palmolive): asking an LLM for a 1–5 score gives unrealistic distributions; asking for free text and mapping it to a Likert distribution by embedding similarity to anchor statements (**SSR**) reaches **~90% of human test–retest reliability** on 57 product concepts and 9,300 human responses. Open-source implementation: `pymc-labs/semantic-similarity-rating`.

→ **whynot pre-tests every ad on a panel using SSR**, and we validate the panel against our own human test.

## 4. Retargeting creative should answer the objection

Practitioner consensus: retargeting creative must address the reason the visitor didn't buy (price, trust, sizing, delivery), not reintroduce the product. Today this is done by hand with 2–3 generic objections per category.

→ **whynot infers the objection per visitor and maps it to a template family.**

## 5. Creative volume is the bottleneck

- Under Meta's Andromeda system, the creative fatigue window dropped from 4–6 weeks (2024) to **2–3 weeks (2026)**.
- Brands testing **20+ new ads per month see 65% higher ROAS** than those testing fewer than 10 (Common Thread Collective, 170+ brands).
- E-commerce CPMs on Meta are up ~20% year over year in 2026.

→ **whynot produces and refreshes creatives continuously at near-zero marginal cost.**

## 6. Market thesis

- YC Summer 2026 RFS: **AI-native service companies** that sell the service, not the software.
- a16z (Big Ideas 2026): AI apps judged on outcomes, enabling outcome-based pricing.

→ **whynot is an AI agency, priced on results.**

## Sources

- Ghost Ads: https://conference.nber.org/confer/2016/EoDs16/Johnson_Lewis_Nubbemeyer.pdf
- Uplift modelling: https://en.wikipedia.org/wiki/Uplift_modelling
- Privacy-robust incrementality (refs to Criteo uplift datasets): https://arxiv.org/pdf/2606.03878
- AdLlama / RLPF: https://arxiv.org/abs/2507.21983
- SSR synthetic consumers: https://www.emergentmind.com/papers/2510.08338 , https://github.com/pymc-labs/semantic-similarity-rating
- Retargeting creative by objection: https://www.adstellar.ai/blog/retargeting-ad-creative
- Ad fatigue stats: https://rocketium.ai/academy/all/ad-fatigue-statistics
- Creative volume vs ROAS, CPMs: https://jetfuel.agency/meta-ads-strategy-for-dtc-ecommerce-brands-in-2026-the-andromeda-playbook/
- YC RFS: https://ai-native-agency.com/blog/yc-ai-native-agency
- a16z Big Ideas 2026: https://a16z.com/newsletter/big-ideas-2026-part-1/
