# Partner pilot: Monday Nov 2

One day with the partner (VietBuddy) to get consent and data, measure R1, publish the predictions, and launch the
pilot within his cap. This file is the checklist and the message to send. Rules from `CLAUDE.md` apply: written
consent, a hard cap set by him, his explicit approval before the first live launch, every action logged.

## 1. Consent message (send before anything else, keep his written answer)

> Hi! Before we start, here is exactly what whynot would do with your ad account. Please reply "I agree" (or tell
> me what to change).
>
> 1. **Access.** Read access to your Meta ad account (ad history, results per ad) and, for the pilot, permission to
>    create and pause ads. You can remove it at any time in Business Settings.
> 2. **Your past ads.** We use your past ads and their results to measure whether our simulator would have ranked
>    them the way reality did. Your data stays on our machines (`data/private/`), never in our public repo. In our
>    demo and write-up, your results appear only as aggregate numbers (for example "68 % of pairs ranked right"),
>    and your app is named only if you say yes: **may we name VietBuddy in the demo? yes / no**.
> 3. **Cap.** We never spend more than **€___ per day** in total on the pilot (you choose). The software refuses
>    anything above it.
> 4. **Approval.** Nothing goes live without your OK. Mode: **you approve each launch** (we send you the ads first)
>    or **autopilot within the cap** (we pause losers and launch new ads, you can block anything). Choose one.
> 5. **Dates.** From Monday Nov 2 to **___** (we suggest one week). You can stop it at any time: one command pauses
>    everything we created within seconds.
> 6. **What we create.** New ads (images and short videos) using your real app screens and store page, never
>    generated product pixels. Every ad, pause and budget change is logged with its reason.

Record: his answer (screenshot) in `data/private/partner/consent/`, and one line in `DECISIONS.md` (date, cap,
mode, end date, naming yes/no).

## 2. Before Monday (us)

- [ ] `MODEL_API_KEY` active (credits visible), `uv run python scripts/smoke_models.py` green.
- [ ] Sandbox ready: `META_SANDBOX_AD_ACCOUNT_ID`, `META_SANDBOX_TOKEN`, `META_PAGE_ID` (setup in `META_APIS.md`).
- [ ] A fresh VietBuddy run: `uv run whynot create <App Store URL> --countries US --daily-cap <his cap>`.
- [ ] Sandbox rehearsal: `uv run whynot publish outputs/runs/<run> --approve "<name>"`, then
      `uv run whynot stop outputs/runs/<run> --by "<name>"` → everything PAUSED in seconds.
- [ ] R1 rehearsal on fake data: `uv run pytest tests/test_backtest.py` (and the dry run below on a fake export).

## 3. Monday, in order

1. **Consent** (section 1). No access before his written "I agree".
2. **Data.** Either he exports from Ads Manager (level: Ads; columns: Ad ID, Ad name, Amount spent, Impressions,
   Link clicks, Results, Body, Title; whole lifetime) and we save it as `data/private/partner/ads.csv`, or he gives
   us read access and we set `PARTNER_AD_ACCOUNT_ID` + `META_ACCESS_TOKEN`.
3. **R1** (protocol pre-registered in `DECISIONS.md` on Oct 31, do not change it after seeing data):
   ```bash
   uv run python scripts/r1_backtest.py --name vietbuddy --csv data/private/partner/ads.csv --brand VietBuddy --dry-run
   uv run python scripts/r1_backtest.py --name vietbuddy --csv data/private/partner/ads.csv --brand VietBuddy
   # or --api instead of --csv (creatives included, so the image conditions run too)
   ```
   Commit only `validate/results/r1-vietbuddy.json` (numbers only). Whatever the result, it is published.
4. **His best videos** (E14-9, optional): MP4s with consent into `data/private/partner/videos/`.
5. **Predictions before results** (E8-4): rank the ads we will launch with the simulator, write the ranking to
   `validate/predictions/pilot-<date>.json`, then
   `sha256sum validate/predictions/pilot-<date>.json` → commit + push the file and post the hash publicly
   (X / Discord) **before** activation.
6. **Publish PAUSED** on his account: set `META_AD_ACCOUNT_ID`, `META_ACCESS_TOKEN`, `META_PAGE_ID`,
   `AUTONOMY_LEVEL` (`propose` or `autopilot` as he chose), `MAX_DAILY_AD_SPEND_EUR` = his cap, then
   `uv run whynot publish outputs/runs/<run> --live --objective traffic --approve "<his name>"`.
   Show him the ads in Ads Manager (link printed).
7. **Activate** only on his explicit OK: `uv run whynot publish outputs/runs/<run> --live --activate-only --approve "<his name>"`.
8. **Kill switch ready** in a terminal: `uv run whynot stop outputs/runs/<run> --live --by "<name>"`.

## 4. Each day of the pilot

- `uv run whynot daily outputs/runs/<run>` (one day, today; real account). Read
  `outputs/runs/<run>/agency/reports/<day>.md`, send him the report, act on his blocks.
- New video ads are published by the daily loop (one ad set each, the plan's persona targeting) when the autopilot allows it; in `propose` mode they wait in "Waiting for your approval" until `--approve`.
- Anything odd → `whynot stop` first, questions after.

## 5. After

- Compare the committed predictions with the real results (E8-4) and publish the comparison, good or bad.
- Remove our access if he asks; delete `data/private/partner/` when the pilot and the write-up are done.
