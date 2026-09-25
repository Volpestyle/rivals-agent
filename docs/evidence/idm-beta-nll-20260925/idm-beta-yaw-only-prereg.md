**Addendum: β-NLL on yaw only** (pre-registered 2026-09-25, after A1-A4 and before these runs; lead's decision
`beta-default`).
- **Why:** A1-A4 favoured β-NLL on yaw everywhere. On pitch it cost at Gate 1: the moving median error went from
  0.508° to 0.568°, and extrapolated 1σ coverage from 0.734 to 0.604. So β-NLL is not default-on yet. This test puts
  β-NLL on yaw alone, with the plain Gaussian NLL on pitch.
- **Code:** one commit on branch `idm/beta-yaw-only-20260925` from `fe5c9ca`. It adds an axis option to the same
  flag (`--beta-nll 0.5 --beta-nll-axes yaw`), whose default is both axes. The default path and a default checkpoint
  stay unchanged. With `yaw`, the β weight stop-gradient(var^β) applies to the yaw element only; pitch keeps today's
  NLL.
- **Runs:** 3 epochs, MPS, niced, after edge-input-2 frees the Mac:

  | Run | Fold (held out) | Seed |
  |---|---|---|
  | **Y1** | 051828 | 0 |
  | **Y2** | 205528 | 0 |
  | **Y3** (Gate 1) | 171533, the dev fold | 0 |

- **Judge: all of these must hold.**
  1. **Yaw learned on both folds:** raw-μ yaw agreement on moving rows ≥ **0.85**, both held out and in-sample
     (171533), for Y1 and Y2.
  2. **Gate 1 yaw (Y3, `run_fit`'s own Gate 1 on 171533):** direction agreement ≥ **0.99** and yaw abstention
     ≤ **1 %**.
  3. **Gate 1 pitch equal to plain (Y3):** moving median error within **0.02°** of plain's **0.508°**, read one-sided
     as ≤ 0.528° (a lower error is not a failure); and extrapolated 1σ coverage ≥ **0.70**.
- **Reading:**
  - **Pass:** yaw-only β-NLL is the default-on candidate, to fit-review.
  - **Fail:** the lead decides for β-NLL on both axes, with the pitch cost on record.
- **Reported beside:** pitch agreement, and Gate 1's calibrated-band coverage and edges.

