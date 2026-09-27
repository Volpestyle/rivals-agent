# Research finding: semantic edges, decoder state and pad snapshots differ

Read-only investigation, 2026-09-26. No production files changed and no live
objects instantiated. This is a pure mapping result, not a measured input-loss
rate or a demonstrated gameplay bug.

## Reproduced in the current executor

The [probe](executor_trace_probe.py) calls the existing `decode_step` and
`pad_state` functions for Web Cluster only, with zero requested camera motion.
It prints hashes of the production sources used. It opens no recordings.

```powershell
uv run --no-sync python docs/research/executable-imitation/executor_trace_probe.py
```

| Predicted semantic requests | Decoded press flags | Consecutive LT snapshots |
|---|---|---|
| tap, tap, idle | 1, 1, 0 | 1, 1, 0 |
| hold, hold, idle | 1, 0, 0 | 1, 1, 0 |
| tap, idle, tap, idle | 1, 0, 1, 0 | 1, 0, 1, 0 |

A semantic tap has decoded `(held, press, release)=(0,1,1)`. `pad_state`
sets the physical control high when either held or press is true; it takes no
release argument. A tap therefore occupies the whole output step, as documented.
If those snapshots are applied consecutively with sample-and-hold behavior and
no intermediate neutral write, adjacent taps form one continuous high interval.
The decoded press count is two; the snapshot transition count is one.

An intervening release from a scheduler or watchdog can change the physical
trace. The probe does not model that timing, USB delivery, game sampling or
actual casts. No such outcomes can be inferred from this test. The inspected
source search found uses in offline evaluation/tests, not an integrated live
range-BC caller proving how these snapshots are scheduled.

## A tempting fix would lose necessary information

The identical snapshot prefixes above do not imply equivalent decoder states.
After two taps, `prev_held` is zero. After two holds, it is one. Apply identical
next-step tap probabilities to both:

| Prefix | Same next request | Next decoded `(held, press, release)` | Next LT |
|---|---|---|---|
| tap, tap | tap | (0,1,1) | 1 |
| hold, hold | tap | (0,0,1) | 0 |

The second case decodes a hold ending, rather than another tap. Thus retaining
only the pad snapshots would lose state needed to predict the executor's next
output. Conversely, naming semantic flags physically delivered edges is too
strong. The distinction is between:

- requested/decoded semantics and the decoder's internal previous-hold state;
- generated pad snapshots and their actual application/release times;
- visible game response, which remains separately observed or unknown.

The existing semantic history is not intrinsically an invalid input: its hold
and press fields determine the intended snapshot, and its hold field preserves
decoder memory. This finding does **not** justify deleting that history or
blindly substituting a physical held bit. It identifies a reporting and modeling
boundary to preserve explicitly.

## Why this changes the research plan

`train.py::predict_self` and `executed_runs` use decoded semantic outputs and
saturated camera commands. They do not reconstruct a timed sequence of delivered
pad edges. Their metrics can establish decoded behavior; they cannot, on their
own, establish distinct physical button presses or successful casts. These
functions also consume recorded frames, not the frames their actions would cause.

Before attributing a gain to a new memory architecture, evaluate the known
decoder as a stateful transducer. Keep its state explicit and account for
application/release timestamps when those become available. Learn unknown game
response from permitted visual evidence, rather than asking a network to
rediscover a known Boolean mapping. This is an engineering baseline, not itself
a novel architecture.

For a simple sample-and-hold executor with one-bin highs and at least one-bin
lows, N bins can contain at most ceil(N/2) rising edges when initially low.
Consecutive requested taps cannot violate that limit through terminology.
Longer registration/release requirements reduce the feasible rate. These are
discretization bounds, not measured current game limits. A finer scheduler
changes the command alphabet and requires its own delivery evidence.

The [cooldown lemma](command-effect-inference.md) assumed reliably separated
pulses. This finding does not refute it: its common controller sets the physical
command equal to a feasible, separated cast sequence. It shows why semantic
press flags must not be substituted for that physical command sequence.

## Literature update

[RACE, ICLR 2026](https://proceedings.iclr.cc/paper_files/paper/2026/file/fab80bb9d97e9b9ff5c19f91f72838c6-Paper-Conference.pdf)
already addresses part of the larger execution problem: it learns desired robot
states instead of commands, retimes predicted trajectories under physical
limits, and aligns chunks during asynchronous inference. Desired effects plus
feasible execution therefore remain a prior-art baseline, not a new general
claim. Its measured robot-state setting does not automatically supply the
missing cast observations or device semantics in this project.

## Next decisive comparison

On owner-selected admitted development predictions, compare semantic press
counts with reconstructed pad-snapshot edges under an explicitly declared
scheduler. Stratify adjacent taps, tap-to-hold, hold-to-tap and separated taps.
Keep observed cast counts separate. First establish whether any mismatch occurs
often enough to affect the relevant policy; this synthetic counterexample
does not estimate prevalence.

Any proposed production change needs coordination with the fit/executor owner
and independent review before use. Do not add gaps globally: they can delay
valid actions or interrupt intentionally held controls. The research baseline
should preserve the scheduler and compare interpretations first.

This provides a concrete project-specific uncertainty to resolve before a
larger experiment. Doctoral novelty and improved live behavior remain unproved.
