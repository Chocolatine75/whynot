# whynot

**An autonomous growth marketer for Shopify stores that finds out why each visitor didn't buy, and answers it with an ad built for them.**

Built for the [Meta Global AI Developer Hackathon](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) (Oct 26 – Nov 4, 2026), Indie Developer track, theme *Build for Your World*.

---

## The problem

Small e-commerce brands are losing on Meta ads:

- Ads wear out in 2–3 weeks under Meta's Andromeda delivery system, so brands need 20+ new creatives a month to keep performing. A small shop can't produce that.
- Retargeting shows everyone the same "you forgot this" ad. It ignores *why* the visitor left: sizing doubt, shipping cost, trust, price.
- Retargeting spends heavily on people who would have bought anyway. Attribution hides it, and the merchant pays for sales the ad didn't cause.

## What whynot does

1. **Understands why visitors don't buy.** From Shopify browsing behaviour, it infers each visitor's likely objection (size, price, shipping, trust…).
2. **Studies what works in the market.** It reads competitors' long-running ads from the Meta Ad Library, including who they actually reach, and writes a strategy brief.
3. **Builds reusable ad templates**, one family per objection, then personalizes them per visitor at near-zero cost. The real product is always composited pixel-exact (SAM 3.1), never hallucinated.
4. **Pre-tests every variant** on a synthetic consumer panel before spending a cent.
5. **Targets only persuadable visitors** with an uplift model, so budget isn't wasted on sure buyers.
6. **Launches, monitors and refreshes** campaigns on Meta through the Marketing API.
7. **Proves causal sales** with a holdout group, and tells the merchant what to fix in the store.

## Built with Meta models

| Model | Role |
|---|---|
| Muse Wonder | Market brief from the whole competitor ad corpus in one long-context call |
| Muse Spark | Objection labelling, copywriting, computer use to read ad snapshots |
| Muse Spark Open (via Baseten) | Synthetic consumer panel at scale |
| Muse Image | Ad scenes, consistent across a series |
| SAM 3.1 | Exact product cutout composited onto every scene |

## Docs

- [Product](docs/PRODUCT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Research behind the product](docs/RESEARCH.md)
- [Competitive landscape](docs/COMPETITION.md)
- [Hackathon context and rules](docs/HACKATHON.md)
- [10-day plan](docs/PLAN.md)
- [Demo script](docs/DEMO.md)
- [Decision log](docs/DECISIONS.md)

## Built during the hackathon

Everything in this repository was written during the hackathon, starting Oct 26, 2026. The commit history is the record.

## Team

- Matteo Atkinson ([@Chocolatine75](https://github.com/Chocolatine75))
- Tom Angles ([@Tooom123](https://github.com/Tooom123))

## License

MIT
