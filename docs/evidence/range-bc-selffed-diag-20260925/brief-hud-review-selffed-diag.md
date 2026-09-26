# Brief: why are self-fed rollouts degenerate? A bounded, read-only diagnosis (hud-review, VUH-1346)

Owner: hud-review (you). Consumer: the lead, then the real fit's pre-registration. Written by the lead, 2026-09-25 20:59
CDT (PC clock). Bounded: diagnosis only, no training, no new fit, about an hour of work.

## Question

In every model of the plumbing fit and both interim groups, self-fed rollouts on dev give macro press-F1 0 and camera
MAE equal to the zero-motion baseline, while teacher-forced figures are non-trivial. A policy that collapses when fed its
own outputs would do nothing live. Find out, from existing artifacts, what the self-fed rollout actually outputs and
why, before the real fit is pre-registered.

## What to look at (existing only)

- `interim94-s012`'s seed-0 `model_nohud` and `history_only` checkpoints and their CPU reference / probability files on
  the Mac (`/Users/james/dev/range-bc-data/runs/interim94-s012/`), the report's self-fed blocks, and
  `policy/range_bc/` (the self-fed evaluation path, previous-action dropout, the history features).
- Describe, on dev: the press probabilities under self-feeding over time (do they sit just under the threshold, decay
  to zero after the first steps, or never rise?), the camera outputs (near zero from the start, or decaying?), and how
  that differs from teacher-forced on the same rows. Say whether the collapse comes from the fed-back history (e.g. a
  model that mostly copies the previous action, so an all-zero start stays zero), from the decision threshold, or from
  the evaluation code itself (a bug is possible: check it).
- Inference on the Mac CPU or MPS is fine if needed (niced; nothing else runs there now). No training.

## Hand-back

`fit-selffed-diag.md` in this folder: the finding with the numbers and plots or tables that show it, whether it is a
model property or an evaluation defect, and one or two concrete, pre-registerable changes for the real fit (for example
scheduled sampling, history dropout rates, a threshold rule) with what each would test. Limitations. No commits, no
Linear, no game input, no edits in the checkout. One swarm completion_notice to the lead when done.
