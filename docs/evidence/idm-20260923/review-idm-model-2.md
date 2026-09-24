# Re-check: IDM model fixes on the landed bytes (VUH-1353)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-23. Read-only.

**Bytes.**
- `d402c74` holds exactly the hand-back's bytes. The working tree (CRLF) hashes to `idm-model-2.md`'s values:
  - `frames.py` `137844b5`;
  - `train.py` `b615ab26`;
  - `test_idm_model.py` `a1cbb694`.
- LF-normalised, they equal the committed blobs (`5df5c34d`, `149c1eb7`, `1ef9b184`), and `git diff HEAD` is empty.
- `model.py` (`fe353209`) and `__init__.py` are unchanged.

**Ran** (my own environment built from the lockfile, torch 2.14.0+cpu):
- **Tests:** the four test files, **55 passed**.
- **Probes** on synthetic data in my scratchpad, using the landed code:
  - `probe2.py`: the loss, the checkpoint and the store binding;
  - `run.py`: an end-to-end `run_fit` on two synthetic sessions, with training stubbed and `require_committed`
    recording its argument.

## Verdict: every item you listed is confirmed. One new blocker: a real fit can never finish (C1)

| Item | Result |
|---|---|
| The checkpoint carries the support set, train press counts, code closure, and target, store and calibration hashes | **Yes.** `provenance()` carries seed, `supported` (full vocabulary), `train_press_counts`, `code_closure`, per-target `sha256` (hashed before and after load), split, `media_sha256`, `calibration` and rows, and per store `media_sha256`, `frames_sha256` and `hud_sha256`. `checkpoint_bytes` refuses meta without these (probed); `load_checkpoint` requires them and restores `model.support` (round trip probed) |
| `predict` refuses a differing support set | **Yes.** `model_support` refuses a model without a set and a caller's set that differs (probed). `gate1` scores on the model's own set, and so do its baselines |
| `require_committed` guards a real fit | **Only partly; see C1** |
| The store refuses another media sha256 or pts | **Yes.** `bind` refused another `media_sha256`, a pts off by one frame, and a 60 fps header (all probed). A store naming a denylisted media is refused when opened (probed with the pinned denylist's hash in a synthetic manifest; no sealed data touched). `run_fit` binds every store before use |
| A masked NaN gives finite gradients | **Yes.** With NaN and inf in masked targets and a NaN in a masked sigma, the loss is finite and the gradients are finite and **bit-identical** to the clean batch's (probed) |
| Per-regime total std | Present. The predictor reports the total std, `sqrt(model var + camera_sigma(pred, predicted regime)²)`, and the predicted `gain_regime`; abstention bounds are 1° and 3°. `model_std_coverage` gives abstention and within 1σ/2σ per **true** regime. The 3° extrapolated bound is the lane's choice and awaits your call |

## C1 (blocks any real fit): the closure changes during `run_fit`, so the fit always refuses after training

- `run_fit` takes `code_closure()` and calls `require_committed` **before** loading any target. `T.load` then imports
  `agent/human_intake.py` and `agent/human_demos.py` lazily, through `idm_targets.load_denylist`, `import` inside the
  function.
- The closure taken after the fit therefore holds 26 modules against 24, and
  `require(prov["code_closure"] == closure, …)` fails.
- **Reproduced end to end with the landed code:**
  - `run_fit refused: FitError the code closure changed during the fit`, after the (stubbed) fit;
  - no output directory was written;
  - `require_committed` had checked 24 modules, and `agent/human_intake.py` and `agent/human_demos.py` were not among
    them.
- **Two consequences:**
  - A real fit trains fully and is then refused, so no checkpoint is ever written.
  - The denylist and target-loading code escapes the committed-code guard.
- The test suite misses this: its `run_fit` test refuses at `require_committed`, before `T.load`.
- **Fix:**
  - Import everything a run needs before the first closure: for example `T.load_denylist()` at the top of `run_fit`, or
    module-level imports of `agent.human_intake` and `agent.human_demos` in `idm_targets`.
  - Or: take the closure after all loading and before `fit`, `require_committed` on that closure, and compare at the
    end.
  - **Add an end-to-end `run_fit` test** with a stubbed fit, like my `run.py`. It should assert the run completes and
    that the committed closure includes `agent/human_intake.py`.

## Minor

- **The store's pts list is not in the provenance.** `store_entry` records the array hashes but not `frame_pts` or a
  hash of `frames.json`. Add a manifest sha256.
- **`bind` checks pts only for frames that some target row names** (`frame0`/`frame1`). Window frames beyond the rows'
  coverage, at run edges, go unchecked. The media-sha binding is the real guard.
- **Neither `bind` nor `Examples` checks that the store's width and height equal `Config`'s.** A narrower store would
  pass through the adaptive pooling and slip past the 448 px (F3) guard. Require equality in `bind`.
