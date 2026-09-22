# First learned range integration

Lead: w2:p1. Technical plan: [learning-plan.md](../learning-plan.md).
Acceptance/results: VUH-1311, VUH-1346 and VUH-1319 in Linear.

## Current direction: fluid execution, 2026-09-22

James rejected standing Idle as the default contrast for Spider-Man play.
VUH-1349 is canceled. The legacy binary policy and failed visual packet below
retain their historical meaning; no labels or checkpoint classes are remapped.
The next experiment learns individual web starts while aim/movement run
independently, under [the event contract](range-policy-reframe.md). Its changed
consumer, final model integration, controller and first two source labels have
the bounded acceptances recorded below.
Priorities are mechanics, useful picks, escape, fluent swings/momentum/bhops and
teammate support. Imitation initializes the agent; later bounded RL may improve
outcomes and learn new techniques as the action space expands. The caller
contract below describes the delivered legacy mode, not a new deployment receipt.

## Event execution acceptance, 2026-09-22 12:39 CDT

Lead accepts the independently reviewed `RangeSkill` controller and guarded Live
actuator. A web-start request is consumed once; no-new-start leaves scripted
movement/aim independent. Observation and execution clocks remain distinct.
Expiry stops offensive authorization without discarding valid current tracking;
slow processing/proof/lock acquisition cannot authorize an expired write. Terminal
records retain the original pulse owner and actual release attempts, including
failures. The existing watchdog bounds held requests at its documented resolution,
not an independently measured game-visible pulse duration.

Root reproduced all three original failures before repair. Independent delta
review passed 220 tests, excluding four changing policy-dependent cases. Root's
integrated synthetic suite passed 237 checks. The controller and Live actuator
landed separately in `33303c0`; final event-policy integration is accepted below.

Independent admission review supports n199/n200 of the frozen earlier-session
event packet, and lead accepts those two labels solely for a TRAIN-only fit/reload
diagnostic. The other 106 grid coordinates remain unknown. The non-start has zero
ammo, and tracks are constructed per window; no useful timing, persistent live
selector equivalence, validation performance or gameplay claim follows. Corpus
owner persisted the genuine receipt without changing the frozen candidate.

## First admitted human fit, 2026-09-22

The reviewed event software is pushed on main in `8f78ae9`. The first two admitted
human rows have now trained on Mac MPS and reloaded on Windows CPU, with exact
Mac-CPU/Windows-CPU probability equality. The actual MPS fit took 2.615 seconds;
the GRU predicted both training labels, as did the simple ammo baseline. All 106
unknown bins remain masked. No validation or deployment binding was created.

Checkpoint SHA-256:
`7f6f9dafc14e3459e6e7835707b177c3c7fd6357574fc13969a3db25ead1cdc8`.
The [retained result](../evidence/range-first-human-fit-20260922/README.md) contains
actual reports, commands, admission receipts and the limited interpretation.
The next source task inspects at most six new bins from the same authorized span
for target-agreed starts and ammo-available non-starts. This does not expand
admission, rewrite the first packet or request standing-idle footage.

## Event policy and caller acceptance, 2026-09-22

Independent same-reviewer acceptance covers the new event policy/consumer,
legacy numeric-helper extraction and final frozen Loop join. Immutable media
cannot be duplicated by session aliases. Valid causal observations with no
selected target stay in history, so first acquisition may infer without invented
earlier targets; an unsupported current target still refuses. Reports call their
confidence filter `confidence_filtered` and do not imply executor acceptance.

The reviewer ran 69 event-policy tests and the four saved-checkpoint caller tests
previously deferred. Actual synthetic checkpoint -> CLI -> consumer -> Decider ->
Loop -> Controller -> fake pad -> on-disk RunLog passed. Additional independently
executed no-new, low-confidence and unknown-ammo cases verified movement, neutral
refusal and resource rejection. Synthetic metadata stayed synthetic throughout;
the real live loader rejects it before hardware. No extra unchanged RSC audit was
needed. Root adopts this software acceptance for landing.

The new caller is `python -m agent.loop --brain range-skill`, with explicit
`--range-checkpoint`, `--range-sha256`, `--range-identity`, normal cooldowns and
at most 20 seconds. `--live` additionally requires `--range-runtime` and
`--range-deployment`; source identity, selector/feature semantics and the separate
runtime receipt are validated before capture or pad attachment. Legacy
`--brain range` is offline only. A numerical fit and portable checkpoint do not
supply physical cast calibration, independent validation or deployment approval.

## Accepted software delta, 2026-09-22

Independent `range-review` examined the policy, typed consumer, loop, controller
timestamp delta and regression tests outside the producing lane. Its first review
reproduced two P1 findings: a gate could renew an attack before missing-observation
or history checks, and one identity conflated source KBM settings with the pad
runtime. Both were fixed by the producer and independently retested. The final
frozen review found no new blocking findings. Lead reproduced the integrated
suite: **169 passed**, isolated CPU PyTorch/perception environment; the shared
stdlib environment was unchanged.

The reviewer additionally exercised the actual CLI, loader, Decider, Loop,
Controller, LiveIO, Live/watchdog and recording writer with synthetic observations
and an injected fake device. Startup navigation and image writing were stubs.
The valid synthetic fixture recorded 13 decisions, nine Engage decisions, zero
keep-alives and final neutral output. A separate uncertainty transition neutralized
all 21 later ticks after 26 earlier attack ticks. These are software checks, not
human training or gameplay evidence. Synthetic metadata used to test the human
loader branch is never a deployable human artifact.

## Caller contract

`python -m agent.loop --brain range` is the bounded candidate path. It requires
an explicit checkpoint, external SHA-256 and source-identity JSON. Live use also
requires separate runtime and deployment JSON files:

```text
--range-checkpoint CHECKPOINT
--range-sha256 SHA256
--range-identity SOURCE_IDENTITY_JSON
--range-runtime RUNTIME_IDENTITY_JSON
--range-deployment DEPLOYMENT_BINDING_JSON
--cooldowns normal --max-s 20 --decision-hz 10
```

Use `--dry RUN_DIR` for a named offline recording or `--live` only after the
actual admission, validation, runtime measurement and independent-review gates.
No genuine human checkpoint or deployment binding was produced by this software
review. Source identity is KBM provenance. Runtime identity separately pins the
observed virtual-pad settings, calibration, controller/selector code, perception
and semantic review. The external deployment binding pins those to exact model
bytes and the source identity. Hash equality cannot prove that current settings
were inspected; the lead must supply actual reviewed evidence.

Loading and compatibility checks precede pad attachment. Range policy runs use
the checkpoint cadence, at most 20 seconds, fresh consumer/history per invocation,
and no scripted warmup or idle keep-alive attacks. Existing range/focus, decision
age, input lease and neutral-on-exit guards remain. A valid retreat can still be
gate-owned; learned choice is only Idle/Engage delegation timing.

Every decision's trace is copied on its producing thread and saved with its
originating State. `meta.json` includes source/runtime/deployment receipts and
the limited capability claim. Wrong cadence, missing runtime binding, wrong
checkpoint bytes and incompatible profiles refuse before capture or pad setup.

## Scoreboard time contract

The existing board row `t` remains the pre-hold request time. New live rows add
`captured_t`, `capture_interval` and `capture_clock`. The interval is the selected
board frame's grab start/return in loop seconds, frozen before range reacquisition;
`captured_t` is its upper endpoint. It does not measure game rendering or the
player's observation. Missing timing stays missing. The episode adapter must
preserve the interval, reject boundary-straddling evidence and never reinterpret
legacy `t` as acquisition. No new automatic readiness or designated-KO reader is
claimed; initial episode evidence still needs native-video audit.

Re-run the changed boundary without game input:

```powershell
uv run --offline --no-project --with torch --with opencv-python-headless --with numpy --with pytest python -m pytest tests/test_range_policy.py tests/test_learned_range_loop.py tests/test_loop.py tests/test_live_pad.py -q
```

## Mac training / Windows loading check

Both Mac checkouts were clean before fast-forwarding the main checkout and moving
the dedicated offline worktree to accepted revision `7670e3f`. The new range GRU
trained on the M5 Max using PyTorch 2.14.0, `mps:0`, under `nice -n 10`: eight
synthetic training examples, four separate synthetic validation examples, 80
epochs. It classified 4/4 versus the majority baseline's 2/4; these deliberately
simple fixtures establish execution only. Reloading the saved weights on Mac CPU
gave identical probabilities. The identical file was copied to Windows and the
actual loader and evaluator again classified 4/4 on CPU, with origin `synthetic`
and `offline=True`. It has no deployment binding and must never run live.

Checkpoint SHA-256:
`668e6c5c5a22d7d66d8924db9560d0c3c29c88f32a9ed49e70767d659e647053`.
Local reports and checkpoint are under `data/diagnostics/range-mps-20260922/`;
the Mac source directory is
`/var/folders/sq/lm465hcj1c97b3wysf7f40h40000gn/T/rivals-range-mps-synthetic-6r8dqp93`.
No human media was read for this check and the Windows GPU stayed with the game.

## Accepted offline episode scorer

Independent review accepted the four-file VUH-1319 delta after fixing reset
history across trials, range loss/recovery at readiness, actual executed-baseline
evidence and joint scenario/settings counts. Pre-ready or cross-reset boards
cannot award a kill. Unknown deadlines do not fabricate observed duration.
Acquisition intervals remain separate from rendered kill occurrence.

The lead verified the frozen hashes and joined the scorer with the accepted
policy, controller and loop: **261 passed** in isolated CPU Torch/perception.
The full stdlib suite passed **683 tests, 44 skipped**; no shared environment
change or real corpus read. Independent scorer review passed 88 pure tests with
four unchanged pixel skips and reused the accepted native-reader evidence.

This accepts offline software and the observation interface. VUH-1319 remains
open for real audited readiness/target/outcome observations and measured
reset/respawn/throughput. No real feasibility gate has passed.

## Accepted failed visual candidate and next training source

Lead accepted the frozen `20260922T032454-642Z-24328-1` packet as failed
candidate diagnostic evidence only. Independent admission review reproduced all
20 causal snapshots (17 unique native frames), State/target/gate results, all
26 features and known bits, and default five-step window validation. Native
target disagreements and all eleven sampled neutral exclusions were inspected.
The four labels stay null: **0 Idle / 0 target-agreed Engage / 4 unknown** and
**zero admitted Examples**. This is a bounded finding about those rows and
locators, not an exhaustive claim about every original frame.

Frozen `candidate-rows.json` SHA-256:
`1f7e730de59ca88bb92695448ef982a6a274ef68d8750228087c5e6290c753b4`.
Frozen `artifact-hashes.json` SHA-256:
`0c590472e75dc3c9764ffc6a00222cac415f773b7c90a1479cca5c8df8c0645d`.
Source-profile document SHA-256:
`85c8afc43ddc29308155ae7ed7ab7d7d3460c8c7ca76b3e95388ce63b136f5f2`.
The profile explicitly preserves unknown earlier motor settings. Its digest is
not a claim of complete known settings or current pad calibration.

The default PAD profile assigns source E/F to the wrong abilities. Existing MK
and visual slot mapping repair identity/ammo, but the mapped reader still calls
zero-charge/countdown slots ready. A separate nearby-body filter failure leaves
the causal selector on a distant Galacta bot; that bot is not proven scenery.
Green squad chat is a distinct false positive. VUH-1294 and VUH-1314 own these
bounded repairs; frozen candidate outputs are not overwritten or auto-admitted.

VUH-1349 requests a short train-only Galacta recording with genuine grounded
waits for resources and ordinary attacks. The existing cuts are retained.
VUH-1347 remains a separate validation recording. VUH-1348 asks only about the
later original's resource overrides. No new timing calibration or DPI check is
required by the failed packet's disposition.

## Fresh scripted live diagnostic, September 22

Reviewed revision `87f34a3` ran from the lead-owned detached
`C:/Users/volpe/repos/rivals-agent-live` worktree, isolating the run from pending
perception edits. Its data junction points to this checkout's retained evidence.
Guarded re-entry reached Spider-Man in the range. A practice-settings screenshot
at `data/live-readiness/20260922-1124/practice-settings/ps-0.jpg` shows No Ability
Cooldown off; the tool read it without toggling. Gameplay corroborates normal
resource behavior: web ammo 5 to 4, uppercut charges 2 to 0 with countdowns, and
pull countdown 7 to 1. Current motor settings/calibration are not certified.

`data/l1/scripted-diagnostic-20260922-1130/` contains the 20.014-second scripted
loop, 200 decisions, 968 reflex ticks, no range gaps, no reported errors and
successful neutral shutdown. Measured rates were 48.4 Hz reflex and 10 Hz
decisions; decision-lag p95 78.91 ms. These software costs are not calibrated
capture/display/input latency. The final scoreboard was acquired over loop
seconds [27.6021449000109, 27.607298499991884], independently of legacy pre-hold
`t=26.589`.

The inspected native ending board shows **3 KOs / 825 damage / 0 deaths**.
Scene/feed evidence identifies Luna Hero Simulation respawns. There was no
audited initial counter baseline or designated Galacta readiness/incarnation, so
this is an unscored scripted reference diagnostic, not the learned pilot or a
passing episode benchmark. Fragment-recovery acceptance remains NOT EXERCISED.
The legacy metadata's `Season 10, Version 20260911` is a kit default, not
independently observed current patch evidence.

Original native 60 fps video and inspected HUD/overview sheets are under
`data/live-readiness/20260922-1130/`. Original `scripted-native.mp4` SHA-256:
`8a29e34e864f22915f363f27c6505d09370b086a2c7afc32fb96f3a673a420ba`.
The 26-second excerpt covers original seconds 5 to 31, with initial setup and
idle tail cut; SHA-256:
`337c370cefda80ffdb79527f54536b1451512ff94bf5fdaecf3bc522a0c0f040`.
[Inspected video and limits on VUH-1319](https://linear.app/vuhlp/issue/VUH-1319#comment-c32af3ab-b495-44b6-9036-6ced4952c53b).

## Accepted HUD reconciliation

Independent review accepted `perception/hud.py` SHA-256
`5ec7e109f168aeb05978724540eca1dace96fda981fea2861dc16ae3de2a5f58`
and `tests/test_hud.py` SHA-256
`9a3563c597654fcbc179f8af717f4dda7099ea2dd07ee86ea4791561f6787f98`.
It reproduced 22 selected tests and the 19 native source readiness corrections,
with all charges/countdowns unchanged and existing occlusion unknowns retained.
Three original PAD controls were unchanged; six new native PAD frames from the
scripted diagnostic additionally verified actual countdown behavior through
`read -> state_kwargs -> State` (RB7/5/3/1 False, X4/2 unknown when the badge
cannot be read). Root inspected the actual delta and matching frozen hashes.

Standalone and aggregate reads reconcile the same evidence without changing
State or source layouts. No future images or labels enter the reader. Unknown
badges/countdowns and gold in-use icon semantics remain limitations; a positive
countdown with spare charges has controlled-contract coverage, not new native
proof. This accepts the observed reader repair, not a human cohort or live result
with the repaired code. Native source/target remeasurement remains separate.
