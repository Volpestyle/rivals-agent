# LAND

Independent read-only review by fit-review, 2026-09-26, VUH-1346. **No blocking gate-correctness findings.** The executed G1 selection and mandatory scope-fit guard pass review. There is one report-compatibility qualification: the preserved bytes are the existing metric/verdict blocks, not the entire report or its config (N1 below).

Reviewed only the four requested uncommitted files against `main` at `7ad63e5fa3b00eff4b47c94433059f16c47143ef`. Hand-back hashes match `3ba780b6f5d1104b3de1076f4490be1a53dc48ab95cf2597be11ad8f76a172c0` and `c1b410f6222146ec255a6f1f4e8454912fd7f59974f19a416ac6af0c5b8136f5`. This verdict accepts code for the stated executed-G1 decision; it does not authorize a validation read or a fit launch.

## Findings

**N1 — note: whole-report byte identity is not true, and the stored proof does not claim that scope in its comparisons.** `policy/range_bc/train.py:883` adds `config.g1_press_source` even with the flag off. The added CLI test explicitly expects `teacher_forced` there. `countermeasures/repro_g1.py` compares existing metric blocks and gate verdicts from `evaluate_set`; it does not regenerate or compare the whole `run_fit` report/config. Accordingly, the literal requested check “flag off is byte-identical in verdicts and reports” is satisfied for those existing metric/verdict blocks, but **not for the complete report schema**. This additive metadata is explicitly disclosed in the producer's hand-back and does not alter a gate. Describe the compatibility claim as “existing metric blocks and verdicts unchanged.” If exact default-off config shape is required as well, emit the new config key only when enabled and update the default CLI assertion. This review does not certify whole-report identity.

## Gate behavior

- **Off:** `gates.g1` falls back to the same teacher-forced inputs, with the same arithmetic and thresholds. `gates.evaluate` adds no new verdict keys. Independent canonical-JSON comparisons against the actual `main` implementation matched for complete, incomplete-seed and unknown-pitch fixtures. The retained stored-report proof also reports equality of all old metric blocks and gate verdicts.
- **On:** `evaluate_set` passes the selected arm's and the history-only twin's `executed_teacher_forced` dictionaries directly. G1 reads their macro press-F1 for both seed 0 and the three-seed mean. Camera MAE continues to come from the original teacher-forced model/twin. G0 and G2-G6, thresholds and the self-fed headline are unchanged. The added keys are `G1_press_source` and `G1_teacher_forced_probability`; `pilot_worthy` may change as the intended consequence of G1.
- **The old G1 is actually ungated.** `pilot_worthy` enumerates G0-G6 explicitly. My inverse control made probability G1 fail while executed G1 and the other gates passed; `pilot_worthy` remained true. The producer's opposite control makes probability G1 pass but executed G1 fail and correctly blocks the pilot.
- **No fallback on missing executed seeds.** `gates.evaluate` checks all three seeds in both executed dictionaries before calling `g1`. Independent controls removed each seed from either side and emptied either side; each remained incomplete/not pilot-worthy. Separate seed-0-fail/mean-pass and seed-0-pass/mean-fail controls confirmed both executed press conditions are required.
- **The executed metrics are the previously reviewed ones.** AST comparisons against main confirm `executed_runs`, `predict_teacher`, `predict_self`, `own_previous`, `_median_classes` and `fit` are unchanged. The evaluated executed window is still `{early: 1, late: 0, self_fed: true}`. No decoder, mask, saturation, hold-state, training or self-conditioning change is hidden in this patch.

## Echo test and fit enforcement

`test_g1_can_read_the_executed_press_f1_and_is_unchanged_by_default` is a meaningful **gate-input regression**: it supplies strong probability metrics but an executed model no better than the twin, and verifies that executed G1 and pilot-worthiness fail while the reported probability G1 passes. It substitutes metric blocks; it is not a new end-to-end simulation of a temporal echo. The unchanged, previously reviewed late-0 execution/metric path supplies that premise. An in-memory mutation making `g1` ignore the new press inputs was killed by the added test's assertion. The torch integration test separately verifies that `evaluate_set` wires the actual executed blocks into the gate and preserves other metrics/gates.

The `run_fit` requirement at `train.py:771-773` executes before preregistration/parity files, denylist loading, code closure checks, output-directory creation, cohort loading or training. The CLI flag is `store_true` with false default; both `main()` and direct `run_fit()` reach this guard. The accepted flag is then forwarded unchanged to both dev and validation evaluation, and the report records its source. There is no alternate scope-fit path or silent fallback in the reviewed files. Choosing smoke/plumbing remains a different recorded scope, not a scope-fit bypass.

Independent refusal probes used nonexistent train/dev/val/cache paths: without the flag, the call raised the required `pass --g1-executed` error and created no output. With it, the call passed this check and stopped at the missing-preregistration requirement, also without output. The existing broader scope-fit refusal test passed with its updated flag handling, so the older prerequisite checks still execute.

The real-fit draft's decided change is consistent with this implementation: G1 press-F1 uses executed teacher-forced T, camera retains the existing G1 comparison, and the real fit must pass the flag. This review does not assess the draft's other experiment choices or future judge script.

## Evidence

Retained proof: `countermeasures/repro-g1-interim94-s012.json`, SHA256 `e366859f21955c32e7cbab57d2795fda34f5ccd59c6743067b7261f8fdb1a9d5`. I inspected its generator and checked the receipt: all default block/verdict comparisons are true, on/off metric blocks match, the reported probability G1 equals default G1, and the other gate fields match. Checkpoint files are hashed against stored report entries by the generator. I did not independently rerun its MPS inference or read the underlying corpus. The v2 scope guard changes no evaluation code, so the v1 proof remains applicable within the scope described in N1.

Independent checks used `UV_PROJECT_ENVIRONMENT=C:/Users/volpe/.uv-envs/fit-review`, CPU with one OMP/MKL thread, bytecode and pytest cache disabled, temporary files outside the checkout, and no corpus opt-in:

- `uv run --no-sync pytest tests/test_range_bc.py -q -p no:cacheprovider -k 'g1 or oracle or gate'`: **6 passed, 129 deselected**, 1.98 s.
- `uv run --no-sync pytest tests/test_range_bc_torch.py -q -p no:cacheprovider -k 'scope_fit_refuses_what_the_review_asked or evaluate_set_can_gate_g1_on_the_executed_press_f1'`: **2 passed, 36 deselected**, 42.33 s.
- `review-fit-g1-probes.py`: requested hashes, unchanged-function comparisons, old/current default verdict identity, inverse ungated-probability control, missing-seed and seed-0/mean controls, mutation sensitivity, pre-output/pre-data refusal, and proof consistency all passed. Its first attempt stopped on a missing directory for synthetic mutation fixtures; creating that external temporary directory corrected the probe, with no repository change.

| Reviewed file | LF SHA256 |
|---|---|
| policy/range_bc/gates.py | 027a09a41f86dc7df1c99272aead3cfd919ee27818584fdb86e807d9c70583e3 |
| policy/range_bc/train.py | f5365d30c53f8bbb77f8108c9526e2bca27e983b583c0a1fc83ba21c5a84206e |
| tests/test_range_bc.py | cd806415383a8f6d41b85b84b115e5aefb5a082f039d51f31defea4f1608dec7 |
| tests/test_range_bc_torch.py | a6daaf444409d0e45d7eec5bef543f88501ddebf83678c19dd8ea9837e261e01 |

No checkout edits, commits, Linear actions, game input, Mac jobs, or real validation/sealed-session reads. Earlier accepted evidence is reused for unchanged behavior.
