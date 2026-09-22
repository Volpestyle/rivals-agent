# VUH-1346: originating step on failed/refused sends

2026-09-22. Frozen for the existing range-review after root's native audit.
Not independently accepted or deployed. Only `agent/loop.py`,
`tests/test_range_skill_loop.py` and this note changed. No native evidence,
deployed worktree, model/human/media files, input/capture, installs, commits or
Linear records were accessed or changed by this work.

## Reproduction and correction

Before editing, actual Loop/Controller/FakePad/RunLog with an injected guarded
send error produced two decisions but only decision 1's `decision_trace`. No
accepting step was logged. A later executor-release row identified pulse owner 2
and the failed send, demonstrating that cancellation had replaced the missing
step trace. This reproduces the logging mechanism root observed natively; it is
synthetic software evidence, not a replay or relabeling of that native run.

The range-skill tick now freezes the original controller trace, proposed pad,
decision State and decision trace in memory before the send. It performs no
writer call there. A send exception follows the existing release path first,
then writes its originating step, preserving the original exception if that
diagnostic writer also fails. Deadline refusal similarly releases first, then
the normal row retains the original step alongside the not-sent result.

Decision deduplication advances only after the frame writer returns. Repeated
sends for an already logged decision retain its `d` and pulse owner without
duplicating State/decision_trace. On an already propagating range-skill error,
a subsequent log-close exception is recorded in `errors` rather than replacing
that original error. Close errors without an earlier error still propagate.
Existing RangeLost handling still returns the existing range_lost stop.

No send/release sequence, calibration, threshold, deadline, cadence, State schema
or observation/resource timestamp changed. Snapshot construction is additional
in-memory bookkeeping; the existing send-time guard still judges the actual
time after it. Controller/Live and policy code are untouched.

## Integration interface

| Artifact/field | Meaning |
|---|---|
| `frames.jsonl`, `type=executor_send_failure` | Originating step after release attempts for a send that raised. Contains `d`, exact `observation_t`, `proposed_pad`, original `range_skill_trace`, `send_result`, and first-use State/decision_trace. `reason=send_failed`. No top-level `pad` field, because delivery is unknown. |
| Normal step row, `send_result.status=not_sent` | Original controller step/proposed pad retained. Top-level `pad` is the existing neutral request. Successful physical release must be assessed separately. |
| `range_skill_trace` | Detached original `event=step`, including controller acceptance, pulse owner, original execution/observation/resource clocks. Acceptance does not prove a successful send. |
| `proposed_pad` | Snapshot offered to the sender, distinct from delivery or release. Also present on successful range-skill step rows. |
| `executor_release` | Existing independent cancellation trace and actual release attempt/result timestamps. Still recorded before the failure/refusal step row. |
| `meta.json.executor_events` | Existing release events plus mirrors of refused send origins: `executor_send_failure` or `executor_send_refusal` (`reason=send_deadline`). Mirrors are retained before frame-log writing, so successful summary writing can preserve evidence if that writer fails. |

The mirrored event is the **same send**, not another attempt or acceptance.
Consumers combining frames and meta should join by original `observation_t`,
decision `d`, and the send result's `attempted_t` or `checked_t` plus status.
Filter `type=executor_release` when counting release events. A normal not-sent
frame row corresponds to the metadata `executor_send_refusal` mirror. Image
references added by RunLog after the mirror is copied may exist only in the
frame row. Neither a failed send nor a returned release establishes physical
device delivery or game-visible action.

If both frame and summary writing are unavailable, durable evidence cannot be
promised; the origin remains in the Loop's in-memory `executor_events`, and log
errors remain in `errors`. A failed release stays `release_returned=false` with
both actual attempts retained. No log recovery retries send input or invents a
new decision.

## Verification

```powershell
uv run --no-sync python -m pytest tests/test_range_skill_loop.py tests/test_loop.py tests/test_range_cast_probe.py -q -rs
```

186 passed, 9 skipped in 14.40 seconds: eight Torch-dependent existing cases and
one opt-in corpus case were skipped. No corpus option or install was used.

Twelve new cases use actual Loop/Controller/FakePad/RunLog. They verify:

- Original missing acceptance/decision now retained for both OSError and RangeLost;
  original State/resources and proposed pad survive mutation by the failing sender.
- Pre-send deadline refusal retains its accepting step, exact clocks and not-sent
  result while no LT reaches the fake pad.
- Release precedes diagnostic writes, including two failed release attempts;
  frame-log and close-log faults cannot replace the original send error.
- Metadata mirror survives frame-log failure for both failed and not-sent sends.
- A failed repeated send references one previously logged decision; successful
  controls retain one trace per decision and no added failure events.
- Logging failure after a successful send still releases before close, and an
  otherwise unaccompanied close error still propagates.

Root owns archive/evidence integration and runtime hashes. This is an isolated
logging delta requiring independent review; it does not change the interpretation
or contents of the finalized native artifacts.

Frozen SHA-256 (this note's hash is handed back separately):

| File | SHA-256 |
|---|---|
| agent/loop.py | `94fc09fed1ffd9d86ec3452644931a9c64adba61db54a4f96da43498057437da` |
| tests/test_range_skill_loop.py | `4ca46b2f5393f27565a647345ea79f19b4ef7c4fe30c02786e4bf815acadd514` |
