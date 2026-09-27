# Joint review index: lead clarification

VUH-1346, 2026-09-27. This index supplements the frozen
[combined review packet](budget-bridge-joint/HANDBACK.md). It resolves the
2,639-second documentation question in REVIEW-SCOPE.md without changing any
candidate, frozen hand-back, review scope, manifest, or historical evidence bytes.

Lead decision: Swarm message `05887c95-cd2f-4a0e-a3a5-b14c4cb54fcc`, thread
`r3-modal-fanout-review`, received from herdr-lead generation 2.

- **2,639 seconds is historical diagnostic arithmetic only. It is not a constraint.**
  It came from the superseded interpretation that held all 13 task maxima together.
- Writer eligibility uses the full measured forecast at 1.25 padding.
- Launch admission uses settled spend + current launch holds + a 300-second
  verification reserve, under the unchanged time and dollar caps. The frozen code
  already implements this rule; no implementation or test change is needed.
- The steering STOP condition is now: **if the Writer or any admission gate STOPs
  tonight, round 3 waits for James; no further bridging.** This applies to every
  gate, not only prefix or extraction.

fit-review should use this clarification when reading the old 2,639-second
wording and the previously unresolved question in the frozen hand-backs. The
request remains one joint pre-run review of the same exact candidate bytes.

Original joint manifest SHA256:
`10fc4e4806fb26ed7fadd1063c70d8065496d53774a5de9a85abd3188e83b4aa`.
All 79 manifest members were rehashed successfully before writing this index.
No launch, commit, production edit, or approval-ledger write is authorized or
performed by this clarification.
