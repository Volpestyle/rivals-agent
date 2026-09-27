# Expanded IDM preparation, 2026-09-27

Owner: idm-owner / VUH-1353. EXPLORATORY, $0, no fit result.

The lead released the game/OBS sitting hold at 16:01 CDT and authorized the three
missing admitted TRAIN range stores within one decoder slot. Explore-policy
explicitly released the Mac heavy slot; its dual-grid preparation is queued after
all three stores. IDM must notify explore-policy directly when releasing it.

The isolated Mac root is `/Users/james/dev/idm-data/range-stores-a730f75`.
The source archive is `git archive a730f75` of agent, policy, perception, scripts,
pyproject.toml, uv.lock and the registry/denylist metadata. No live checkout edits,
sealed source payloads or original recording transfers occur. Packet tar SHA256:
`aabc8d141b3f030e4af67784f85130b1339344d1474448989612b4cd0c6112f7`.
All transferred members were hash-checked on the Mac against packet-manifest.json.
The new directory has its own locked, offline perception environment (CPython
3.12.13, NumPy 2.5.3). Python uses one CPU thread for NumPy; FFmpeg decoding and
filters are explicitly bounded to two threads each, under nice10. Every store
uses a fresh output directory, pinned inputs and the existing exact-ordinal/PTS
checks; frames.json is written only on successful completion. Payloads are
rehashed before reporting done. A 30-second heartbeat records elapsed time,
Python peak RSS and written motion-frame bytes. No automatic partial retry.

Order: 045729 first (10.26 admitted min), inspect stored/native control samples,
then 035932 (30.15 min) and 203745 (45.98 min), serially. The originals and
reviewed tables/imports already live under the read-only explore directories.
The API is passed the current pinned IDM denylist explicitly; no legacy range
consumer pin or frozen file is edited. Minimum free disk is 60 GiB before each
store; preflight found about 337.57 GB free.

First store started 21:05:47 UTC, wrapper PID73044, job
`idm-range-store-20260926T045729-166Z-79780-1`. At 450 seconds it had written
2,228,341,248 motion bytes; Python peak RSS was 546,734,080 bytes. This is a
launch/progress record, not a completed store or validation result. Completion,
visual control inspection and remaining-store launch are subsequent records.

The -5 corrected a1 tables, targets and two receipts were also copied to a fresh
`/Users/james/dev/idm-match-data/a1-951cd9e/20260927T052001-827Z-150600-5/`.
All five destination SHA256 values equal their Windows-first manifest. No
original was recopied and no historical table was overwritten. Exact transfer
receipt SHA256 is `31c1f75a26d3d7f891e178aa821952381b41f5dc96eb275c4b4983de94d60d2c`.
The first verification attempt found system Python lacks hashlib.file_digest;
only hash verification was retried with streamed hashing. The files were not
recopied or changed. -5 still needs its native store; -4 remains held.
