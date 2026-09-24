# scoreboard-fix: yaw-2, β-NLL at seeds 1 and 2; the six-run result (VUH-1353)

2026-09-24.
- **Pre-registration:** the lane-doc addendum "Addendum: yaw-2", LF sha256 `dc38e388faf16808…`, landed in
  `cfd5535`. The original section (`21e17dd9…`) and the addendum are byte-unchanged.
- **Runs:** T1 and T2 in one niced MPS queue, exit 0 after 48 min, code `4e7f005`. Same fold, data, fit settings and
  judge as T.
- **Not done:** no commits, no Linear, no game input.

## The result

The judge is raw-μ yaw direction agreement on moving rows, by `analyse.py`'s definition, applied by `judge_yaw2.py`
(`d63d4427…`). "Learned" means ≥ 0.85 on both 051828 (held out) and 171533 (in-sample).

| Run | Loss | Seed | Held out | In-sample | **Learned** | Yaw corr (held out) | \|μ\|/\|true\| (held out) | Yaw std, still / moving (held out) | Pitch agreement (held out / in-sample) |
|---|---|---|---|---|---|---|---|---|---|
| `loso-051828` (plumbing) | plain | 0 | 0.523 | 0.442 | no | 0.063 | 0.064 | 0.118 / 1.469 | 0.836 / 0.829 |
| C1 | plain | 1 | 0.567 | 0.569 | **no** | 0.147 | 0.050 | 0.135 / 1.224 | 0.829 / 0.870 |
| C2 | plain | 2 | 0.920 | 0.954 | **yes** | 0.736 | 0.658 | 0.108 / 0.714 | 0.823 / 0.807 |
| T | β-NLL 0.5 | 0 | 0.976 | 0.988 | **yes** | 0.920 | 0.811 | 0.143 / 0.398 | 0.814 / 0.846 |
| **T1** | β-NLL 0.5 | 1 | **0.946** | **0.968** | **yes** | 0.854 | 0.900 | 0.206 / 0.618 | 0.783 / 0.779 |
| **T2** | β-NLL 0.5 | 2 | **0.973** | **0.991** | **yes** | 0.902 | 0.878 | 0.146 / 0.503 | 0.798 / 0.778 |

- The `loso-051828` row comes from `idm-diag`. Its in-sample figure (0.442) is `loso-051828` on 171533.
- **β-NLL learns yaw on 3 of 3 seeds. The plain loss learns on 1 of 3.**

**The addendum's fixed reading:** β-NLL becomes the candidate camera loss. It goes to fit-review, and lands behind the
flag, default off, until Gate 1 is re-run with it.

## Beside the judge (reported, not judged)

- **Yaw magnitude:** β-NLL's means are near full scale, 0.81–0.90 of the truth held out, against 0.66 for the one
  plain seed that learned.
- **The failure signature:** the plain loss's failing seeds put the motion in the variance (moving std 1.2–1.5°, means
  about 5 % of the truth). β-NLL's moving std is 0.40–0.62°.
- **Pitch is a little lower under β-NLL:** 0.78–0.85 against the plain loss's 0.81–0.87.
  - The clearest case is in-sample on 171533: T1 0.779 and T2 0.778, against 0.807–0.870 for the plain seeds.
  - This is the guard the pre-registration named: reported, not judged. **Fit-review should weigh it before β-NLL is
    relied on.**
  - One possible cause, untested: β-NLL also down-weights the pitch mean's gradient where pitch variance is small.
    Beyond the three seeds here, none of this is measured.
- **T1's loss** stayed nearly flat through epoch 2 (1.553 → 1.507), then fell to 1.161. It still learned yaw by the
  end of epoch 3. The loss is on the β-weighted scale; it is not comparable with the plain runs'.

## The runs

All `gate1-dev`, 144,932 train examples, 3 epochs, MPS; code `4e7f005` (branch `idm/yaw-test-20260924`, clean).
Hashes were checked across the wire.

| Run | Fit | Checkpoint sha256 | report.json sha256 |
|---|---|---|---|
| T1 (`yaw-t1`) | 1,304 s | `bc82a2a44b0db857204b759cbaf962e417abed7947a2c1bcc7a9f68aa454eb32` | `e7dcfd85e52afcbb36d951b1b27b2dd69925b69e2b046a74ccdb980c4236062f` |
| T2 (`yaw-t2`) | 1,307 s | `a85a15303d8e5d9ce1afc0972238bbdb5b38e7824ada8ec5050f7258471ba5d9` | `92dfeef4489690c254622e2d27257f1dcd2428d6a844c2c2250b7346c4644e20` |

C1, C2 and T are as in `idm-yaw-test.md` (`de69898`).

**Files:**
- **Runs:** in `C:\Users\volpe\repos\rivals-agent\data\idm\runs\yaw-t{1,2}\` (gitignored), with `yaw2.log` and
  `yaw2.exit`.
- **Per-row predictions** (`scratchpad\idm-diag\`):

| File | sha256 |
|---|---|
| `yaw-t1-on-051828-predictions.jsonl` | `2935290aa6d4e1af98e19162804337ab76ba3733a3a37528d4fd779d44c70238` |
| `yaw-t1-on-171533-predictions.jsonl` | `d4de30f6962b58297718845f98cd0689b9c8f57b59bc4cddd84f9fcf54c2958d` |
| `yaw-t2-on-051828-predictions.jsonl` | `75bd143c7b076c9353c9a877dabfe492d3f7f525a90b87216c7056ae4b1c2122` |
| `yaw-t2-on-171533-predictions.jsonl` | `399e43fb49eeadd656a8fd8174699e4acc5b67d8affc486eeb09d715513f13d9` |

## The lane doc

- **Measured entry:** "**Result (measured 2026-09-24, after both pre-registrations)**", appended after the addendum
  inside the yaw section, uncommitted (+21 lines).
  - Entry LF sha256 prefix `cbebbfb465d2d1bc`.
  - File: working tree `121b93fe0452576727140518829091f6419a62a9aa56914c6996c9687b831195`, LF
    `f1de4fd8bb6525206b2b2c273d20e77d607f0158f9843b1acdf15d711244e83a`.
- The pre-registered text above it is byte-unchanged (checked).

## For landing β-NLL

- **The code is ready** on `idm/yaw-test-20260924` at `4e7f005`, one commit on `1df31e7`: `--beta-nll`, default off,
  default path bit-identical, with its test.
- **What still remains:**
  - fit-review of the change;
  - a rebase onto main. `policy/idm/train.py` and `tests/test_idm_model.py` are unchanged on main since `1df31e7`
    (checked, empty diff), so the commit applies cleanly;
  - then Gate 1 re-run with the flag on before the default changes.
- The pitch note above belongs in that review.
