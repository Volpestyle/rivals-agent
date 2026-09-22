# rivals-agent

A vision-based agent that plays Spider-Man in the Marvel Rivals **practice range** on a
virtual Xbox 360 pad. Windows `supedupsilly` owns gameplay, recording and the live
agent loop; the M5 Max Mac owns offline preparation, training and evaluation.
Development can run on either machine. `CLAUDE.md` is a symlink to this file.

## Read before doing anything

1. `docs/plan.md`: scope boundary, gate results, architecture, perception decisions. The
   scope boundary is binding: pixels only, no anti-cheat evasion, no matchmade modes, and
   a path the game rejects stays closed. Stop and report instead of working around it.
2. The `rivals-live-game` skill (`.agents/skills/`) before sending any input to the game.
   On the PLAY lobby the pad's `X` starts a live Quick Match.
3. Linear project **Rivals Agent** (team Vuhlp): what is done, in progress and blocked.
   Accepted results and evidence go on the issue; working notes stay in `docs/lanes/`.
4. `docs/machines.md` before moving code, data or jobs between machines: ownership,
   SSH directions, immutable recording relocation and checkpoint boundaries.

## Where things live

| Path | Holds |
|---|---|
| `docs/plan.md` | Lead-only. One writer, because a shared edit lost sections once |
| `docs/machines.md` | Mac/PC responsibilities, remote access and transfer procedure |
| `docs/lanes/<lane>.md` | Each lane's present-state notes and measured facts; the lane's owner is its only writer |
| `docs/spiderman-kit.md` | Sourced controller bindings, cooldowns, tracer rule, combos, settings |
| `docs/evidence/` | Inspected screenshots and contact sheets per lane |
| `agent/` | `State` contract, intents, scripted brain, Jev client, replay |
| `perception/` | HUD readers, enemy finders, training, offline State replay |
| `scripts/` | `pad.py` (pad token sequencer), `padrun.sh`, `capture.py`, `record.py` |
| `.env` | `JEV_URL`, `JEV_MODEL`, `JEV_KEY` (TypeSafe's direct API, the default route) and `OPENROUTER_API_KEY` (fallback), and `HF_TOKEN` (read-only Hugging Face token, for gated pretrained encoders only; nothing is ever uploaded); gitignored, also at `C:\rivals-agent\.env`. Never print or log a key. `JEV_KEY` goes to whatever `JEV_URL` names, so set or clear them together |

## Rules that came from real failures

- `State.frame` is required and comes from the frame actually processed. Every
  `Detection.bbox` is in those pixels. A default frame size once put every box 2x off.
- A perception reader returns a value or an explicit unknown (`None`), never a guess, and
  the brain never reads unknown as zero.
- Any loop that sends input confirms the range HUD on a fresh frame first and stops when
  it disappears. Workers never navigate the lobby; they hand back to the lead.
- Detections inside the player's own screen region are ignored before aiming: a labeller
  once boxed Spider-Man's arm as an enemy.
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
