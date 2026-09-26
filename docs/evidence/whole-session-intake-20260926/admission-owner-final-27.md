# admission-owner final 27: B1 and F2 fixed (review-intake-0926.md `af85359c`); the code delta for re-review

## B1: excluded registry lists are validated at the shared boundary

**`agent/human_demos.read_splits`**, which `human_intake.check_registry` calls after the denylist, now ends with
`_check_excluded`.
- **`EXCLUDED_LISTS = ("calibration_sessions", "evaluation_sessions")`.** For every row of either list:
  - its session id, resolved media path and (when present) `expected_media_sha256` must be disjoint from every split row
    and from every other excluded row;
  - it may carry no `split` and no `sealed`;
  - an evaluation row's `kind` may not name a split (`train`, `val`, `test`, `gate2`).
- **Consequences:**
  - a calibration or evaluation recording can never also be a split placement;
  - the reader never returns one. `read_splits` returns split rows only, as before.
- **Unchanged:** the rules for split rows. The live registry (`26d55f3d…`: 16 split rows, 3 calibration, 8 evaluation)
  passes.
- **The reviewer's cross-category case** (a calibration row copied into `sessions` as train) is now refused: "…
  shares its session id with a split row or another excluded row".
- **Tests** (`tests/test_human_demos.py`):
  - `test_calibration_and_evaluation_rows_never_resolve_to_a_split`: 9 cases, covering an id, path or hash shared with a
    split row, a row carrying a split, and a kind naming a split, for each list;
  - `test_excluded_lists_are_disjoint_from_each_other_and_do_not_add_placements`: a clean registry returns only the
    split row; calibration against evaluation clashes by id, path and hash refuse.

## F2: the relocated load shares the sealed checks

**`agent/human_intake.load_dataset_relocated`:**
- **Header check:** it refuses on the header's `sealed` or on a header split in `hd.SEALED_SPLITS` (not `== "test"`).
- **Placement check:** after resolving the placement, it refuses on the placement's own split in `SEALED_SPLITS`, unless
  `unseal=True`.
- **Sealed flag:** it requires the header's `sealed` flag to equal `placement.split in SEALED_SPLITS`.
- **All of this happens before the body is read.**
- **The reviewer's `relocation_repro.py`** now ends in `SealedError: gate2 artifact is sealed`, not
  `artifact checksum mismatch`.
- **Test** (`tests/test_human_intake.py`): `test_relocated_load_refuses_a_gate2_placement_before_the_body_even_if_the_header_claims_unsealed`.
  - The reviewer's case (header `split: gate2`, `sealed: False`) is refused by the header check.
  - A header that also claims `split: train` is refused by the placement check.
  - `unseal=True` with the lying flag refuses with `sealed header mismatch`.
  - The payload line reads "MUST NOT BE READ" and is never parsed.

## N1

- **Tally:** `tally.json` is regenerated from the final registry at landing; I'll do it last, after the 23:57 and late-take
  rows settle.
- **`assemble_session.py`:** changed only in the late take's own `MOTOR_STATEMENTS` entry, after the review started. It
  adds the `7ad63e5` quote and the calibration basis. Its LF is `a11fd5d1…`, the pin your review recorded. The late
  take's evidence gets its own session review.

## Tests

- intake, importer, gate2, timed, edges, range_bc, idm_targets and execution: **332 passed, 5 skipped**;
- no corpus test run (`--corpus` not given).

## The delta (LF sha256; the CRLF files are CRLF in the tree)

| File | Before (review) | Now |
|---|---|---|
| `agent/human_demos.py` (CRLF) | `8c71f6ae…` | `614042e5cb8eb45164a4b7d3b49249180048dd9c530ae14c540484fb8e72dd38` |
| `agent/human_intake.py` (CRLF) | `e753e6ec…` | `8ecf85e48181568f9af9fd81de0227b0c0e54cb3ad613a6a870d19dbdecf53e0` |
| `tests/test_human_demos.py` (CRLF) | `01e9fdcd…` | `d952b428ab1b9574fe8d6db8ab5687ff829ff635f2beea8937ce471695d85c4b` |
| `tests/test_human_intake.py` | `98133b82…` | `fc81c28e77684c0a15987f415f5821730fb240270d8124c126340619baaa1c96` |
| `data/human/sessions/assemble_session.py` | `a11fd5d1…` (your pin) | unchanged since your pin |
| `data/human/session-splits.corpus.json` | `26d55f3d…` | unchanged |

- **Unchanged:** `intake_session.py` (`80830341…`), `test_gate2_split.py` and `test_human_intake_timed.py`.
- **Not re-snapshotted yet:** the 23:57 assembly and the late take's remaining steps run from
  `code-snapshot-3936f94-4c9638d1`, which predates B1 and F2.
  - Neither fix changes a placement or a verdict for any registered session: the live registry passes B1, and F2 only
    touches relocated loads.
  - The landed code will be these bytes. A later re-assembly would run from a new snapshot.

No commits, no Linear, nothing on the Mac.
