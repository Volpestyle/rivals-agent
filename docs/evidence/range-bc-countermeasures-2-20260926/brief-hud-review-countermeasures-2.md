# Brief: countermeasures round 2, aimed at the known-idle absorbing state (hud-review, VUH-1346)

Owner: hud-review. Reviewer: fit-review (Codex) for the code, before any run. Consumer: the real fit's arms (the corpus
is ready at 180.57 train min, b8f48ed). Written by the lead, 2026-09-26 06:28 CDT (PC clock).

## Lead's decision on round 1 (fit-countermeasures.md ee5f43b5): NEITHER WORKS, and the next test is reordered

Your inference is accepted as the rationale: one-step self-conditioning feeds a lagged copy of the true history, and
prev dropout 0.5 feeds "unknown"; neither trains the absorbing state the diagnosis found (a KNOWN all-idle history while
the human acts). So round 2 tests two arms that target it directly; dropout 0.5 is set aside (reason recorded).

## Result

A pre-registered round 2 on the SAME data, dev and recipe as round 1 (80.5 train min; comparable to A and C), judged by
the same S1-S4 self-fed checks and the same K skill-retention rule, with two new arms, each changing one thing:
- **D, known-idle corruption:** during training, at a declared rate, the previous-action input is replaced by a KNOWN
  all-idle vector (known = 1) for a run of steps, including steps where the human acts, so starting an action from
  idle must come from the frames. Declare the rate and run-length distribution before any run, with the reasoning.
- **E, sequential self-conditioning:** the model's own decoded actions are rolled forward across a window (no-grad,
  executor.decode_step semantics as already reviewed) and fed as the history for the trained pass, at a declared rate
  and window length.
Both default off; default path byte-identical (the same two proofs as round 1).

## Steps

1. Code (policy/range_bc), tests, the two reproduction proofs; hand back fit-countermeasures-2-code.md; DECISION. The
   lead has fit-review review it; fix findings.
2. Pre-register fit-countermeasures-2-prereg.md (arms D and E, three seeds each, one invocation per arm group as round
   1, the thresholds unchanged, what each outcome means for the real fit; include what to do if one arm passes S but
   fails K). Lead's OK before launch.
3. Run on the Mac from a git archive of the landed commit, collect, judge, hand back fit-countermeasures-2.md.

## Also, bounded

Diagnose B seed 0 (dev flat at 2.39 for 13 epochs) from its existing log and checkpoint only: a real optimisation
failure (dead units, gradient collapse, the warmup) or an unlucky seed? One paragraph in the code hand-back; no rerun.

## Rules

As before: edit only policy/range_bc and its tests; no commits, no Linear, no game input; own UV env; PC processes
under ~3 GB; no PC background poll (the lead wakes you). Your context is large: if it is near its limit, write a state
note first (handoff/hud-review-state.md) so a fresh owner could continue.
