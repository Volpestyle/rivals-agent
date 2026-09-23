# fit-replay-contract (VUH-1359, VUH-1346; replay labels for VUH-1353)

**What this is:** the design and test-backed contract for how expert replay labels enter `rivals-range-steps-v1`.
There was no fit, no commit, no Linear write and no game input.

**Where it is:**
- the design: lane doc `docs/lanes/end-to-end-fit.md`, section "Replay labels";
- the contract: `policy/range_bc/steps.py`, docstring "REPLAY source", enforced by `steps.load`.

## The contract, in short

**Header** (`source_kind: "replay"`):

| Field | Content |
|---|---|
| `calibration` | `{kind: "replay_degrees", source, label_sources: {camera, movement, edges}}`: no counts gain, degrees direct |
| `expert_context` | `{player, match_id, viewer_fov_assumption, replay_source}`, replacing the settings identity |
| `swing_mode` | From the expert's `control_context`; null = unknown, which drops `web_swing` live |
| `media_sha256` | The replay capture |
| Refused if present | `bindings`, `device_scope`, `injected_events`, `settings_hash`, `accel_on`, `media_relocation` |

- **Denylist:** irrelevant to replays. It still runs and cannot match.
- **Relocation:** the cache refuses one for a replay.

**Rows:**

| Field | Content |
|---|---|
| `held_start`, `held_end`, `press`, `release` | 14 × (0 \| 1 \| null); edges are onset flags |
| `held_known`, `press_known`, `release_known` | Per-control masks, required to equal "the value is not null" |
| `yaw_deg`, `pitch_deg` | float or null |
| `beyond_pad_envelope` | bool |
| Refused if present | Mouse counts, `relative_known`, wheel, `unsupported` |
| `hud` (optional) | replay-hud's ability states, for stratification only |

- **Framing** is unchanged: 30 Hz anchors on the capture's composition clock.
- **Checks:** edge conservation where all four values are known; continuity where both holds are known.

**Aggregating 60 Hz intervals into one 33.3 ms step,** for the labellers' writer:
- camera: the degrees add; the step is unknown if either interval is unknown, and flagged if either is flagged;
- holds: the state at the step's end and at its start;
- onsets: 1 if either interval has one, 0 only if both say a supported "no", null otherwise;
- release: only where both holds are known;
- actions no labeller emits: all null.

**In the fit:**
- **Targets** carry `known`, `press_known` and `release_known`. Human rows set all three from `held_known`, so their
  behaviour is unchanged.
- **Masks:** the loss uses a `[B, T, 3, 14]` mask, so each channel's term averages over its own known entries.
- **Metrics:** every channel is gated separately, and press rates use press-known steps.
- **Previous action:** no bit is set for an unknown channel.
- **Statistics, prior and `pos_weight`:** per channel.
- **Cohorts** hold one source kind. Replay-plus-human mixing is future work, and refused today.

## Tests

**Stdlib** (`tests/test_range_bc.py`):
- a replay recording loads, with unknowns exactly where the fixture put them;
- refused: 8 header violations and 9 row violations (human-only fields, wrong calibration kind, missing label source or
  expert context, mask/value disagreement, out-of-range values, conservation break, bad types);
- a mixed cohort is refused;
- a replay relocation is refused;
- unknown channels are never scored or fed back.

**Torch** (`tests/test_range_bc_torch.py`), **the test asked for:** a replay window with unknown movement has no mask
on any of the 4 directions × 3 channels. Their gradient is exactly zero, while known movement steps get gradient.
Flipping the values behind the unknown labels leaves the loss bit-identical.

**Fixture:** `fixture.replay_session`. It has movement unknown in periodic spans; holds for primary, swing and crawl;
cast onsets with 10% abstention and no release label; the actions no labeller emits left unknown; camera in degrees,
with pitch sometimes unknown; and the envelope flag.

**Results (Windows):**

| Suites | Result |
|---|---|
| `test_range_bc.py` and `test_range_bc_contract.py` | 106 passed |
| `test_range_bc_torch.py` | 20 passed |
| `test_range_bc_hudmap.py` | 5 passed, 1 skipped (corpus) |

The human path is unchanged: every existing test still passes.

## Bytes (every file differing from `HEAD` `e763b1f`)

This includes the not-yet-landed D2 and runbook changes from fit-smoke:
```
6db2dd1e7191ad597c8c539776baff53f941a1554dbe8455bfc6bbdacf9df5ce  policy/range_bc/baselines.py
b8d03d5cefd7ed46a9b2689fc82bc12ebe58c1bf6ac16bb80221a19f1049bf80  policy/range_bc/bench.py
7ec50165cdf6445f94cb3ebedf32890b7e14044c6e501b7f3bb8df710fe741c8  policy/range_bc/cache.py        (D2 + replay: no relocation)
e1d69e40e09a6f87a47b6c87c08c9ea133644341cc5808c838d016d8d58b256d  policy/range_bc/fixture.py
8ced54513aca4642b43af878ba0c0c0f18c8eabb2769955bb85cc0845c2683dc  policy/range_bc/metrics.py
9549fd6daa80685139f59bfa3bc63f607fa8ede0a0b93eafd90b7d2ad9fb3424  policy/range_bc/steps.py
d9abfd01c45bf9b9acb264dfa18939039a075cc175c4034039c216f4c36939e8  policy/range_bc/train.py
1f7505a44c635f80bdc9114a204c3e8eed3a8693c3fda1730e92dfc15f570133  tests/test_range_bc.py
ac28ff088edba44cc86189e1b1b85c4fbf170b0bc6ad5acb226701a11bf7818f  tests/test_range_bc_torch.py
cab7f2c2867ff78daf603f4730f227a7ade2705f600c6c8d142673295aa8d14a  docs/lanes/end-to-end-fit.md
35c66e79923c6d8404300036847c93118f3d66970bee3b1c54e896697b32c154  docs/evidence/fit-readiness-20260923/README.md  (fit-smoke, unchanged since)
```
**Dependency, not mine:** D2 needs intake's `agent/human_intake.py` with `check_media`, landing at the intake lane's
next DONE.

## For the lead and the labelling lanes

1. **replay-hud's lane doc is not in this checkout.** The contract follows the inverse-dynamics doc's heads and the
   brief's description of replay-hud (ability states, cast events, abstentions). If replay-hud emits releases or hold
   durations, map them to `release` and `held_*` under the same known masks.
2. **The labellers need one writer** that applies the 60 Hz → 33.3 ms aggregation above. The fit lane will add a
   contract test against it, as for intake, when it exists.
3. **Mixed replay-plus-human cohorts** are refused by design. Enabling them is a separate decision: gates, splits, and
   how the expert's context meets James's.
