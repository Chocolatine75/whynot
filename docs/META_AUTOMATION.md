# Meta automation: connect once, the agency runs the account

For agents and humans wiring the engine into the platform (`web/`). Engine side: `src/whynot/run/connect.py`,
`src/whynot/agency/orchestrator.py`, `src/whynot/run/schedule.py`, `src/whynot/cli.py`. Tested for real on Nov 2
(see the last section). Built by Matteo + Claude. A front end can call these commands and read their JSON.

## The flow in four commands

```
whynot connect --token-stdin --json                      # once: the owner's Meta login → saved connection
whynot agency <App Store link> --countries US --daily-cap 20 --connection <file> [--level ...] [--json]
whynot schedule <run> --at 08:00 [--json]                # every morning: the day runs by itself
whynot status <run> --json                               # what the run page shows
```

`whynot agency --resume <run> [--approve NAME]` continues a run (today's day, or a step waiting for approval).
`whynot stop <run> --by NAME --live` is the kill switch (CLI + button, Tom's E8-6).

## 1. Connect (`whynot connect`)

- Input: the owner's Meta user token, **on stdin** (`--token-stdin`) or from an env variable (`--token-env`,
  default `META_USER_TOKEN`). Never as an argument: command lines are visible to every process.
- What it does: exchanges the login for a **60-day token** (with whynot's developer app, see below), finds the ad
  accounts and Pages, checks permissions (`ads_management` required), picks the only active account and the only
  Page you can advertise with (else `--account ID` / `--page ID`), asks Meta when the login ends.
- Saved to `data/private/connections/act_<id>.json` (gitignored, mode 600). This file holds the token; nothing else
  does. Pass its path to `whynot agency --connection`.
- Optional `--app-id <id>`: the **advertised** app's Meta app id (only if the app is registered with Meta: enables
  app-install campaigns, see 2).

`--json` prints one object, never the token:

```json
{"ok": true, "connection": "/…/data/private/connections/act_2579757785851312.json",
 "act": "act_2579757785851312", "account_id": "2579757785851312", "account_name": "…", "currency": "EUR",
 "page_id": "1352874221250687", "page_name": "Whynot test", "app_id": null, "user_name": "…",
 "granted": ["ads_management", "ads_read", "…"], "sandbox": false, "warnings": ["…"],
 "connected_at": "2026-11-02T…", "expires_at": "2026-12-31T…", "can_publish": true, "can_read": true}
```

On failure: `{"ok": false, "error": "<plain reason: expired login, missing permission, several accounts…>"}`,
exit code 1.

### Settings (`.env`)

| Variable | What | Needed for |
|---|---|---|
| `WHYNOT_META_APP_ID` | whynot's developer app: **ad-research-hackathon**, `1689171966196247` | the 60-day exchange + renewal |
| `WHYNOT_META_APP_SECRET` | its secret (App Dashboard → Settings → Basic). Never commit it | same |
| `META_USER_TOKEN` | a login to connect from the CLI (Graph API Explorer, app ad-research-hackathon) | CLI only; the site pipes its own |
| `META_APP_ID` | the **advertised** app registered with Meta (not whynot's app) | app-install campaigns only |
| `FB_TOKEN` | Ad Library research (competitor ads). Matteo's, long-lived to Dec 31 | `create`, videos |

Facebook Login on the site must request: `ads_management`, `ads_read`, `pages_show_list`, `pages_read_engagement`,
`pages_manage_ads` (+ `business_management` for accounts owned by a Business Manager).

## 2. The campaign objective is chosen alone

Meta **blocks** ads that link to the App Store under the traffic objective (error 1487810, seen on a real account).
`--objective auto` (default) decides at the connect step, before any money is spent on research:

1. the connection has the app's Meta app id → **app installs**, ads link to the App Store;
2. else → **traffic** to `--landing-url`, or else the developer's website from the store page (`sellerUrl`);
3. neither → the run stops at `connect` with the reason (nothing spent).

The chosen objective is in `status.objective` and in the connect step's outputs.

## 3. Run the agency (`whynot agency`)

Steps: `connect → create → publish → daily`. A finished step is never redone or re-billed; a failed one stops the
chain and is retried by `--resume`; a step waiting for the owner's approval does not block the next ones.
Every step writes `AgentEvent`s to `<run>/events.jsonl` (agent, parent, inputs/outputs digests, guards, cost).

Safety, enforced in the engine (the site never needs to re-check):
- `--level dry_run` (default from `.env`): nothing is sent to Meta. `propose`: the owner approves each action
  (`--approve NAME`). `autopilot`: acts within the cap; the **first live launch** still needs `--approve` once.
- `--daily-cap`: one cap for the whole account (static campaign ≤ half, video ads the rest).
- `--paused`: test mode, everything is created on Meta **PAUSED and never activated** (nothing can spend).
- The login is renewed alone when < 10 days are left; an expired login stops the run before any spend.

`--json` prints one object at the end:

```json
{"ok": true, "status": "done|waiting|error", "run": "/…/outputs/runs/<run>", "usd": 0.15, "error": null,
 "steps": {"connect": {"status": "ok", "outputs": {"objective": "traffic", "expires_at": "…", "renewed": false,
                                                  "can_publish": true, "warnings": []}},
           "create": {"status": "ok|cached", "outputs": {"ads": 12, "ad_sets": 4, "planned_eur_per_day": 20.0}},
           "publish": {"status": "ok|skipped|waiting", "outputs": {"campaign": "1202…", "url": "https://adsmanager…"}},
           "daily 2026-11-02": {"status": "ok", "outputs": {"live": 0, "new": 1, "paused": 0, "published_paused": 1,
                                                          "waiting_approval": 0, "committed_eur": 0, "cap_eur": 20,
                                                          "report": "agency/reports/2026-11-02.md"}}}}
```

Exit code: 0 done, 2 waiting for approval, 1 error. A run started by the site should be spawned detached (like
`web/lib/start.ts` does for `create`) and polled with `whynot status`.

## 4. Every morning (`whynot schedule`)

`whynot schedule <run> --at 08:00` installs a macOS LaunchAgent (`~/Library/LaunchAgents/ai.whynot.<run>.plist`)
running `uv run whynot agency --resume <run>`; output in `<run>/agency/schedule.log`. Elsewhere it returns the
crontab line to add. `--remove` stops it. `--json`:
`{"at": "08:00", "how": "launchd", "label": "ai.whynot.<run>", "plist": "…", "log": "…", "installed": true}`.
A scheduled run can do nothing a manual one cannot (same level, cap, approvals, kill switch).

## 5. The run page (`whynot status`)

`whynot status <run> --json` = the run's `agency/state.json` plus `ok`:
`config` (the AgencyConfig), `account` (the connection, no token), `objective`, `website`, `steps`
(connect/create/publish: `status`, `outputs`, `usd`, `seconds`), `days` (one record per day, same shape as the
daily step above), `schedule` (if any), `first_live_approved_by`, `static_committed_eur`. Daily reports for the
owner: `<run>/agency/reports/<day>.md` and `.json`.

## Tested for real (Nov 2, PAUSED, nothing spent)

- `whynot connect`: exchange with the app secret accepted, login valid to Dec 31; a real renewal call passed.
- `whynot agency` on Matteo's account `act_2579757785851312`, Page "Whynot test", run
  `outputs/runs/20261102-meta-auto-test`, $0.15: objective chosen alone = traffic to https://www.vietbuddy.app/;
  campaign `120254672319090204` (2 ad sets, 6 ads) + the daily video ad uploaded and published, all PAUSED.
  Read back from Meta: no issue (static ads PENDING_REVIEW, video IN_PROCESS).
- Not yet real: reading real results (needs ads ACTIVE, i.e. spend), the LaunchAgent on the Mac.
