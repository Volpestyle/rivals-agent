# Round 3 physical-idle sidecar v1

Producer: r3-sidecar. Consumer: r3-impl. Independent reviewer: binds-review.
Output directory: `data/human/round3-idle-sidecars-20260926/`.
Producer/reader module: `policy/range_bc/idle_sidecar.py` (stdlib only).
This contract is published before extraction. Changes require notice to the lead.

## Layout

- `manifest.json`: one manifest for exactly the five preregistered train sessions.
- `<session_id>.idle.jsonl`: UTF-8, LF, header followed by exactly one row for every frozen step-table row, including rejected/masked rows.
- Additional diagnostic/test receipts may accompany these files; they are not training inputs.

## JSONL header

`format`: `rivals-range-idle-sidecar-v1`; `role`: `train`; `session_id`: string;
`table_sha256`: lowercase SHA256 of the original table bytes; `step_ns`: integer;
`k`: integer 30; `idle_weight`: number 0.1;
`raw_sha256`: object mapping `inputs.jsonl`, `frames.csv`, `metadata.json` to lowercase SHA256;
`producer_sha256`: object mapping repository-relative producer/dependency source paths to lowercase SHA256.

## JSONL rows

| Field | JSON type / logical dtype | Meaning |
|---|---|---|
| `i` | integer / int64 | Zero-based table row index, exactly equal to the frozen row's `i`. |
| `anchor_ns` | integer / int64 | Exactly equal to that row's `anchor_ns`. Never round through float. |
| `null` | boolean or null / tri-state | `true`: physically idle proven over anchor state and `(anchor, anchor+step_ns]`; `false`: physical activity proven; `null`: incomplete/invalid/ambiguous evidence. Unknown has full weight. |
| `idle_run_length` | integer / int64 | Length of the maximal contiguous true-null run within an eligible accepted normal-regime run, before windowing. Zero outside such a run. Each member repeats the same length. |
| `weight` | number / float64 | Exactly 0.1 if `null=true` and `idle_run_length>=30`, otherwise 1.0. |

Extra diagnostic fields may be added without changing these meanings; consumers ignore them.
Rows key by `(session_id, i, anchor_ns)`, never frame ordinal alone. A consumer must preserve all rows;
existing validity, known-channel and burn-in masks remain its responsibility. Raw classification can
be true on an ineligible row, but its run length is zero and its weight remains one.

## Manifest

Top-level fields:

- `format`: `rivals-range-idle-manifest-v1`.
- `role`: `train`; `k`: 30; `idle_weight`: 0.1.
- `base_commit`: full `9d61d593ac7adf2aac2abd63e5fe0d764509344f`.
- `registry_sha256`, `denylist_sha256`: hashes of registry and denylist used before opening any logger.
- `producer_sha256`: same source-hash object as headers.
- `sessions`: object keyed by each of the five authorized full session IDs. Each entry has:
  - `sidecar`: basename `<session_id>.idle.jsonl`;
  - `sidecar_sha256`, `table_sha256`, `raw_sha256`;
  - `rows`: integer count; `step_ns`: integer;
  - `statistics`: diagnostic object (null counts, eligible maximal-run lengths, weighted row share,
    total effective row weight, and per-head unweighted/effective known masses before windowing).
- `scored_mass_audit`: string identifying r3-impl as owner; producer statistics do not substitute
  for the exact `Batches.windows` audit with burn-in and overlapping occurrences.

Diagnostic fields beyond this minimum may be added. All SHA256 values bind exact bytes, including line endings.
The lead freezes the manifest's externally computed SHA256 after independent review. The producer's output alone
is not acceptance and does not authorize training. Any correction creates a new versioned output directory.

## Reader API and validation

```python
from policy.range_bc.idle_sidecar import load_weights

weights = load_weights(
    table_path, sidecar_path,
    manifest_path=manifest_path,
    manifest_sha256=reviewed_manifest_sha256,
    registry_path=registry_path,
    denylist_path=denylist_path,
)
```

Returns `array.array('d')`, one float64 weight per table row. Raises `ValueError` (or subclass) on refusal.
Before returning any weights, checks the externally pinned manifest bytes, registry/denylist pins,
exact five-session train allowlist, selected session's registered train role and absence from the denylist,
the frozen table hash, selected sidecar hash, header/manifest source provenance equality, and every row key,
tri-state/run-length/weight relationship and total row count. No permissive missing-sidecar fallback.
Raw logs need not exist on the consumer machine: their hashes are authenticated by the reviewed manifest,
not re-read by the consumer. Producer source hashes are provenance, not a requirement that a later consumer's
checkout still contain those exact dependency bytes.

No dev, validation, test, gate2 or reader logger is an input. No media or image cache is read by this producer.
Payload files are streamed; only compact derived state/weights and bounded metadata are kept in RAM.
