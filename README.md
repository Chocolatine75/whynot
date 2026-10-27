# whynot

**A flight simulator for Meta ads.** Drop your ad into a simulated Instagram feed, next to your competitors' real ads. Thousands of viewer agents, built from real Meta audience data, react to it and tell you *why not*. Agents then evolve the ad, generation after generation, until it wins the feed — before you spend a cent.

Built for the [Meta Global AI Developer Hackathon](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) (Oct 26 – Nov 4, 2026), Indie Developer track, theme *Build for Your World*.

---

## The problem

On Meta in 2026, the machine automates targeting, bidding and budgets. **The creative is the only lever left — "the creative is the targeting" — and it is made blind.** Advertisers guess, pay Meta to find out (the learning phase is testing with real money), and even when an ad wins, nobody knows why. Big brands pay $4,500–$11,000 per ad for a pre-test score. Small advertisers — DTC brands, mobile apps — gamble their budget.

## What whynot does

1. **Reads the market and the customer.** Competitors' ads from the Meta Ad Library (who they really reach, how long they run), reviews, on-site or in-app behaviour: what makes people buy, and *why not*.
2. **Invents ad concepts, not variations.** Agents write ~10 templates, each a distinct concept grounded in evidence, with a "genome" of parts that can change (hook, first shot, proof, persona, format). Andromeda rewards concept diversity; near-duplicates get grouped and cannibalise.
3. **Composes variants cheaply.** Deterministic code assembles statics and short videos. The real product (or app screen) is cut out with SAM 3.1 and never generated.
4. **Simulates the feed.** Viewer agents (Muse Spark Open, multimodal) see your ad among your competitors' and react: do they get it, believe it, what's their objection, would they buy, which ad do they prefer?
5. **Explains why.** Counterfactuals: remove or swap one element (tracked by SAM 3.1), re-simulate, measure its effect.
6. **Evolves the ad.** Creative agents read the objections and counterfactuals and mutate the genome until the ad wins the simulated feed.
7. **Proves the simulator.** Backtested on design partners' real ad history, checked against human panels and Ad Library longevity, and pre-registered public predictions. Every simulated number is labelled as simulated.
8. **Launches and learns.** Winners go to Meta through the Ads MCP / Marketing API (capped, sandbox by default); real results recalibrate the simulator for that account.

## Built with Meta models

| Model | Role |
|---|---|
| Muse Spark Open (via Baseten) | Viewer agents: watch the ad in the feed, react, explain — thousands of calls |
| Muse Glimmer / fine-tuned Spark Open | Distilled viewer: cheap student trained on the big viewer (and real outcomes) |
| Muse Wonder | Reads the whole competitive feed and customer corpus in one cached 1M-token call → strategy |
| Muse Spark | Agents (strategist, creative director, critic), computer use to capture Ad Library creatives |
| Muse Image | Scenes, first frames, concept assets — consistent across a series |
| SAM 3.1 | Exact product / app-screen cutouts; element tracking in video for counterfactuals |
| Muse Voice Transcribe | Transcribes competitors' and our video ads for the viewers and captions |

Plus the Meta Ad Library API (feed + calibration), Marketing API and Ads MCP (launch + real metrics).

## Docs

- [Targets: final product, results, criteria](docs/TARGETS.md) ← the bar
- [Product](docs/PRODUCT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Plan](docs/PLAN.md) · [Status / session handoff](docs/STATUS.md)
- [Demo script](docs/DEMO.md)
- [Research behind the product](docs/RESEARCH.md) · [Competitive landscape](docs/COMPETITION.md)
- [Meta APIs notes](docs/META_APIS.md) · [Hackathon context and rules](docs/HACKATHON.md) · [Decision log](docs/DECISIONS.md)

## Built during the hackathon

Everything in this repository was written during the hackathon, starting Oct 26, 2026. The commit history is the record.

## Team

- Matteo Atkinson ([@Chocolatine75](https://github.com/Chocolatine75))
- Tom Angles ([@Tooom123](https://github.com/Tooom123))

## License

MIT
