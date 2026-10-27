# Plan

Two people. **A** = pipeline / ML / data. **B** = product / integrations / UI / demo. Swap freely; update owners here.

Deadline: **Wed Nov 4, 9:00 PM ET = Thu Nov 5, 03:00 Paris.** Submit Wed Nov 4 evening Paris time, never at the last hour.

The bar is in `TARGETS.md` (R1–R10 and the per-criterion checklist). Each milestone ends with a gate: if the gate fails, fix it before going deeper.

**Principle: vertical slice first, depth after.** A thin end-to-end loop that works beats perfect layers that don't connect.

## M0 — Foundations (Oct 27–28)
- [ ] (both) Claim Meta credits + spend limit, Baseten, Modal
- [ ] (A) `costs` wrapper + smoke tests of every model, real IDs in `META_APIS.md`
- [ ] (B) **Partner store confirmed in writing** — the #1 dependency. Install tracking + exit question ("What stopped you?") as early as possible: ground truth for R1 accumulates from now
- [ ] (A) Ad Library ingest (tokens stripped), one market end to end
- [ ] (B) App skeleton: web app + API, one page that runs a job and shows its agent log and cost

**Gate:** every model answers through the wrapper; partner store yes/no is known.

## M1 — Vertical slice (Oct 29–30)
One product, two visitors, two different ads, end to end, ugly is fine:
session → objection → template → SAM cutout + Muse Image scene → composer → pixel guard → panel score (on the image) → shown in the UI with cost.
- [ ] (A) Objection inference v0 (rules + Muse Spark on ambiguous sessions)
- [ ] (A) Panel v0 on Muse Spark Open with SSR, image input
- [ ] (B) SAM cutout decoding, Muse Image scene, composer, pixel guard
- [ ] (B) 2–3 templates by hand
- [ ] (both) **Launch the blind human test** (needs the slice's ads) — collection runs in the background until Nov 3

**Gate:** the demo hook (two visitors, two ads) runs live with no manual step; R5 holds.

## M2 — Depth on the engine (Oct 31–Nov 1)
- [ ] (A) Strategy brief with Muse Wonder → generates the templates (not hand-written anymore)
- [ ] (A) Snapshot reading (computer use / vision) of competitor ads
- [ ] (A) Distilled objection classifier, evaluated vs rules and ground truth (R1)
- [ ] (A) Panel vs Ad Library longevity (R4)
- [ ] (B) Agent loop: plans, calls tools, checks guards, retries, budget cap, verifiable log
- [ ] (B) Partner store on-site banner / cart email A/B live (R8)
- [ ] (explore) Synthetic shoppers browsing the store with computer use — keep if it works and looks great

**Gate:** R1 and R4 measured (whatever the value); agent log readable end to end.

## M3 — Product surfaces (Nov 2–3)
- [ ] (B) **Public teardown**: Shopify URL → objection map + 3 ads + fixes in < 90 s (R6, R7)
- [ ] (B) Merchant dashboard: objection map, templates, variants + scores, agent log, cost counter, launch/export
- [ ] (B) Marketing API: sandbox creation, budget cap, dry-run default; optional capped split test (R10) only with explicit OK
- [ ] (both) Send the teardown to real merchants, collect quotes (R9)
- [ ] (both) Analyse human test (R2) and panel vs humans (R3)

**Gate:** a stranger runs the teardown on their own store without help; R2 and R3 measured.

## M4 — Ship (Nov 3–4)
- [ ] Go through `TARGETS.md`: every line ✅ / 🟡 / ❌ with values
- [ ] One command reproduces every number
- [ ] README final, architecture diagram, what-was-built list
- [ ] Record the 3-min video (see `DEMO.md`) + 30 s cut for X
- [ ] Submit on Cerebral Valley (repo public, video public, both members listed); flag open weights
- [ ] Post on X

## Cut list if late (in order)
1. Criteo uplift side check
2. Live Marketing API launch (fall back to export) and R10
3. Synthetic shoppers via computer use
4. Snapshot reading via computer use (fall back to ad text)
5. Weekly report

Never cut: the vertical slice, the public teardown, the human test (R2), R1, R3, R5, the cost counter, the agent log.
