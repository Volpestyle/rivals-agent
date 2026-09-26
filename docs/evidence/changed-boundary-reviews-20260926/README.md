# Changed-boundary reviews, 2026-09-26

Verbatim independent reviews of changes that decide what enters training or evaluation, with the hand-back each reviewed.
Round 2's first review is named `review-fit-countermeasures-2.md` like round 1's delta re-review in
`changed-boundary-reviews-20260925/`; the two are different files, told apart by folder and hash.

| Review | Hand-back | Change | Verdict | Landed |
|---|---|---|---|---|
| `review-fit-countermeasures-2.md` (fit-review, Codex gpt-6-astra, b6cd026e…) and the delta re-review `review-fit-countermeasures-2b.md` (40d700ce…) | `fit-countermeasures-2-code.md` (hud-review, 1117a6c9…) and the F1 fix `fit-countermeasures-2-code-2.md` (bcd1e395…) | `policy/range_bc/train.py`: countermeasures round 2, both default off. D, known-idle corruption of the previous-action history (`--idle-corruption`, `--idle-run`); E, sequential self-conditioning, a K-step closed-loop rollout of the model's own executed decisions (`--self-roll`, `--self-roll-steps`, `--self-roll-ramp`); `tests/test_range_bc_torch.py` | land with fixes, then land: F1 the rollout start sampler reached `T-K`, one step short of K fed-back inputs (fixed by `self_roll_starts`, start in [burn-in or 1, T-1-K], refused when empty; re-reviewed); N1 the supplied E kill check was weaker than described (a stronger independent mutation fails); N2 B seed 0's saturation is a supported mechanism, not a proved cause | this commit |
