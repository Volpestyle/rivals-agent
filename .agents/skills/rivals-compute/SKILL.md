---
name: rivals-compute
description: Where and how this repo runs training and other heavy compute (PC vs Mac vs Modal vs AWS), the Mac queue and PC-memory rules, cloud caps and teardown, the explore/confirm tracks, and the job-status convention for the dashboard. Use before launching any fit, feature extraction, bulk decode, benchmark or rented GPU.
---

# rivals-compute

Read `docs/compute.md` (the compute protocol) in full before starting a job. It is the only source for machine roles,
caps, the explore/confirm tracks and review timing; they change often, so this skill doesn't restate them.

The mechanics that rarely change:

- **Mac:** launch with Git Bash `ssh -n -T -o BatchMode=yes mac` (PowerShell 5.1 around ssh hangs), nohup and niced,
  with status and `.exit` files. Judge completion from the files, never the launcher.
- **PC background CPU work:** idle or BelowNormal priority, ≤2 ffmpeg threads, ≤~3 GB per process, streamed.
- Every job writes a status file (`scripts/job_status.py`) so it shows on the job board
  (`https://jamess-macbook-pro.tailb90f24.ts.net:9443/`).

Before writing or debugging Modal code, load the `modal` skill (Modal's own, v1.5.5, refreshed with
`modal skills update` on the Mac; it points at the current docs and `modal changelog`). Modal can restart a container
and redeliver the same call (2026-09-27, ~19:15 UTC: two lanes lost their runs this way within 2 s). A worker must
tolerate re-entry: resume only from a completed, hash-checked stage, and refuse a partial one instead of refitting.

Never train by reading frames or feature caches at random straight off a Modal Volume: stage them onto the
container's local disk first, hash-check, then read locally. On 2026-09-27 Volume-backed random reads ran 3-15x slower
and cost two lanes about $14 of runs that never finished (`docs/steering/spend-ledger-20260927.md`). The exception is a workload
whose Volume-read path has already completed at a measured rate (e.g. the ~20 GiB 4x4 yaw cache). Time a new
workload with a short probe before sizing its full run.

Machine access: `docs/machines.md` and the `mac-remote` / `windows-pc` skills. Live input: the `rivals-live-game` skill.
