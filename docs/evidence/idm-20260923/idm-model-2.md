# scoreboard-fix: IDM model review fixes K1, K2, the masked-loss guard and per-regime camera std (VUH-1353)

`review-idm-model.md` and its addendum are applied, all offline. There was no real data, no decode and no Mac, and
nothing is committed. `idm_targets.py` and `idm_eval.py` are untouched: they are clean against the landed 2f5c95e.
I put the per-regime coverage in `policy/idm/train.py`'s Gate 1 output so the landed harness did not change.

## Bytes (uncommitted)

| File | sha256 |
|---|---|
| `policy/idm/__init__.py` | `85a5437371e305077f1fbda70cb6ec1898486c63dc43821d6e9dad9ec4299937` (unchanged) |
| `policy/idm/frames.py` | `137844b550deed663648f4db71b01e8a2ab26bed53c6beee7a0b460113e2cd38` |
| `policy/idm/model.py` | `fe353209b359387cb41f46ca566c9ba1982ab0ad51635e8f686da2ab159388ce` (unchanged) |
| `policy/idm/train.py` | `b615ab260cb8632c48c7b0b3f06d705d3704418e13902091265bcce7b8b86671` |
| `tests/test_idm_model.py` | `a1cbb694a713ac996565b3a040c9df1bfff39eddd6f3709afa26b2b2c854ddc0` (16 tests) |
| `docs/lanes/inverse-dynamics.md` | `c5b3451652caa836fe35647debabccf50f41aa0e72b8ddd67f38fbd1e5b557b0` |

The lane doc diff against HEAD holds everything since the data step: the data-step entries, the decisions, the S1–S4
review fixes, the Gate 1 harness, "the IDM model as code" and "model review fixes".

**Checks:**
- `uv run --group execution pytest tests/test_idm_model.py tests/test_idm_targets.py tests/test_idm_eval.py
  tests/test_replay_camera.py` gives **55 passed**: the earlier 49, plus 6 new model tests.
- `uvx ruff check policy/idm tests/test_idm_model.py` is clean.

## K1: provenance in the checkpoint

**The checkpoint meta (`provenance()`) and the report carry:**
- `supported` over the full vocabulary, and `train_press_counts`;
- `code_closure`: range_bc's `code_closure()`, the LF sha256 of every imported repo module;
- per target file: its sha256, **taken as it is loaded** (hashed before and after `T.load`, which must agree), split,
  `media_sha256`, `calibration` and row count;
- per frame store: `media_sha256`, `frames_sha256`, `hud_sha256` and the size;
- `seed`.

**Guards:**
- `checkpoint_bytes` refuses a meta that lacks any of these, or whose support set differs from the model's.
- `load_checkpoint` refuses a meta without provenance and restores `model.support`.
- `predict` and `gate1` take the support set from the model and **refuse a caller's set that differs**. A model
  without one is refused.

**Addendum:** `run_fit` calls range_bc's `require_committed(closure)` first, **before any file is read**, so a real
fit never runs from an untracked or dirty package. It also requires the closure to be unchanged after the fit. The
report keeps `git_commit` beside `code_closure`.

**Tests:**
- the checkpoint round trip, with every provenance field checked;
- widening the support set is refused in the checkpoint and in `predict`;
- the fit refuses uncommitted code before any target is loaded (with `T.load` spied).

## K2: pixels bound to the targets

- The frame store manifest now records `frame_pts`, parallel to `frame_indices`, and `write_store` requires pts for
  every frame.
- **`bind(targets, store)`** refuses the whole file when:
  - the store's `media_sha256` differs from the target header's;
  - any frame both name has a different pts;
  - the header's `frame_period_ns` is not 8,333,333 (the offsets assume 120 fps).

  `Examples` and `predict` bind every file; `run_fit` binds every store up front.
- **Opening a store refuses a denylisted session id or media** (`refuse_sealed`, with the pinned denylist by default).
- The docstring states the decode job's duty: check the denylist before decoding, then record the media and pts.

**Tests:** a wrong media, a one-frame pts mismatch and a 60 fps header are each refused. A sealed id and a sealed
media each refuse a store; the test uses a fake denylist, not the sealed names.

## Masked-loss guard

`loss_terms` zeroes masked camera targets **and sigmas** before the NLL.

**Test:** it puts a NaN, an inf and a NaN sigma into masked slots. The loss stays finite, every parameter gradient is
finite, and the gradients are bit-identical to the clean batch's.

## Camera uncertainty used per gain regime (addendum K2)

- **Per axis, the predictor reports:**
  - `yaw_std_deg` / `pitch_std_deg`, the **total** std: sqrt(the model variance + `camera_sigma`(predicted value,
    predicted regime)²);
  - `gain_regime`, the regime of the predicted counts' rate over the row's interval.
- **Abstention bound, per predicted regime** (pre-registered in `CAMERA_ABSTAIN_STD`):
  - **calibrated: 1°;**
  - **extrapolated: 3°.** Extrapolated labels carry about 20 %, so 3° admits up to about 15° per interval
    (900 °/s, twice the pad's yaw envelope) from a sure model. A single 1° bound would have abstained on almost every
    fast turn by construction.
  - **Your call:** these bounds are my choice; change them before any real fit if you want others.
- **Gate 1 adds `model_std_coverage`:** per session, axis and **true** regime, it reports `evaluable`, `answered`,
  `abstention_rate`, `within_1std` and `within_2std`. It also adds `pitch_truth` (for example,
  `derived_equal_sensitivity`); the report carries it too.

**Test:** with the model's variance pinned at e^−12:
- a 10° prediction is extrapolated, with std = sqrt((0.5 g + 2.0)² + e^−12), and is answered;
- a 0.2° prediction is calibrated, with std about half a count;
- a 20° prediction exceeds 3° and abstains.

## Not addressed

- **HUD sampling at the measured press → HUD lags** (the review's design note): the HUD branch still sees only the
  start and end frames.
- **`test_opened`** stays caller-supplied (cosmetic, per the review).
- **The frame-store decoder** is not written.
