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
  config.py            settings from .env (one place)
  costs.py             prices + append-only cost ledger
  models.py            ModelClient: the ONLY way to call a model (logs cost of every call)
  ingest/adlibrary.py  competitor ads from the Ad Library (tokens stripped, retries)
  assets/sam.py        SAM 3.1 output parser (cutouts of real product / app screens)
  create/
    templates.py       concept + genome (YAML), validation, sampling, mutation, variant ids
    composer.py        deterministic static ads from a genome (Pillow)
    guards.py          checks every ad must pass (product pixels, legibility, palette, policy)
  sim/
    personas.py        personas allocated from real reach data
    feed.py            market feeds (balanced exposure) and candidate feeds
    viewer.py          viewer agents: prompt, strict JSON parsing, retries, parallel runs
    scores.py          per-ad scores (preference lift, intent, objections)
  run/autopilot.py     autonomy levels, caps, approval rules, loser/fatigue review, action log
  validate/
    stats.py           AUC, pairwise accuracy, bootstrap CIs, Wilson, binomial test
    longevity.py       R3: simulator vs Ad Library longevity
scripts/               thin command-line entry points (argparse); no logic that isn't in src/
templates/examples/    hand-written example templates
tests/                 one test file per module + test_hardening.py (regressions) + test_properties.py (invariants)
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

- `policy_safe` guard is not implemented yet (needs a model); until it is, no ad is publishable.
- Composer v0 renders `static_1080` only; reels need ffmpeg.
- SAM mask payloads are parsed, not decoded yet.
- Autopilot decides; it does not call Meta yet.
- Hypothesis runs a few hundred examples per property in CI; raise `max_examples` locally when changing safety code.
