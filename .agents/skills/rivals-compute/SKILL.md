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

Machine access: `docs/machines.md` and the `mac-remote` / `windows-pc` skills. Live input: the `rivals-live-game` skill.
