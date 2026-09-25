# scoreboard-fix: β-NLL becomes the IDM's default camera loss (item 1 of the beta-default decision) (VUH-1353)

2026-09-25.
- **Scope:** a working-tree edit in the shared checkout on `9a39228`, uncommitted, for fit-review's check against its
  five conditions before you land it.
- **Not done:** no commits, no Linear, no runs.

## What changed

**`policy/idm/train.py`:**
- **The default:**
  - `CAMERA_BETA_DEFAULT = 0.5`, with the decision comment.
  - `fit(..., camera_beta=CAMERA_BETA_DEFAULT)` (was `None`).
  - `--beta-nll` defaults to it (was no default, which meant the plain loss).
- **`--beta-nll 0` restores the plain Gaussian NLL** through `camera_beta_from_cli()` (0 → `None`). Any other value is
  β, and `fit()` still refuses anything outside (0, 1].
- **Both axes:** as landed in `d10f583`. The yaw-only branch is not on main, and nothing about axes changes.
- **The `loss_terms` primitive keeps `camera_beta=None` = the Gaussian NLL,** so the fit passes β explicitly; its
  docstring says so.
- **What a run records:**
  - the checkpoint meta carries `camera_beta_nll` whenever β is on, which is now every default run;
  - the report's `camera_loss` is `{"kind": "beta_nll", "beta": 0.5}` by default and
    `{"kind": "gaussian_nll", "beta": null}` with `--beta-nll 0`.
  - **Before this, a default checkpoint had no `camera_beta_nll` key; now it has one.** A default checkpoint made
    after this change is therefore not byte-comparable with a pre-change default one. That is truthful provenance,
    and noted for fit-review.
- **The module docstring's "Loss:" line** names the default, the decision and the `0` escape.

**`tests/test_idm_model.py`:**
- **Renamed** `test_beta_nll_is_off_by_default_…` to
  `test_the_loss_primitive_defaults_to_the_gaussian_nll_and_beta_rescales_only_the_gradient_weight`. Its assertions
  are about `loss_terms`, whose default is unchanged, so only the name and docstring changed.
- **New:** `test_the_camera_loss_defaults_to_beta_nll_half_on_both_axes`:
  - `CAMERA_BETA_DEFAULT == 0.5`, and `fit`'s default is it;
  - the parsed CLI default is 0.5;
  - `--beta-nll 0` maps to `None`;
  - a negative β is refused by `fit`.
- **The fresh-subprocess `run_fit` test** (which passes no `--beta-nll`) now asserts that the report's `camera_loss`
  is `{"kind": "beta_nll", "beta": 0.5}` and the checkpoint meta's `camera_beta_nll` is 0.5.
- **The byte-reproducibility and learning test** now runs under the β default and still passes: the same seed gives
  the same bytes, and the loss falls.

**`docs/lanes/inverse-dynamics.md`:**
- The decision entry "**Decision (2026-09-25, lead's `beta-default`, `9a39228`) …**" is placed at the end of the part-A
  section.
- Its evidence table puts plain, β-NLL on both axes and β-NLL on yaw only side by side: yaw learned, pitch A2, the
  A3 coverage and bounds, and A4's yaw and pitch at Gate 1.
- The pitch cost and the seed-fragility of pitch are stated.

## Bytes (working tree on `9a39228`; +68 / −14 over three files)

| File | sha256 (working tree, CRLF) | sha256 (LF) |
|---|---|---|
| `policy/idm/train.py` | `534f80914ecd555e10395e5277cb66c43dcbce6638e586aac4240867e5fda029` | `f6e0bc27bc721c2a28f3396e8d115df248aabfcf136c6c06791af6698b4f8d62` |
| `tests/test_idm_model.py` | `3e75f2824cb6d3d23c38d2ec8d7da045e825a979614369e656ba9f454e53325c` | `36346b4a8f96414a4269f536dbe5b5d0aea65918baa70a7a99e8562b46fa8b11` |
| `docs/lanes/inverse-dynamics.md` | `1249250190827db054d6fe88dc8ffd247f5fa3d86c3d8157236d7ed213659739` | `7cb264791315d076d37336b0c3b742c0b599dfda979c5c8378e51d1be5d5346a` |

**Tests:**
- **Execution:** `uv run --group execution pytest tests/test_idm_model.py tests/test_idm_decode.py
  tests/test_idm_targets.py tests/test_idm_eval.py tests/test_replay_camera.py` gives **85 passed**, up from 84.
- **Lint:** `uvx ruff check` is clean.
- **Environment:** a private `UV_PROJECT_ENVIRONMENT`.

## Next

Item 2, the post-hoc pitch-std calibration: pre-registered in the lane doc before anything is computed, with inference
only, on the existing β checkpoints.
