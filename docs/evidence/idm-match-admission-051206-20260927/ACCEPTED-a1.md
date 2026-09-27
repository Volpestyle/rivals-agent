# Match -4 accepted after the ping-wheel correction

The lead's pre-authorized acceptance is recorded in
`receipt/match-admission-051206.accepted-a1.json`, SHA256
`1aec79937aa7dca19cb6526b5d7c9ffdcb2ba6a53c7c09fb972edf6fe0d5325e`.
It supersedes the unchanged historical accepted receipt and cites the
ping-wheel audit, fit-review's LAND of `d4ebdb1` (report `91b1c8b3...`),
and frame-review's final native verdict
`eb8442d91ab0aee2460dce0979aa97090f7263880ec38981407814ca4df72c41`.

Only old segments 015, 030 and 043 were replaced. Independent review agrees
on all 59 segments: ten accepted, totaling 297.666654770 seconds. It checked
331 native boundary frames and all 159 owner frame hashes. Input replay
across the accepts found only bound buttons and keys. The settle after the
clipped end of segment 015 falls in already rejected segments 016/017.

Corrected assembly finished on 2026-09-27 at 21:13:25 UTC with exit 0 and no
guard failure; peak observed process working set was 168,267,776 bytes.
Pending receipt production also exited 0 without failure. The imported
payload retains exactly the historical metadata, events, packets and decoded
PTS. All 46 unchanged segments (7,082 step rows) match after normalizing
global row and run identifiers, with run partitions preserved. No accepted
interval overlaps a held button-3 cut or its release settle.

The corrected table has 12,189 rows, including 8,923 eligible rows. The
receipt producer verified the assembly freeze, and the IDM consumer's receipt
loader passed against denylist `09e8b9d3...`. Original assembly bytes remain
in versioned files pinned by `assembly-ping-a1-supersedes.json`.

| Artifact | SHA256 |
|---|---|
| Pending-a1 receipt | `d1753e8fb9dab6fc7921286ffd12e02c6c162db3645d3905bf3fb57a3d1e9029` |
| Corrected steps | `058c5293dc3152b9a8edc5299192b27d59444b11badf994c2cca25e0344fadaf` |
| Corrected imported demo | `f5f9c4dce9bc1f8ce3526ee29fb06cb216dec94207e0ded4594c1c58a3203409` |
| Assembly freeze | `c1d83d8b48f4aabe75f5101577ab193310d75318470fe12bb6eb10e374dcb751` |

Run records and semantic verification are under
`data/admission-codex/runs/20260927T051206-888Z-150600-4/ping-a1/`.
This acceptance covers the corrected PC artifacts; it does not claim a
Mac transfer. Consumers must pin accepted-a1 and these corrected tables.
