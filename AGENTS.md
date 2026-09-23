# rivals-agent

A vision-based agent that plays Spider-Man in the Marvel Rivals **practice range** on a
virtual Xbox 360 pad. Windows `supedupsilly` owns gameplay, recording and the live
agent loop; the M5 Max Mac owns offline preparation, training and evaluation.
Development can run on either machine. `CLAUDE.md` imports this file (its one line is `@AGENTS.md`).
`.claude/skills` and `.codex/skills` are git symlinks to `.agents/skills`. They work on the Mac, but the PC
checks them out as plain text (`core.symlinks=false`), so read skills there directly from `.agents/skills/`.
Claude Code has no plain-file way to point at another skills folder, so they stay symlinks.

## Read before doing anything

1. `docs/plan.md`: scope boundary, gate results, architecture, perception decisions. The
   scope boundary is binding: pixels only, no anti-cheat evasion, no matchmade modes, and
   a path the game rejects stays closed. Stop and report instead of working around it.
2. `docs/recording-protocol.md` and `docs/recording-log.md`: the current direction, set by James on
   2026-09-23. It is whole-session keyboard/mouse recordings for one end-to-end policy that outputs
   semantic actions plus camera degrees, executed by the pad. The log is the ledger of every take.
   `docs/learning-plan.md` is the canonical plan and holds the advancement gates.
3. The `rivals-live-game` skill (`.agents/skills/`) before sending any input to the game.
   On the PLAY lobby the pad's `X` starts a live Quick Match.
4. Linear project **Rivals Agent** (team Vuhlp): what is done, in progress and blocked.
   Accepted results and evidence go on the issue; working notes stay in `docs/lanes/`.
5. `docs/machines.md` before moving code, data or jobs between machines: ownership,
   SSH directions, immutable recording relocation and checkpoint boundaries.

## Where things live

| Path | Holds |
|---|---|
| `docs/plan.md` | Lead-only. One writer, because a shared edit lost sections once |
| `docs/learning-plan.md` | The canonical learning plan: milestones, advancement gates, reward contract. Lead's |
| `docs/recording-protocol.md`, `docs/recording-log.md` | What James does per recording session, and the ledger of every take (the lead appends rows; the admission lane fills intake status) |
| `docs/machines.md` | Mac/PC responsibilities, remote access and transfer procedure |
| `docs/lanes/<lane>.md` | Each lane's present-state notes and measured facts; the lane's owner is its only writer |
| `docs/spiderman-kit.md` | Sourced controller bindings, cooldowns, tracer rule, combos, settings. Its "Patch reflected" line is read at run time: keep it byte-identical within the first 2,000 characters |
| `docs/evidence/` | Hash-pinned run records: frames, receipts, reports and the scripts that made them. Never edited or moved; `docs/evidence/README.md` indexes them |
| `agent/` | `State` contract, intents, scripted brain, tracker, pad controller, live loop and start phase, learned range brains, human demonstration import and whole-session intake, placement, Jev client (frozen), replay |
| `perception/` | HUD readers, scoreboard and event stream, enemy finders (green outline; the YOLO path is kept for VOD footage), camera motion, offline State replay |
| `policy/` | Learned policies: `range_bc/` (end-to-end whole-session fit), `range_skill_policy.py` (web-start head, checkpoint `698d8831`), `execution.py` (keyboard/mouse baseline), and the MLX chooser (`live`, `train`, `encode`, `frames`, `corpus`, `behaviour`) |
| `scripts/` | Pad and capture: `pad.py`, `padrun.sh`, `capture.py`, `record.py`. Arrival and menus: `reenter.py`, `l4_menu.py`, `l4_practice_settings.py`. Placement: `place.py`. Also `range_benchmark.py`, `range_cast_probe.py`, `import_human_demo.py`, `recording_watch.py`, `pins.py` and `regenerate_sealed.py`, plus the one-off measurements `l4_measure.py`, `l4_trial.py` and `padprime_m1.py` |
| `agent/server.py`, `agent/session.py`, `scripts/clankie_bridge.ps1`, `docs/clankie.md` | Clankie's session API bridge (VUH-1316): bounded sittings around `agent.loop`. Disabled on the PC (its scheduled task and firewall rule are installed but off, VUH-1325) and being wired on the Mac. The bridge author owns these files; keep them |
| `tests/` | `uv run pytest` (stdlib) and `uv run --group perception pytest`; fixtures under `tests/fixtures/` |
| `justfile`, `ruff.toml`, `.pre-commit-config.yaml`, `.github/` | `just test`, `test-perception`, `check`, `closure`; lint; the `DECLARATION:` commit guard for the identity-pinned files; CI |
| `.env` | `JEV_URL`, `JEV_MODEL`, `JEV_KEY` (TypeSafe's direct API, the default route) and `OPENROUTER_API_KEY` (fallback), and `HF_TOKEN` (read-only Hugging Face token, for gated pretrained encoders only; nothing is ever uploaded); gitignored, also at `C:\rivals-agent\.env`. Never print or log a key. `JEV_KEY` goes to whatever `JEV_URL` names, so set or clear them together |

## Rules that came from real failures

- `State.frame` is required and comes from the frame actually processed. Every
  `Detection.bbox` is in those pixels. A default frame size once put every box 2x off.
- A perception reader returns a value or an explicit unknown (`None`), never a guess, and
  the brain never reads unknown as zero.
- Any loop that sends input confirms the range HUD on a fresh frame first and stops when
  it disappears. Workers never navigate the lobby; they hand back to the lead.
- The outline finder drops small marks inside the hero's measured screen region (a frame-terms
  zone, `perception/outline.py`) before any box reaches the tracker; nothing in `agent/` filters
  detections by screen region, so that guard is the only hero-region protection. A labeller once
  boxed Spider-Man's arm as an enemy; the zone is measured, not guessed (VUH-1355).
- Capture and pad code run inside the PC's desktop session, not plain SSH.
- The PC's GPU belongs to the game while it is running. Train on the Mac (MPS), niced;
  CUDA training is an explicit exception while the game and recording are stopped.
- Capture, perception, safety and latency-sensitive control stay on the PC. SSH moves
  jobs and artifacts; a Mac round trip is not the default live action path.
- One agent drives the PC desktop at a time.

## Agent delivery protocol

Use `herdr-lead` for swarm coordination and `herdr` for pane operations. Keep one
lead responsible for dispatch, shared integration and Linear status transitions;
co-leads route scope decisions through that lead. A status request alone creates no work.

- **Organize around two outcomes:** expert learning (audited demonstrations through a
  baseline-compared policy) and reliable autonomous episodes (tracking, recovery, resets
  and measured outcomes). Their owners join at learned-controller evaluation and RL;
  use the advancement gates in `docs/learning-plan.md`, not a new parallel roadmap.
- **Keep ownership through delivery.** One accountable owner carries each bounded result
  from its prerequisites through integration and its next usable experiment. Specialists
  own named files or artifacts and hand back to that owner. A brief names the existing
  Linear issue, result, paths, acceptance, reviewer and next consumer; transfers are explicit.
  Check the actual model and effort against `herdr-lead` before assigning consequential work.
- **Use Linear as the result record.** Reuse the issue for the independently acceptable
  outcome; use checklists for its steps and blocking relations only for real prerequisites.
  Keep acceptance, accountable owner, current evidence, limitations and next action there.
  Workers publish substantive results once; the lead owns disputed acceptance and transitions.
  Load `linear-issues` and use the direct workspace Linear MCP for writes. Plans hold design,
  lane docs hold technical findings, and panes hold coordination; none is a second status queue.
- **Validate measurements early.** Pair a reader or label-rule change with a small inspected
  native-frame sample before a large extraction. Test the demonstrated failures and valid
  controls together; synthetic correctness alone cannot establish that a label is true.
  Use only authorized development evidence; sealed sources remain under the plan's contract.
- **Review the changed boundary.** Required independent review remains binding. Reuse accepted
  evidence for unchanged inputs and behavior; re-review the delta and unresolved findings.
  A new review or benchmark needs a named uncertainty, not another completion ceremony.
- **Keep capacity tied to a deliverable.** Park workers with no independent ready result.
  During shared-data migration, keep one corpus writer and stop dependent readers; spare
  capacity may address the independent episode stream. Do not fill idle panes with new scope.
- **Report delivery honestly.** Say what was produced, accepted, landed or demonstrated,
  with evidence and the next blocker; a running pane is not progress. If two updates add only
  preparation or coordination, name the blocker and shorten the path to a concrete attempt.

## Working here

- `uv run pytest` runs the stdlib-only offline suite; no network, no game. Tests that import
  `cv2`, `numpy` or `perception` are skipped there and run with `uv run --group perception pytest`
  (`uv sync` afterwards restores the stdlib-only environment). Perception lanes run the second form.
- A test that reads the demonstration corpus under `data/` carries `@pytest.mark.corpus` and is skipped
  unless `--corpus` is given, so a whole-file or broad `-k` run never opens sealed or mid-migration files
  by accident. Each lane marks its own tests.
- Python via `uv`; standard library first; add a dependency only when a few lines cannot do it.
- Review is independent of the lane that wrote the code. Code that sends input to the live
  game, and code that decides what enters a training or evaluation set, gets a read-only
  review by an agent outside the lane (preferably another model family) before it is relied
  on; the lead verifies each finding before dispatching a fix to the owning lane. A lane's
  own tests and report are evidence, not a review.
- Several agents often share this checkout. Edit only the paths your brief names, and
  load the `shared-checkout` skill before committing.
- **Frozen review packets.** A lane note whose current bytes are pinned by a review receipt or a freeze
  manifest is never edited or moved, not even to fix a link or a stale "not yet accepted" line; the receipt
  that pins it records its acceptance. `docs/lanes/range-lead.md` lists the pinned range notes and states
  their present status, and `docs/evidence/README.md` does the same for evidence, which follows the same
  rule. Before editing a lane note, search `docs/evidence/` and `data/` for its sha256 (both the LF and CRLF
  forms). Code has an equivalent: editing any file of a deployment freeze (for checkpoint `698d8831`, the 16
  files hashed in `data/runtime/galacta-pilot-20260923-preflight/*-deployed.json`) forces a re-freeze before
  that checkpoint runs again.
