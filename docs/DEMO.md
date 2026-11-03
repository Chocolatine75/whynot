# Demo script (3 minutes) and shot list

For whoever records the video (Tom). Everything shown is real and built during the hackathon. Every simulated number stays labelled "simulated" on screen. The partner (VietBuddy) is named only if he agreed; otherwise use the WhatsApp run (public app) for every screen.

The story: **a founder pastes a link and hands over their ads; the agency researches, creates, tests, runs and reports; then we show, honestly, how far its judgement can be trusted.**

## Before recording

- Web app: `cd web && npm run dev` → http://localhost:3100, browser at 1920×1080, zoom 100 %, dark mode off, bookmarks bar hidden, a clean profile (no tokens, emails or notifications).
- Runs to have ready in `outputs/runs/`: the WhatsApp run `20261101-222732-id310633997` (statics + trend-14/15/16 videos) and the VietBuddy run `20261101-014653-id6796837982` (127 competitor ads, evolution).
- Terminal: big font (18 pt), `whynot costs` and `./scripts/check.sh` output prepared.
- Voice-over recorded separately (quiet room), then laid on the screen capture. ~430 words in total.
- Tools: OBS (screen), any editor (CapCut / DaVinci) for cuts, captions and the 30 s cut.

## The script

| Time | On screen | Voice-over |
|---|---|---|
| **0:00–0:12** Hook | Black, then a trend video ad (trend-14, humor) plays full screen, sound on, for 6 s. Cut to the home page: one search bar in the middle. | "This ad was made, tested and published by an AI agency. Nobody on our team wrote it. Small businesses can't afford an agency, and Meta makes them pay to learn that their ads are bad. So we built one." |
| **0:12–0:25** Paste | Paste the WhatsApp App Store link into the bar, press Enter. The run page opens on the agency timeline. | "You paste your App Store link. That's it. whynot is a team of agents built on Meta's models." |
| **0:25–0:50** Research and strategy | Run page, *Market* section: the grid of competitors' real ads from the Ad Library, then *Strategy*: profiles, angles that work, angles nobody uses. | "A scout pulls your competitors' real ads from the Meta Ad Library: what they say, how long they run. Muse Wonder reads all of it with your store page and writes the strategy: who your customers are, which angles work, and which ones nobody uses yet." |
| **0:50–1:15** Ads | *Ads* section: statics with the real WhatsApp screens; hover one to show the "0 px changed" guard. Then the three videos side by side, one plays with sound (trend-15). | "The creative director turns that into distinct concepts. Code composes the statics with your real screens, cut out by SAM 3.1, never generated: a pixel guard checks it. Video ads are storyboarded skits on a trending format, with Muse Image photos, your real app animated in the phone, voices and captions, then checked by ear with Muse Voice Transcribe." |
| **1:15–1:45** Simulated feed | *Test* section: one of our ads inside the feed between competitor ads; open a viewer's reaction card (noticed / understood / believed / **why not**). Tag "simulated" visible. | "Before spending a cent, every ad goes into a simulated feed, next to your competitors' real ads. Viewer agents running on Muse Spark Open, Meta's open weights, react like your customer profiles: did I notice it, do I believe it, and why not." |
| **1:45–2:05** Evolution | *Evolution* section (VietBuddy run): score per generation with the noise band; gen 2 above gen 0. | "Agents mutate the losers and run tournaments. A gain only counts if it beats the measured noise. Here, generation two beats the original in both audiences. Simulated, and labelled as such." |
| **2:05–2:30** Run | *Launch* section: the plan with the daily cap, the Approve button, the "Pause everything" kill switch. Then Meta Ads Manager (real account, PAUSED campaign, ids blurred). | "You approve once. whynot publishes on Meta within your cap, everything paused until you say go. Every morning it reads results, pauses tired ads, ships new ideas and reports. One button stops everything." |
| **2:30–2:50** Honesty | `/validation` page: R3 result (0.52 vs shorter copy 0.62), bias suite (brand −0.47), the pixel guard 80/80. Then the terminal: `whynot costs` → $5.5. | "Is the simulator right? We measure it, and we publish when it fails: it doesn't yet predict which competitor ads run longest, and it's biased against unknown brand names. That's why every simulated number is labelled. The whole hackathon cost five dollars fifty of model calls." |
| **2:50–3:00** Close | Home page, cursor in the bar. Logos: Muse Wonder, Muse Spark, Muse Spark Open, Muse Image, SAM 3.1, Voice Transcribe. | "Meta automated the media buyer. whynot is the rest of the agency. Paste your link." |

## 30-second cut (X)

0:00–0:06 trend-14 with sound · 0:06–0:12 paste the link · 0:12–0:20 statics, videos, the simulated feed · 0:20–0:26 approve, kill switch · 0:26–0:30 "whynot: the AI ad agency on Meta's models". Captions burned in (people watch muted).

## Recording checklist

- [ ] 1080p, readable fonts, no tokens, emails, account ids or partner data on screen (unless agreed)
- [ ] "Simulated" visible every time a simulated number is
- [ ] Voice-over timed to the table (≤ 3:00 total)
- [ ] Real runs only, no mock screens
- [ ] Public repo link and the video link tested in a private window
