# whynot

**An AI ad agency for small businesses on Meta.** whynot's agents research your market and your customers, create ads for each customer profile, test every ad in a simulated Instagram feed before spending a cent, then publish, steer and report. The owner just checks.

Built for the [Meta Global AI Developer Hackathon](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) (Oct 26 – Nov 4, 2026), Indie Developer track, theme *Build for Your World*.

---

## The problem

- **Small businesses can't run Meta ads well.** An agency costs thousands a month. Doing it yourself means producing new concepts every 2–3 weeks (ads wear out fast under Meta's Andromeda delivery system), guessing what will work, and paying Meta to find out.
- **Meta automates delivery, not creation.** Targeting, bidding and budgets are automated; the creative is the last lever ("the creative is the targeting"). Advantage+ tweaks your visuals (backgrounds, text, video from a still); it doesn't create a new ad concept.
- **Testing costs real money.** The learning phase is testing with your budget. A proper pre-test from Kantar or System1 costs $4,500–$11,000 per ad. Even winners come with no explanation.

## What whynot does

The product is an agency. Its engine is a loop: **templates generate, the simulator judges, the agents evolve.**

1. **Research.** Agents pull competitors' ads from the Meta Ad Library (how long they run, who Meta really shows them to) and read the business's reviews, pages and past ads to find why people buy — and *why not*.
2. **Strategy.** Muse Wonder reads the whole corpus in one cached call and writes the strategy: customer profiles (personas), angles that work, angles nobody uses.
3. **Create.** A creative director agent writes ~10 templates. Each template is a distinct ad concept, backed by evidence, with a "genome" of parts that can change (hook, first shot, proof, persona, format).
4. **Produce.** Code assembles statics and short videos from the genes. The real product or app screen is cut out with SAM 3.1 and never generated; scenes come from Muse Image.
5. **Test before spending.** Every ad is placed in a simulated feed next to competitors' real ads. Viewer agents built from real Meta reach data (Muse Spark Open) say whether they get it, believe it, and why they wouldn't buy. Counterfactuals show which element helps or hurts.
6. **Evolve.** Agents mutate the genes until the ad wins the simulated feed.
7. **Run.** Winners are published through Meta's Ads MCP / Marketing API within the owner's caps. The agency rotates creative, pauses tired or losing ads, and ships new concepts every week. Meta's own systems keep handling bidding and delivery.
8. **Report and learn.** A weekly report says what was done and why; the owner approves or blocks. Real results recalibrate the simulator for that business.

**Personalised by profile, not by person.** Meta audiences need hundreds of people and Meta decides who sees what. whynot creates different concepts for different customer profiles; Meta delivers each to the people who respond.

**Why trust an autopilot?** Every ad is tested before it costs anything, spend is capped, every action is logged and explained, and the simulator's reliability is measured and published.

## Built with Meta models

| Model | Role in the agency |
|---|---|
| Muse Wonder | Strategist: reads the whole market and customer corpus in one cached 1M-token call |
| Muse Spark | Agents (scout, researcher, creative director, analyst, account manager); computer use to capture competitors' ad creatives |
| Muse Spark Open (via Baseten) | Viewer agents in the simulated feed — thousands of calls on open weights |
| Distilled viewer (Muse Glimmer or fine-tuned Spark Open) | Cheap student viewer trained on the big one |
| Muse Image | Scenes and first frames, consistent across a series |
| SAM 3.1 | Exact product / app-screen cutouts; element tracking for counterfactuals |
| Muse Voice Transcribe | Transcripts of video ads for the viewers and captions |

Plus the Meta Ad Library API (research, feed, calibration) and the Ads MCP / Marketing API (publishing, real metrics).

## Getting started

```bash
uv sync                      # install (Python 3.12+)
cp .env.example .env         # then fill in your keys
uv run pytest                # unit tests, no network
uv run python scripts/smoke_models.py   # calls every model once, a few cents
uv run python scripts/fetch_competitors.py --name demo --page-ids <ids> --countries FR
```

Every model call goes through `whynot.models.ModelClient`, which logs its real cost to `outputs/costs.jsonl`.

## Docs

- [Targets: final product, results, criteria](docs/TARGETS.md) ← the bar
- [Product](docs/PRODUCT.md) · [Architecture](docs/ARCHITECTURE.md)
- [Plan](docs/PLAN.md) · [Status / session handoff](docs/STATUS.md)
- [Demo script](docs/DEMO.md)
- [Research](docs/RESEARCH.md) · [Competitive landscape](docs/COMPETITION.md)
- [Prior art](docs/PRIOR_ART.md) · [Meta APIs notes](docs/META_APIS.md) · [Hackathon context and rules](docs/HACKATHON.md) · [Decision log](docs/DECISIONS.md)

## Built during the hackathon

Everything in this repository was written during the hackathon, starting Oct 26, 2026. The commit history is the record.

Related prior work we learned from (ideas only, no code reused): [VoodRadar](https://github.com/edouardfoussier/voodoo-anthropic-hack-winner), winner of the Voodoo × Anthropic Hack 2026. See [Prior art](docs/PRIOR_ART.md).

## Team

- Matteo Atkinson ([@Chocolatine75](https://github.com/Chocolatine75))
- Tom Angles ([@Tooom123](https://github.com/Tooom123))

## License

MIT
