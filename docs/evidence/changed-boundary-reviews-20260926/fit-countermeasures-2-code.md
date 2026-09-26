# fit-countermeasures-2-code (VUH-1346): known-idle corruption (D) and sequential self-conditioning (E), for review

Brief `brief-hud-review-countermeasures-2.md` (`99c96599…`), step 1. Uncommitted in the shared checkout, on
`0917aac`. Needs fit-review before the pre-registration or any run.

## Files (LF sha256)

| File | Before (`0917aac`) | After |
|---|---|---|
| `policy/range_bc/train.py` | `f5365d30…` | `693f12a60cdf14fa29c321c95c56d23075b03e50a2af337d6e9043d19507890b` |
| `tests/test_range_bc_torch.py` | `a6daaf44…` | `85ee15007c9e107f3d7a2e036d596f3b5ac8aad1e0567d1d9c3d8827c5da6aff` |

- **Size:** `train.py` +145 / −12.
- **Untouched:** `metrics.py` and `gates.py`.
- **Deployment freeze:** not in it.
- **Other lanes:** the checkout's other files are theirs.

## What changed (all default off; the default path is the old code path)

### A shared per-step decode

`own_previous`'s loop body moved, unchanged, into **`_sent_vector(p, cy, cp, prev_h, live, pk, rows, width)`**: one
step of `executor.decode_step`'s rule for a batch, returning the vector `predict_self` feeds next and the new held
bits.
- `own_previous` calls it, with the same operations in the same order.
- The round-1 parity and boundary tests still pass.

### D, known-idle corruption (`--idle-corruption P --idle-run LO HI`, defaults 0 and 8 48)

`IDLE_CORRUPTION_RULE`. Each training sequence, with probability P, gets **one run** of L steps:
- L is uniform in [LO, HI], clipped at the window's end;
- the run starts uniformly in [burn-in, T−1] (steps 32-95 of the 96-step window, so it lands on scored steps);
- the run's previous-action input is **`train.idle_vector`**: the *known* all-idle vector `predict_self` feeds after a
  step in which nothing was sent (no hold, press or release; the zero camera class on yaw, and on pitch where the
  session's pitch gain is known; known bit 1), whatever the human did.

**Mechanics:**
- applied after prev dropout; the model call is the ordinary `forward`;
- draws from `torch.Generator(seed·1000003 + 2)`, the same draws whatever P is;
- the generator exists only when enabled.

### E, sequential self-conditioning (`--self-roll P --self-roll-steps K --self-roll-ramp F`, defaults 0, 32, 0.5)

`SELF_ROLL_RULE`. Per batch, a start s is drawn uniformly in [burn-in, T−K] (32-64 for K = 32). Then **`rolled_history`**:
1. builds the LSTM state with a no-grad pass over the batch's own input up to s;
2. rolls K steps **closed-loop**: each step is fed the `_sent_vector` decode of the step before, from the batch's input
   at s (which also seeds the previous executed hold);
3. uses the camera median through `_median_classes`, the reviewed exact rule.

**Replacement:** each sequence, with probability `P · min(1, step / (F · total))`, takes the rolled inputs at s+1..s+K
in the trained pass.

**Mechanics:**
- frame features are computed once and carry the gradient; the rollout sees them detached, no-grad;
- draws come from `torch.Generator(seed·1000003 + 3)`, the same whatever the rate is;
- the rollout is skipped when no sequence is picked.

**Unlike round 1's C:** the rolled history is the model's own closed-loop output. An idle model rolls into the known-idle
state while the human acts, which is exactly the absorbing state. C's one-step decode came from the true history.

### Guards and records

- **Guards:** `fit` and the CLI refuse:
  - more than one of self-conditioning, idle corruption and self-roll;
  - P outside [0, 1];
  - LO < 1 or LO > HI;
  - K < 1;
  - a ramp outside (0, 1].
- **Report config:** always gains `idle_corruption` (`{p, run, rule}` or null) and `self_roll` (`{p, steps, ramp,
  rule}` or null).
- **Checkpoint meta:** gains them **only when enabled**, so default checkpoints are byte-identical.

## Tests

| Where | Suites | Result |
|---|---|---|
| PC, own `UV_PROJECT_ENVIRONMENT` (stdlib) | `test_range_bc.py`, `_contract`, `_plumbing` | **146 passed, 2 skipped** |
| Mac, `code-r2` (a `git archive` of `0917aac` plus the two files, hashes checked, own venv) | torch, `test_range_bc.py`, `_contract`, `_plumbing` | **190 passed, 1 skipped** (557 s; `countermeasures/r2-tests.log`) |

**New tests:**

| Test | Shows |
|---|---|
| `test_idle_vector_is_what_predict_self_feeds_after_nothing_was_sent` | equals `prev_vector` of a decoded all-idle step with the saturated zero camera, with and without a pitch gain |
| `test_idle_corruption_writes_one_known_idle_run_per_hit_sequence_and_draws_the_same_whatever_p` | P = 0 leaves the input unchanged and leaves the generator in the same state as P = 1. At P = 1 every sequence has exactly one contiguous known-idle block, starting at or after the burn-in, 8-48 steps unless clipped at the end, and nothing else changes |
| `test_rolled_history_is_the_closed_loop_executor_decode` | `rolled_history` equals a reference that makes the same batched model steps but decodes with `executor.decode_step`, `vocab.median_class`, `executor.saturate` and `steps.prev_vector`. Exactly, for three (s, K) cases including K past the window's end; steps outside the segment unchanged |
| `test_d_and_e_are_off_by_default_act_only_through_the_history_and_are_reproducible` | P = 0 gives the default's bytes, for each option. Enabled is byte-reproducible and differs. On a `history=False` model each option gives the same bytes as off. Combining two is refused, as are a bad run range and K = 0 |
| `test_the_fit_cli_records_known_idle_corruption_and_self_roll` | default config nulls; each option's config (with its rule) and checkpoint meta; the CLI refuses a combination |

**Kill checks** (`countermeasures/mutation_r2.py`, in memory only; exit 0 means both killed):
- E rolling on the **true** history instead of its own decode fails the rollout test;
- D feeding "unknown" (`prev_vector(None)`) instead of known-idle fails the idle-vector test.

## Default-off proofs (the round-1 pair, on `code-r2`)

**(a) Stored report.** `repro_metrics.py` re-evaluated `interim94-s012` (`countermeasures/r2-repro-metrics.json`):
- `teacher_forced`, `self_fed`, `sanity`, `human_sanity` and the gates are **byte-identical**;
- the output file is byte-identical to arm A's re-read (`8a13a3fd…`).

**(b) Retrain.** `countermeasures/r2-proofs.zsh` retrained the control's seed 0 with default options into
`runs/r2-repro-control47-seed0`, compared by `proof_b_receipt2.py` into `countermeasures/r2-proof-b-receipt.json`.
**Result: byte-identical.** The run went 06:47:56 → 07:16:51, exit 0; the receipt is `f7d2a620…`.

| Checkpoint | Retrained file = stored file = both report entries |
|---|---|
| `model_nohud-seed0.pt` | `5cb5a1887483a63ce4c67f3647b36b063a6998fd3cc905e65b6a01d60d2ba6b1` |
| `history_only-seed0.pt` | `6a0cce0ade7b5c74d2517bb2126062dc76fa7f7ff7dde7e09afeeb1e087dbe11` |

Also equal:
- the seed-0 teacher-forced, self-fed and sanity blocks;
- the baselines and human sanity;
- the epoch logs without wall time;
- `train_statistics` and `ar2`.

**The receipt's `all_equal` is false for one reason only.** Its config comparison excludes just round 1's two new keys,
and the config now also carries `g1_press_source` (`95c1d48`), `idle_corruption` and `self_roll`.
`countermeasures/r2-config-check.txt` shows the config minus those five new keys equals the stored one. The new keys'
values:
- `g1_press_source` "teacher_forced";
- `idle_corruption` null;
- `prev_dropout` 0.2;
- `self_condition` null;
- `self_roll` null.

## B seed 0: an optimisation failure, not an unlucky seed

From its checkpoint only (inference, no rerun):
- `countermeasures/b0_probe.py` → `b0-probe.json`;
- `countermeasures/b0_probe2.py` → `b0-probe2.json`;
- 1,024 dev rows of 205528.

**What the probe shows:**
- **B seed 0's frame features exploded:** mean |feature| 29.0, max 738, against 1.9 (max 94-119) for seeds 1 and 2.
- **That saturated its LSTM:** 99-99.6 % of the input-to-hidden gate pre-activations are beyond ±5, against 44-55 % for
  seeds 1 and 2.
- **So the hidden state is nearly constant across rows:** mean std 0.005, against 0.35.
- **So are the outputs:** action-probability std 0.001 against 0.055; camera 0.0001 against 0.013.
- **The encoders are not dead:** the crop embedding varies strongly across rows (std 10.9); 179 and 173 of 256 units
  are dead in the global and crop embeddings, against 20-135 in the live seeds.

**What went wrong:** the gradient cannot pass the saturated gates, so the model sat on the prior. Its train loss went
flat at 2.46 after epoch 0, and dev stayed at the untrained 2.39.

**Why frames-only is exposed:** the encoders end in an unnormalised ReLU, so embeddings can grow without bound, and a
frames-only model has no history path to learn through. Seeds 1 and 2 were half-saturated too, which fits their slow,
late learning.

**Consequence:** a frames-only arm needs input normalisation (for example a LayerNorm on the frame features) or a lower
learning rate before its result means anything. Arms with a history input have a second gradient path.

**Not checked:** whether the explosion happened in epoch 0 or the warmup. No intermediate checkpoint exists.

## For the pre-registration (step 2, after review)

**Proposed:** D at P 0.5, runs 8-48; E at P 0.5, K 32, ramp 0.5.
- **D** at P 0.5 covers about 16 % of scored steps: a mean of 21.0 corrupted steps per hit sequence within the 64
  scored steps.
- **E** at full rate covers about 25 %: half the sequences, 32 of 64 scored steps.

The reasoning goes in `fit-countermeasures-2-prereg.md`.
