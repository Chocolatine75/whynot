# Engineering guide

How the code is organised, the rules every change follows, and what "done" means. Read this before writing code (humans and agents alike). The product is in `PRODUCT.md`, the design in `ARCHITECTURE.md`, the bar in `TARGETS.md`.

## One command

```bash
./scripts/check.sh      # lint (ruff) + types (mypy) + tests with coverage (pytest); CI runs exactly this
```

CI (`.github/workflows/ci.yml`) runs it on every push to `master` and on every pull request. A red CI blocks the merge.

## Layout

The package follows the agency loop. Each stage reads and writes plain data (dataclasses, JSONL, YAML, PNG) that can be inspected on disk.

```
src/whynot/
  cli.py               `whynot create ...` (entry point)
  config.py            settings from .env (one place)
  costs.py             prices + append-only cost ledger + spend report (`whynot costs`)
  models.py            ModelClient: the ONLY way to call a model (logs cost of every call, run budget)
  cassette.py          recorded model answers: WHYNOT_CASSETTE=record|replay|off (replay = $0, offline)
  budget.py            per-command model cap: estimate refused before running, hard stop during it
  jsonio.py            JSON out of model answers
  agency/
    create.py          the `create` pipeline: stages, run folder, resume, events
    report.py          the owner's report (report.md)
  agents/
    ask.py             ask_json: validated answers, repaired with the exact errors, never guessed
    scout.py           search terms → Ad Library → real competitors (noise filtered)
    strategist.py      Muse Wonder: personas, objections, angles, claims — every quote verified verbatim
    director.py        templates + ad copy; numbers only from verified claims, policy, diversity (CopyRules)
    evolver.py         one-element mutations answering simulated objections
  ingest/
    adlibrary.py       competitor ads from the Ad Library (tokens stripped, retries)
    appstore.py        App Store page, reviews, real screenshots, competitor apps
  assets/
    sam.py             SAM 3.1 output parser (cutouts of real product / app screens)
    brand.py           brand palette from the app icon (legible by construction)
  create/
    templates.py       concept + genome (YAML), validation, sampling, mutation, variant ids
    composer.py        deterministic static ads from a genome (Pillow)
    guards.py          checks every ad must pass (product pixels, legibility, palette, policy)
    policy.py          rule-based Meta ad-policy checks (personal attributes, absolutes, bait)
  sim/
    arena.py           fair feeds: brand name, head-to-head slots, placebos, bias flag
    personas.py        personas allocated from real reach data
    feed.py            market feeds (balanced exposure) and candidate feeds
    viewer.py          viewer agents: prompt, strict JSON parsing, retries, parallel runs, answer cache
    scores.py          per-ad scores (preference lift, intent, objections)
    tournament.py      round-robin games between our variants, Bradley-Terry ranking with CIs
  run/
    autopilot.py       autonomy levels, caps, approval rules, loser/fatigue review, action log
    campaign.py        campaign plan in Marketing API shape, validated; launch via the autopilot
    meta.py            Marketing API client (the only code that writes to an ad account)
    publish.py         publish a plan: autopilot-gated, all PAUSED, resumable (publish.json)
  validate/
    stats.py           AUC, pairwise accuracy, bootstrap CIs, Wilson, binomial test, Kendall tau, Bradley-Terry
    longevity.py       R3: simulator vs Ad Library longevity
    retest.py          test-retest noise floor: the smallest simulated difference reported as real
web/                   client platform (Next.js): lib/runs.ts reads run folders, lib/start.ts starts the engine,
                       components/AgencyRoom.tsx shows a run; tests in web/test (vitest)
scripts/               thin command-line entry points (argparse); no logic that isn't in src/
templates/examples/    hand-written example templates
tests/                 see "Kinds of tests" below; fixtures/ holds recorded real API responses
```

Adding a stage: new module in the matching sub-package, a module docstring that states its contract (inputs, outputs, guarantees, what it does *not* do), a test file, a line in the module table of `ARCHITECTURE.md`.

## Rules for code

1. **Every model call goes through `ModelClient`.** It checks the model has a price *before* calling, and logs the cost even when the call fails. Never import the OpenAI SDK elsewhere.
2. **No secrets in logs, files or errors.** Tokens are stripped from URLs (`strip_token`) and redacted from error messages (`redact`). `save_jsonl` refuses to write a token.
3. **Fail loudly on bad input, with a message that says what to fix.** Validate at module boundaries (templates, env, API responses, model answers) and raise a module-specific error (`TemplateError`, `ComposeError`, `ViewerParseError`, `SamParseError`, `AdLibraryError`). Never guess a value a model didn't give; count it as a failure.
4. **Deterministic by default.** Anything random takes a `seed`. The same inputs give the same output (composer pixels, feeds, samples, bootstrap CIs).
5. **Live actions only through `run/autopilot.decide`.** It enforces the cap, the autonomy level and the first-launch approval. Lowering spend is always allowed; raising it never exceeds the cap.
6. **Simulated numbers are labelled as simulated** wherever they are written (`"simulated": true` in experiment outputs, "simulated" in the UI).
7. **Thin scripts.** A script parses arguments, calls library functions, prints and writes results. If a script needs logic, that logic goes in `src/` with tests.
8. Style: ruff (line length 120), type hints on public functions, mypy clean. Docstrings and comments in English, short, saying *why*.

## Kinds of tests

| Kind | Where | What it proves |
|---|---|---|
| Unit | `test_<module>.py` | each function does what its docstring says, failure paths included |
| Contract | `test_appstore.py`, `test_adlibrary.py` + `fixtures/` | our parsers read **real recorded** Apple / Meta responses |
| Adversarial | `test_strategist.py`, `test_director.py`, `test_scout.py` | a model that invents quotes, numbers, ids or competitors is caught, repaired or refused, never trusted |
| Property | `test_properties.py`, `test_campaign.py`, `test_policy_brand.py` | invariants over thousands of random inputs (cap never exceeded, pixels never altered, buttons always legible) |
| End-to-end | `test_create_pipeline.py` on `world.py` | the whole `create` pipeline on a fake world (App Store, Ad Library, CDN, models) with the real model client: valid plan, reproducible images, no token leaks, costs match, resume re-bills nothing, failures stop cleanly |
| Regression | `test_hardening.py` | one test per bug found, named after it |
| Live | `test_live.py`, `pytest --live` | the real services still answer the way the contracts assume (free endpoints) |
| Platform | `web/test/*.test.ts` (vitest) + browser check | run folders read safely (path traversal, symlinks), inputs validated, engine started without a shell, formatting |
| Real run | `uv run whynot create ...` | the product on a real app, with a hard model budget; outputs in `outputs/runs/` (gitignored) |

## Rules for tests

- **No network, no keys.** Tests use fakes (`tests/fakes.py` for the model SDK, `httpx.MockTransport` for the Graph API). Real calls live in `scripts/` (smoke tests, experiments), never in `tests/`.
- **One regression test per bug**, in `tests/test_hardening.py` or the module's test file, named after the failure it prevents, with a one-line comment saying what the bug was.
- **Invariants get property tests** (Hypothesis, `tests/test_properties.py`) when they must hold for *any* input: the cap is never exceeded, product pixels are never altered, feeds give balanced exposure, parsers only raise their own error, statistics stay within their bounds.
- **Test the failure paths of safety code** (guards, autopilot, token handling) as carefully as the happy path.
- Coverage (lines + branches) must stay ≥ 90 % (`fail_under` in `pyproject.toml`); it is 96 % today. Don't add tests just for coverage: add the test that would catch a real mistake.
- A flaky test is a bug. If a test depends on a seed, check it on many seeds before relying on it.

## Definition of done

A change is done when:

- [ ] `./scripts/check.sh` passes locally and CI is green;
- [ ] new behaviour has tests, including failure paths; a fixed bug has a regression test;
- [ ] module docstring and `ARCHITECTURE.md` say what the module guarantees;
- [ ] decisions are in `DECISIONS.md` (one line + why), checkboxes in `PLAN.md`, a log line in `STATUS.md`;
- [ ] any number it produces is reproducible with one command and labelled simulated if it is;
- [ ] nothing secret or partner-private is in the diff.

## Known limits (be honest about them)

- `policy_safe` is rule-based (v0); a model-based review is planned. Meta's own review still applies.
- Composer v0 renders `static_1080` only; reels need ffmpeg.
- SAM mask payloads are parsed, not decoded yet.
- Autopilot decides and the campaign plan is in Marketing API shape; nothing calls Meta's write API yet.
- **Simulator:** the ranking *between our variants* is the reliable output (fair feeds, placebo-checked; on VietBuddy, variants now spread 0–4× while placebos score ~0). The size of the win *over competitors* is not proof of quality yet: the research market (EU/UK) includes ads for other products (other languages), so topic match inflates it. Validation against real results (R1, R4) is what will settle it.
- The ad font comes from the machine (Arial on macOS, DejaVu on Linux/CI) unless one is put in `assets/fonts/`: pixels can differ between machines. Shipping an open-licence font fixes it.
- Screenshots come from one App Store storefront: a French ad shows the US (English) screens. Per-language storefronts are next.
- Viewers see ad text (ours and competitors'), not images, to keep the comparison fair until creative capture exists.
- `--budget-usd` caps one invocation; a resumed run gets a fresh budget (finished stages are not re-billed).
- Hypothesis runs a few hundred examples per property in CI; raise `max_examples` locally when changing safety code.
