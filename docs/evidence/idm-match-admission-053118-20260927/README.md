# Match -6 ping-wheel revision: pending independent delta review

Session `20260927T053118-260Z-150600-6`, VUH-1353 / VUH-1359.
No match admission receipt has been accepted for this session.

The original independent review rejected owner-accepted segments 002 and 031:
physical mouse button 3 opened a communication wheel within them. Its record
remains `independent-review.v1.verdicts.json`, SHA256
`5d1b56cfbb91f1d95cfe2d68529ea830f546cc892501b04bc272277c9fa2f85c`.
The original owner record, evidence and images remain in `.v1` paths.

The lead authorized held-button-3 cuts plus two seconds after release. Code
`b35afbf` has independent LAND; see
[the code review](../admission-reviews-20260927/review-ping-wheel-b35afbf.md).
The ping-aware snapshot manifest is
`4fe07b4b8ab6a2534b6d9d72499949eca5f76316a72368cb86fd8412a7c53a3c`.

## Revised packet

Paths are under `data/human/sessions/20260927T053118-260Z-150600-6/`.

| Artifact | SHA256 |
|---|---|
| `segments-evidence.json` | `56de079121df399bf58d8aa270fc57aafcdfb4925c571f579abfddfb0c2df3b3` |
| `owner-verdicts.json` | `4acf3b49728e718cd8fd9faa3caf7b0007ca2f554967955a137230be35844dfa` |
| `ping-a1-delta.json` | `a1b83e0bda10e4b43175c71768aba038cfb5c0a3ab48e11261466e76f265c2e6` |

Owner proposes nine accepts totaling 257.649989703 seconds and 48 rejects.
49 segments retain identical bounds, rule and all native review-frame hashes;
their prior owner and independent agreement is reused. The eight changed
segments are 002, 003, 004, 031, 032, 033, 034 and 035. Changed retained gameplay:

- 002: [0.639668539, 32.831333919) seconds.
- 031: [272.914657648, 285.247990489) seconds.
- 035: [287.672990391, 298.506323292) seconds.

Admission-codex inspected every supplied thumbnail for the changed segments
that contain frames, and verified all evidence input/JPEG pins. Thumbnail
inspection does not establish native-frame acceptance. Frame-review owns that
delta verdict and may reuse its prior unchanged evidence. The guarded evidence
run exited 0 with no failure; maximum observed process working set was
338,604,032 bytes. Run record:
`data/admission-codex/runs/20260927T053118-260Z-150600-6/ping-a1/evidence.run.json`.

The recording includes the first match and the next match's controllable setup
phase (old 043/048, now 047/052), as independently confirmed. It remains one
recording family in `idm_train`; no registration or metadata rewrite occurred.
