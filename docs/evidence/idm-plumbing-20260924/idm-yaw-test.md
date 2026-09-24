# scoreboard-fix: the yaw falsification test, against its pre-registered judge (VUH-1353)

2026-09-24.
- **Pre-registration:** `docs/lanes/inverse-dynamics.md` "### Yaw falsification test (2026-09-24)". It landed in
  `efea1e4`, and the section's LF sha256 is still `21e17dd95008ecf9…`, unchanged since the go.
- **Runs:** the three as registered, in one niced MPS queue on the Mac. The queue exited 0 after 70 min.
- **Not done:** no commits to main, no Linear, no game input.

## Result against the judge

The judge is raw-μ yaw direction agreement on moving rows (|true| ≥ 0.5°), by `analyse.py`'s definition, applied by
`judge_yaw.py` (`adab45be…`). "Learned" means ≥ 0.85 on both sessions.

| Run | Session | Moving rows | **Yaw agreement** | Yaw corr | median \|μ\|/\|true\| | Yaw std median, still / moving | Pitch agreement |
|---|---|---|---|---|---|---|---|
| **C1** (seed 1, loss unchanged) | 051828, held out | 10,310 | **0.567** | 0.147 | 0.050 | 0.135 / 1.224 | 0.829 |
| | 171533, in-sample | 2,500 | **0.569** | 0.100 | 0.064 | 0.021 / 1.092 | 0.870 |
| **C2** (seed 2, loss unchanged) | 051828, held out | 10,310 | **0.920** | 0.736 | 0.658 | 0.108 / 0.714 | 0.823 |
| | 171533, in-sample | 2,500 | **0.954** | 0.784 | 0.721 | 0.017 / 0.553 | 0.807 |
| **T** (seed 0, β-NLL β = 0.5) | 051828, held out | 10,310 | **0.976** | 0.920 | 0.811 | 0.143 / 0.398 | 0.814 |
| | 171533, in-sample | 2,500 | **0.988** | 0.946 | 0.870 | 0.088 / 0.310 | 0.846 |

**Verdicts:** C1 **not learned**; C2 **learned**; T **learned**.

**The pre-registered reading, row 2 ("exactly one control learns"):** the current loss learns yaw only sometimes, so
**fragility is established**. One treatment seed cannot show that β-NLL removes it. **The next step is seeds, not a
loss change.**

## My call on the predictions

- **The registered reading holds as written.** Under the current loss, the 051828 fold learned yaw in 1 of 3 seeds
  (seed 0 in `loso-051828` failed, seed 1 failed, seed 2 learned). Across the plumbing folds at seed 0 it was 1 of 4.
- **The lane's stated expectation was met,** though it is not part of the judge: at least one control failed and T
  learned.
- **Consistent with the mechanism, but not decisive** (a single seed):
  - T learned yaw on the very seed and data where the unchanged loss failed (`loso-051828`: 0.52 held out, 0.44
    in-sample).
  - It learned it better than the successful control on every yaw figure: agreement 0.976 against 0.920, correlation
    0.92 against 0.74, magnitude ratio 0.81 against 0.66.
  - Its moving-row std is lower: 0.40° against 0.71°.
  - The failing control C1 shows the same signature as the failed seed 0: yaw means about 5 % of the truth, with the
    motion carried in the variance (moving std 1.22° against 0.14° still).
- **Pitch is unaffected by β-NLL:** 0.81–0.85 against the controls' 0.81–0.87.
- **What would settle it** (a proposal, not run): the same fold with β-NLL at seeds 1 and 2, beside the two controls
  already run, so both losses have three seeds on the same data. Pre-register it before running.
  - If β-NLL learns yaw on all three while the current loss learns one, the fragility is the loss's, and β-NLL is the
    change to review.
  - If β-NLL also fails a seed, it reduces fragility at most, and the input or optimiser is next.
  - Cost: two fits, about 45 min of Mac time.
- **Losses are not comparable across arms.** T's train loss (1.556 / 1.162 / 0.882) is on the β-weighted scale;
  C1's is 0.680 / 0.448 / 0.314 and C2's 0.675 / 0.503 / 0.323.

## The runs (all `gate1-dev`, 3 epochs, 144,932 train examples, MPS)

| Run | Code | Fit | Checkpoint sha256 | report.json sha256 |
|---|---|---|---|---|
| C1 (`yaw-c1`) | `1df31e7` (clean) | 1,267 s | `3799fe463874ea2d7e832aa1d56afe38d6b346dd24c2fc3e2d27d82e9e7dc9d9` | `fba0d3209f3a17017e93bf2b878bd897e300286f4153e0388b1a145c10ca97f2` |
| C2 (`yaw-c2`) | `1df31e7` (clean) | 1,280 s | `855885bfb5efb1d3993adb8106c214853095f2be8431fa7a7f477757d361744b` | `7372886221868aec747b3d7069dec70e2f4ec204906d1850ca7e87f3124b1ad1` |
| T (`yaw-t0`) | `4e7f005` (clean; branch `idm/yaw-test-20260924`) | 1,283 s | `17e2eee8ad759131f9c87dd82e804dd81c07c4d34184a497738eb7273acfc873` | `78100f7fe90ba00abead1bf441288060a15df221951230cfc8de7cc233b2fe24` |

- T's report records `camera_loss: {"kind": "beta_nll", "beta": 0.5}`, and its checkpoint meta carries
  `camera_beta_nll: 0.5`. The controls' reports record `camera_loss: null`, because their code predates the field.
- All six files were hash-checked across the wire. They are in `C:\Users\volpe\repos\rivals-agent\data\idm\runs\yaw-{c1,c2,t0}\`
  (gitignored), with `yaw.log` and `yaw.exit`.

**Per-row predictions** (raw μ, log-variance, answers and press probabilities; `diag_predict_ckpt.py`), in
`C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\e2b139e9-140b-415b-a993-b4f5737950d7\scratchpad\idm-diag\`:

| File | sha256 |
|---|---|
| `yaw-c1-on-051828-predictions.jsonl` | `49cfe4d6a3f299999bf67b1b444a7ad2b28177543aaf75f8c050e79344279b1f` |
| `yaw-c1-on-171533-predictions.jsonl` | `2dff97f9535714c5e51ff85760016544313d13f772f5e0e49487e5cf93529517` |
| `yaw-c2-on-051828-predictions.jsonl` | `6c098f82aed996b8127bee862f963ea2555d277615876d1f842a94f2366a40d4` |
| `yaw-c2-on-171533-predictions.jsonl` | `15eb84504130f9c8b4b4e7a512925349469082b834c2b9475dbe7392aab6c4c2` |
| `yaw-t0-on-051828-predictions.jsonl` | `2ad6c113d2b39bf39061547fa997215f39d4eaa3a85118cae3fbee93d2a542cd` |
| `yaw-t0-on-171533-predictions.jsonl` | `0e79401fe88f9f0a415dfe4cb2184f5333229a1e4b860b3fe1ec84b3c3059add` |

## The branch commit

- `idm/yaw-test-20260924` at **`4e7f005716b1613ac4ae089ec96aa784c7d31619`**, pushed. Its parent is `1df31e7`.
  - It adds `loss_terms(..., camera_beta=None)` and `fit(..., camera_beta=None)`, where β-NLL weights each camera
    element's NLL by stop-gradient(var^β), plus `--beta-nll` on `fit`.
  - The default is today's loss bit for bit. The checkpoint meta key is added only when the flag is set.
  - The report gains `camera_loss`.
- **Test** `test_beta_nll_is_off_by_default_and_rescales_only_the_gradient_weight`:
  - the default equals omitting the argument, bit for bit;
  - the mean's gradient equals var^(β−1)(μ − y);
  - the log-variance's gradient is only reweighted;
  - β outside (0, 1] is refused.
- **Tests on the branch:** 66 passed (execution group: model, decode, targets and eval), and ruff is clean.
- **The private PC worktree is** `C:\Users\volpe\repos\rivals-agent-idm-yaw`. The Mac worktree
  `rivals-agent-worktrees/idm-yaw` is at the same commit. Nothing from the branch is on main; you decide what, if
  anything, lands.
