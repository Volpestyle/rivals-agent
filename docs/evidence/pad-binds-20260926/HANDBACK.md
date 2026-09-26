# HANDBACK: pad-binds, 2026-09-26

To herdr-lead (actor c302f78b). The Opus 5.5 review returned LAND WITH FIXES (VUH-1384);
the lead-requested fixes are applied below, ready for lead integration/delta review. **Not deployed, not calibrated, not touch-tested,
not re-frozen, and no alt agent run is safe yet.** No game input, desktop actions,
staging or commits were performed. HEAD at handback preparation:
`e188323e12c1e59e00bb1b2e076106dd5c6d1a0c`.

Brief verified SHA256:
`4cad2d45d80aaf5623cd1daa71165953b77f16ca37b724a00f95a2421321b471`.
All five settings screenshots and the supplied HUD crop were visually inspected;
they agree with the brief. `screenshot-sha256.json` pins these supplied sources.
Advanced is collapsed, so the curve/deadzones/boost/assist are unknown.
No direct workspace Linear tools are exposed in this session; the brief assigns
issue filing/status to the lead. No Linear write; VUH-1384 is identified by the supplied review.

## Fixes after binds-review (lead-requested delta)

Review read in full, SHA256
`32a723f93c3007518813f53cf925a12571b21b35b1785eb3dc770f2b6c35eba2`.

- **F1:** explicit `PREREGISTERED_UNSENDABLE` keeps ultimate, melee, team_up and
  goh_targeting false. Pad labels remain derived. `PAD_SENDABLE`, action order
  and M&K defaults equal HEAD; `tests/test_range_bc.py` is restored exactly to
  HEAD, so it is no longer a path to stage. A high-support regression test keeps
  all four masked through decode. No new pre-registration or sendability flip.
- **F2/F5:** the repository live-game skill now documents B Amazing Combo,
  X GOH Targeting with unknown hold behaviour/may open CHANGE HERO, semantic
  `combat:` holds and the atomic `LS+RS` token. The touch test now explicitly
  measures X-hold/hero-picker behaviour. Deployment docs name
  `agent/pad_bindings.py` alongside controller.py, loop.py and record.py, including
  the flat hand-tool dependency. The skill is added to the stage list.
- **F3:** recorder button codes are restricted to COMBAT_BUTTONS plus X/RB/A;
  seven negative tests reject START/BACK/d-pad/Y before a report is written.
- **F4:** failed calibration attempts retain a JSON record with `acceptance:
  failed` and the exception; tests cover constructor failure, mid-run failure
  and Ctrl-C, while retaining close-on-exit and exclusive output creation.
- **F9:** wall-crawl tap behaviour is marked U/inferred; Crouch/sprint/pause U
  is restored without the L3 speculation. Both protected kit-prefix checks pass.
- **F6:** remains with the lead/James; no keyboard-toggle/header work was done.

Post-fix focused tests (no game/capture; fake pads): **261 passed, 1 skipped**
(stdlib, 20.44 s), **62 passed** (private perception environment, 0.35 s).
Complete output: `pytest-fixes-stdlib.txt`, `pytest-fixes-perception.txt`.
Commands (the stdlib run excludes cv2 tests):

```powershell
uv run pytest -q tests/test_pad_bindings.py tests/test_controller.py tests/test_live_pad.py tests/test_loop.py tests/test_range_bc.py
$env:UV_PROJECT_ENVIRONMENT = 'C:/Users/volpe/AppData/Local/Temp/rivals-pad-binds-perception-20260926'
uv run --group perception pytest -q tests/test_record_pad_bindings.py tests/test_l4_scripts_close.py tests/test_pad_bindings.py
```
The first perception attempt found a misplaced assertion in the new test; it
was corrected before the passing rerun. Ruff and `git diff --check` pass.

New per-file hashes: `review-file-sha256-fixes.json` (18 paths to stage plus
restored test_range_bc.py), SHA256 `f726ff70263d514e617f5691d89c749afe14ea92556bc3608d020962ccb61b77`.
The original `review-file-sha256.json` and review document are unchanged.
`paths-to-stage.txt` is current; no staging, commit, input or deployment occurred.

## Mapping inventory (current working-tree file:line)

| Location | Role and evidence / disposition |
|---|---|
| `agent/pad_bindings.py:11`, `:27`, `:37`, `:51`, `:63` | Sole executable combat mapping, semantic aliases, atomic partial-report builder, derived combat whitelist, device enum names. Device names are not a second action mapping. |
| `agent/controller.py:43`, `:89`, `:137`, `:146`, `:266` | Live whitelist/codes and guarded report writes. Reset, set every button/axis, then ONE update; both ultimate clicks present together. Existing fresh-frame proof, lease, range refusal and neutral-on-close remain. |
| `agent/controller.py:192`, `:462`, `:558`, `:585` | Combat: keepalive primary, all primitive taps/holds and bursts, disengage jump and attack bookkeeping now consume shared bindings. RangeSkill at `:926` calls the shared web-cluster primitive; physical LT trace bookkeeping remains a report observation. |
| `agent/controller.py:198` | UI: guarded scoreboard View/BACK only. No environmental-interaction route through normal combat sends. |
| `agent/loop.py:59`, `:61`, `:80`, `:90` | Same derived whitelist, semantic keepalive and activity detection; no second mapping. Clean/clamp still runs before output. |
| `policy/range_bc/executor.py:24`, `:39`, `:57`, `:70` | Movement to left stick; held/press/release decoding; combat report built from shared mapping; degrees through Cal. Separate BUTTON/TRIGGER mapping copies removed. |
| `policy/range_bc/vocab.py:20`, `:21`, `:28`, `:33`, `:101` | Action indices/M&K defaults preserved. Pad labels derive from mapping. An explicit pre-registration set keeps ultimate, melee, team_up and goh_targeting unsendable regardless of support; simple_swing remains unbound/unsendable. Swing settings equality gate retained. |
| `scripts/pad.py:25`, `:31`, `:43`, `:66` | Raw physical hand tool, not guarded autonomy. Shared device enum map; new `combat:action:seconds` holds and atomic `LS+RS`. Existing raw menu tokens and dangerous-button check remain. |
| `scripts/record.py:45`, `:149`, `:182`, `:188`, `:194`, `:214`, `:304` | Raw report writer supports only COMBAT_BUTTONS plus hero-picker X/RB/A; recording routine's attack/jump/team-up/pull, occasional web pan and idle escape use semantic mapping. Random team-up formerly Y now R3; jump formerly A now LB. Routine still avoids swing/menu/hero-picker inputs. |
| `scripts/record.py:219` | UI hero picker: X hold, RB tabs, A portrait, X confirm. Kept physical; regression test verifies this sequence. These old UI assumptions need current visual proof, not a combat rebind. |
| `scripts/reenter.py:49`, `:560`, `:667`, `:1016` | Arrival's one Spider-Power attack derives from mapping. Low-level trigger emission remains physical, behind screen-specific whitelist. |
| `scripts/reenter.py:1040`, `:1044`, `:1052`, `:1057`, `:1058` | UI: A on proven practice tab/range tile/Spider-Man, RB hero tabs, X hero confirmation. Unchanged, with existing screen/cursor proof. Lobby X remains forbidden. |
| `scripts/l4_menu.py:124`, `:184`, `:193`, `:201` | UI-only A/B/START/LB/RB; `_tap`, `confirm`, `token` enforce named-screen proof. Unchanged. |
| `scripts/l4_practice_settings.py:53`, `:66`, `:92`, `:99` | UI via Menu: open pause/practice settings, confirm cooldown switch, back out. No combat mapping. Unchanged. |
| `scripts/l4_measure.py:136` | Combat press-floor probe now tests semantic web_cluster and jump (LT/LB), not the old A jump. |
| `scripts/l4_measure.py:191`, `:253`, `:272`, `:289` | Camera-only yawmap/yawleft/period and CLI; new output path, focal override, raw forward/back shifts and optional report-timing receipt. Historical rate output is still a candidate, not calibration acceptance. |
| `scripts/l4_trial.py:78`, `:200`, `:253`, `:313`, `:315` | Sends controller snapshots / invokes named controller primitives. Inherits new mapping; no independent action/button table. Scoreboard delegates to Live. Unchanged. |
| `scripts/range_cast_probe.py:311` | Uses Loop and RangeSkill requests, hence controller web-cluster mapping. Its physical report validation observes what was sent; no new direct bind. Unchanged. |
| `agent/startup.py:35`, `:51`, `:91`; `scripts/padprime_m1.py:38`, `:68` | Right-stick-only startup/prime; report observer. No combat bind. Camera response assumptions stale, inventoried below. Unchanged. |
| `scripts/place.py:504`, `:739`; `agent/placement.py:33`, `:92` | Stick-only placement/measurement via guarded holds; no combat button map. Old sensitivity contract remains closed to the alt until reviewed recalibration. Unchanged. |
| `scripts/replay_steps.py:65`, `:438` | OFFLINE semantic label construction from recorded HUD events (`CASTS` maps semantic action to HUD event). Never opens a pad or emits buttons; must not rewrite historical labels to new physical binds. Unchanged. |
| `scripts/range_benchmark.py:1`; `agent/human_demos.py`; `agent/human_intake.py`; `policy/execution.py` | Offline evidence/recorded native input or M&K semantics, not live Xbox emitters. Left unchanged. |
| `scripts/padrun.sh:8` | Passes raw tokens to a deployed pad.py; no semantic mapping itself. Existing standalone `C:\rivals-agent` copies need the shared module deployed with the reviewed change; this lane made no deployment. |
| `docs/evidence/**` and frozen lane/evidence records | Historical input/measurement scripts and receipts remain immutable, even when describing old buttons. They are not current implementation callers. |

## Diff and semantics decisions

- One physical combat table, shared by the scripted controller, learned executor,
  vocabulary display (sendability separately pre-registered), recorder, arrival attack and calibration press
  probe. The hand tool resolves semantic holds through it too.
- Alt binds: Jump LB, primary RT, web LT, Get Over Here RB, swing A held, Amazing
  Combo B, targeting X, Team-Up A R3, Team-Up B L3, ultimate L3+R3. Melee Attack
  is NONE: semantic melee aliases Spider-Power/RT, with OR combination if both
  model outputs are active. R3 is never melee. Y and Simple Swing are unbound.
- Ultimate is one full snapshot containing both clicks, then one release.
  Dedicated fake-device tests inspect actual Live and recorder update reports
  and the interrupted hand-tool path; there is no intermediate singleton report.
  Intentional Team-Up A/B singleton commands remain distinct permitted actions.
- Swing's scripted hold already existed; only its binding changed. Learned held
  steps maintain it, and inactive steps release. A press-only event remains one
  33.3 ms hold, not a sustained swing/toggle. Wall crawl requires sustained Jump
  at contact; wall sprint adds held primary. The current policy has no distinct
  wall-crawl action, and its jump pulses do not establish wall-crawl skill.
- Buttons that really navigate menus are kept physical. UI proof/whitelists and
  combat range proof/lease are preserved. BACK stays excluded from combat.
- Cal is explicitly stale for 247/124, with old values retained for offline
  comparison. Calibration code now keeps new output paths (exclusive creation),
  accepts measured focal, retains raw shifts including reverse pulses, and can
  use the existing watch_pad observer for actual update-return timings. No gains
  were invented. Failed calibration attempts now retain a JSON failure record.
  `place.py` lowmap still requires a future reviewed profile update.
- `docs/spiderman-kit.md` now cites "James's alt settings, screenshots 2026-09-26"
  and uses current controller inputs throughout its mapping/ability/primitive/
  combo tables. First 2,000 **bytes and characters**, and therefore the Patch
  reflected line, are byte-identical. Prefix SHA256:
  `468c18599dcda56998c9fef52fe8b4a4e23543af7d62ffa2b0f7eba180b30aeb`.
  The old title/intro stays frozen; the updated section explicitly supersedes it.
- `docs/pad-bindings.md` records the current profile, limitations, stale camera
  consumers and next-session procedure. No pinned lane note/evidence was edited.

## Deployment freeze impact

The union of `data/runtime/galacta-pilot-20260923-preflight/*-deployed.json` is
16 files. Exactly **three** were touched: `agent/controller.py`, `agent/loop.py`,
`scripts/record.py`. The other 13 were not edited. `agent/pad_bindings.py` is a new
runtime dependency and must be included in the next reviewed deployment/freeze.
No deployed checkout/copy was updated, no freeze manifest was edited or regenerated.

## Pre-review verification (historical; post-fix focused results are above)

Pre-review full command: `uv run pytest` (exit 0).

```text
2149 passed, 75 skipped in 287.30s (0:04:47)
```

Full output: `pytest-final.txt` beside this handback. Final private-environment
perception subset (exit 0), full output `perception-final.txt`:

```text
36 passed in 1.54s
```

`git diff --check` and the repository's configured Ruff checks pass.
An AST inventory of all `agent/`, `scripts/`, and `policy/` Python code found no
remaining hardcoded non-neutral combat button/trigger state constructors outside
the new table: the remaining physical literals are the scoreboard BACK and the
recorder's hero-picker X/RB/A/X UI sequence.

The initial full run found one stale test whitelist assertion (old A/X/LB/RB)
while 2,130 other tests passed and 75 skipped. That assertion was updated to the
current profile. Initial perception coverage ran 338 cases: 337 passed and one
arrival-log wording assertion failed. Keeping the existing log format fixed it;
its rerun passed. No input was sent by these tests: pad/capture are fakes.

The 199-pass focused run covered controller, Live, executor and 18 new mapping
checks (plus one corpus skip). The 36-pass final perception subset covers the
calibration script's success/failure/close behavior, refusing preexisting output
and invalid focal before opening a pad, focal/report timing plumbing, recorder
combat commands/atomic ultimate, unchanged hero-picker UI and the corrected
arrival log test. Perception environment:
`C:/Users/volpe/AppData/Local/Temp/rivals-pad-binds-perception-20260926`.

No corpus/sealed input was opened deliberately; corpus tests stayed skipped.
No physical response, targeting effectiveness, wall/swing hold duration, camera
rate, or deployment readiness is established by offline tests. Independent
review is still required before relying on the changed input boundary.

`uv run ruff` was unavailable in the base environment; `uv tool run ruff check`
on all owned Python paths passed (one pre-existing malformed noqa warning in
reenter.py). `git diff --check` passed; Git also prints ordinary autocrlf notices.

## Exact paths to stage after independent review (18)

Nothing staged by this lane. Also saved as `paths-to-stage.txt`.

```text
agent/pad_bindings.py
agent/controller.py
agent/loop.py
policy/range_bc/executor.py
policy/range_bc/vocab.py
scripts/pad.py
scripts/record.py
scripts/reenter.py
scripts/l4_measure.py
docs/spiderman-kit.md
docs/pad-bindings.md
tests/test_pad_bindings.py
tests/test_record_pad_bindings.py
tests/test_controller.py
tests/test_live_pad.py
tests/test_loop.py
tests/test_l4_scripts_close.py
.agents/skills/rivals-live-game/SKILL.md
```

Do not stage unrelated `docs/machines.md`, `docs/waiting-on-james.md`,
`scripts/job_board.py`, or the other lane's `perception/replay_cuts.py`,
`tests/test_replay_cuts.py`, or `docs/lanes/idm-gate2-anchors*`. This lane did not
edit them. Handoff files/test logs in this temporary folder are review artifacts,
not repository paths to stage. `before-status.txt` records the starting unrelated
untracked files; index was empty at handback preparation.

## Stale calibration inventory

Source of the old `Cal`: `docs/lanes/l4-controller.md`, “Measurements (Linear
curve, H / V sensitivity 265 / 75, aim assist 0)”, and its immutable L4 evidence.
None of those settings establish the alt's current advanced profile.

| Constant or consumer | Historical value and provenance |
|---|---|
| `Cal.yaw_map` | stick/rate: 0/0, .1/18.5, .2/61.5, .3/110, .45/172, .6/241, .8/320, 1/415 deg/s; `l4_measure.py yawmap` |
| `Cal.pitch_map` | 0/0, .5/43, 1/99 deg/s; same measurement |
| `Cal.focal_1280` | 465 px; pinned to a 2.08 s full turn at .45 stick (~173 deg/s), not solved from image shifts alone |
| `Cal.yaw_deadzone`, `pitch_deadzone` | Both None (unmeasured); interpolation through zero is not a measured deadzone |
| `Cal.latency_s`, `press_s` | .045 s controller latency budget; .033 s press duration, based on old A jump registering 8 ms in 6/6 trials and 17–20 ms pad-to-screen latency |
| Primitive durations | strike .7 s, pull .8 s, uppercut .5 s, melee 1.3 s, swing 1 s; recheck tap/hold response |
| `Controller` Search/Disengage | .45 yaw search, full-up 1.8 s then half-down 1.8 s leveling, integral pitch budget .30 stick-seconds, 180-degree turn from the yaw map |
| `scripts/reenter.py` | .45 stick / 172 deg/s and 465 px focal for door steering |
| `agent/placement.py` | 172 deg/s and 930 px focal at 2560 wide |
| `agent/startup.py`, `scripts/padprime_m1.py` | .45 stick for .3 s, later -.45; old observed prime 52–58 degrees and device-settle timing |
| `scripts/place.py` | half-stick pitch previously 43 deg/s; pitch reset times already None; lowmap explicitly requires Linear/265/75/assist 0 and checks against the old Cal |
| `perception/camera_motion.py` | derives focal from Cal; a degrees estimate inherits its focal assumption |
| `policy/range_bc/executor.py` | feedforward, saturation/feasibility ceilings and rate bands derive from, or describe, the old maps; default ceilings 415/30 yaw and 99/30 pitch degrees/step |
| `scripts/l4_measure.py yawleft` | historical fallback focal 760 is known wrong in the L4 note; always supply a newly period-pinned `--focal` |

Focal length is geometric, not a sensitivity gain; retain 465 only if the new
measurement independently confirms it. Do not scale any rates by 247/265 or
124/75. Mouse degrees-per-count calibration in `vocab.py` belongs to recorded
M&K sessions and must not be replaced with pad sensitivity numbers.

## Next PC session: calibration procedure

This is a future supervised measurement, not authorization to run it now.
The lead owns the desktop session, follows `rivals-live-game`, records native
video and retains all attempts. Stop on a rejected input path or lost range HUD.

1. After independent review, use the intended deployed checkout and the same
   `agent.controller.Live` virtual Xbox pad as the agent. Record checkout/code
   hashes, patch, account/profile, resolution/FPS, and screenshots of Spider-Man's
   entire Advanced section (curve, deadzones, boost, latency, acceleration, aim
   assist), 247/124 and all hero toggles/binds. Do not reset James's settings.
   Human places Spider-Man on open, level ground with textured scenery and no
   bot near the crosshair. No concurrent pad/capture-control owner; hands off
   during measurements. Ensure cooldowns/readiness before press trials.
2. Run the existing calibration script inside that desktop, from the checkout.
   Use a private environment with perception plus vgamepad. For example, in
   PowerShell (replace the output directory with a new sitting identifier):

   ```powershell
   $env:UV_PROJECT_ENVIRONMENT = 'C:/Users/volpe/AppData/Local/Temp/rivals-pad-calibration'
   uv run --group perception --with vgamepad python scripts/l4_measure.py period --report-timing --out data/calibration/alt-NEW/period-1.json
   uv run --group perception --with vgamepad python scripts/l4_measure.py yawmap --report-timing --out data/calibration/alt-NEW/yawmap-candidate-1.json
   ```

   Re-establish the same safe view before each process: each opens a new pad and
   starts with the existing bounded walk/attack keepalive, which can move the
   pose. `period` holds .45 yaw for 7 seconds, guarded and renewed. Confirm in
   the video that its reported period is **one** full turn, not two turns or a
   repeated-texture match. Repeat as `period-2.json` and `period-3.json`.
3. Pin focal length using that 360-degree rate and the raw .45-stick image
   shifts in `yawmap-candidate-1.json`. The script now retains `dx`/`dy`.
   For the yaw patch center, x=360 px from center at 1280 width,
   `angle(f, dx) = degrees(atan(360/f) - atan((360+dx)/f))`.
   Choose positive f so the difference of the two .45-stick pulse angles
   divided by their **observed report hold-time difference** matches 360/T.
   `Live.hold` renews every 50 ms, so nominal .06/.12-second pulses can overrun;
   nominal script `rate_deg_s` fields alone are insufficient. Retain report
   timings with `--report-timing`, which uses the existing
   `agent.startup.watch_pad` observer after construction and embeds reports in the JSON, and
   compare with native video. Observer timestamps are update-return times, not
   hardware arrival times. A noisy/multiple solution leaves focal unknown.
   The equal-pulse focal candidate and old `yaw` optical-flow estimate are not
   acceptance evidence: L4 previously found them ill-conditioned.
4. With that measured f, repeat the map three times with new outputs:

   ```powershell
   uv run --group perception --with vgamepad python scripts/l4_measure.py yawmap --report-timing --focal <measured-pixels> --out data/calibration/alt-NEW/yawmap-pinned-1.json
   uv run --group perception --with vgamepad python scripts/l4_measure.py yawleft --report-timing --focal <measured-pixels> --out data/calibration/alt-NEW/yawleft-1.json
   uv run --group perception --with vgamepad python scripts/l4_measure.py press --report-timing --out data/calibration/alt-NEW/press-1.json
   ```

   Yawmap samples .1/.2/.3/.45/.6/.8/1 yaw and .5/1 pitch with two durations
   each; yawleft checks -.3/-.6/-1. Retain frames, match scores, report timings
   and every failure. Reject ambiguous scenery matches, pitch clamps, bot
   aim-assist interference or disagreement between repeats/directions. Measure
   negative pitch from the retained return-pulse `back` shifts too before assuming symmetry. `press` tests Web-Cluster/LT
   and current Jump/LB at 8/16/25/33/50/80/120 ms, six trials each. It observes
   hero animation, so inspect the recordings; readiness failure is not a failed
   input and animation noise is not proof of a successful press.
5. Measure the low end and both deadzones using the existing
   `scripts/place.py --lowmap --declaration <new-measurement.json>` procedure:
   yaw .02/.04/.05/.06/.07/.08/.09/.10 for 1 s, pitch
   .05/.1/.15/.2/.3/.4/.5 for .5 s, twice each direction, with still-frame noise
   controls. **Prerequisite:** the lead must update and independently review
   its profile contract `LOWMAP_PAD_SETTINGS` against the newly observed
   Advanced settings, plus supply the newly measured full maps/focal to its
   fit. As written, this tool correctly refuses the alt profile; never attest
   the old 265/75 settings or bypass its declaration to make it run. Its
   declaration pins the current range-entry record, process identity, valid
   authorization window and James present/recording. A reported `cal_candidate`
   is not `cal`. Use measured rates/durations and the existing direction,
   repeat, noise, monotonicity and off-axis checks; keep deadzone intervals.
6. Record one bounded touch test per semantic action, observing the expected
   jump/cast/HUD change and release. Include melee/primary alias, Team-Up A
   alone, B alone and X targeting. Capture the alt's UI binds, then check a
   bounded X hold under fresh range proof: measure whether and when it opens
   CHANGE HERO. Hold behaviour is unknown; a range-HUD loss must release input
   and stop, leaving any menu recovery to the lead. Keep goh_targeting masked
   pending that evidence and a separate pre-registration change.
   For ultimate inspect actual pad reports:
   every down report has **both** LS+RS and the release clears both. Hold swing
   across multiple ticks then release; against a safe wall compare a short
   jump tap with a sustained Jump hold, then release; test held wall sprint.
   Confirm that no team-up fires as an unintended singleton part of ultimate.
   Use `Live.send_guarded`/`Live.hold` with `combat_controls`, not sequential
   thumb-click hand-tool taps. Single-action success does not establish a
   useful learned swing or wall-crawl policy.
7. Lead integrates measured Cal, timing, startup/arrival/placement effects and
   executor feasibility results; rechecks PID settling, pitch leveling and the
   configured curve across rates/directions. Review this delta, then re-freeze
   the affected deployment and the new mapping dependency. Only then consider
   a bounded agent pilot. Old receipts and checkpoints are not silently amended.

The lowmap profile update and supervised measurements are next-session work;
this offline change does not claim to complete them.
