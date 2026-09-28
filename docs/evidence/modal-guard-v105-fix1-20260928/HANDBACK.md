# v1.0.5 F1 correction: retain non-app overhead

Replacement release for review:
`4a4d57d5ec2b97566b5bc59f212c8f4b9357198fe0eb7270874902079bdd8af6`.
Supersedes rejected candidate `3b962fc` / release `a822de3d`; its packet stays
frozen. No LAND, installation, live journal mutation or paid action yet.

Read fit-review's full `review-modal-guard-v105-3b962fc8.md` and original runnable
probe. F1 is valid: the app-only billing coverage omitted each covered attempt's
entire bound, including non-app storage/setup overhead. Neither the app rows nor
a summary with an unrelated storage total prove that overhead's inclusion.

Covered terminal attempts now retain their full `hold.overhead_usd` separately.
The per-app reconciliation evidence includes `retained_overhead_usd`; totals expose
`covered_terminal_overhead_usd`, included in `retained_terminal_usd`, outstanding
and commitment. Missing/invalid overhead provenance does not reconcile: it retains
the whole original bound. Uncovered/active/uncertain/external allowances remain
unchanged and are not charged a second copy of their embedded overhead. There is
no automatic storage-overhead release path in this version. Separately bound
resource settlement would require a new contract; no manual credit was added.

The exact reviewer scratch case now refuses: covered app actual $1, bound $1.04
including overhead $0.04, summary $197.75 and a correctly installed scratch WARN
authorization cannot reserve $2.25. Commitment would be **$200.04**. The $197.71
control admits exactly $200. The unchanged reviewer probe now exits at the expected
workspace-cap refusal (`reviewer-probe.log`); its exact original bytes are copied
as `reviewer-probe.py`. New regression controls cover zero overhead, external holds
retained separately, missing provenance and malformed/negative overhead.

## Corrected real snapshot replay

No fresh provider query or live ledger write. `replay.py` reads only the prior
frozen packet's `ledger-state.json` and `billing-v105-readonly.json` and reuses the
same 24 matched app coverage proofs. The corrected calculation is:

| Component | USD |
|---|---:|
| Metered floor | 69.09386987 |
| Uncovered terminal allowances | 11.627080 |
| Covered attempts' retained overhead | 1.17 |
| Total retained terminal allowances | 12.797080 |
| Commitment | **81.89094987** |
| Headroom at authorized $200 | **118.10905013** |

The $1.17 is a conservative retained liability, not a measured unpaid invoice.
The initial $80.72094987 projection omitted it and is superseded by `replay.json`.
Run `uv run python -m docs.evidence.modal-guard-v105-fix1-20260928.replay` from
the repository root. The old frozen replay intentionally keeps its old expectation.

## Validation and delivery

Windows **137 passed, 5 platform skips**; native Mac SDK1.5.5 **142 passed**.
Ruff passes. The overhead-omission mutant fails the exact cap-edge regression;
its scratch release is rehashed so a release mismatch cannot create a false kill.
Source/test LF bytes and archive hash are pinned by `validation.json`.
Mac tested source:
`/Users/james/dev/range-bc-data/handoff/modal/shared-library-v105-fix1/`.
Archive SHA256 `784a80056481c7806e32b81f899bf64831ae06c4994a556db72819a5e842a71c`.

Only reconciliation overhead accounting, its tests and README changed. The $200
maximum, $150 WARN new-reservation gate, release/month-bound lead policy, clocks,
teardown, pacing, campaign caps and stages retain prior reviewed/tested behavior.
The v105 installation procedure in the prior HANDBACK remains applicable with
**this replacement release hash and its future reviewer JSON**, never the rejected
FINDINGS receipt. Lead ACCEPT is still required before install/configure-policy.
Default/live ledger cap remains unchanged until that explicit policy operation.

Next consumer is IDM's separately authorized $1 local-disk timing probe, first in
AppCreate order. The three 8x8 yaw relaunches remain cancelled; the newly authorized
dropout0.5 4x4 campaign is a separate owner packet. This fix authorizes no run.
