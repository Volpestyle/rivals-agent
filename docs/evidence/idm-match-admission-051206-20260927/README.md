# Match -4 assembly and pending admission

Session `20260927T051206-888Z-150600-4`, VUH-1353 / VUH-1359.
Produced by admission-codex. Independent frame-review agrees with the owner on
all 49 segments: eight accepts (303.633321196 seconds), 41 rejects, no blocking
findings. All 141 producer review-frame hashes match the independent decode.

The producer receipt is **pending lead acceptance**:
`receipt/match-admission-051206.pending.json`, SHA256
`a1d168ea015c7b4eff204af60be5aa4ab4d18d69c333e637ba55d99477208acf`.
Acceptance belongs in a separate receipt; this record stays frozen.

## Result and pins

All session paths below are under
`data/human/sessions/20260927T051206-888Z-150600-4/`.

| Artifact | SHA256 |
|---|---|
| `artifact-hashes.json` | `c3dad2c1348a6590463aaf906c12582227da8acc15b375ada1691f5742216716` |
| `independent-review.verdicts.json` | `84b11c1f3632155420019c3e1d7f92b6f209995bca2d15a34e5bca325b35717d` |
| `owner-verdicts.json` | `ea41484e73bf9c2ba8bc061679e0821995d5e3e47757deb280f4185b430b33ef` |
| `20260927T051206-888Z-150600-4.steps.jsonl` | `d02b32a7665f68ec4f36e3e33b9075a625897018e3f31386c59343ce8ed2fc48` |
| `imported-demo.jsonl` | `058f84d4a178f1e66b6cfd14f3f7c94104f4cc8cd9a8ce5a2cb0dc5d5a842653` |

Assembly verified 50,229 decoded frames against recorder PTS with the 21 ms muxer
offset; maximum residual was 1/3000 second. The step table has 12,194 rows,
9,103 accepted and gap-free eligible rows, and 5.060555 counted minutes. Large
generated tables and images remain local, hash-pinned by the committed freeze.

The guarded assembly exited 0, with no surviving owned descendants, and maximum
observed per-process working set 169,644,032 bytes. `assemble.run.json` records
the command and resource observations. The pending-receipt writer then passed
its freeze, identity, split, motor and demo-pin checks; `receipt.run.json` records
that separate exit-0 run. Neither run changes registration or media metadata.

Owner review used supplied thumbnails; independent review decoded 1,919 native
frames and re-hashed the media. Conservative cuts include seg-041 (dead) and
seg-029 (no_range_hud), where some own play was discarded. Seg-030's grab close-up
at 297.7–297.9 seconds remained own camera. No disagreements required changes.
Capture/display/input latency remains uncalibrated. This is exploratory live
match input for `idm_train`, not range evaluation or held-out data.

Code review receipts are in [admission-reviews-20260927](../admission-reviews-20260927/README.md).
