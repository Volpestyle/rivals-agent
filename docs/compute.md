# Compute protocol: where training and other heavy jobs run

How this repo uses the PC, the Mac and rented GPUs. Read it before starting any job that trains, extracts features,
decodes video in bulk or rents compute. Machine access details live in `docs/machines.md`; experiment discipline lives
in `docs/steering/charter-20260926.md` and `docs/learning-plan.md`. Written 2026-09-26 from that day's decisions.

## Which machine, for what

| Machine | Use it for | Never |
|---|---|---|
| **PC** (`supedupsilly`, RTX 4080 Super) | The game, OBS recording, the live agent loop, capture and pad code. Light CPU work (hashing, JSON scans, one-file ffprobe) | Training or GPU jobs. James keeps the PC free to play or record, or for supervised live agent runs. While the game runs its GPU is the game's, except for live-agent inference (below) |
| **Mac** (M5 Max, 128 GB, MPS) | Explore sweeps, inference-only audits, cache builds, small fits, the job board. One queue | Two heavy jobs at once. Anything that should be on the PC's live path |
| **Modal** (workspace `volpestyle`, profile `rivals`) | Confirm-track fits that fan out: many GPUs in parallel, billed per second | Launching without a reviewed harness, a lead-approved receipt and a native `timeout=` on every function |
| **AWS** (account 842434829012) | A fallback only. G/VT quota is 8 vCPU on-demand in us-east-2 | Anything, unless Modal is unavailable. The 2026-09-26 benchmark showed a 4-vCPU L40S is CPU-starved |

Measured 2026-09-26 on round 2's A recipe (one epoch; `docs/evidence` and VUH-1346): Mac ~240 s/epoch; Modal
L40S with 8 CPUs 124 s/epoch (~36 min and ~$1.54 per 13-epoch fit); Modal A10 187 s; Modal L4 318 s; AWS L40S with
4 vCPU 292 s. A fit needs ~21 GB of VRAM, so a 48 GB card holds two. The post-training CPU evaluation is CPU-bound,
so give cloud boxes 8 CPUs or more.

Measured 2026-09-28 on two IDM fits, both 3 epochs:

| Fit | Where | Updates | Trainer time | End to end | Cost | Evidence |
|---|---|---|---|---|---|---|
| full03 | One Modal L40S | 122,598 | 5.95 h | 7 h 34 min with evaluation | about $22 | `docs/evidence/idm-expanded-full03-result-20260928/` |
| Mac refit | Mac MPS | 135,390 | 2.16 h | 2 h 53 min | $0 | `docs/evidence/idm-match-refit-mac-result-20260928/` |

The Mac refit did more updates in less time. The two runs used different pipelines, so this doesn't support a claim
that one machine is faster. Use the Mac refit as the planning anchor for local IDM fits. There is no measured PC
number; before planning a PC fit, check that it fits in the card's 16 GB (round 2's policy fit needed 21 GB).

## Rules for PC jobs (while James may be playing)

- Idle or BelowNormal priority, at most 2 ffmpeg threads, each process under ~3 GB. Stream files (hash in 1 MiB
  blocks); never read a whole video into memory; never index `np.load(npz)[key]` in a loop.
- At most 2 concurrent decodes across all processes. Check free RAM before each.
- If the game or OBS is running and the job would compete (bulk decode, re-encode), move it to the Mac queue instead.
- James's SPIDEY CLIPS HEVC compression batch yields automatically when the game or OBS starts. Nothing may hash,
  copy or extract from a clip until `D:/SPIDEY CLIPS/_hevc_compress_log.jsonl` shows it replaced.
- Live-agent inference may use the PC's GPU while the game runs (James, 2026-09-27, 12:36 CDT). The owner measures and
  reports the game's FPS cost. Training on the PC's GPU remains an exception for when the game and recording are stopped.
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
- **Keep the Mac usable for James.** Every Mac process runs at `nice -n 10` (plus `taskpolicy -b` for background
  work), with decoders at `-threads 2` and torch/OMP at 2 threads. All lanes together stay within about 4–6 cores.
  On 2026-09-30, ten uncapped labellers and an 8-thread decode maxed the fans; slower is fine.

## Modal

- Profile `rivals` in `/Users/james/.modal.toml` on the Mac, workspace `volpestyle`. Verify with
  `modal profile list` before any write. Renew with the device-code flow in the `mac-remote` skill; never with James's
  stored password.
- Data goes in the Modal volume `rivals-range-bc`, and only after every file's sha256 is verified inside Modal against
  a pinned manifest. Only train and frozen-dev caches and steps, code and receipts go up. Sealed, test and validation
  data never leave James's machines.
- Every paid run: a projected cost worked out before launch, a native `timeout=` on every function, one GPU class for
  the whole experiment, and teardown proven afterwards (zero containers). **No running-spend stop and no other custom
  budget code** (see "No custom budget code" below). Lane caps are James's allocations, which the lead tracks by hand.
  **Modal workspace usage limit is $200** (James, 2026-09-27 22:08 CDT). That limit, enforced by Modal, is the
  hard cap.
  **No custom budget code** (James, 2026-09-28 ~02:30 CDT), after our own guard killed healthy runs twice: at 22:00 a
  false workspace stop, then at 02:08 a billing query that timed out. Spend is bounded by Modal alone: every function
  sets `timeout=` (measured p95 plus a margin), which bounds each invocation, under the $200 workspace limit.
  A timeout doesn't bound the whole app's bill, so the lead's estimate also counts CPU and RAM, startup, storage and
  any repeated invocations. Before a paid launch the lead reads the bill by hand (`modal billing summary` or
  `modal billing report`, on the Mac) and adds the run's estimate; after it ends, the lead records the bill in the
  spend ledger. The tell-James threshold is a lead process, not code. `cloud/modal_guard` keeps only what protects
  the work: detached apps, the timeout, teardown proof, paced AppCreate, checkpoint re-entry and local-disk staging.
  **Allocations are dated.** The last ones were the weekend of 2026-09-26/28: a $150 total across round 3 (cap $60),
  explore (cap $35) and IDM, with James told before spend passed $150. That weekend is over, round 3 is retired and
  the IDM is parked; before the next paid run the lead confirms the current allocation with James. The weekend's
  per-run history is in git (`git log -p -- docs/compute.md`) and in `docs/steering/spend-ledger-20260927.md`.
  Standing guidance kept from it: when quality and a small saving conflict, choose quality (matched devices, clean
  comparisons); an arm that clearly beats its control goes next to a multi-seed confirm run, not to more single-seed
  variants. Changing a document or on-disk constant does not change an already-running guard.
- A confirm-track fan-out (round 3's `handoff/modal/fanout/`) calls only the reviewed entry point
  (`policy/range_bc/cm3_run.py fit --arm --seed`), one fit per call, each authenticated by a lead-approved receipt.
  It never retries training automatically. The harness itself is launch plumbing, covered in "The two experiment tracks".

## The two experiment tracks

- **Explore** (steering charter): fast sweeps on the full admitted train cohort and frozen dev, on the Mac or on Modal
  under their own hard cap. There's no pre-registration, pinning, judge or review. Every result is tagged EXPLORATORY in the lane note. Nothing from explore reaches
  a real fit or a pilot without a confirm run.
- **Confirm:** a pre-registration committed to `docs/evidence/<folder>/` before any result exists, with amendments as new
  `-aN` files. The judge is written and tested on synthetic inputs, pinned, and reviewed before any result is read. The lead approves each stage receipt (weights → proof → smoke → budget →
  extraction → fits) in `approvals.json`, and the judge's reading and the evidence land in the repo and on the Linear issue.
- **Review only where it pays off** (James, 2026-09-27 ~13:30 CDT: "we shouldn't waste too much time reviewing unless
  we know the reviews pay off in the long run"). This replaces the earlier review-after-landing and launch-plumbing rules.
  - **Reviewed before it lands or runs:**
    - code that sends live-game input;
    - a new or changed spend guard, or anything else that could let spend exceed a hard cap;
    - anything that could open sealed data.
  - **Reviewed after landing, before its result is used:**
    - admission of training or evaluation data, including the frame verdicts; this review caught the ping wheel in
      accepted matches on 2026-09-27;
    - a confirm run's judge, before anyone reads a result.
  - **Not reviewed:** everything else. That covers exploratory code and results, launch plumbing (mounts, wrappers,
    transfers, collection, status, teardown), and record-keeping fixes. The owner's own tests are the check, and a real
    failure is investigated when it shows up. An explore result gets its review when it is promoted to a confirm run.
  - **Small spends:** a run under $5 that uses an already-reviewed spend guard, changing only its cap or name
    configuration, launches without waiting for review.
  - A change to a pre-registration still needs a pre-result `-aN` amendment before its result is read.
- **Launch Modal jobs from the Mac** (James, 2026-09-27). Windows launch paths kept hitting path, CRLF and
  Python-version bugs this weekend. Build packets anywhere, but create Modal apps from the Mac.
- **Share an operational lesson the same day** (James, 2026-09-27). When a lane learns how a platform behaves, e.g.
  "stage data to local disk, don't read frames at random from a Modal Volume", it goes into `cloud/modal_guard` or
  the `rivals-compute` skill that day, so another lane doesn't pay for it again. The spend ledger is
  `docs/steering/spend-ledger-20260927.md`.
- **Shake down a new launcher first** (steering lead, 2026-09-27, after round 3 spent ~18 h failing one launch piece at a
  time). A new or changed Modal launcher runs one cheap explore job at the real concurrent app count before a confirm
  run depends on it. Its hold and timeout values come from measured p95 plus a margin, not from estimates.

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
