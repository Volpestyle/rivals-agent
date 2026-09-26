# Evidence index

Each entry below is a record: inspected frames, receipts, reports and the scripts that produced them. Later
artefacts, fit reports, Linear comments and lane docs pin these files by path and by sha256, so an entry is never
edited, moved or deleted, not even into an archive folder:

- About 44 evidence scripts find the repo root by path depth.
- 17 folders link out with `../`.
- Pinned JSON elsewhere names these paths.
- Tests read `l1/`, `l4/` and `hud-calibration-20260923/`.

This index is the pointer instead. Everything here predates the whole-session recording direction of 2026-09-23
(`docs/recording-protocol.md`).

**Status** is one of:

- **current**: the latest record of its kind.
- **historical**: an accepted step that later work built on.
- **superseded**: replaced by the entry named.

**Line endings.** Receipts pin text files in the byte form of the machine that wrote them. The PC checks out CRLF
(`core.autocrlf=true`), while git and the Mac hold LF, and the per-folder `.gitattributes` files keep some folders
byte-exact.

- Verify these against `git show :path`, which gives the LF bytes: the `range-fragment-repair-20260922/summary.json`
  pins and `fit-readiness-20260923/driver-review.md`.
- Verify these on a Windows checkout: the pilot-2 `archive-manifest.json` files under `data/runtime/`.

Never add a root `.gitattributes` text or eol rule (`docs/cleanup-audit-20260923.md` §4).

| Entry | Issue | What it records | Status | Linked from |
|---|---|---|---|---|
| `l0/` | | Pad input accepted, mouse click ignored: the reason for the pad path | historical | `plan.md` |
| `l1/` | | Capture proofs: dxcam frame, dropped to lobby, run1 sheet | historical (test input) | `lanes/l1-capture.md`, `plan.md`, `scripts/record.py --selftest`, `tests/test_loop_frames.py` |
| `l2/` | | HUD readers | historical | `lanes/l2-hud.md`, `lanes/l6-integration.md`, tests |
| `l3/` | | Detector autolabel and eval sheets, YOLO and the green-outline finder | historical | `lanes/l3-detector.md` |
| `l4/` | VUH-1296 | Controller lane working evidence: run sheets, arrivals, the scoreboard truth set (no README; `lanes/l4-controller.md` describes it) | historical (test input) | `lanes/l4-controller.md` and six other lane docs, four tests |
| `reentry/` | | One re-entry refusal frame | historical | `lanes/reentry.md` |
| `episode-collection-review-20260922/` | VUH-1319 | Independent acceptance of `--collect-episode` | historical | nothing outside evidence (the Galacta slot folders pin it) |
| `range-hud-performance-20260922/` | | Accepted `_masks` compute reduction; the data is in `data/diagnostics/range-hud-performance-20260922/` | historical | `lanes/range-hud-performance.md`, `tests/test_hud_performance.py` |
| `range-hud-countdown-performance-20260922/` | | Bounded countdown-filter result. Landed in `67a7e31`; its README still says pending independent review, and the lead records the acceptance on Linear | historical | `lanes/range-hud-countdown-performance.md`, `tests/test_hud_countdown_performance.py` |
| `range-cast-calibration-d-20260922/` | VUH-1346, VUH-1347 | Native Web-Cluster calibration: two scripted casts hit; offline human-policy replay | historical (the base of the request series) | `archive/range-lead-20260922.md` |
| `range-first-human-fit-20260922/` | VUH-1309 | First admitted human-event fit | superseded by `range-human-fit-v2-20260922` | `archive/range-lead-20260922.md` |
| `range-human-fit-v2-20260922/` | VUH-1309 | Six-label human Web-Cluster diagnostic | superseded: `range-request-timing-20260922` reinterprets it as a visual-onset forecast | `archive/range-lead-20260922.md`, `learning-plan.md` |
| `range-request-timing-20260922/` | VUH-1346 | Human requests against visible cast timing | historical | `lanes/learned-range-skills.md`, `archive/range-lead-20260922.md`, `learning-plan.md` |
| `range-request-human-fit-20260922/` | VUH-1309, VUH-1346 | Received-request fit, checkpoint `6ee38807`; also holds `fit_cohort_20260923.py`, used by the cohort fit | superseded as a model by `range-request-cohort-fit-20260923` (its scripts are still used) | `archive/range-lead-20260922.md`, `learning-plan.md` |
| `range-request-cohort-fit-20260923/` | | Admitted two-session request cohort fit, checkpoint `698d8831` | current | this index only (and `data/`) |
| `fit-readiness-20260923/` | VUH-1346 | Mac fit readiness and the cohort-fit driver review | current | `lanes/galacta-pilot.md` |
| `range-request-runtime-20260922/` | VUH-1346 | First human-trained request policy in the range: one hit (request runtime series 1/5) | historical | `archive/range-lead-20260922.md`, `learning-plan.md` |
| `range-request-timing-runtime-20260922/` | VUH-1346, VUH-1347 | Instrumented request-model run: an accepted failed diagnostic (2/5) | historical | `learning-plan.md` |
| `range-request-efficiency-runtime-20260922/` | VUH-1347 | Completed request-model diagnostic: 10 s phase, one hit (3/5) | historical | `lanes/range-request-pulse-lifetime.md`, `learning-plan.md` |
| `range-request-owned-pulse-runtime-20260922/` | VUH-1346 | Eight learned web hits (4/5) | historical | `learning-plan.md` |
| `range-request-20s-runtime-20260922/` | VUH-1346 | First learned-request Luna KO (5/5, the latest of the series) | historical | `learning-plan.md` |
| `range-request-expiry-20260922/` | | Accepted request cancellation: an expired request is not range loss | historical | nothing outside evidence |
| `range-owned-pulse-software-20260922/` | | Request start and owned pulse: software acceptance | historical | `learning-plan.md` |
| `range-fragment-repair-20260922/` | VUH-1314 | Fragment contract repair, before and after | historical | `lanes/tracker.md` |
| `range-support-followup-20260922/` | VUH-1314, VUH-1351 | Existing-footage support search (zero new examples) and fragment contract followup | historical | `lanes/tracker.md`, `tests/test_tracked_body_execution.py` |
| `galacta-pilot-20260922/` | VUH-1319, VUH-1347, VUH-1351 | Galacta pilot 1: stopped after two pairs | historical | `plan.md`, `learning-plan.md`, `lanes/galacta-pilot.md` |
| `galacta-pilot-slot01-20260922/` | VUH-1319 | Pilot 1, slot 1: first near learned allocation | historical | the pilot-1 README |
| `galacta-pilot-slot03-20260922/` | VUH-1319 | Pilot 1, trial 3: scripted mid-distance kill | historical | the pilot-1 README |
| `galacta-pilot-slot04-20260922/` | | Pilot 1, slot 4: learned approach without an attack | historical | the pilot-1 README |
| `galacta-pilot-20260923/` | VUH-1319 | Galacta pilot 2 (checkpoint `698d8831`): stopped after three slots; its raw data is in `data/` | current | `lanes/galacta-pilot.md`, `recording-protocol.md` |
| `practice-settings-20260923-0040.jpg` | | James's practice-settings screenshot for pilot 2. Its path is written in pinned `data/benchmarks/galacta-pilot-20260923/*.json` | current | `lanes/galacta-pilot.md` |
| `changed-boundary-reviews-20260923/` | VUH-1294, VUH-1314, VUH-1355 | Five verbatim independent reviews | historical | nothing outside evidence (four are pinned by `data/`) |
| `hud-calibration-20260923/` | VUH-1294 | James's HUD calibration take: labels and frames | current (test input) | `lanes/l2-hud.md`, `perception/hud.py`, `tests/test_hud_calibration.py` |
| `player-zone-20260923/` | VUH-1355 | Where the hero is drawn and what the player guard drops | current | `lanes/l3-detector.md`, `perception/outline.py`, three tests |
| `flat-target-20260923/` | VUH-1356 | Can the range controller refuse a fused two-bot box by its shape? No | current | `lanes/range-skill-controller.md` |
| `replay-measurement-20260923/` | VUH-1328 | In-client replay as a demonstration source: measurement (the rest is in gitignored `data/demos/`) | current | nothing outside evidence |
| `human-execution-refactor.md` | VUH-1307, VUH-1326 | OBS input-logger integration and the human execution pipeline (commit `db6492a`); relevant again to whole-session recording | historical | nothing outside evidence |
| `range-bc-plumbing-20260924/` | VUH-1346, VUH-1359 | Range BC plumbing fit: nine pre-registered runs at `afff279` (MPS byte-repeatable; twin 1.3717 vs no-HUD 1.4310 dev loss; scaling gap flat), run 1's HUD parity re-emitted, and the real fit's `preregistration.json` (13 epochs, wd 1e-4, stride 64) | current | `lanes/end-to-end-fit.md` |
| `range-bc-interim-20260925/` | VUH-1346, VUH-1359 | Range BC interim fit (a scaling point, not the real fit): the plumbing recipe on 80.5 train min against the same-recipe 33.6-min control, three seeds each; reading Opens (no-HUD press-F1 lead over the twin +0.007 -> +0.036), the loss gap near zero but short of Closes, camera behind persistence and ar2, seed 0 bit-identical across queues, self-fed degenerate | current | `lanes/end-to-end-fit-interim.md` |
| `range-bc-selffed-diag-20260925/` | VUH-1346 | Why self-fed range BC rollouts are degenerate: copycat use of the previous action makes a known-idle history absorbing (no hold starts, camera zero); a model property, not an eval bug. Qualifies `range-bc-interim-20260925`: its press-F1 counts presses the executor never executes | current | `lanes/end-to-end-fit-interim.md` |
| `range-bc-countermeasures-20260926/` | VUH-1346 | Countermeasures round 1 against the copycat collapse (frames-only; one-step self-conditioning): NEITHER WORKS by the pre-registered self-fed checks; self-conditioning raises executed press-F1 0.035 -> 0.052 but stays collapsed; round 2 reordered to target the known-idle state | current | `lanes/end-to-end-fit-interim.md` |
| `idm-plumbing-20260924/` | VUH-1353 | IDM plumbing at `1df31e7`: four frame stores (26 GB on the Mac), MPS smoke byte-repeatable, leave-one-session-out 3-epoch fit (camera beats zero, yaw direction at chance on fast folds, no edge skill); reports, store manifests and the lane's three accounts | current | `lanes/inverse-dynamics.md` |
| `changed-boundary-reviews-20260924/` | VUH-1346, VUH-1353 | fit-review's verbatim review of the replay window-level loss (verdict: land) with hud-review's hand-back | historical | nothing outside evidence |
| `changed-boundary-reviews-20260925/` | VUH-1353 | fit-review's verbatim review of the beta-NLL default flip (verdict: land with one doc fix) with scoreboard-fix's hand-backs | historical | nothing outside evidence |
| `idm-beta-nll-20260925/` | VUH-1353 | The beta-NLL camera loss toward default-on: second fold (beta 6 of 6 across folds, plain 2 of 6), pitch margin, per-regime calibration; gate-1 re-run and the edge-head input test to follow | current | `lanes/inverse-dynamics.md` |
| `whole-session-intake-20260923/` | VUH-1359, VUH-1309 | Independent per-session reviews and hand-backs for the first four whole-session admissions (051828, 171533, 200129, 205528), the calibration take and the transcode reviews | historical | `lanes/human-admission.md` |
| `whole-session-intake-20260925/` | VUH-1359, VUH-1309 | Reviews and hand-backs for the 2026-09-24 takes (three admitted, 47.0 min; the multi-speed calibration take: yaw gain speed-independent), the motor-step fix, the edge rule and the importer duplicate-timestamp tolerance; tally 94.18 of 180 min | current | `lanes/human-admission.md` |
| `whole-session-intake-20260926/` | VUH-1359 | The 2026-09-25 recordings: validation take 212646 (15.58 min, beside train), training takes 203745 (45.98 min, Timed Practice cut) and 045729 (10.26 min); train 150.42 of 180; the gate2 sealed split, timed_practice and settings_change cuts, per-session motor statements and category-disjoint registry checks, each independently reviewed | current | `lanes/human-admission.md` |

Adding evidence: add a new dated folder with its own README, then add its row here. `data/` is gitignored, so a
run's output there stays untracked unless it is force-added on purpose.
