# galacta-pilot-20260923: binding procedure, operator checklist, time estimate

Prepared offline on 2026-09-23 against main `4e9d10e` (VUH-1319, VUH-1311, VUH-1314). Nothing here has touched the game.
The learned candidate is checkpoint `698d8831a6740d1d060ed3691dc2102fc1a39987ad4c7a03ad4c96a49df9ce1b` at confidence 0.7.
The schedule is `data/benchmarks/galacta-pilot-20260923/schedule.json`. The whole binding chain was dry-run in scratch with a
**mock** effective setup (see [Dry-run record](#dry-run-record)). The live tree `C:\Users\volpe\repos\rivals-agent-live` is
still at `e5511c5`: fast-forwarding it is step 1 of the window.

| File | Does |
|---|---|
| `candidate.json` | Pinned inputs: checkpoint, fit reports, cohort `SourceIdentity` (digest `fff3cab1…`), identity and predeclared commits, driver-review blob hash |
| `freeze_deployed.py` | Refuses unless the live tree is clean at `main`, runtime paths are unchanged since `4553072`, and perception/selector hash to the cohort's. Writes `controller-deployed.json`, `perception-deployed.json` (the diagnostic's manifests re-pinned; their Luna run scope and old selector kept under `historical_from_baseline_manifest`), `calibration-current.json`, `deployment-check.json` |
| `collect_settings.py` | Saved settings receipt: client/build, pad profile, display, enemy colour, re-read game PID, the operator's screenshot. Refuses a patch or pad-profile change against the slot-4 receipt |
| `issue_binding.py` | Re-checks deployed bytes, builds `runtime-settings.json`, the scope record `runtime-semantic-review.json`, `SkillRuntimeIdentity` and `SkillDeploymentBinding`, and validates it |
| `check_binding.py` | Reads the three JSON files the way `agent/loop.py` does and live-loads the checkpoint (zero inference), then runs 12 refusal controls. Writes `loader-preflight.json` |
| `launch_slot.ps1` | One slot, once, in order, as a `C:\desk` job. `-CheckOnly` runs every pre-launch check and sends nothing |
| `run_instrumented.py` | The slot-4 thread-settings wrapper, with a per-slot record path |
| `scout.py` | The loop's readers on a saved native frame: HUD, boxes, height bins. A setup reference only |

## The binding

`SkillDeploymentBinding.validate` requires the runtime's patch, cooldown regime, selector hash and revisions to equal the
source's, and the runtime settings hash to differ from the source profile. The runtime identity issued here is:

| Field | Value | Source |
|---|---|---|
| `patch` | `1.1.3870120/build25364676` | `version.json` + Steam manifest, re-read at the window; must equal the source |
| `cooldown_regime` | `normal` | Practice menu (No Ability Cooldown OFF), checked from play each range entry |
| `selector_sha256` | `00fd672e…` | `digest` of `agent/brain.py` + `agent/tracker.py` as CRLF git blobs at the live HEAD |
| `perception_sha256` | `a30b3cae…` | same over `perception/hud.py`, `outline.py`, `agent/loop.py`: like-for-like with the cohort (slot 4 put the manifest hash here instead; the manifest is now pinned in the scope record) |
| `controller_code_sha256` | sha256 of `controller-deployed.json` | the 13 files of the reviewed controller manifest, live bytes vs git blobs |
| `calibration_sha256` | sha256 of `calibration-current.json` | reviewed D defaults and gates, re-read from the live controller and required unchanged |
| `runtime_settings_sha256` | sha256 of `runtime-settings.json` | pins `saved-settings.json` and `effective-setup.json` |
| `semantic_review_sha256` | sha256 of `runtime-semantic-review.json` | scope: schedule hash, the 10 learned run names, game PID, range entry, reviews |
| binding `review_sha256` | `c12a20a85b8f1b90d762e020b98f970e6d8c1fbc0b06fed7fde0a1ba45cb8030` | sha256 of the committed blob of `docs/evidence/fit-readiness-20260923/driver-review.md`, read from the live HEAD. Its git blob id (SHA-1) is `aa3e7990…`; this PC's working-tree bytes hash to `d7482291…` (mixed endings) |

**One binding per game PID and range entry**, scoped to the ten learned allocations, each consumed once by
`launch_slot.ps1`. Slot 4 issued one binding per run; with 10 learned slots that is 10 extra effective-setup records in
the window for no added check, because the setup facts that bind (patch, pad profile, settings, range entry) are
per entry, and per-trial readiness belongs in the schedule's own fields. **Re-issue** after a game PID change, a range
re-entry or any deployed-byte change: move the binding files (`effective-setup.json` through `loader-preflight.json`) to
`superseded/<n>/`, then repeat steps 3 to 5. The launcher refuses a PID that differs from the binding's.

## Procedure (the window)

PowerShell, from `C:\Users\volpe\repos\rivals-agent\data\runtime\galacta-pilot-20260923-preflight`. Each step stops on failure.

```powershell
$LIVE = 'C:\Users\volpe\repos\rivals-agent-live'
function Step { uv run --offline --no-project --python 3.11 @args; if ($LASTEXITCODE) { throw "refused: $args" } }
# 0. Lead, before the window: schedule and these files landed; no commit under agent/ perception/ policy/ scripts/ since 4553072.
# 1. Fast-forward the live tree (a detached worktree of the shared repo).
if (git -C $LIVE status --porcelain) { throw 'live tree dirty' }
git -C $LIVE merge-base --is-ancestor HEAD main; if ($LASTEXITCODE) { throw 'not a fast-forward' }
git -C $LIVE checkout --detach main; if ($LASTEXITCODE -or (git -C $LIVE status --porcelain)) { throw 'checkout failed or dirty' }
# 2. Freeze (refuses on any identity or byte mismatch).
Step python -B freeze_deployed.py
# 3. After the checklist's setup items: the operator writes effective-setup.json (below), then:
$GAME = (Get-Process -Name Marvel-Win64-Shipping).Id
Step python -B collect_settings.py --pid $GAME --screen C:\desk\out\galacta-0923-ready.png
# 4. Binding, then 5. the live-load check with 12 refusal controls.
Step --with torch==2.14.0 python -B issue_binding.py
Step --with torch==2.14.0 python -B check_binding.py
# 6. Each slot N in order, as a C:\desk job (desktop session): . C:\desk\lib.ps1; & .\launch_slot.ps1 -Index N -GamePid $GAME
#    Run it with -CheckOnly first when in doubt; it consumes nothing.
```

`data` in the live tree is a **junction** to the shared checkout's `data\`. The fast-forward writes tracked `data/` files
through it; that was replicated in scratch (see the record) and leaves both trees clean. Never move the live tree
backwards: that deletes the shared checkout's tracked data files through the junction.

**`effective-setup.json`** (the operator writes it from native evidence; `issue_binding.py` refuses `mock: true` here):
`root_ready_for_pilot` true; `observer`; `observed_utc`; `game_pid`; `range_entry` (arrival record or time); `frame`
`[2560,1440]`; `observed` with `range`, `spiderman`, `normal_cooldown_menu`, `friendly_fire_off`, `pad_web_layout`,
`galacta_setup`, `monitor_present`, `capture_preflight` all true; `display_idle_off_disabled` true/false as James chose;
`cpu_percent`; `observations`; `limits` (bot health and movement unknown); `evidence` `[{path, sha256}]`, which
`issue_binding.py` re-hashes.

## Operator checklist (one page)

Before the binding, once per range entry:

1. **Monitor sink.** `Get-PnpDevice -Class Monitor | Where-Object Present` lists the monitor, and
   `python scripts\capture.py preflight` (live tree, desktop session) reports dxcam frames. Zero frames: stop, James powers
   the monitor on.
2. **Display idle-off.** Windows turns the display off after 15 min (VIDEOIDLE `0x384`) and virtual-pad input does not
   reset it; that killed dxcam on 2026-09-20. `powercfg /query SCHEME_CURRENT SUB_VIDEO VIDEOIDLE` shows it;
   `powercfg -change -monitor-timeout-ac 0` disables it, `powercfg -change -monitor-timeout-ac 15` restores it.
   **James decides**; record the choice. If it stays on, a real keyboard or mouse touch at least every 10 minutes keeps it off.
3. **Game.** Practice range, Spider-Man, at the courtyard-stairs pair of GALACTA BOTs; the designated bot is the **right
   bot by the stair railing**. No lobby navigation by workers: if the game is not in the range, hand back.
4. **Practice settings** (pause menu, under 5 minutes in menus): No Ability Cooldown OFF, Friendly Fire OFF, 240 FPS cap,
   as in `docs/evidence/practice-settings-20260923-0040.jpg`. Bot health and movement are not on that screen: unknown.
5. **Cooldowns from play.** Fire one Web Cluster: ammo drops below 5 and refills (2 s per charge). Get Over Here shows a
   cooldown number.
6. **Only desktop driver.** The lead confirms no other agent or pane is driving the desktop; `C:\desk\jobs` is empty.
7. **Game PID re-read** with `Get-Process -Name Marvel-Win64-Shipping`; the binding records it.
8. **PAD binding check.** The saved pad profile equals the slot-4 receipt (hold-to-swing, sensitivity 265, aim assist 0;
   `collect_settings.py` refuses otherwise) and the range HUD shows **pad** glyphs (LT web, RT melee). Keyboard prompts on
   the HUD (as on the 00:40 menu screenshot, or the match pilot-runner saw) are a stop.

Before every slot (`launch_slot.ps1` checks the starred items itself):

9. **CPU below 60 %\*** with **no sibling decode\*** (no ffmpeg/ffprobe; ask the lead about other heavy jobs).
10. **Fresh normal resources.** HP 250/250, five webs, swing 3, uppercut 2, cooldowns showing, no ongoing recharge: wait
    at least 20 s after a scripted combo (swing charges take 6 s each).
11. **Designated bot, full health, planned bin.** Take a native screenshot and run `scout.py` on it: the right bot's box
    height `h` is near `>= .325` or mid `.065 < h < .325` as the slot plans. Name shown and no health bar = undamaged
    appearance. After a KO, wait for the respawn (its duration is not measured; record it). The trial's bin is the one on
    its own first-phase frame; the scout is only a placement reference.
12. **Caps and guards.** The launcher passes `--max-s 20 --collect-episode --stop-on-feed --game-pid`; the foreground-PID
    and range proofs, the 14+20 s scope and Live's 0.25 s neutral lease are on in every mode. Nothing to switch.
13. **Native capture.** The launcher starts `ddagrab` → `h264_nvenc` 60 fps for 60 s beside the loop's own 10 fps frames.
14. **Kill switch.** The game reads the pad only while its window has focus, and every send is re-proved against the
    foreground PID and the range HUD. To stop a trial at once, bring any other window to the front (Alt-Tab or a click):
    the next proof fails, Live returns the pad to neutral and the loop stops. `Stop-Process` on the loop's python is the
    hard stop; what ViGEm does with the pad when its process dies was not rehearsed.

**Hand-back rule.** After each learned slot the launcher runs `fragment_accounting.py` and prints `STOP` on a boundary
anomaly. Stop the pilot, send no further input and report to the lead after any of:
- a refusal storm: 5 or more consecutive first-consumed decisions refused for a target reason, or more than 25 % of them;
- any `invalid_tracking_observation`;
- a stall: a gap over 0.5 s between range steps, or a stop reason other than `max_time`, `candidate_feed` or `range_lost`;
- logged errors, a launch exit code other than 0, the game leaving the range, a PID change or a lost monitor.
The slot stays in the denominator with its evidence. No replacement retry, no tuning.

## Time estimate

| Part | Minutes | Basis |
|---|---|---|
| Range entry and settings, if the game is not already in the range | 5-8 | first pilot's entries 2 and 3 (about 5 min each) |
| Fast-forward, freeze, settings, binding, loader check (scripts) | 1 | dry run: each script 1-2 s |
| Checklist 1-8 and `effective-setup.json` | 5-8 | operator inspection of native frames |
| 20 slots at 4-5.5 min | 80-110 | launch 14-33 s (first pilot slots 1, 3, 4); checks and capture preflight about 20 s; placement, scout and refill about 2 min; post-slot audit about 2 min |
| One or two re-entries after an inactivity drop, with re-issue | 8-16 | the drop fires about 10 min after the last move or attack; a long audit pause triggers it |
| Archive: hashes, execution ledger, VUH-1314 accounting summary | 10-15 | |
| **Total** | **about 2 h 15 min expected, 1 h 50 min to 2 h 40 min** | |

Ask James for **2.5 hours**; 3 hours covers an unmeasured Galacta respawn time and a slow re-entry. A stop under the
hand-back rule ends the window early. Slots 1-4 alone take about 35 minutes after setup; they include two learned trials
(slot 1 near, where the finder fragments), which should settle VUH-1314's exercised / NOT EXERCISED question.

## Dry-run record

All offline, 2026-09-23, in the scratchpad: an isolated `git clone --shared` of this repo at main `4e9d10e` stood in for
the live tree; no game, pad, capture or desktop input.

| Step | Result |
|---|---|
| Freeze on the real live tree (`e5511c5`) | Refused: not `main` |
| Freeze on the clone at `4e9d10e` | Passed: perception `a30b3cae…`, selector `00fd672e…` (the cohort's), 13 controller and 7 perception files equal their blobs, calibration unchanged since D |
| Freeze tamper cases | One byte appended to `hud.py`: refused (dirty). Second freeze into the same directory: refused before writing |
| `collect_settings.py --dry-run` (game not running) | Patch `1.1.3870120/build25364676` equals the source; hold-to-swing saved; client, build, display, pad profiles and enemy colour equal the slot-4 receipt |
| `issue_binding.py` with a mock effective setup | Binding validated (dry-run binding `1645706c…`, not for use). The scope record pins the schedule `cc0614fd…`, learned slots 1, 4, 6, 7, 9, 12, 14, 15, 17, 20, and the four changed-boundary reviews by hash (three from the lead's handoff folder) |
| `check_binding.py` | Live load (`offline=False`) through the JSON files: origin `reviewed_human`, confidence 0.7, 10 Hz cadence valid. 12 of 12 refusal controls refused for their named reason: first-pilot checkpoint in the binding or as expected hash, first-pilot selector, other patch, cooldowns off, settings hash equal to the source profile, onset semantics, expected runtime with the LF perception hash, a non-hash review reference, another source digest, the first-pilot source identity, no binding |
| The real CLI, `agent.loop --live --brain range-skill` with the launcher's arguments, from the clone | Accepted the binding and stopped at the focus gate ("no perception, capture or pad opened"). PID 4 is never foreground, and the environment had no vgamepad, dxcam or OpenCV. With the first pilot's hash: "range checkpoint refused: checkpoint digest mismatch". No run directory created |
| `launch_slot.ps1 -CheckOnly` | Slot 1 passed every check (CPU 4 %, one monitor present). Slot 2 refused until slot 1 was consumed, then passed. A consumed slot 1 refused. A PID other than the binding's refused. A real launch pointed at scratch refused. The real live tree refused (moved since the freeze) |
| Fast-forward through the `data` junction | Scratch replica at `e5511c5` with `data` as a junction, moved across a commit adding a tracked `data/benchmarks/` file: exit 0, clean, with and without the file already at the junction target |
| `scout.py` on the first pilot's setup frames | near-03 `(1082,677,1481,1168)` h .341 near; slot04 `(1249,506,1432,687)` h .1257 mid: the recorded values |

**Not dry-run:** the real fast-forward, and everything that needs the game: effective setup, PID, capture preflight,
Focus/Screenshot, ffmpeg, the loop past its focus gate, the scoreboard, the kill switch. The calibration refusal path
(a changed `Cal` cannot be committed without moving `main`). `Stop-Process` behaviour of the ViGEm pad.

## Note (2026-09-23, operator): re-issue scripts run as desk jobs after a pane restart

After the Herdr restart at ~13:50 the resumed operator pane could no longer read through the live tree's `data`
junction (bash `Permission denied`, PowerShell "path not found"); from that pane `git status` in the live tree showed
all 125 tracked `data/` files as deleted, while the desktop session (C:\desk jobs, where the launcher runs) saw the tree
clean at the same HEAD. `freeze_deployed*.py` and `issue_binding.py` check the live tree, so after any pane restart run
them as `C:\desk` jobs; the launcher is unaffected. (Staged outside the repo: editing this tracked README mid-pilot would
dirty the live tree through the junction and the launcher would refuse. Land after the pilot.)

## Note (2026-09-23, operator): launcher stderr fix, and where the run's operator files are

`launch_slot.ps1` now runs the capture preflight, the git reads and the fragment accounting through `cmd /c`: under
`ErrorAction Stop`, Windows PowerShell 5.1 turns uv's stderr ("Installed N packages") into a terminating error. The
fixed copy ran slots 1-3 from `C:\desk\pilot0923\` because a mid-pilot edit here would have dirtied the live tree.
The operator's other scripts from that folder are in `operator/` (declared-change freeze, archive, inspect, setup
writer, keep-alive, setup specs, declaration text, reader recheck, stopped-pilot score), resets in `resets/`, and the
setup evidence the two effective-setup records pin in `evidence/`. The pilot stopped after slot 3; see
`docs/evidence/galacta-pilot-20260923/README.md`.
