# Brief: countermeasures for the copycat collapse, tested before the real fit (hud-review, VUH-1346)

Owner: hud-review (you), from code through the test's result. Reviewer: fit-review (Codex; the lead relaunches it) for
the code change, before any run. Consumer: the real fit's pre-registration. Written by the lead, 2026-09-25 21:08 CDT (PC
clock). Lead decision: your two proposals in `fit-selffed-diag.md` are accepted as the direction.

## Result

A pre-registered test, on the same 80.5-minute train set and dev as `interim94-s012`, of whether the countermeasures
remove the absorbing idle and latched states while keeping executed teacher-forced skill. Its reading decides which
arms and headline metrics the real fit pre-registers.

## Steps

1. **Metrics (code, behind no flag: reporting only).** In `policy/range_bc`, add to every report, beside the
   existing figures: an executed-decode teacher-forced press-F1 (`executor.decode_step` over the teacher-forced
   probabilities, the decisions the pad would send), `held_change_f1` per action, and the self-fed checks your
   diagnosis defined (hold-onset recall, executed presses per action against the human count, share of steps with any
   hold on, camera MAE against zero motion). Existing figures must stay byte-identical (show it on a stored report).
2. **Training option (code, flag default off).** Self-conditioned history (scheduled sampling): during training the
   previous-action input is replaced by the model's own decoded previous action at a rate ramped from 0 to a
   pre-declared p; `prev_dropout` configurable. Default-off output must reproduce the existing checkpoints byte for
   byte (MPS determinism is established). Tests. Confirm no edited file is in the 16-file deployment freeze
   (`data/runtime/galacta-pilot-20260923-preflight/*-deployed.json`).
3. **Hand back the code** (`fit-countermeasures-code.md`: diff summary, LF sha256, tests in your own
   `UV_PROJECT_ENVIRONMENT`, the reproduction proofs) and send DECISION. The lead has it reviewed; fix findings.
4. **Pre-register the test** (`fit-countermeasures-prereg.md`): arms = the existing `model_nohud` candidate (re-read
   from the interim checkpoints on the new metrics, no retraining), `--frames-only`, and `model_nohud` with
   self-conditioned history at the declared p; three seeds; the interim recipe otherwise. Judge on the self-fed checks
   (thresholds as your diagnosis proposed, fixed before any run) and the executed teacher-forced press-F1. Say what
   each outcome means for the real fit. Lead's OK before launch.
5. **Run on the Mac** (niced, Git Bash ssh, status and exit files; no background poll on the PC, the lead wakes you),
   collect, judge, hand back `fit-countermeasures.md`.

## Rules

Edit only `policy/range_bc/`, its tests, and your own new lane note. No commits (the lead lands after review), no
Linear, no game input. Own `UV_PROJECT_ENVIRONMENT`. The PC is short on memory while James plays: keep PC-side
torch runs small or run tests on the Mac. One swarm message per DECISION/DONE/BLOCKED.
