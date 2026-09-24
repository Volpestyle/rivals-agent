# Cleanup audit, 2026-09-23 (phase 1, read-only)

Branch `cleanup/2026-09-23` from main `9de857c`, worker `repo-cleanup`. This file is the only change on the branch:
nothing was moved, deleted or edited. Every item below is a proposal. The lead and James decide what proceeds, and
phase 2 does it item by item, one commit each, with both suites run.

Method: `git ls-files`/`ls-tree` for sizes; an `ast` import graph over all 195 tracked `.py` files (code, tests,
`docs/evidence`, tracked `data/`), including relative imports and the bare-name imports that `agent/controller.py`
enables by putting `scripts/` on `sys.path`; greps across docs, skills, runbooks and evidence; sha256 scans matched
against receipts; both test suites run on this worktree. Four read-only sub-audits (top-level docs, core lane docs,
range lane docs, evidence) are merged here, and their "nothing references X" claims were verified by grep. The
full sub-audit notes, with more line references, are in the handoff folder beside `cleanup-audit.md`.

## Headlines

1. **The repo is 416.6 MB at HEAD, and 350 MB of that is `docs/evidence` (91% of it images). None of it should go.**
   Evidence can't move: 44 evidence scripts find the repo root by path depth, 17 folders use `../` links, paths sit
   inside hash-pinned files, and four test files read evidence at run time. Rewriting history would change the commit
   ids that bindings cite. The only lever for size is how future captures are saved.
2. **Little code is dead, and much of what looks dead is load-bearing.** The pinned `agent/loop.py` imports
   `agent/jev.py`, `agent/replay.py` and `agent/demos.py` at import time. It also imports `policy/live.py` lazily
   (which pulls in `train`, `encode`, `frames` and `corpus`), and `scripts/record.py`, `reenter.py` and `capture.py`
   through `sys.path`. Evidence scripts import `policy/execution.py`. The real candidates are:
   - `localjev/` (316 lines): nothing imports it and no test covers it.
   - The closed B0 chain (1,172 lines, plus 620 lines of tests).
   - The dormant Clankie bridge (413 lines, plus its test and doc).
3. **The do-not-touch set is 16 files, not five.** The pilot-2 deployment freeze
   (`data/runtime/galacta-pilot-20260923-preflight/{controller,perception}-deployed.json`) hashes:
   - `agent/{brain,controller,intents,learned_range_skill,loop,startup,state,tracker}.py`
   - `perception/{hud,outline,scoreboard}.py`
   - `policy/{execution,range_policy,range_skill_policy}.py`
   - `scripts/{capture,record}.py`

   Editing any of them, even whitespace, forces a re-freeze before checkpoint `698d8831` can run again.
4. **Pins exist over both LF and CRLF bytes** (`core.autocrlf=true` on the PC). Receipts record
   `LF_normalized_sha256` and `CRLF_blob_sha256`. So there must be no root `.gitattributes` text or eol rule, and any
   closure tool has to print both forms.
5. **Today's direction can't be reached from the entry docs.** Nothing in the repo links `docs/recording-protocol.md`
   or `docs/recording-log.md`, and five files still say a keyboard/mouse checkpoint cannot drive the pad.
   `learning-plan.md` (2,437 lines) is about 600 lines of live plan and 1,800 of history. The "Decision layer" in
   `plan.md` repeats 75 of 79 lines from `lanes/l5-brain.md`.
6. **Lane docs: ten are frozen review packets.** Their current bytes are hash-pinned, so they are never edited or
   moved; they get indexed instead. `range-lead.md` is unpinned and nothing links to it, so it is the right place for
   a range present-state index. `l2-hud.md`, `l4-controller.md` and `policy.md` read like diaries with present state
   buried; that is the owners' job, routed by the lead.
7. **Hygiene:**
   - On the PC, the git symlinks `CLAUDE.md`, `.claude/skills` and `.codex/skills` are checked out as plain text.
     A Claude session on the PC reads `CLAUDE.md` as the literal word "AGENTS.md" (this session saw exactly that),
     not the rules.
   - On a fresh clone, 35 tests fail or error because they read gitignored `data/` without a skip guard.
8. **Tooling (James's addendum).** A justfile, pre-commit with a `DECLARATION:` guard, a GitHub Actions workflow and
   a recording watch-folder script are drafted and tested on this PC; the exact contents are in §6. Each is a new file
   and can be removed by deleting it.

## Decisions needed

| # | Question | Who | Recommendation |
|---|---|---|---|
| D1 | `localjev/`: keep it as a parked record, or delete the code (git history keeps it)? | James | Delete the code. Archive `lanes/local-jev.md` with its "Measured" and "Verdict" sections intact, because `learning-plan.md:2214` cites the latency numbers. |
| D2 | Retire the B0 chain (`policy/b0.py`, `b0_multilabel.py`, `b0_support.py`, `b0_reads.py` and `tests/test_b0*.py`)? Also `policy/behaviour.py`? | James, policy owner | Delete B0 after a tag (`learning-plan.md:527-534`: "no further B0 fit authorized"). `behaviour.py` is the accepted VUH-1311 consumer but is not on today's path; keep it until the end-to-end fit lands. |
| D3 | Clankie bridge (`agent/server.py`, `agent/session.py`, `scripts/clankie_bridge.ps1`, `tests/test_session_api.py`, `docs/clankie.md`): keep it dormant, or retire it? | James | Either works, but retire it as one unit and remove the disabled scheduled task and firewall rule on the PC in the same step (`clankie.md:95-100`). Otherwise keep it and give it one row in `AGENTS.md`. |
| D4 | YOLO path (`perception/autolabel.py`, `train.py`, `eval.py`, `setup_pc.ps1`) | James | Keep. `l3-detector.md:478` says "Do not retire the YOLO path", since it is the only candidate for VOD footage. Separately, fix `autolabel.py`/`eval.py` defaulting `--sheet` into `docs/evidence/l3/`, where a re-run overwrites evidence. |
| D5 | Replace the `CLAUDE.md` symlink with a regular one-line file containing `@AGENTS.md`? | Lead | Yes. It works on both machines; the symlink only works on the Mac. |
| D6 | Adopt the "frozen review packet" rule for the ten pinned lane docs, and rewrite `range-lead.md` as the range index? | Lead, owners | Yes (§3.4). |
| D7 | Split `learning-plan.md` into a live plan plus a verbatim `docs/archive/` history doc? | Lead | Yes, with stub headings for the five inbound anchors and the glyph-contract paragraph (§3.1). |
| D8 | Which tooling pieces to land, and when to run `pre-commit install`? It installs into the shared `.git/hooks`, so every worktree of the PC clone gets it at once. | James, lead | Land all five files. Install hooks only after the config is on main, with `--allow-missing-config` (§6). |
| D9 | `range-hud-countdown-performance` landed in `67a7e31`, but its evidence README says "Pending independent review", and the repo has no acceptance record. | Lead | Record the acceptance, or the gap, on Linear. |

## 1. Size

| Area | Files | Lines | Bytes | Notes |
|---|---:|---:|---:|---|
| `docs/*.md` (top level) | 10 | 4,141 | 0.31 MB | `learning-plan.md` alone is 2,437 lines / 171 KB |
| `docs/lanes/` | 35 | 13,617 | 1.03 MB | 16 of them are `range-*.md` notes (3,168 lines) |
| `docs/evidence/` | 1,002 | md 8,353 (77 files); code 9,503 (75 `.py`/`.ps1`/`.sh`) | 350.1 MB | 398 jpg + 53 png; 36 top-level entries |
| `data/` (force-added) | 229 | | 46.7 MB | Pilot-2 frames, freeze and binding, benchmarks, one HUD diagnostic |
| `agent/` | 17 | 7,572 | 0.42 MB | `loop.py` 1,374, `demos.py` 1,296, `controller.py` 1,092, `jev.py` 810 |
| `perception/` | 14 | 6,487 py | 0.42 MB | Plus `hud_truth.json` (3,753 lines) and `gt/range-green.json` |
| `policy/` | 14 | 4,860 | 0.27 MB | |
| `scripts/` | 20 | 3,807 py | 0.23 MB | 13 `.py`, 2 shell, 5 template PNGs (all used) |
| `localjev/` | 6 | 316 | 0.01 MB | |
| `tests/` | 115 | 23,010 py | 16.6 MB | 53 `.py`; 62 fixtures (15.4 MB, all used through globs) |
| `AGENTS.md` + live-game skill | 2 | 259 | | |
| `uv.lock` | 1 | | 0.59 MB | |
| **HEAD total** | 1,470 | | 416.6 MB | Pack 131 MiB; blobs outside HEAD come to 31.9 MB, so history is not the weight |

Code (22,984 lines) and tests (23,010 lines) are about the same size.

Ten largest markdown files:

| Lines | File | What it is |
|---:|---|---|
| 2,437 | `docs/learning-plan.md` | The canonical plan: about 600 lines live, about 1,800 history (§3.2) |
| 2,391 | `docs/lanes/l2-hud.md` | HUD readers lane. 482 lines of format 2-4 migration history come before Status; about 520 lines belong to other owners |
| 1,397 | `docs/lanes/l4-controller.md` | Controller lane. About 1,220 lines of dated run reports come before the present-state table at L1250 |
| 1,035 | `docs/lanes/policy.md` | Titled "the learned chooser (steps 1-3)", but it opens with about 700 lines of VUH-1311 addenda and has an archived B0 section inline |
| 724 | `docs/lanes/l3-detector.md` | Detector lane (outline finder, YOLO); four stale spots |
| 655 | `docs/evidence/changed-boundary-reviews-20260923/review-hud-1294.md` | Verbatim independent review; a record, keep |
| 574 | `docs/lanes/learned-range-skills.md` | API and handoff for `policy/range_skill_policy.py`; hash-pinned |
| 569 | `docs/lanes/human-admission.md` | Admission ledger; its current state is the last section; being edited now |
| 552 | `docs/evidence/fit-readiness-20260923/driver-review.md` | Verbatim review of the cohort fit driver; a record, keep |
| 551 | `docs/lanes/demos.md` | Demonstration corpus lane; current |

## 2. Dead code

### What the pinned and frozen files hold in place

- **Pinned `agent/loop.py`:**
  - At import time it loads `.brain`, `.controller`, `.demos` (`COOLDOWNS`), `.intents`, `.jev` (`pct`, line 40),
    `.replay` (`label`), `.state`, `.startup` and `.tracker`.
  - Lazily it loads `.human_demos`, `.learned_range`, `.learned_range_skill`, `policy.range_policy`,
    `policy.range_skill_policy`, `policy.live` (`--brain learned`, line 1184) and `.jev.AsyncJev` (`--brain jev`).
  - Through `sys.path` (set by `agent/controller.py:19`) it loads `record` (lines 122 and 1155) and `reenter`
    (line 1132); `controller.py` itself loads `capture` and `record`.
- `tests/conftest.py:51` imports `agent.jev` in an autouse fixture, so every test loads it.
- Pinned `perception/outline.py:476` does `from detect import draw` in its `__main__` block.
- **Evidence scripts** can't be edited, because they pin their own sha256. Each count below is the number of evidence
  scripts that import the module:

  | Module | Scripts | Module | Scripts |
  |---|---:|---|---:|
  | `agent.state` | 27 | `agent.controller` | 8 |
  | `policy.range_skill_policy` | 15 | `agent.intents` | 6 |
  | `agent.brain` | 13 | `policy.execution` (`torch_module`) | 6 |
  | `perception.outline` | 10 | `perception.hud` | 5 |
  | `agent.loop` | 9 | `agent.learned_range_skill` | 5 |
  | `agent.tracker` | 9 | `agent.human_demos` | 1 |

  Two more scripts run `python -m scripts.range_benchmark`. Renaming or removing any imported name breaks a re-run.
- The 16-file pilot-2 freeze (headline 3).

### Module verdicts

| Module | Lines | What reaches it | Verdict |
|---|---:|---|---|
| `localjev/` (`gpustat`, `netprobe`, `paired`, `selftest`, `serve.sh`) | 316 | Nothing (`paired` is imported only by `selftest`). No test. Named only in `lanes/local-jev.md` | **Delete candidate (D1).** Risk: none to tests or pins. `local-jev.md` would then describe removed code, so the owner adds "removed in `<sha>`". The `.localjev/` line in `.gitignore` can stay, since the Mac install still exists |
| `policy/b0.py`, `b0_multilabel.py`, `b0_support.py`, `b0_reads.py` | 1,172 | Each other, plus `tests/test_b0.py` and `test_b0_format5.py` (620 lines). MLX, so these run only on the Mac; they are skipped on the PC | **Delete candidate (D2)**, after `git tag archive/b0-20260923`. The runbook lines in `policy.md:326-328, 485-486` become history. Not in any receipt |
| `policy/behaviour.py` | 542 | `tests/test_behaviour.py` (528) | **Owner decides (D2).** Keep until the end-to-end fit lands |
| `policy/live.py`, `train.py`, `encode.py`, `frames.py`, `corpus.py` | 1,529 | Pinned `loop.py --brain learned` → `live` → `train`/`encode`/`frames`/`corpus` | **Keep.** Deleting them leaves a pinned CLI option that fails with ImportError |
| `agent/jev.py` | 810 | `loop.py:40` (`pct`, at import time), conftest, `learned_range.py`, `policy/live.py`, tests | **Keep.** Its kit-legality helpers are live; a split would mean editing pinned callers |
| `agent/server.py`, `agent/session.py`, `scripts/clankie_bridge.ps1` | 413 | Each other, plus `tests/test_session_api.py`. `docs/clankie.md` has no inbound link | **James decides (D3)** |
| `perception/autolabel.py`, `train.py`, `eval.py`, `setup_pc.ps1` | 357 | No code. `l3-detector.md` and `evidence/l3/README.md` | **Keep (D4)** per `l3-detector.md:478`. Fix the `--sheet` default that writes into evidence |
| `perception/detect.py` | 67 | `replay_states.py` (optional finder) and pinned `outline.py` `__main__` | **Keep** |
| `perception/evalread.py` | 130 | `tests/test_evalread.py` only | **Archive candidate, owner decides.** Its point ("damage and KOs are not on screen") was superseded by `perception/scoreboard.py`. Both `l2-hud.md:487-500` and `l6-integration.md:7-8` claim to own it |
| `perception/replay_states.py`, `agent/replay.py` | 303 | Tests; `replay.label` is imported by pinned `loop.py` | **Keep** |
| `scripts/padprime_m1.py` | 104 | `tests/test_padprime_m1.py`, `tests/test_startup.py:312` | A one-off VUH-1314 M1 experiment. **Archive only with the l4 owner**: it needs two test edits for about 100 lines saved |
| `scripts/l4_measure.py`, `l4_trial.py` | 647 | Tests; `controller.py:308` cites `l4_measure`'s yawmap; `policy/corpus.py` reads `l4_trial` recordings | **Keep** |
| `scripts/regenerate_sealed.py` | 62 | Runbook in `l2-hud.md` | **Keep.** Fix its docstring (line 5 points to `learning-plan.md`; the ruling is at `plan.md:99-106`) |
| `scripts/capture`, `record`, `reenter`, `pad`, `padrun.sh`, `l4_menu`, `l4_practice_settings`, `import_human_demo`, `range_benchmark`, `range_cast_probe` | | Runtime (through `sys.path`), skill runbooks, tests, evidence | **Keep** |
| `agent/learned_range.py`, `policy/range_policy.py`, `policy/execution.py` | | Legacy loading and pilot-2 `check_binding.py`; evidence fits; the freeze | **Keep** |

**Function level:** almost nothing. The only top-level names referenced nowhere else are in pinned files:
`NoTracker` (`loop.py`), `read_numbers` and `read_ability` (`hud.py`), and `RED` (`outline.py`). A few more are used
only by tests: `KIT_REFERENCE` (`events.py`), `independent_count` (`behaviour.py`), `Example` (`range_policy.py`,
frozen) and `on_leave_dialog` (`l4_menu.py`). Four helpers in `perception/camera_motion.py` belong to a lane
editing that file right now. None of these justifies a commit.

## 3. Doc bloat

### 3.1 Constraints on any doc edit

- **`docs/spiderman-kit.md` line 6 is read at run time.** Pinned `loop.py` (`kit_patch`) and `policy/corpus.py`
  search the first 2,000 characters for `**Patch reflected: …`, and `tests/test_loop.py:861` asserts the value.
  Keep the line byte-identical and inside that window.
- **Headings that pinned code cites by name** must survive any trim:
  - `tracker.md`: "The body witness (range mode)", "Split bodies" and "Coasting: a deliberate trade" (cited by
    `tracker.py`, `brain.py`).
  - `l3-detector.md`: "Where the 13 misses come from", the ranging measurement and the threshold-58 measurement.
  - `loop.md`: "Safety".
  - `learning-plan.md:601`: the glyph-contract paragraph, cited by `hud.py:1713`.
  - Unpinned code and tests also cite headings in `l2-hud.md` ("Event stream format"), `demos.md` ("The loaded
    Event") and `l4-controller.md` ("Measurements", which the live-game skill uses).
- **Inbound anchors:**
  - `plan.md:73, 86, 91, 111` link into `learning-plan.md`.
  - `lanes/policy.md:408, 521` link to `#b0-auxiliary-pretraining-by-predicting-observed-ability-events`.
  - Leave stub headings behind any move.
- **Ten hash-pinned lane docs** (§3.4): never edit or move them. Nothing in CI reads the pins, but the file stops
  matching its receipt. `galacta-pilot.md` has already drifted from its `93dc9f1` pin this way.
- **Evidence reviews cite lane-doc line numbers at a named commit**, so they still resolve in history. Trims make
  those numbers stop matching HEAD, which is acceptable.

### 3.2 Top-level docs

| Doc | Finding | Proposal | Who |
|---|---|---|---|
| `AGENTS.md` | **Read list (lines 10-20)** omits `learning-plan.md`, `recording-protocol.md` and `recording-log.md`; nothing in the repo links the two recording docs. **"Where things live" (21-31)** is stale: no rows for `policy/`, `localjev/`, `tests/` or the recording docs, only 4 of 15 scripts listed (not `reenter.py` or `l4_practice_settings.py`, which the skill runs), and `docs/evidence/` described as "screenshots". **Line 6** says `CLAUDE.md` is a symlink, which it isn't on the PC (§4) | Add the three docs to the read list. Refresh the table | Lead |
| `plan.md` | **Direction** says a keyboard/mouse checkpoint can't drive the pad (lines 48-51, 82-88), and the pilot summary stops at 09-22 (63-81). **Ownership** (131-134): "Codex lead owns dispatch… retired Claude lead", which contradicts `learning-plan.md:937`. **Architecture diagram** still shows YOLO and the Jev swap (167-191). The lane table is the original 09-20 plan and lists 5 of 35 lanes (193-210). The **perception decision** "YOLO vs classical being compared" was settled long ago (218). **"Decision layer" (225-313)** is 75 of 79 lines verbatim from `l5-brain.md`, including "There is no track id" (false; `agent/state.py:36`). The **Jev section** (315-321) is duplicated in three places. **VUH-1347** is still described as requested, though its take was recorded on 09-23 (324-336) | Add a dated 09-23 Direction bullet and mark the old ones superseded. Write one role-based ownership line. Update the diagram. Replace "Decision layer" with a link. Trim the Jev section, the lane table and VUH-1347 | Lead (lead-only file) |
| `learning-plan.md` | Live: 3-40, 215-320, 948-1008, 1273-1342, 2021-2085, 2088-2274 (with trims). History: 41-214 (run diary), 321-919 (B0 and the VOD-chooser work; `policy.md` holds its results), 1009-1270 (RL proposal that calls itself historical), 1343-1706 and 1714-2020 (parked VOD pilots), 2275-2427 (acquisition logs). Lines 920-947 (roadmap diagram, milestone-to-Linear list) are misplaced under the B0 heading. Lines 17-27 and 241-244 contradict the 09-23 direction | Move 920-947 into Roadmap. Copy the history blocks verbatim into `docs/archive/learning-plan-history.md`, leaving stubs for the anchors and the glyph paragraph. Result: about 650 lines | Lead |
| `spiderman-kit.md` | "Nothing has been checked in the live game" (3-4) is contradicted by line 7 and by the skill. Team-Up "irrelevant" (61) is contradicted by `recording-log.md` (C fires in the solo range). The practice-settings facts (228-236) and "bots shoot back" (244) conflict with the skill's live facts | Update with pointers; don't touch line 6 | Lead |
| `human-demo-schema.md` | Still the importer contract. Line 3 names a pane ID. 360-432 is a dated verification log. "Still required for admission" (425-432) is stale | Trim to the test commands | Importer lane |
| `execution-training.md`, `machines.md` | Accurate. Dated test-run logs at `execution-training.md:139-146` and `machines.md:134-162`. The raw-KBM action identity may be superseded by the end-to-end fit | Trim the logs; revisit when `end-to-end-fit.md` lands | Lead |
| `visual-range-supervision.md` | Only `learning-plan.md:156` links it, and that line calls it historical | Archive to `docs/archive/` and repoint the link | Lead |
| `clankie.md` | No inbound link. It is the only record of the PC artefacts (disabled scheduled task, firewall rule) | Keep, and add one row in `AGENTS.md`, unless D3 retires it | Codex, VUH-1316 |
| `recording-protocol.md` | "Per the learning plan's step 4" (70) is ambiguous: there are four step-4s. It means `learning-plan.md:237` | Make it an anchor link | Lead |
| `recording-log.md` | Fine | Keep | Lead |
| Live-game `SKILL.md` | "Dead ends" (122-124) hold only with No Ability Cooldown ON, and lines 128-133 then say to switch that off. "Range bots never attack" appears twice | Add one clarifying clause | Lead |

**Claims duplicated across three or more files:**

- **"A keyboard/mouse checkpoint can't drive the pad":** `plan.md:87`, `learning-plan.md:25, 241`,
  `machines.md:128`, `execution-training.md:3` and `human-demo-schema.md:3, 431`. This is exactly what the 09-23
  direction changes. Keep one canonical statement and point the others at it.
- **"The PC GPU belongs to the game":** in 5 files, all agreeing. Make `machines.md` canonical (optional).
- **The $100 budget:** `plan.md:124` and three places in `learning-plan.md`.
- **The milestone-to-Linear map:** `plan.md:91-98` and `learning-plan.md:941-946`, which have already drifted
  (milestone A lists different issues in each).

### 3.3 Core lane docs (proposals for owners)

| Doc (lines) | Finding | Proposal |
|---|---|---|
| `l2-hud` (2,391) | Lines 3-484 (format 2-4 history) come **before** Status. L7 "`agent/demos.py` reads format 2" is false: `EVENT_FORMAT = 5` (`demos.py:61`). L2267-2293 say a pad/M&K layout table is still needed, but `hud.py:62-103` has `Layout`/`MK`. L1746-2266 (about 520 lines) are VOD-corpus provenance and the camera-motion probe, which belong to demos and inverse-dynamics | Status first, then the format-5 contract, then a short changelog. Move the VOD and camera sections once `inverse-dynamics.md` lands |
| `l4-controller` (1,397) | Diary: about 25 dated run reports (L10-1233) before the present state at L1250. The header (L5-8) about the PC state is stale. "State" is stale (9 controller tests; there are 26). "Awaiting re-review, freeze stands" (L1092) contradicts the runs above it | Write a present-state head of about 150 lines; keep the run reports below or in an archive note. Keep the "Measurements" heading |
| `policy` (1,035) | The title says steps 1-3, but L3-715 are prepended VUH-1311 addenda. An archived B0 section is inline (L405-517). Nothing relates the doc to today's direction | Write a 10-line present-state head and move the B0 section to an archive note |
| `l3-detector` (724) | The "Open ask for L4" (L293-313) is done. The swatch-sweep section (L425-447) contradicts Status. The test-harness fact (L275-279) is superseded by conftest. Status still lists YOLO weights, though recall was about 3%. About 110 lines of "not viable" VOD finders | Trim to dead-end rows plus evidence pointers; keep the cited measurements |
| `l5-brain` (413) | "Not yet running against the live game" (L1-14), but loop30a/b and later runs happened. "`Detection.tagged` has no producer" (L335), but `hud.read_tagged` exists. It cites 113 tests (there are about 1,376) and says "repo not cloned on the PC" | Update Status/Open, or date-stamp the doc |
| `loop` (269) | "Never run live" (L3), "Not built: the tracker" (L263) and "Nothing is committed" (L269) are all false (`loop.py:542` defaults to `Tracker()`) | Fix four lines; keep "Safety" |
| `reentry` (454) | Header "none re-run live" is contradicted by L308-360. "The cursor finder is ours, not `l4_menu.find_cursor`" compares against a finder that no longer exists | Update the header; cut the comparison to one line |
| `jev` (98) | 44 of its 83 non-blank lines are verbatim in `l5-brain`'s Jev section. "Not built" (L95-98) is false: `AsyncJev` exists | Make it a pointer, keeping the path because `plan.md` links it |
| `local-jev` (514) | "Running." (L10), but `learning-plan.md:2221` says "parked" | Archive per D1 |
| `l6-integration` (153) | Its eval finding is superseded by `perception/scoreboard.py` and by the refuted ult-charge proxy. It cites the removed `brain.NEAR_H` and has an ownership clash with `l2-hud` | Archive, or add a "superseded by" line |
| `replay-research` (105) | `docs/evidence/replay-measurement-20260923` answers most of the "What to test" list (L94-105) | Add a pointer |
| `combo-arsenal` (168) | l4 settled the default-RB half of the Sekkombo question; commit `055410a` settles the swing bindings | Add pointers |
| `demos` (551) | One run-on "Mutation checks" paragraph (L535-551) | Trim to counts plus a pointer |
| `tracker` (481), `l1-capture` (50) | Current (l1 has one extra blank line at EOF) | Keep |

### 3.4 Range lane docs: consolidation proposal

There are **16** `range-*.md` notes (3,168 lines), not eleven. 29 of the 31 commits touching them are from
2026-09-22.

**Ten docs are frozen review packets.** Each one's current sha256 is held by a receipt or freeze manifest:

- `range-decision-timing` (pinned in 3 places)
- `range-episode-collection`
- `range-failed-send-trace`
- `range-hud-countdown-performance`
- `range-hud-performance` (pinned in 3 places)
- `range-live-focus`
- `range-owned-pulse-loop`
- `range-request-expiry` (pinned in 2 places)
- `range-request-pulse-lifetime`
- `learned-range-skills`

Their "not yet accepted" status lines are stale on purpose: acceptance is recorded in the evidence that pins them.
Do not edit or move them, even to fix a link. Their status belongs in an index.

**Proposal:**

1. **Rewrite `range-lead.md` in place as the range present-state index.** It is unpinned and has no inbound links,
   but it stopped on 2026-09-22 at 17:00, before four learned runs, both Galacta pilots, checkpoint `698d8831` and
   today's direction. Its "Caller contract" documents `--live --brain range`, which `loop.py:1234` now refuses. The
   new page contains:
   - **Present state:** the live caller `python -m agent.loop --brain range-skill` and its required flags;
     `request-start-owned-pulse-v1`; checkpoint `698d8831` and where its binding lives; a pointer to
     `recording-protocol.md`.
   - **Run ledger:** a pointer to `learning-plan.md:75-135`, not a copy.
   - **Index table:** one row per note with its conclusion, its acceptance record and whether it is pinned.

   The old body moves to `docs/lanes/archive/range-lead-20260922.md`, with its relative links rewritten.
2. **The live `range-skill` caller contract is currently written only across six frozen notes.** `loop.md` mentions
   none of it: phase slots, expiry as cancellation, owned-pulse end H, `--game-pid`, `--collect-episode`,
   `scope_not_after`. The index above, or a "range-skill mode" section in `loop.md` from its owner, gives it one
   present-state home. Deleting notes without that would lose the only record.
3. **Merge before archiving:**
   - The three HUD deltas (readiness reconciliation, `_masks` reuse, `_countdown_char` vectorization) get one
     paragraph each in `l2-hud.md`, which today has none of them.
   - The outline health-strip repair gets a paragraph in `l3-detector.md` or `tracker.md`.
   - Then archive the unpinned, closed notes: `range-hud.md`, `range-perception.md`, `learned-range.md`, and
     optionally `range-policy-reframe.md`. `learning-plan.md:151` links that last one; fix the link in the same
     commit.
4. **Keep in place:**
   - `range-benchmark.md`: cited by code docstrings.
   - `range-cast-probe.md`: the runbook for a script that is still in use.
   - `range-skill-controller.md`: has a live 09-23 section; the owner may refresh its L3-8.
   - `galacta-pilot.md` and `human-admission.md`: being edited now. Owner notes:
     - The "(unexecuted)" heading at `galacta-pilot.md:214` is stale; pilot 2 stopped at 3 of 20 slots.
     - `human-admission.md` puts its 09-22 disposition first, while its current state (v5, manifest `bcaa1cf4…`)
       is the last section; it also has a second H1 at L192.

Every code path and symbol cited in these 20 docs still exists. What is stale is status claims, not paths. Linear
comments may link these docs by path; that was not checked (read-only brief).

### 3.5 Evidence

- **Keep every entry in place. Move nothing, including into `archive/`. Delete and dedupe nothing.** The 22
  identical-content groups (147 KB) are intentional copies, each pinned in its own folder. The superseded fits
  (`range-first-human-fit`, `range-human-fit-v2`) total 0.26 MB and are pinned by later folders.
- **Add one new file, `docs/evidence/README.md`.** It is an index with one row per entry: date, Linear issue,
  one-line result, status (current, historical, or superseded by X) and owning doc. Its first line should say that
  everything predates the 09-23 whole-session direction.

  Nine entries have no link from outside `docs/evidence`, and the index gives them one:
  - `episode-collection-review-20260922`
  - `human-execution-refactor.md`
  - `replay-measurement-20260923`
  - `range-request-expiry-20260922`
  - `changed-boundary-reviews-20260923`
  - `range-request-cohort-fit-20260923`: the current checkpoint, and no lane doc links it
  - the three `galacta-pilot-slot0*-20260922` folders

  The index should also say which pins are over LF and which over CRLF:
  - `range-fragment-repair`'s `summary.json` and `fit-readiness`'s `driver-review.md` verify only against
    `git show :path`.
  - The pilot-2 `archive-manifest.json` files verify only on a Windows checkout.
- **Stray files at the evidence root:**
  - `practice-settings-20260923-0040.jpg`: its path is written in pinned pilot-2 JSON, so keep it.
  - `human-execution-refactor.md`: keep and index it. It documents the OBS input-logger pipeline, which is
    relevant again today; `recording-protocol.md` could link it.
- **Series:**
  - The request runtime series has five folders (133 MB, cross-pinned). They are distinct accepted diagnostics,
    not superseded.
  - The fits run first → v2 → request timing → request fit `6ee38807` → cohort fit `698d8831` (current).
  - Galacta pilot 1 (four folders) and pilot 2 do not supersede each other.
- **Unowned, not an evidence change:** by default, `perception/autolabel.py` and `perception/eval.py` write
  `--sheet` output into `docs/evidence/l3/` (D4).

### 3.6 Dead links (mechanical check of every tracked `.md`)

| Where | Target | Proposal |
|---|---|---|
| `docs/lanes/range-perception.md:31-37, 236-240, 350-354` | 19 links into `data/diagnostics/range-perception-20260922/`, which is untracked and exists only on the PC | The doc is unpinned. When the owner archives it (§3.4), mark these links as PC-local |
| `docs/lanes/policy.md:156` | `data/experiments/next-behaviour-v1/smoke-01/README.md`, which exists only on the Mac | Owner marks it Mac-local |
| `evidence/range-request-efficiency-runtime-20260922/preflight/caller-review.md:54-91` | 4 links one level too shallow | Record: do not fix |
| `evidence/l4/firstdoor-codex-handback.md:36-40` | 7 PNGs under the untracked `data/reenter/` | Record: do not fix |
| `evidence/changed-boundary-reviews-20260923/review-vuh1315.md:106, 228` | `tests/test_options*.py`, which existed on the reviewed tree, not on main | Record: do not fix |

False positives, which need no action: `local-jev.md:61, 117` name files in other repos; `l4-controller.md:1265`
lists `agent/anchors.py` as "Not written"; `l5-brain.md:307` is an `scp` command. There is no root README;
`AGENTS.md` serves as one.

## 4. Repo hygiene

- **Symlinks on the PC.** `CLAUDE.md`, `.claude/skills` and `.codex/skills` are git symlinks (mode 120000), but
  `core.symlinks=false` on this machine (Git for Windows' system config and the repo config), so they check out as
  9- and 17-byte text files.
  - Claude Code on the PC gets the word "AGENTS.md" as its project instructions, not the rules.
  - `.claude/skills` is not a directory, so the live-game skill doesn't load as a project skill.
  - **Fix for `CLAUDE.md` (D5):** a regular file containing `@AGENTS.md`, which uses Claude Code's import syntax and
    works on both machines.
  - **`.claude/skills`** needs either Developer Mode plus `core.symlinks=true` and a re-checkout on the PC, or
    leaving it as is. Codex reads `AGENTS.md` and `.agents/skills` natively.
- **Tests that read gitignored `data/` without a skip guard.** On a fresh worktree (this one), 35 distinct tests fail
  or error (one of them in both suites):

  | Suite | Result | Test | Reads |
  |---|---|---|---|
  | stdlib | 1 failed | `test_range_skill_loop::test_recorded_first_phase_acquisitions_match_82_4_62_without_retiming` | `data/diagnostics/range-request-runtime-timing-20260922` |
  | perception | 29 errors | `test_hud_countdown_performance.py` (a module fixture) | `data/diagnostics/range-hud-countdown-performance-20260922` |
  | perception | 3 failed | `test_replay_states.py` | `data/run1` |
  | perception | 1 failed | `test_scoreboard::test_a_frame_without_a_scoreboard_reads_nothing` | `data/run1` |
  | perception | 1 failed | `test_hud::test_hud_accuracy` | `data/l2` |
  | perception | 1 failed | the stdlib test above, which fails in this run too | as above |

  - The brief's "4-5 known failures" are the four `data/run1` tests plus `test_hud_accuracy`, which also holds the
    load-sensitive 12 ms latency gate. The shared checkout has the other two `data/diagnostics` folders; a fresh
    clone does not.
  - The guard in `test_scoreboard.py:125` does nothing: `glob(...)[0]` raises IndexError before its
    `if frame is None` check runs.
  - **Proposal:** the owners add `pytest.skip` guards when the data is missing. Until then, CI uses the xfail plugin
    in §6.
- **Bytecode inside pinned folders.** Tests import scripts that live under tracked `data/` (for example
  `data/runtime/galacta-pilot-20260923-preflight/operator/archive_slot.py`), so a test run writes `__pycache__` into
  those folders. It is gitignored, but it is churn inside `data/`. `PYTHONDONTWRITEBYTECODE=1` is set in the justfile
  and in CI (§6). This worktree's copies were removed after the baseline run.
- **Nothing stray is tracked.** No `__pycache__`, `.pyc`, `.env`, weights or `.pt` files. Binaries outside evidence
  are all in use: `tests/fixtures` (15.4 MB, loaded through globs) and `scripts/templates/*.png` (`l4_menu.py`,
  `record.py`). No Git LFS.
- **`.gitattributes`.** The 20 per-folder files (5 variants, mostly `* -text`) are deliberate. **Add no root
  `.gitattributes` with a `text`, `eol` or `-text` rule**: it would change the CRLF bytes that the runtime identity is
  defined over and renormalize `data/` files whose pins assume CRLF. A binary-only rule is harmless but does little.
- **Line endings.** Code is clean: every non-evidence file is LF in the index, with no CRLF or mixed files outside
  evidence and `data/`. `git diff --check` over the whole tree flags only one blank line at EOF in
  `docs/lanes/l1-capture.md:50` (the owner's). `ruff`'s minimal set is clean. There is one invalid `# noqa` directive
  at `scripts/reenter.py:1131`, which pinned `loop.py` loads at run time; leave it.
- **Worktree admin.** `git count-objects` warns about garbage at `.git/worktrees/rivals-agent-cleanup/refs`. It is
  harmless; the lead can prune it.

## 5. Order of operations

Each step is one commit, and each runs `uv run pytest` and `uv run --group perception pytest` followed by `uv sync`
(or `just test` and `just test-perception`), plus `git diff --check`. The comparison is against the baseline in the
appendix.

| Step | Item | Risk: what could break | Needs |
|---|---|---|---|
| 1 | This audit (landed in phase 1) | Nothing | — |
| 2 | Tooling, one commit per file group: `ruff.toml` + `justfile`, `scripts/pins.py`, `.pre-commit-config.yaml`, `.github/**`, `scripts/recording_watch.py` | Nothing on landing, since each is a new file. `pre-commit install` is a separate step that affects every worktree of the clone (§6) | D8 |
| 3 | `docs/evidence/README.md` index (new file) | Nothing: no pins, no tests | Lead yes on the status wording |
| 4 | `scripts/regenerate_sealed.py:5` docstring pointer | Nothing (a docstring in an unpinned, unfrozen file) | Lead yes |
| 5 | `AGENTS.md` read list and "Where things live"; `plan.md` 09-23 Direction bullet; `recording-protocol.md` step-4 anchor | Nothing (text) | Lead (lead-only files) |
| 6 | `CLAUDE.md` → `@AGENTS.md` regular file | Mac sessions must still load the rules: check one session on each machine after landing | D5 |
| 7 | `plan.md` trims (Decision layer, Jev, architecture, lane table, VUH-1347) | The anchors in §3.1 (none of these sections is an anchor target; check with `git grep` before and after) | Lead |
| 8 | `learning-plan.md` split into `docs/archive/` (verbatim) | Five anchors and the glyph paragraph cited by pinned `hud.py:1713`: leave stubs and verify with `git grep` | D7 |
| 9 | Range index (`range-lead.md` rewrite), HUD and outline paragraphs into `l2-hud`/`l3`, archive four unpinned notes | Relative links in the moved body; the `learning-plan.md:151` link; possible Linear links (keep stubs) | D6, owners |
| 10 | Owner fixes to stale headers (`loop`, `l5-brain`, `reentry`, `l4`, `l3`, `jev` → pointer, `l6`, `replay-research`, `combo-arsenal`, `demos`, `human-admission`, `galacta-pilot`); kit fixes; schema trim; skill clause; archive `visual-range-supervision.md` | Headings cited by pinned code (§3.1); the kit's line 6 | Owners, through the lead |
| 11 | Delete `localjev/` | None to tests or pins; `local-jev.md` gets a "removed in" note | D1 |
| 12 | Tag, then delete the B0 chain (4 modules, 2 test files) | Mac-only tests: also run `uv run --group policy pytest` on the Mac. The `policy.md` runbook lines become history | D2 |
| 13 | Clankie retirement, with the PC task and firewall rule removed | `tests/test_session_api.py` goes with it | D3 |
| 14 | `--sheet` defaults out of `docs/evidence/l3/` | `l3/README.md` commands; the owner decides the new default | D4, l3 owner |

**Never, in cleanup:**

- Edit or move evidence.
- Edit any of the 16 frozen files or the ten pinned lane docs.
- Add a root `.gitattributes` text or eol rule.
- Rewrite history.
- Run `ruff format` or `--fix` across the tree.
- Create files named in the brief's list of other lanes' uncommitted work.

## 6. Tooling proposal (James's addendum)

Today the repo has no CI, no pre-commit hooks, no task runner and no linter. The five pieces below are all new files;
nothing existing is edited, and each can be removed by deleting it. They were drafted in a scratch copy and tested on
this PC (Windows, PowerShell 5.1, uv 0.9.26) at `9de857c`.

| Piece | Files | Tested here |
|---|---|---|
| Task runner | `justfile`, `ruff.toml` | Ran with just 1.58.0 through `uvx --from rust-just just`: `test`, `test -k "'brain and not replay'"` (55 passed), `test-perception` passing and failing (exit 1 passed through, `uv sync` still ran, cv2 gone afterwards), and `check` (clean at `9de857c`). The `[unix]` variant was not run; it needs the Mac |
| Closure and declaration guard | `scripts/pins.py` | `closure` prints 10 sha256 values (LF and CRLF for each file), and every one appears in existing receipts (brain CRLF `0deaafb7…` in 29 files, LF `71165c51…` in 9, and so on). It exits 0 at HEAD. `commit-msg` passed eight cases in a scratch repo: non-pinned change, pinned change without a trailer (refused), trailer plus a commented template, empty trailer (refused), `DECLARATION` in the body rather than the trailer block (refused), clean merge carrying the branch's change, merge with new resolved bytes (refused), staged deletion (refused) |
| Hooks | `.pre-commit-config.yaml` | `pre-commit validate-config` passed. A full `pre-commit install` in a scratch repo refused an undeclared commit to `agent/loop.py`, accepted a declared one, and ruff caught an undefined name (F821) |
| CI | `.github/workflows/tests.yml`, `.github/ci/missing_data.py` | actionlint is clean. The plugin turned all 35 non-passes in this worktree's perception run into xfails, and the 1 in the stdlib run; one `test_replay_states` test xpasses, which `strict=False` allows. **Not run on GitHub** (that needs a push), so the first run is also the first macOS run of the stdlib suite |
| Recording watch folder | `scripts/recording_watch.py` | Tested with fake sessions: one new, one open, one already logged, one with a missing video. The new session's row went in after the table's last row, the CRLF line endings were kept, a re-run added nothing, the open session was skipped and the missing video was retried |

**Notes the lead and James should weigh:**

- **Hooks are per clone, not per worktree.** `pre-commit install` writes into the shared `.git/hooks`, so the shared
  checkout, every lane worktree and any worktree-based live tree get the hooks at once. Land the config on main
  first, then install with `--allow-missing-config`, so branches cut before it keep committing. The Mac clone
  installs separately.
- **The guard covers the five files James named.** The pilot-2 freeze covers 16 (headline 3). Extending `PINNED` in
  `scripts/pins.py` is a one-line change if the lead wants the guard on all of them.
  - A merge is refused only when a pinned file ends up with bytes that neither parent had. The branch commits that
    made the change carried their own declarations.
  - `git commit --no-verify` bypasses the guard by design. The rules already forbid skipping hooks unless asked.
- **Ruff starts at the minimal set** (syntax errors and undefined names), which is clean today. The default set
  reports 233 findings, mostly style in tests and the B0 chain. Ratchet up later. Never run `ruff format`: it would
  rewrite pinned files.
- **CI cost and scope.** On a private repo, macOS minutes bill at 10x and Windows at 2x. The stdlib suite takes about
  1 minute of test time per OS, and the perception suite about 5 minutes (Windows only; add `macos-latest` there if
  wanted). Each job checks out about 130 MB. The `paths` filter skips pushes that touch only lane docs or the
  recording notes. Tests read `docs/evidence/**` and `docs/spiderman-kit.md`, so docs as a whole are not skipped.
- **The watcher only prepares.**
  - It reads `metadata.json` and the video's bytes, never `inputs.jsonl`, `frames.csv` or a decode, and it writes
    nothing under `Videos/`.
  - It adds the row in whichever checkout it runs from (the shared one) and leaves it uncommitted for the lead,
    because the log is the lead's.
  - The printed command is the committed importer (`scripts/import_human_demo.py`). Change the `INTAKE` template when
    the admission lane's whole-session intake lands. This proposal does not reference its uncommitted file.
  - It reads the metadata of every complete session, including one James might later call a validation take. That is
    counts and paths only, the same facts the log already holds for the sealed VUH-1347 take. If the admission lane
    wants even that withheld, a `--skip SESSION` flag is a few lines.
- **Installing tools:** `uv tool install rust-just` and `uv tool install pre-commit`. Ruff runs through
  `uvx ruff@0.14.0`, so it is pinned without adding a dependency group or touching `uv.lock`.

### `justfile`

```just
# Task runner. Install once: `uv tool install rust-just` (or `winget install Casey.Just` / `brew install just`).
# Every recipe is one command that reads the same in PowerShell and zsh, except test-perception's two variants.
# Arguments are spliced unquoted: quote a multi-word one twice, e.g. just test -k "'brain and not replay'".

set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

# tests import hash-pinned scripts under data/ and docs/evidence/; keep bytecode out of those folders
export PYTHONDONTWRITEBYTECODE := "1"

ruff := "uvx ruff@0.14.0"

default:
    @just --list

# stdlib-only offline suite: no game, no network; cv2/numpy harnesses are skipped
test *args:
    uv run pytest {{args}}

# perception group, then `uv sync` back to stdlib-only even when tests fail; exits with pytest's status
[unix]
test-perception *args:
    uv run --group perception pytest {{args}}; rc=$?; uv sync; exit $rc

# perception group, then `uv sync` back to stdlib-only even when tests fail; exits with pytest's status
[windows]
test-perception *args:
    uv run --group perception pytest {{args}}; $rc = $LASTEXITCODE; uv sync; exit $rc

# whitespace errors (unstaged and staged), then lint; never `ruff format`, which would rewrite pinned files
check:
    git diff --check
    git diff --cached --check
    {{ruff}} check .

# git blob, LF and CRLF sha256 of the five identity-pinned files; exits 1 if any differs from HEAD
closure *args:
    uv run python scripts/pins.py closure {{args}}
```

### `ruff.toml`

```toml
# Lint only. Never run `ruff format`: it would rewrite the identity-pinned files (scripts/pins.py).
target-version = "py310"
extend-exclude = ["docs", "data"]   # evidence scripts are hash-pinned records, not maintained code

[lint]
# Syntax errors and undefined names: clean at 9de857c. The default set (E4, E7, E9, F) reports 233, mostly style.
select = ["E9", "F63", "F7", "F82"]
```

### `scripts/pins.py`

```python
"""The five identity-pinned runtime files: print their closure, or refuse an undeclared commit to them.

  uv run python scripts/pins.py closure [--json]      # `just closure`
  python scripts/pins.py commit-msg <message-file>    # the pre-commit commit-msg hook (.pre-commit-config.yaml)

Checkpoint bindings pin these files' bytes. Receipts record two forms because the PC checks out CRLF
(core.autocrlf) while git and the Mac hold LF: `LF_normalized_sha256` and `CRLF_blob_sha256`, as in
data/runtime/galacta-pilot-20260923-preflight/controller-deployed.json. `closure` prints both, the git
blob id, and whether the working file still matches HEAD.

A commit that changes one of them is refused unless its message carries a `DECLARATION:` trailer saying
why and which binding it invalidates. A merge is checked only for bytes that neither parent had (a
conflict resolution); the branch commits that made the change carried their own declarations.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PINNED = ("perception/hud.py", "perception/outline.py", "agent/loop.py", "agent/brain.py", "agent/tracker.py")
TRAILER = "DECLARATION"


def git(*args, check=True):
    return subprocess.run(("git", *args), capture_output=True, text=True, check=check).stdout


def closure(root):
    rows = []
    for rel in PINNED:
        lf = (root / rel).read_bytes().replace(b"\r\n", b"\n")
        blob = hashlib.sha1(b"blob %d\0" % len(lf) + lf).hexdigest()   # what `git hash-object` gives the LF bytes
        rows.append({"path": rel, "git_blob": blob,
                     "LF_normalized_sha256": hashlib.sha256(lf).hexdigest(),
                     "CRLF_blob_sha256": hashlib.sha256(lf.replace(b"\n", b"\r\n")).hexdigest(),
                     "matches_HEAD": blob == git("rev-parse", f"HEAD:{rel}", check=False).strip()})
    return rows


def touched():
    """Pinned paths this commit changes: the index against HEAD, and for a merge only bytes new to both parents."""
    changed = set(git("diff", "--cached", "--name-only", "--no-renames", "--", *PINNED).split())
    merging = subprocess.run(("git", "rev-parse", "-q", "--verify", "MERGE_HEAD"), capture_output=True).returncode == 0
    if merging and changed:
        changed &= set(git("diff", "--cached", "--name-only", "--no-renames", "MERGE_HEAD", "--", *PINNED).split())
    return sorted(changed)


def declared(message_file):
    """True when the message carries a non-empty DECLARATION: trailer (git's own trailer parsing)."""
    for line in git("interpret-trailers", "--parse", message_file).splitlines():
        key, _, value = line.partition(":")
        if key.strip().upper() == TRAILER and value.strip():
            return True
    return False


def commit_msg(message_file):
    paths = touched()
    if not paths or declared(message_file):
        return 0
    print("Refused: this commit changes identity-pinned file(s):", *(f"  {p}" for p in paths), sep="\n", file=sys.stderr)
    print("Checkpoint bindings pin their bytes (run `just closure`). If the change is intended, end the message\n"
          "with a trailer in the same block as Co-Authored-By, for example:\n"
          f"  {TRAILER}: agent/loop.py changes <what>; binding <which> must be re-issued (VUH-NNNN)", file=sys.stderr)
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("closure").add_argument("--json", action="store_true")
    sub.add_parser("commit-msg").add_argument("message_file")
    a = ap.parse_args(argv)
    if a.command == "commit-msg":
        return commit_msg(a.message_file)
    rows = closure(Path(git("rev-parse", "--show-toplevel").strip()))
    if a.json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            print(f"{r['path']:22} blob {r['git_blob']}  LF {r['LF_normalized_sha256']}  "
                  f"CRLF {r['CRLF_blob_sha256']}  {'= HEAD' if r['matches_HEAD'] else 'CHANGED vs HEAD'}")
    return 0 if all(r["matches_HEAD"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
```

### `.pre-commit-config.yaml`

```yaml
# Install once per clone (hooks live in the shared .git, so every worktree of that clone gets them):
#   uv tool install pre-commit
#   pre-commit install --allow-missing-config
# --allow-missing-config lets branches cut before this file landed keep committing.
default_install_hook_types: [pre-commit, commit-msg]
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.0
    hooks:
      - id: ruff-check          # no --fix: a hook never rewrites a staged file
        stages: [pre-commit]
  - repo: local
    hooks:
      - id: identity-pinned-declaration
        name: identity-pinned files need a DECLARATION trailer
        entry: python scripts/pins.py commit-msg
        language: python        # stdlib only; pre-commit supplies the interpreter on both machines
        stages: [commit-msg]
        always_run: true
```

### `.github/workflows/tests.yml`

```yaml
# Offline suites on every push. No game, no pad, no network in the tests; recordings under data/ are
# gitignored, so the tests that read them are xfail(strict=False) here only (.github/ci/missing_data.py).
name: tests

on:
  push:
    paths:                        # tests read docs/evidence/** and docs/spiderman-kit.md, so docs are not ignored wholesale
      - "**"
      - "!docs/lanes/**"
      - "!docs/recording-*.md"
  workflow_dispatch:

concurrency:
  group: tests-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

env:
  PYTHONPATH: .github/ci          # makes `-p missing_data` importable
  PYTHONDONTWRITEBYTECODE: "1"

jobs:
  stdlib:
    strategy:
      fail-fast: false
      matrix:
        os: [windows-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.11"
      - run: uv run pytest -p missing_data -p no:cacheprovider -q

  perception:
    runs-on: windows-latest       # the PC runs perception live; add macos-latest here if the Mac replays need it (10x minutes)
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.11"
      - run: uv run --group perception pytest -p missing_data -p no:cacheprovider -q
```

### `.github/ci/missing_data.py`

```python
"""CI only: tests that read recordings a fresh clone does not have are xfail(strict=False) there.

Loaded by .github/workflows/tests.yml as `pytest -p missing_data` with PYTHONPATH=.github/ci. A developer run
never loads it. Each entry names the gitignored data it reads, and the mark applies only while that path is
absent, so a machine that has the data still runs these tests and still has to pass them.
"""
import pytest

NEEDS = {   # node id, or file for a whole module: the untracked path it reads (measured on a fresh clone, 2026-09-23)
    "tests/test_replay_states.py": "data/run1",
    "tests/test_scoreboard.py::test_a_frame_without_a_scoreboard_reads_nothing": "data/run1",
    "tests/test_hud.py::test_hud_accuracy": "data/l2",       # also the 12 ms median latency gate: runner-load sensitive
    "tests/test_hud_countdown_performance.py": "data/diagnostics/range-hud-countdown-performance-20260922",
    "tests/test_range_skill_loop.py::test_recorded_first_phase_acquisitions_match_82_4_62_without_retiming":
        "data/diagnostics/range-request-runtime-timing-20260922",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        for prefix, data in NEEDS.items():
            if (item.nodeid == prefix or item.nodeid.startswith(prefix + "::")) and not (config.rootpath / data).exists():
                item.add_marker(pytest.mark.xfail(strict=False, reason=f"reads {data}, which is gitignored and not in CI"))
```

### `scripts/recording_watch.py`

```python
"""Prepare finished input-logger sessions for intake: hash the video, add a recording-log row, print the command.

  uv run python scripts/recording_watch.py                     # poll ~/Videos/RivalsInput every 60 s (the PC)
  uv run python scripts/recording_watch.py --once --dry-run    # one pass; print rows, write nothing

A session is ready when its metadata.json says `complete: true` and the video it names has stopped changing.
This script only prepares. It reads metadata.json and the video's bytes, and nothing else: never inputs.jsonl
or frames.csv, never a decode, never a write under Videos/. It registers, splits, seals and imports nothing;
that is the admission lane's (docs/human-demo-schema.md, docs/machines.md "Record on Windows, import on the
Mac"). A take James calls a validation take is sealed there before anything reads its content.

The row goes into the table in docs/recording-log.md. Content and Cooldowns are left for the lead to fill
from what James says; the intake status column carries what the logger reported and the video's sha256 (the
`expected_media_sha256` a Mac registry needs). A session whose id is already in the log is skipped, so
re-runs and restarts are safe. The log edit is left uncommitted for the lead.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "docs" / "recording-log.md"
HEADER = "| Video (Videos/) | Logger session |"
INTAKE = ('uv run python scripts/import_human_demo.py import --session "{session}" --review <review.json> '
          '--splits <session-splits.json> --output <imported-demo.jsonl>')


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def settled(video, settle_s):
    """The video exists and its size and mtime did not change over settle_s."""
    try:
        before = video.stat()
        time.sleep(settle_s)
        after = video.stat()
    except OSError:
        return False
    return (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)


def row(meta, video, digest):
    minutes = (int(meta["end_ns"]) - int(meta["start_ns"])) / 60e9
    logger = ", ".join((
        "logger complete" if meta.get("status") == "complete" else f"logger status {meta.get('status')!r}",
        "clean stop" if meta.get("clean_stop") is True else "NOT a clean stop",
        f"{meta.get('queue_dropped_events')} drops", f"{meta.get('raw_input_errors')} raw-input errors"))
    return (f"| {video.name} | {meta['session_id']} | {minutes:.1f} min | (lead: from James) | (lead: from James) "
            f"| {logger}; video sha256 `{digest}`; intake pending |")


def insert(text, line):
    """Add `line` after the last row of the recording table, keeping the file's own line endings."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)
    start = next((i for i, s in enumerate(lines) if s.startswith(HEADER)), None)
    if start is None:
        raise SystemExit(f"{LOG}: no table starting {HEADER!r}; nothing written")
    end = start
    while end + 1 < len(lines) and lines[end + 1].startswith("|"):
        end += 1
    return newline.join(lines[:end + 1] + [line] + lines[end + 1:])


def read_log():
    with open(LOG, encoding="utf-8", newline="") as handle:     # keep the checkout's own line endings
        return handle.read()


def scan(root, settle_s, dry_run):
    log = read_log()
    for meta_path in sorted(root.glob("*/metadata.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue                                   # still being written: next pass
        if meta.get("complete") is not True or not meta.get("session_id") or meta["session_id"] in log:
            continue
        video = Path(meta.get("video_path", ""))
        if not video.is_file():
            print(f"{meta['session_id']}: video {video} not found; will retry", file=sys.stderr)
            continue
        if not settled(video, settle_s):
            continue
        before = video.stat()
        digest = sha256(video)
        after = video.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            continue                                   # changed while hashing: next pass
        line = row(meta, video, digest)
        if dry_run:
            print(line)
        else:
            log = insert(read_log(), line)
            with open(LOG, "w", encoding="utf-8", newline="") as handle:
                handle.write(log)
            print(f"{LOG.relative_to(ROOT)}: added {meta['session_id']}")
        print(f"  recorded_video_path: {meta['video_path']}\n  expected_media_sha256: {digest}\n"
              f"  when the admission lane has registered and reviewed it:\n    {INTAKE.format(session=meta_path.parent)}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path.home() / "Videos" / "RivalsInput")
    ap.add_argument("--every", type=float, default=60.0, help="seconds between passes")
    ap.add_argument("--settle", type=float, default=10.0, help="seconds the video must stay unchanged")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print rows; write nothing")
    a = ap.parse_args(argv)
    while True:
        scan(a.root, a.settle, a.dry_run)
        if a.once:
            return 0
        time.sleep(a.every)


if __name__ == "__main__":
    sys.exit(main())
```

## Appendix: test baseline on this worktree (`9de857c`, fresh, no untracked `data/`)

| Suite | Passed | Skipped | Failed | Errors |
|---|---:|---:|---:|---:|
| `uv run pytest` | 1,264 | 60 | 1 | 0 |
| `uv run --group perception pytest` | 2,088 | 147 | 6 | 29 |

All 35 distinct non-passing tests read gitignored `data/` (§4). No test touched the game, the network or the pad. `uv sync`
restored the stdlib-only environment afterwards.
