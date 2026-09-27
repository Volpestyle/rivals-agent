# Match -5 accepted after the ping-wheel correction

The lead's pre-authorized acceptance is recorded in
`receipt/match-admission-052001.accepted-a1.json`, SHA256
`94701525132536f5794b4fefd9e06e6bdecdccb1f70c8bef0589a3b6af02c216`.
It supersedes the historical accepted receipt, which remains unchanged.
The receipt pins the pending entry, the original acceptance, the ping-wheel
audit, fit-review's LAND of `d4ebdb1`, and frame-review's final agreement
`df3e8409b85bf4fd79f943099ea116e9e590402decae40d0cdf08c246097aead`.

Only old segment 030 was replaced. Independent review agrees on all 52
segments: seven accepted, totaling 342.399986311 seconds. The unbound VK52
finding remains recorded; inspected frames show no menu, and the lead agreed
that it needs no cut.

Corrected assembly retry2 completed on 2026-09-27 at 20:33:39 UTC with exit 0
and no guard failure. Peak observed process working set was 189,366,272 bytes.
The two earlier game-interrupted attempts remain recorded as failures.
No decoder, capture or game input ran during receipt production.

The owner verified all 47 unchanged segments (12,303 step rows): every field
matches after normalizing global row and run identifiers, with run partitions
preserved. Raw imported metadata, events, packets and decoded PTS match the
historical assembly exactly. No accepted interval overlaps the held button-3
cut or its release settle. The table has 15,852 rows, including 10,267 eligible
rows. The receipt producer verified the complete assembly freeze; the IDM
consumer's receipt loader passed using denylist `09e8b9d3...`.

| Artifact | SHA256 |
|---|---|
| Pending-a1 receipt | `54af72ad31cfcaa0d8c53870cbf3cd04bbc4c9e536febb8612a84f35c8adc63d` |
| Corrected steps | `2c25a3fc96fb7e5a3ec41b173e958b79fd14e76293b09ad9d4c842f2de11dcf8` |
| Corrected imported demo | `f0fa88940e7190bd5ca74b083e2e790d814bdf20e705370a9eab3ef5c0f95d79` |
| Assembly freeze | `86f7c93e9be9c167ff17a94dbe86529c22cb9f182f447bcf936bb2c2983e3651` |

Run records and the semantic comparison are under
`data/admission-codex/runs/20260927T052001-827Z-150600-5/ping-a1/retry2/`.
Historical assembly metadata is preserved in `.v1` files; the preservation
manifest pins the old imported demo and step table as well.

The Mac relocation in `be254c2` verified the original video and logger files,
which remain reusable. Its label tables are historical: consumers must use
the corrected step/demo hashes above and this accepted-a1 receipt. Corrected
Mac label delivery is separate from this admission; no recording metadata
rewrite, re-registration or duplicate original-video transfer is needed.
