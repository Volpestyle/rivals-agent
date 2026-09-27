# Match -4 ping-wheel correction: owner delta, pending independent agreement

The original acceptance is historical and superseded by the lead's ping-wheel
decision. Its receipt remains unchanged. Only old segments 015, 030 and 043
are replaced; all 46 other evidence segments retain exact JSON values,
including bounds, native frame hashes and JPEG references. Every current
image hash and evidence input pin was checked.

The corrected packet has 59 segments. The owner inspected all 40 supplied
thumbnails across ten changed pieces; three additional slivers contain no
native frame and remain rejected by rule. Five replacement gameplay pieces
are proposed accepted, giving ten accepts and 297.666654770 seconds overall.
The thumbnails do not sample the short wheel itself; independent native-frame
review of the new boundaries remains required. The prior wheel sightings
are retained in the input audit and frame-review's historical findings.

Session directory: `data/human/sessions/20260927T051206-888Z-150600-4/`.

| Artifact | SHA256 |
|---|---|
| `segments-evidence.json` | `e3d2a29a0fa440d964630bd7d687770c6636dab12faf2c204aafbf8da9dec766` |
| `owner-verdicts.json` | `80841ca5c5c759faa32249ef60be02ae8116c6773497931bb8fbc2c7f72ce94f` |
| `ping-a1-delta.json` | `c4375a752879b00944c6bf7eea166a5c8a8e9e66e9e7af8534d0d99214462b1a` |

Old evidence, images and owner verdicts remain under `.v1` names. The original
independent record is copied unchanged to `independent-review.v1.verdicts.json`
(`84b11c1f…5717d`). The delta JSON lists every changed boundary and its parent.
Guarded evidence exited 0 without failure, peaking at 388,591,616 bytes.

Splice code `d4ebdb1` has independent LAND: the retained report is
`docs/evidence/admission-reviews-20260927/review-ping-delta-d4ebdb1.md`,
SHA256 `91b1c8b395e484812a46c96df83bb8bfe592e11d74fefb028f9b5ad8d0bb563d`.
The replacement assembly and accepted-a1 receipt are not yet produced.
