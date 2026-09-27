---
name: rivals-compute
description: Where and how this repo runs training and other heavy compute (PC vs Mac vs Modal vs AWS), the Mac queue and PC-memory rules, cloud caps and teardown, the explore/confirm tracks, and the job-status convention for the dashboard. Use before launching any fit, feature extraction, bulk decode, benchmark or rented GPU.
---

# rivals-compute

Read `docs/compute.md` (the compute protocol) in full before starting a job. The short version:

- **PC:** game, recording, and the live loop only. No training. Background CPU work runs at idle priority, with
  ≤2 ffmpeg threads and ≤~3 GB per process, streamed.
- **Mac:** one heavy job at a time, in the order the lead sets. Launch with Git Bash `ssh -n -T -o BatchMode=yes mac`, nohup
  and niced, with status and `.exit` files. Judge completion from the files, never the launcher.
- **Modal** (profile `rivals`): confirm-track fan-out only, with a reviewed harness, lead-approved receipts, a hard
  cap and proven teardown. Only train and frozen-dev data go up.
- **Explore vs confirm:** explore sweeps are Mac-only and tagged EXPLORATORY. Confirm runs need a pre-registration, a
  judge pinned before results, independent review and stage approvals.
- Every job writes a status file (`scripts/job_status.py`) so it shows on the job board
  (`https://jamess-macbook-pro.tailb90f24.ts.net:9443/`).

Machine access: `docs/machines.md` and the `mac-remote` / `windows-pc` skills. Live input: the `rivals-live-game` skill.
