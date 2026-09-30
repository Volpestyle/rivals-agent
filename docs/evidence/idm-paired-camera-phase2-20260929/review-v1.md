# Independent boundary review v1: IDM paired camera diagnostic, phase two, VUH-1353, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, outside the IDM lane; reviewer of phase one). Read-only.
- I did **not** run `paired.py`, and opened no video, ledger, corpus, checkpoint or D: output.
- I hashed the 185 manifest entries: code, packet files and the full03 runtime source closure.
- I resolved module locations with `importlib.util.find_spec`, bytecode off. As a side effect it ran the closure's
  empty `policy/__init__.py` and the docstring-only `policy/idm/__init__.py`.

Reviewed against `SHA256SUMS.json` sha256 `271eccbd44eca1c17df9b67f2c384e356784e11424f05d83800c1b0ffffee23e`. All 185
entries match: 172 runtime-closure files, `paired.py`, `test_mapping.py`, `README.md`, `access-audit.json`,
`agent/human_demos.py`, `agent/human_intake.py`, the phase-one v2 receipt and the five HUD-alignment inputs.

## Verdict: **LAND** (with notes)

No blocking finding. The notes below should be fixed or recorded, but none of them opens data access or input beyond
the boundary, and none changes the agreement numbers.

## Checks

1. **Data access stays inside the phase-one boundary.**
   - `boundary()` first re-verifies every manifest pin.
   - It then loads the denylist with the landed single-read `human_intake.load_denylist`, using the pin recorded in the
     pinned `access-audit.json`.
   - It refuses either source on session ID or group, pinned media hash, or path, with both sides normalized identically.
   - It re-hashes both videos and the three trust-on-first-use live ledger files before any use.
   - The replay ledger is never opened.
   - New reads are limited to what phase two needs: the pinned checkpoint and its pinned code closure.
   - Every output is created exclusively under `D:/rivals-agent-evidence/idm-paired-camera-development-20260929`:
     `timing-qc.json`, `prepared.json`, `*.rgb`, `*.grey`, `*-decode.log`, `agreement.json`, `comparison.csv` and
     `comparison.svg`. ffmpeg runs with `-n`, and a decoder rerun is refused. The one exception is note N1 (bytecode).
2. **No fit, label export, admission or checkpoint change.**
   - There is no `torch.save`, optimizer, target or registry write.
   - The checkpoint's sha256 is verified (`f681da9f…`) before `train.load_checkpoint(..., device='cpu')`, and the model
     shape is asserted (window 8, 252×448).
   - Outputs are model predictions and pairing metadata. The only logger data written is focus/UI key events and packet
     clock values for QC, with no camera or mouse truth.
   - I resolved imports the way the script would: `policy`, `policy.idm.train`, `policy.idm_targets` and
     `policy.idm.model` all come from the **closure**, and no support-a3 path is imported. See N2 for `agent`.
3. **Refusals.** `score()` refuses in each of these cases:
   - `review.json` is not at the fixed D: path;
   - its sha256 does not equal the operator-supplied pin, or the file is missing;
   - `reviewer` is missing, or `prepared_sha256` does not match the current `prepared.json`;
   - any of `same_identity`, `continuous_pov`, `replay_1x`, `focused` or `ui_excluded` is not exactly `True`;
   - `evidence` is missing;
   - `valid_live_intervals` is missing, empty, widened beyond [120, 155), inverted, overlapping, NaN or mistyped.

   Both stores are re-hashed before use. All of this happens before the model is loaded. That the reviewer actually
   inspected the frames is a procedural claim that code cannot enforce, and the README says so.
4. **−1/0/+1 use the same eligible set.**
   - `pairs()` builds each row once, from the live 17-frame context at offsets −16…+16 in steps of 2.
   - Replay frames are the nearest PTS within 4.6 ms (ties go earlier), their ordinals must advance by 2, the whole
     context must lie inside a reviewed interval, and both ±1 neighbours must exist inside the replay span.
   - All four renderings score the identical `rows`, and agreement is computed on the common set answered by all four.
   - Decode enforces 7–10 ms native PTS steps, so a ±1 shift cannot cross a discontinuity.
   - Rows are fixed before any model output exists.
5. **The README's claims match the code.**
   - Agreement only: `accuracy: None` with the stated reason, and MAE/RMSE are computed between renderings. Distance to
     zero is labelled "not accuracy".
   - Bounded decode of live [120, 155) and replay [89.39, 124.39) at BelowNormal, with 2 codec threads and 1 filter
     thread, and a game/OBS process check.
   - A memory-mapped grey conversion with integer (77, 150, 29) luma.
   - The camera head depends only on motion: `cam = self.camera(m)`, and the HUD tensor feeds only `edge`.
   - The reference gain is used only to reproduce the predictor masks.
   - The Windows swscale limitation is stated, and the decoder command, filter graph and platform are recorded. The
     README claims no bit-identity.

## Notes (fix or record; not blocking)

- **N1 (writes outside D:): bytecode.** `score()` imports the closure's modules from
  `data/idm/cloud-20260927/runtime-full03-05a61b4/code/cloud/idm_payload`, which currently has no `__pycache__`. Without
  `sys.dont_write_bytecode = True`, or `PYTHONDONTWRITEBYTECODE=1`, Python will create `__pycache__` directories inside
  that frozen closure, and `boundary()` does the same under `agent/`.
  - `data/` is gitignored, and `policy/idm/native_entry.py`'s inventory check ignores `__pycache__`, so nothing breaks.
  - But it contradicts "writes only to D:". Set the flag at the top of `paired.py`.
- **N2 (runtime provenance claim): mixed runtime.**
  - `boundary()` imports the **repo's** `agent` package before the closure is put on `sys.path`. The closure's
    `train.py` then does `from agent import human_demos, human_intake`, which binds to the repo copies.
    `human_demos` is identical to the closure's, but `human_intake` differs by today's pin hardening.
  - The scoring path uses neither: `train.py` makes no calls into them, and `_camera` uses the closure's `idm_targets`.
    So the predictions are unaffected, and both repo files are pinned in this manifest.
  - Still, the README's "imports the original runtime source closure" is not literally true, and the closure-first
    resolution of `policy` rests on import order that nothing asserts.
  - After the imports, assert that `train.__file__`, `idm_targets.__file__` and `model.__file__` lie under `CLOSURE`,
    record the paths and sha256s of the loaded `agent` modules in `agreement.json`, and correct the README sentence.
- **N3 (tests): the review gate is untested.** `test_mapping.py` covers only the mapping and metrics. The review
  refusals in item 3 are straightforward, and I verified them by reading, but they sit inside `score()` after
  `boundary()`, so they cannot be tested without real data. Factor them into a pure `check_review(review, prepared_sha)`
  and add synthetic refusal cases, including an interval widening, an overlap and each false flag.
- **N4: hash-then-reread.** The pinned ledger files (`inputs.jsonl`, `frames.csv`) and videos are hashed in
  `boundary()` and then re-read by `prepare()` and ffmpeg. That is acceptable for local development evidence, since
  ffmpeg cannot share a hashed read, but the README could say the authenticated bytes and the parsed or decoded bytes
  come from separate reads.
- **N5 (cosmetic).** The code comment "per-second medians" (`paired.py:229`) describes what is actually per-second
  means; the SVG text correctly says means.

## Conditions

- This LAND authorizes phase-two execution as frozen: prepare, then an agent-reviewed and hash-pinned `review.json`,
  then score.
- A changed packet byte requires re-review of the delta. That includes fixing N1–N3; please route those back as a
  small delta, and they are quick to re-review.
- No accuracy, Gate 2, label or admission use of the outputs.
