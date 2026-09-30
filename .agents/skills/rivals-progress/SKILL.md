---
name: rivals-progress
description: Keep Rivals Agent's Linear records aligned with delivered evidence. Use when publishing a material result, accepting or superseding work, changing a blocker or next step, handing off a lane, or deciding what James still needs to record or calibrate.
---

# Rivals progress

Linear is the current result record; the learning plan defines the gates, the
recording log inventories takes, and retained evidence proves what happened.
This skill joins those records at delivery. It adds no new tracker or review gate.
Use `linear-orient` for discovery and `linear-issues` for authorized writes.
An orientation or status question alone stays read-only; an existing delivery
mandate covers reconciliation within that work's scope.

## Establish what changed

Read the affected issue's current scope, acceptance, relations and latest decision
or result, then the specific recording, sitting or run receipt behind the claim.
Refresh changes since the last read; do not replay the whole project history.
For a question about completed work, follow the acceptance receipt even when an
older plan or current issue checkbox says otherwise. Do not open sealed content.

Keep the claim attached to its actual project, component and conditions. A
learned request head's kill with scripted aim is not an end-to-end policy kill;
an offline metric is not a live result. Shared team membership does not establish
that another project's costs or defects belong to Rivals. Resolve contradictory
claims from evidence and the decision owner; do not silently choose the newest
summary or erase a later human edit.

Before requesting a recording, calibration or answer from James, check the
recording log, relevant sitting record, latest issue result and recorded replies.
Ask only for the missing component and say what it enables. A received take can
still await admission; identify that agent-owned work instead of requesting the
take again. Use existing reviewed receipts rather than reopening raw evidence.

## Deliver the result and its current record together

The result owner publishes a meaningful result once, labelled as produced,
landed, provisional, accepted or demonstrated as the evidence warrants. In that
same delivery, reconcile the issue's current text so a new reader can identify:

- The bounded result in a line, with the observation date where needed, and a link to its one record
  (`SITTING.md` or the evidence README). The detail stays there, never in Linear (`AGENTS.md`, "Documentation:
  one home per fact").
- What remains unverified or unfinished against the existing acceptance.
- The next action, its accountable owner and the gate or consumer it enables.

Edit inaccurate current text instead of accumulating correction comments. Keep
historical results and media intact. A successful run does not automatically pass
its gate, and code landing does not establish measured behavior. A failed run can
complete an experiment whose accepted deliverable is a verdict.

The lead owns acceptance, transitions and cross-lane effects unless explicitly
delegated. Route just the affected dependency, milestone or scope decision there.
When a prerequisite is satisfied or superseded, reconcile its remaining scope
and affected relations; when a real prerequisite appears, link its actual
consumer. Do not block an offline fit on a prerequisite needed only for live play.
Relation omission may not remove an edge: use a supported removal operation.

If accepted direction changes the project goal, active milestone or critical
path, the lead updates the affected project entry points and mutable canonical
instructions in the same delivery. A materially outdated latest project update
needs a concise replacement update; preserve its historical predecessor. Do not
post a project update for every issue or routine retry. Keep caps, counts and
volatile status in their canonical records, not copied into skill summaries.

## Runs ledger and visuals

When a run finishes, paid or free, add its row to `docs/runs-ledger.md`: cost, one-line result, whether its
stated keep criterion was met, and its best visual. The training lab board reads that table, and project updates
draw from it, so the board needs no separate upkeep. Load `result-visuals` to make the visual. Rivals sources:
- **Live episodes:** the retained frames and `frames.jsonl` under `data/calibration/<sitting>/`.
- **Sittings:** James's OBS MKV named in `SITTING.md`.
- **Training runs:** eval reports and curves.
- **World model:** `rl/world_model/out/*/real_vs_imagined.gif`.

Decode recordings on the CPU only while the game and OBS are closed (`docs/compute.md`). Expert-creator footage
may appear on the private board only, never on Linear or the blog.

## Read back and hand off

Read each changed Linear object back. Check the intended text, state and actual
relations, plus preservation of unchanged labels, acceptance and media. Report
the resulting links and any unresolved discrepancy. This verifies the write; it
does not require rerunning accepted experiments or tests.

A result handoff includes its current Linear link and remaining action. If a
write fails or acceptance is disputed, retain the concrete correction and owner
in the existing handoff, and distinguish "result produced" from "record updated".
The lead carries that discrepancy through resolution; a comment, attempted save
or task marked done is not proof the current record changed. Refresh only the
affected records before the next dependent dispatch or progress report.
