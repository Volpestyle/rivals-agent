# Docs index

Which documents are current, which are history and which are frozen. The rules for where a fact lives, how to mark
something superseded and what may be deleted are in `AGENTS.md`, "Documentation: one home per fact". Status lives on
Linear (project Rivals Agent), not here. Checked 2026-09-29; when a note's standing changes, its owner updates its
line here.

## Top level

| Doc | Standing |
|---|---|
| `plan.md` | Current: scope boundary, direction, architecture (lead) |
| `learning-plan.md` | Current for gates and design; passages about option/intent policies and web-start heads are marked superseded (lead) |
| `recording-protocol.md`, `recording-log.md` | Current: what James records; the ledger of every take |
| `compute.md` | Current: machines for jobs, Modal rules, the spend process |
| `machines.md` | Current: machine contract, access, transfers, job board |
| `spiderman-kit.md`, `pad-bindings.md` | Current and frozen (pinned by receipts; `spiderman-kit.md` is read at run time) |
| `human-demo-schema.md`, `execution-training.md` | History: the keyboard/mouse importer and baseline contract; superseded as the product on 2026-09-23 |
| `clankie.md` | Current: Clankie bridge interface; the bridge stays disabled (VUH-1325) |
| `waiting-on-james.md` | Current: James's to-do list for the job board |
| `next-pc-session.md` | Frozen 2026-09-23 plan; newer sittings are in `data/calibration/*/SITTING.md` |
| `cleanup-audit-20260923.md`, `test-audit-20260924.md`, `visual-range-supervision.md` | History |
| `steering/` | Charter and handoff of the retired steering pane (2026-09-26/27), the spend ledger (current) |
| `archive/` | Verbatim history moved out of the plans on 2026-09-23 |
| `research/` | Dated memos and evaluator check-ins; read the newest for a decision's reasoning |
| `evidence/` | Frozen run records; `evidence/README.md` indexes them |

## Lane notes worth reading now

- `lanes/range-lead.md`: the range work's present state and the index of the range notes.
- `lanes/l4-controller.md`: the scripted controller (the baseline; rebind VUH-1319) and camera calibration history.
  Camera calibration's current record is the newest `data/calibration/alt-cam-*/SITTING.md` (VUH-1384).
- `lanes/reentry.md`: `scripts/reenter.py`, the standard way into the range.
- `lanes/l2-hud.md`, `lanes/l3-detector.md`, `lanes/tracker.md`, `lanes/range-perception.md`: perception facts.
- `lanes/explore-policy.md`, `lanes/end-to-end-fit.md`, `lanes/end-to-end-fit-interim.md`,
  `lanes/end-to-end-fit-patch-equivalence.md`: the end-to-end policy's fits and results.
- `lanes/inverse-dynamics.md`: the IDM's home note. The IDM is parked (2026-09-28, VUH-1353).
- `lanes/human-admission-3.md`, `lanes/human-admission-night-complete-20260927.md`,
  `lanes/human-admission-handoff-20260927.md`: data admission.
- `lanes/demos.md`, `lanes/combo-arsenal.md`, `lanes/camera-turn-analysis-20260927.md`: loaders, combo sources,
  camera-turn analysis API.

Everything else under `lanes/` is dated history: the `*-2026092x.md` working notes (IDM runs and receipts, live-loop
sittings, FPS and focal attempts), `policy.md`, `l1-capture.md`, `l5-brain.md`, `l6-integration.md`, `loop.md`,
`galacta-pilot.md`, `range-cast-probe.md`, `learned-range.md`, `range-policy-reframe.md`, `jev.md`,
`replay-research.md` and the `review-*` packets. Don't act on their "next step" lines; check Linear and the newest
dated record first.

## Frozen notes (sha256 pinned; never edit, move or delete)

Found by searching `docs/evidence/` and `data/` (except `data/human` and `data/demos`, which were not searched) for
each note's LF and CRLF sha256, 2026-09-29:

- Range caller packets: `range-decision-timing`, `range-request-expiry`, `range-request-pulse-lifetime`,
  `range-owned-pulse-loop`, `range-live-focus`, `range-failed-send-trace`, `range-episode-collection`,
  `range-hud-performance`, `range-hud-countdown-performance`, `range-benchmark`, `learned-range-skills`.
- `placement`, `replay-hud`, `end-to-end-fit`, `end-to-end-fit-patch-equivalence`, `human-admission`,
  `live-fps-repair-20260927`, `live-loop-diagnosis-20260928`.
- IDM: `idm-first-explore-run-20260927`, `idm-gate2-anchors-results`, `idm-receipt-authority-refresh11-20260927`,
  `idm-receipt-authority-refresh12-20260927`, `idm-still-pitch-proposal-20260928`, `review-killfeed-layout-20260926`,
  plus `idm-explore-implementation-20260926` and `idm-gate2-plan-20260926` (pinned by `idm-explore-hashes-20260926.json`)
  and `idm-gate2-layout-20260926` (pinned by `idm-gate2-layout-delta-20260926.md`).
- Top level: `spiderman-kit.md`, `pad-bindings.md`, `next-pc-session.md`.

A note that is stale but frozen gets its current status here or on Linear, never in the note.
