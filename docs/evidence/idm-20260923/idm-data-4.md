# scoreboard-fix: IDM data review fixes S1 and S3, with S2 and S4 (VUH-1353)

`review-idm-data.md` confirmed the join and the calibration. Both required fixes are applied, plus the two smaller
findings. Offline, no commits.

## Bytes (uncommitted)

| File | sha256 |
|---|---|
| `policy/idm_targets.py` | `c311e4daceda564e1035158a6f8cf10a10caaeea3407aaf37e4930e44d69b8ca` |
| `tests/test_idm_targets.py` | `845cbf7f78dd59588fc38c64e177bf693e0161a812934ac5bba70018ca7ca61a` (18 tests) |
| `policy/idm_eval.py` | `1980875b8f829c2844c60dbcbfa3f26743f7542122649a6019bbc3eb2e4300d3` |
| `tests/test_idm_eval.py` | `14a394d04f3680db52c752d87e643a941f4da608438c13e999824588f8ff38e8` (15 tests) |
| `scripts/replay_camera.py` | `1d822a118e5ecb3dac6d9bf05b38d0d11e8782b67cbd292956afc2aa6875a2e0` (unchanged) |
| `tests/test_replay_camera.py` | `389f178458d0b066da71dbdcef0ee8f6db5f4bf00fc66f81ea044e1cbd210abf` (unchanged) |
| `docs/lanes/inverse-dynamics.md` | `041391fcb5768a4ad5047708f32d66c878a405fc89ded7667818b436f9bef9b8` |

**Tests:** `tests/test_idm_targets.py` + `tests/test_idm_eval.py` + `tests/test_replay_camera.py` gives **39 passed**.

**Targets rebuilt** (`data/idm/targets/`, gitignored): 170,976 intervals, `check` passes. Unsupported: ultimate,
melee, simple_swing.

| File | sha256 |
|---|---|
| 051828 | `2e89adf3079a27c2f64fb2d142cfdd6c39bf1b2895398491e03dc82976bc6d8d` |
| 171533 | `427328415625e68658a34254506ff0dbc30dda61d7a29ad1535c45f6a89898e8` |
| 200129 | `a32a738090a1492e2ff600efdbd7ee9853699569053388ca6ea8102a4d267fd5` |
| 205528 | `5d51f2409b00025da95fa888a4633d3c445c7fd6a1334c06d5d589d984154f73` |

## S1: the sealed take refused by construction

**`build(session_id)`:**
1. Loads the pinned denylist (`data/human/sealed-denylist.json`, LF sha256 `57cfe01f`, the intake's loader).
2. Refuses a denylisted **id before forming any path**.
3. Reads **only the step table's header line** and refuses a denylisted media hash or a split outside train/val.
4. Runs `human_intake.check_registry(REGISTRY, denylist=…)`, denylist first, and requires the session as train/val.
5. Only then reads the rows and hashes and opens the imported demo.

`load()` refuses a denylisted id or media hash after the header line.

**Tests:**
- a fake folder named 053616 (with files) is refused and **no file under it is opened** (open, `Path.open` and
  `read_text` are spied);
- an id whose step header names the sealed media is refused **after reading only that header**;
- the reader refuses a file carrying the sealed media.

## S3: the acceleration caveat per row

**Per interval:**
- **`mouse_rate_cps`:** hypot(dx, dy) / interval seconds.
- **`gain_regime`:** "calibrated" at or under **1,400 counts/s** (the top of the calibration turn's measured speeds,
  about 200–1,400; its mean was 915), "extrapolated" above. Null when the counts are unknown. The reader recomputes it.

The header records the band as `gain_band`.

**Uncertainty,** from `target()` (provisional until a fast-turn calibration):
- `yaw_sigma_deg` and `pitch_sigma_deg` are half a count of quantisation, plus **20 % of the degrees for extrapolated
  rows**. The 20 % is the calibration record's "local px/count falls about 20 % from slow to fast".
- `target()` also returns `gain_regime`, `degrees_kind` (the calibration kind) and `pitch_derived`.

**Gate 1:** `idm_eval` reports camera error per gain regime, and per speed band (≤ 1×, 1–4×, > 4× the 915 counts/s
turn). Tested.

**Measured on the rebuilt targets:** **40.1 % of usable intervals are extrapolated, carrying 90.2 % of all yaw
counts.** The review's 91.7 % cut at the mean turn rate (915) rather than the top (1,400).

## S2 and S4

- **S2:** `target()` refuses a row that isn't usable, and `training_rows(targets)` gives the usable ones. Tested.
- **S4:** tests pin `DECLARED_UNSUPPORTED == {}`, `MIN_POSITIVES == 50`, and team_up and goh_targeting counting by
  their presses.

## Not done (the review's suggestions for `replay_camera`)

- Match the capture by media sha256, not just the basename.
- Add the run's focal and "viewer FOV unverified" to `source.camera`.

`replay_camera` is unchanged. Its landing order stays as the review states:
1. the `steps.py` replay-split change;
2. `replay_steps.py`;
3. `replay_camera.py`.

Resuming the model (`policy/idm/`) next.
