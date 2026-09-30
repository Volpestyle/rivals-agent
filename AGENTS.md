# rivals-agent

A vision-based agent that plays Spider-Man in the Marvel Rivals **practice range** on a
virtual Xbox 360 pad. Windows `supedupsilly` owns gameplay, recording and the live
agent loop; the M5 Max Mac owns offline preparation, training and evaluation.
Development can run on either machine. `CLAUDE.md` imports this file (its one line is `@AGENTS.md`).
`.claude/skills` and `.codex/skills` are git symlinks to `.agents/skills`. A checkout with `core.symlinks=false`
gets them as one-line text files and loads no repo skills; set it to `true` and re-checkout those paths
(the PC was fixed this way on 2026-09-26; see `~/dotfiles/docs/agents/setup.md`).

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
   Use `rivals-progress` when a result, blocker, scope or handoff changes, and before
   asking James for more recording or calibration. A plan or checkbox alone is not completion evidence.
5. `docs/machines.md` before moving code, data or jobs between machines: ownership,
   SSH directions, immutable recording relocation and checkpoint boundaries.

## Where things live

| Path | Holds |
|---|---|
| `docs/plan.md` | Lead-only. One writer, because a shared edit lost sections once |
| `docs/learning-plan.md` | The canonical learning plan: milestones, advancement gates, reward contract. Lead's |
| `docs/recording-protocol.md`, `docs/recording-log.md` | What James does per recording session, and the ledger of every take (the lead appends rows; the admission lane fills intake status) |
| `docs/machines.md` | Mac/PC responsibilities, remote access and transfer procedure |
| `docs/compute.md` | The compute protocol: which machine runs what, the Mac queue and PC memory rules, Modal/AWS caps and teardown, the explore and confirm tracks, and job status for the dashboard. The `rivals-compute` skill points at it |
| `data/calibration/<sitting>/SITTING.md` | What a supervised pad sitting actually ran, measured and left open; newer than any plan |
| `docs/steering/` | The retired steering pane's charter and handoff (history, 2026-09-26/27) and the spend ledger (current) |
| `docs/lanes/<lane>.md` | Each lane's technical findings and measured facts; the lane's owner is its only writer. Status is on Linear |
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
| `docs/README.md` | Which docs and lane notes are current, history or frozen |

## Documentation: one home per fact

Nobody writes the same fact twice. Each kind of fact has one home; every other place links to it or carries a
one-line pointer. When two places disagree, the newest dated record wins (`SITTING.md`, the tail of
`docs/recording-log.md`, an evidence README, the issue's latest Linear comment), and you fix the older place to link
to it instead of adding a third statement.

| Fact | Its one home | Everywhere else |
|---|---|---|
| Status: done, in progress, blocked, owner, next action | The Linear issue | Nothing else keeps status; plans and lane notes link the issue |
| A sitting: what ran, what it measured, what is open | `data/calibration/<sitting>/SITTING.md` | Linear gives the outcome in a line and links it |
| A run's result, receipts and analysis | `docs/evidence/<folder>/README.md` (frozen once written) | `SITTING.md` and Linear give the one-line result and link it |
| A lane's technical findings | `docs/lanes/<lane>.md` (owner only) | Plans link the note; the note links the plan, never repeats it |
| Scope, direction, architecture | `docs/plan.md` (lead) | Lane notes and skills link it |
| Gates, milestones, reward contract | `docs/learning-plan.md` (lead) | |
| Recording takes and James's settings statements | `docs/recording-log.md` | |
| Compute rules, caps, the spend process; spend actuals | `docs/compute.md`; `docs/steering/spend-ledger-20260927.md` | Skills and plans link them |
| A run's cost, one-line result, keep verdict and best visual (paid or free) | `docs/runs-ledger.md`: add the row when the run finishes | The training lab board reads it; Linear updates and posts draw from it. Visual craft: the `result-visuals` skill |
| How to operate a tool (live game, compute, Linear) | The skill in `.agents/skills/` | `AGENTS.md` names the skill and keeps only a safety rule and its reason |
| Kit, bindings, patch | `docs/spiderman-kit.md`, `docs/pad-bindings.md` | |

- **Linear gets the outcome, the decision or blocker and the next action in a few lines, plus a link.** Never the
  detail: numbers, tables and reasoning stay in the record they came from.
- **One result, one record.** A run's analysis lives in its evidence README; a sitting's `SITTING.md` logs the sitting
  and links it. Don't open a new note for a launch plan, a receipt refresh or a check-in: that belongs in the run's
  evidence folder or its Linear comment.
- **Marking something superseded.** Don't rewrite history in place. Start the stale passage with
  `*Superseded YYYY-MM-DD by <link>: <one line>.*`, or put a status line under a note's title:
  `**Status (YYYY-MM-DD): CURRENT | HISTORY | SUPERSEDED | PARKED.** <one line with a link to what replaced it>.`
- **Keep or delete.** Evidence, `data/`, and any note or code file whose sha256 a receipt or freeze manifest pins are
  never edited, moved or deleted ("Frozen review packets" below). An unpinned working note that nobody consults any
  more is trimmed to its status line or removed with `git rm` by its owner or the lead; git history is the archive,
  so don't copy it into `docs/archive/`. Fix inbound links first, and keep a file that a frozen record links to.
  Never delete an untracked file you didn't create.
- **Instructions name one place.** A doc or skill that tells agents to record something names a single home from the
  table above.

## Rules that came from real failures

- A plan is not a record. Before telling James what a sitting needs, or stating what a lane has done, read the
  newest dated records: the `docs/recording-log.md` rows, the lane note, the sitting's
  `data/calibration/<sitting>/SITTING.md`, and the Linear issue's latest comment. Pinned plans such as
  `docs/next-pc-session.md` (2026-09-23) keep their old wording forever. On 2026-09-26 a lead asked James to redo a
  calibration sitting he had finished that evening.
- `State.frame` is required and comes from the frame actually processed. Every
  `Detection.bbox` is in those pixels. A default frame size once put every box 2x off.
- A perception reader returns a value or an explicit unknown (`None`), never a guess, and
  the brain never reads unknown as zero.
- Any loop that sends input confirms the range HUD on a fresh frame first and stops when
  it disappears. Workers never navigate the lobby; they hand back to the lead.
- A live guard protects safety only: game focus, the range HUD and idle warning (monitored throughout, not only
  before attach), human takeover (any key or mouse button), a deadline and a guaranteed pad release. Judge data
  quality (a still or textured view, a confident image shift, frame age under a fixed stick schedule) offline from
  retained frames and native video, and discard the bad spans instead of refusing the run.
  Frame age is a safety check only when the input depends on what the frame shows. Sittings b–e (2026-09-27/28)
  refused about seven camera-calibration attempts on quality checks and measured nothing; each refusal cost James
  a sitting plus a code-and-review cycle, the way over-tight spend guards once cost more than they saved.
- The outline finder drops small marks inside the hero's measured screen region (a frame-terms
  zone, `perception/outline.py`) before any box reaches the tracker; nothing in `agent/` filters
  detections by screen region, so that guard is the only hero-region protection. A labeller once
  boxed Spider-Man's arm as an enemy; the zone is measured, not guessed (VUH-1355).
- The PC's GPU belongs to the game while it is running. Train on the Mac (MPS), niced;
  CUDA training is an explicit exception while the game and recording are stopped.
  Live-agent inference may use the PC's GPU while the game runs (James, 2026-09-27); the owner measures and
  reports the game's FPS cost.
- Capture, perception, safety and latency-sensitive control stay on the PC, and capture and pad code run inside
  its desktop session, not plain SSH. SSH moves jobs and artifacts; a Mac round trip is not the default live
  action path.
- One agent drives the PC desktop at a time.

## Agent delivery protocol

Use `herdr-lead` for swarm coordination and `herdr` for pane operations. An idle Codex worker receives nothing
through Swarm, and `codex queue` does not wake the `--no-daemon` panes (tested 2026-09-28). An idle Claude worker
missed a Swarm message too (2026-09-30), so the lead prompts any idle worker through Herdr. So the lead sends a
message to a Codex worker as one Herdr prompt carrying the whole message, confirms it was submitted, and sends no
Swarm copy. Workers reply to the lead with `swarm_send`, which reaches a Claude lead on its own. Nobody polls an idle
model in a loop (`~/dotfiles/docs/agents/swarm-launch.md`). Keep one
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
  Keep acceptance, accountable owner, a link to the current evidence, limitations and next action there.
  Workers publish substantive results once; the lead owns disputed acceptance and transitions.
  Before handing off a material result, reconcile the affected issue's current result, remaining
  acceptance and next action, then read back the write. The lead reconciles changed dependencies,
  milestones and project entry points in that same delivery; `rivals-progress` gives the procedure.
  If publication fails, keep the exact pending correction and owner in the existing handoff and
  report the result as produced but not yet recorded. Preserve frozen and historical evidence.
  Load `linear-issues` and use the direct workspace Linear MCP for writes. Panes hold coordination and are not a
  status queue; where each result's detail goes is in "Documentation: one home per fact" above.
- **Validate measurements early.** Pair a reader or label-rule change with a small inspected
  native-frame sample before a large extraction. Test the demonstrated failures and valid
  controls together; synthetic correctness alone cannot establish that a label is true.
  Use only authorized development evidence; sealed sources remain under the plan's contract.
- **Review only live-input safety** (lean mode, "Working here"). Everything else ships on the owner's tests and a
  visible result. A new review or benchmark needs a named uncertainty, not another completion ceremony.
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
- **Lean mode (James, 2026-09-30): "first make it work, then make it good".** No ceremony that slows results. New
  work gets no receipts, freeze manifests, hash pins, pre-registrations, or re-review rounds. Frozen *existing*
  records stay untouched, but nothing new gets frozen. Owners test their own code, commit it, and report.
  Before new live-game input code first runs, one quick read-only safety check by any agent other than the author
  (focus, HUD guard, human takeover, deadline, pad release) takes minutes, not a packet. Sealed test data stays
  sealed. Cost is not a gate: rent GPUs when it speeds results, and log the spend in the ledger afterwards.
- Several agents often share this checkout. Edit only the paths your brief names, and
  load the `shared-checkout` skill before committing.
- **Frozen review packets.** A lane note whose current bytes are pinned by a review receipt or a freeze
  manifest is never edited or moved, not even to fix a link or a stale "not yet accepted" line; the receipt
  that pins it records its acceptance. `docs/README.md` lists the pinned notes (`docs/lanes/range-lead.md` gives
  the range ones' status), and `docs/evidence/README.md` indexes evidence, which follows the same rule. Before editing a lane note, search `docs/evidence/` and `data/` for its sha256 (both the LF and CRLF
  forms). Code has an equivalent: editing any file of a deployment freeze (for checkpoint `698d8831`, the 16
  files hashed in `data/runtime/galacta-pilot-20260923-preflight/*-deployed.json`) forces a re-freeze before
  that checkpoint runs again.

- **pre-commit hooks are not installed on the shared PC checkout** (2026-09-23): pre-commit stashes every unstaged tracked file around each commit, which is unsafe when other lanes have uncommitted work in the same tree. Run `uv run pre-commit run --all-files` manually on a clean worktree, or install the hooks only in a private worktree.
