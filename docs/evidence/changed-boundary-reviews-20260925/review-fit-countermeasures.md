# LAND WITH FIXES

Independent review by fit-review, 2026-09-25, VUH-1346. **Fix the two blocking findings below before landing or relying on these countermeasures.** Re-review their changed boundary; a full new training experiment is not needed to resolve them. No checkout edits or commits, Linear actions, game input, Mac jobs, or sealed-session reads were performed.

Reviewed the four-file uncommitted delta against `cf25505927be8cc750ad034b30be0cbaaa181d94`. Brief SHA256 `946268a387dc5f459add78faaf91cbd0757c88b6f253e33d9f4899bff59d6741`; producer hand-back `69b5572e783bd5293d328b40309a97b23952af676700d35c3280fc8a2bcece9a`.

## Findings

### F1 — blocking: unknown human holds become measured idle

**Location:** `policy/range_bc/metrics.py:239-241,260`; missing assertion in `tests/test_range_bc.py:1196-1198`.

`steps` includes every valid row, but `human_any` increments only for known positive holds. A row with all live holds unknown therefore enters the denominator as a negative. Reproduction: one valid row, every hold unknown, all held values zero under their masks, neutral prediction. `selffed_checks` reports `steps=1`, `human_any_hold_share=0.0`. There is no observed human idle on that row. The added unknown-channel test checks onset recall and press ratio, but never the human share.

This biases the human reference downward and compares it against a model share on a different observability basis. That reference is intended to decide whether an arm is latched (within a declared range of the human share). It also violates the existing contract that unknown channels never mean no action. This is a reproduced edge case, not a claim about how many such rows the interim dev contains; I did not read the corpus to estimate prevalence.

**Expected fix:** define and report the denominator for an observable human any-hold label. A known positive establishes any-hold; a negative requires every live hold to be known false. Otherwise preserve unknown and exclude the row from the human comparison. Score a comparable model share on those same rows (the unconditional model share may remain separately useful). Report unknown/excluded counts and return `None` without observable rows. Add controls for all unknown, mixed known-negative/unknown, known-positive/unknown, all known idle, and empty/invalid runs.

### F2 — blocking: the vectorized camera median is not executor-equivalent at the threshold

**Location:** `policy/range_bc/train.py:339`; reference `policy/range_bc/vocab.py:103-111`; missing boundary coverage in `tests/test_range_bc_torch.py:695-706`.

`own_previous` accumulates probabilities in float32 (`cumsum`), whereas `predict_self` hands float32 probabilities to `vocab.median_class`, which accumulates their Python-float values. Near 0.5, float32 rounding can cross the decision threshold early. The independent probe supplies finite float32 logits and reproduces:

- float32 cumulative mass through class 14: `0.5`;
- Python cumulative mass through class 14: `0.4999999988358468`;
- `own_previous` feeds camera class **14**; the executor-reference path feeds class **15**.

Both classes survive the saturation/reclassification unchanged. Thus the training feedback can encode a different camera command than the self-fed executor. The existing random parity test passes because it does not deliberately exercise cumulative threshold ties. This is a narrow numerical edge, not evidence of a material error rate in the stored fits, but exact decode parity is an explicit acceptance requirement of this change.

**Expected fix:** make median selection use the reference accumulation/decision semantics on supported devices, or establish one shared deterministic rule with an explicitly reviewed change to all affected paths. Preserve default-off prediction/report behavior. Add the retained logits from `review-fit-probes.jsonl` as a boundary regression, with values on both sides of 0.5. Account for MPS's dtype support when selecting an implementation.

### N1 — note: MPS retraining proof is a producer claim, not independently replayed here

**Location:** `countermeasures/repro_metrics.py:24-41`, `countermeasures/repro-train.zsh:8-15`, producer hand-back “Reproduction proofs”.

Proof (a)'s canonical-JSON comparison is sound for the stored report blocks: checkpoint hashes are checked before evaluation, all old blocks and gates are compared, and the retained result (`459b388a172ef20e67c3af774d6f5131b253ba2dcc71d0e74e8a4dce8918c05f`) reports all five comparisons true and precisely the two new keys. I inspected the script and result, without rerunning the Mac evaluation.

Proof (b)'s supplied shell script launches the stated retrain and records exit/status; it does not perform or retain the old/new checkpoint and report comparisons. The hand-back states their hashes and equality, but the original/retrained artifacts and a comparison receipt are not in this local packet. The lead should retain that existing comparison output with the two checkpoints' hashes when accepting the MPS claim; this is not a request to repeat the training. My independent CPU comparison compiled the actual old `fit` function from `git show cf25505:policy/range_bc/train.py` and compared four optimizer steps against the new default on synthetic batches. Checkpoint bytes matched, SHA256 `26577846b83ef8eb8aa5730a3f561e97644c21affe86f23e9564a3e9eb31f53e`.

### N2 — note: direct `fit` does not validate previous-action dropout

**Location:** `policy/range_bc/train.py:379-381,754`.

The hand-back says both `fit` and CLI validate previous-action dropout. The CLI does; `fit` itself checks only the self-conditioning probability/ramp. This predates the newly exposed CLI knob and is not a default regression. Correct the claim or add matching validation if direct API callers are meant to get that guarantee.

## What checks out

- `executed_runs` delegates action decisions to `executor.decode_step`, resets holds for each run, and saturates camera degrees while preserving unknown pitch. State advances across unscored rows, matching `predict_self` and `metrics.evaluate`; only valid rows contribute scores. Independent tests confirmed run reset, unscored-state continuity, unknown pitch, and saturation. Action threshold/tap/hold/live-mask parity passed 162 enumerated reference sequences, including logits exactly zero (probability 0.5).
- Default-off control flow preserves model initialization, shuffle order, augmentation/dropout RNG, optimizer scheduling and the forward call. No new RNG is drawn when off. The model has no stochastic layer introduced by this change. The added evaluations are deterministic, and existing report blocks remain separate from the new keys. Default checkpoint metadata is unchanged.
- Self-conditioning is the documented one-step approximation: the first pass sees dropped teacher history; decoded actions are detached and shifted by one step; the second pass receives selected replacements. It does not recompute predictions after each replacement. The causal LSTM sees no future frame/history, and the helper reads no current target tensors. Training batches/statistics remain train-only; dev loss does not drive these replacements or checkpoint selection.
- Tiny synthetic fits confirmed repeatable enabled output, a changed history-dependent model, and unchanged `history=False` output. Forward probes confirmed rate zero equals the ordinary forward pass, rate one uses all own history after step zero, decoded history has no gradient, and frame features still receive gradients. A four-step fit with p=0.5/ramp=0.5 used `[0, 0.25, 0.5, 0.5]`.
- Replacement is independent of dropout as disclosed. Away from step zero, the probability of retaining a deliberately blank input is `prev_dropout * (1 - current_rate)`. This interaction and the one-step approximation must stay explicit in the experiment's pre-registration; neither is an undisclosed implementation defect.
- `frames_only_nohud` correctly disables both history and HUD and receives self-fed checks. It is a reasonable comparison arm for the no-HUD candidate; the lead must explicitly select it in the pre-registration instead of assuming the older HUD-enabled frames-only arm is equivalent.
- Executed teacher-forced hold-change F1 correctly uses its own previous decoded hold while retaining teacher-forced edge tolerance (early 1, late 0). Human onset recall and press counts honor their per-channel masks and the live mask. Zero-denominator onset/press results return `None`; the hold-share exception is F1 above. Camera comparison reuses the self-fed and zero-motion metrics on the same evaluation set and known camera rows.
- None of these four files occurs in the named 16-file deployment freeze manifests.

## Independent verification

All tests used `UV_PROJECT_ENVIRONMENT=C:/Users/volpe/.uv-envs/fit-review`, bytecode disabled, pytest cache disabled, temporary outputs outside the checkout, and no corpus opt-in. Torch ran on CPU with one OMP/MKL thread.

- `uv run --no-sync pytest tests/test_range_bc.py -q -p no:cacheprovider`: **132 passed, 1 skipped**, 18.27 s.
- After installing the locked execution group, `uv run --no-sync pytest tests/test_range_bc_torch.py -q -p no:cacheprovider -k 'own_previous or executed_runs or the_fit_cli_reports_the_new_metrics'`: **3 passed, 32 deselected**, 176.69 s.
- An initial full torch-file run was stopped by me after six successful tests while it was spending time in an unchanged training test. No full-file pass is claimed.
- `review-fit-probes.py` and its retained output `review-fit-probes.jsonl` reproduce both findings and the independent checks above. The probes import code and use synthetic tensors only. Removing `~prev_h` from the vectorized tap rule **in memory only** caused the existing `test_own_previous_decodes_exactly_as_predict_self_sends` assertion to fail: mutation killed. No source file was mutated.

Reviewed LF SHA256s, matching the producer packet:

| File | SHA256 |
|---|---|
| policy/range_bc/train.py | ca9c8439b8e6f32ce645c3f15e0fe79693484643dac72bb4e6ef500da2ac4808 |
| policy/range_bc/metrics.py | bd30152730f7b1e40cdd2471b632871f05cbbadef6a49f033a4d80a8d88e7d76 |
| tests/test_range_bc.py | 416a7d96992cea08b106387db461e54e12e1bc2421c62bc700cca4f4a1962070 |
| tests/test_range_bc_torch.py | 371f5d05867e6d3d12c38b484ca012712c0410eb9dcc3048eb468cfa9fe10f97 |
