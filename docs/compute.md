# Compute protocol: where training and other heavy jobs run

How this repo uses the PC, the Mac and rented GPUs. Read it before starting any job that trains, extracts features,
decodes video in bulk or rents compute. Machine access details live in `docs/machines.md`; experiment discipline lives
in `docs/steering/charter-20260926.md` and `docs/learning-plan.md`. Written 2026-09-26 from that day's decisions.

## Which machine, for what

| Machine | Use it for | Never |
|---|---|---|
| **PC** (`supedupsilly`, RTX 4080 Super) | The game, OBS recording, the live agent loop, capture and pad code. Light CPU work (hashing, JSON scans, one-file ffprobe) | Training or GPU jobs. James keeps the PC free to play or record, or for supervised live agent runs. While the game runs its GPU is the game's |
| **Mac** (M5 Max, 128 GB, MPS) | Explore sweeps, inference-only audits, cache builds, small fits, the job board. One queue | Two heavy jobs at once. Anything that should be on the PC's live path |
| **Modal** (workspace `volpestyle`, profile `rivals`) | Confirm-track fits that fan out: many GPUs in parallel, billed per second | Launching without a reviewed harness, a lead-approved receipt and a spend cap |
| **AWS** (account 842434829012) | A fallback only. G/VT quota is 8 vCPU on-demand in us-east-2 | Anything, unless Modal is unavailable. The 2026-09-26 benchmark showed a 4-vCPU L40S is CPU-starved |

Measured 2026-09-26 on round 2's A recipe (one epoch; `docs/evidence` and VUH-1346): Mac ~240 s/epoch; Modal
L40S with 8 CPUs 124 s/epoch (~36 min and ~$1.54 per 13-epoch fit); Modal A10 187 s; Modal L4 318 s; AWS L40S with
4 vCPU 292 s. A fit needs ~21 GB of VRAM, so a 48 GB card holds two. The post-training CPU evaluation is CPU-bound,
so give cloud boxes 8 CPUs or more.

## Rules for PC jobs (while James may be playing)

- Idle or BelowNormal priority, at most 2 ffmpeg threads, each process under ~3 GB. Stream files (hash in 1 MiB
  blocks); never read a whole video into memory; never index `np.load(npz)[key]` in a loop.
- At most 2 concurrent decodes across all processes. Check free RAM before each.
- If the game or OBS is running and the job would compete (bulk decode, re-encode), move it to the Mac queue instead.
- James's SPIDEY CLIPS HEVC compression batch yields automatically when the game or OBS starts. Nothing may hash,
  copy or extract from a clip until `D:/SPIDEY CLIPS/_hevc_compress_log.jsonl` shows it replaced.
- Steam Input must be **disabled** for Marvel Rivals whenever the agent's virtual pad drives the game
  (`.agents/skills/rivals-live-game/SKILL.md`).

**Dated exception, night of 2026-09-26/27 only** (James, ~02:20 CDT, relayed by the steering lead). This is not a rule change.
- What it allows: explore-policy may run the EXPLORATORY full-cohort chunk arms H=4 and H=8 on the PC's RTX 4080 while the
  Mac runs H=1. It uses the same code, seeds, roster and frozen dev as the Mac arms, and each result names its device.
- Conditions:
  - A guard stops the fit and frees the GPU within ~10 s of any Marvel or OBS process starting.
  - RAM stays modest.
  - The job writes a status file.
  - It is skipped if the caches cannot be on the PC within about an hour.
- Without a new explicit decision from James, the PC stays off-limits for training from 2026-09-27 onward.

## Rules for the Mac queue

- **One heavy job at a time.** The lead sets the order and announces it to the job owners. Every job waits for the
  previous owner's explicit release, and yields at its next checkpoint if the lead asks.
- Launch from Windows over Git Bash `ssh -n -T -o BatchMode=yes -o ServerAliveInterval=15 mac`, under a timeout.
  (PowerShell 5.1 wrapped around ssh hangs.) Long jobs start with `nohup`, niced, with stdin/stdout/stderr redirected to
  files, and write a status file and an `.exit` file. Judge completion from those files and the output artifacts,
  never from the launcher's return.
- Data lives under `/Users/james/dev/range-bc-data/`: frozen `steps15/` and `caches15/` (the 7 interim sessions), one
  directory per experiment (`countermeasures2/`, `explore/`…) and `runs/`. Never write into another experiment's
  directory. Code runs from a pinned `git archive` (`code-<sha>/`) with its own venv, not from a live checkout.
- Training on the Mac is fine while the game runs on the PC; the two don't share hardware.

## Modal

- Profile `rivals` in `/Users/james/.modal.toml` on the Mac, workspace `volpestyle`. Verify with
  `modal profile list` before any write. Renew with the device-code flow in the `mac-remote` skill; never with James's
  stored password.
- Data goes in the Modal volume `rivals-range-bc`, and only after every file's sha256 is verified inside Modal against
  a pinned manifest. Only train and frozen-dev caches and steps, code and receipts go up. Sealed, test and validation
  data never leave James's machines.
- Every paid run: a benchmark or fan-out script with a hard cap, a projected cost printed before launch, a
  running-spend stop, one class for the whole experiment, and teardown proven afterwards (all apps stopped, no
  containers). Caps are James's: $50 for round 3, and $0 cloud for the explore track unless he adds money.
- A confirm-track fan-out (round 3's `handoff/modal/fanout/`) calls only the reviewed entry point
  (`policy/range_bc/cm3_run.py fit --arm --seed`), one fit per call, each authenticated by a lead-approved receipt.
  It never retries training automatically, and it stays disabled until its independent review lands.

## The two experiment tracks

- **Explore** (steering charter): fast sweeps on the full admitted train cohort and frozen dev, on the Mac only. There's
  no pre-registration, pinning or judge. Every result is tagged EXPLORATORY in the lane note. Nothing from explore reaches
  a real fit or a pilot without a confirm run.
- **Confirm:** a pre-registration committed to `docs/evidence/<folder>/` before any result exists, with amendments as new
  `-aN` files. The judge is written and tested on synthetic inputs, reviewed, and pinned before any result. The
  implementation gets an independent review. The lead approves each stage receipt (weights → proof → smoke → budget →
  extraction → fits) in `approvals.json`, and the judge's reading and the evidence land in the repo and on the Linear issue.
- Independent review is always required for code that sends live input, and for code that decides what enters a training
  or evaluation set. Prefer a reviewer from the other model family.

## Seeing what's running

The job board, `https://jamess-macbook-pro.tailb90f24.ts.net:9443/` (tailnet only; `docs/machines.md`, "Training
job board"), shows Mac queues, explore runs, Modal apps and PC jobs. Every job, on any host, writes a status file
using the job-status convention in `scripts/job_status.py`. A job without one is invisible, or shows only as
"unregistered". James's to-do list for the board lives in `docs/waiting-on-james.md`.

## Moving data between machines

- PC→Mac uses one long-lived ssh stream per file, with the hash checked at both ends, at BelowNormal priority. Expect ~2 MB/s while
  James games; 78 GB of originals take overnight. Recordings go through the relocation procedure in `docs/machines.md`.
- Mac→Modal uploads ran at ~10 MB/s (36.7 GB in about an hour). Upload once per data version and reuse the volume.
- Never use SMB shares, and never change network or firewall settings.
