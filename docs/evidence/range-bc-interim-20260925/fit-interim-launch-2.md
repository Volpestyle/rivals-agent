# fit-interim-launch-2 (VUH-1346, VUH-1359): queue 2 is running

**Interim scaling-curve point, not the real fit. Nothing from it is a policy acceptance or a live-pilot candidate.**

**Queue 2 started 2026-09-25 16:44:16 CDT** on the Mac: `nohup nice -n 10 zsh -l …/interim94/queue2.zsh`, pid **52931**,
launched from Git Bash ssh (`ServerAliveInterval=15`) after the lead's OK (swarm message `f4222cd7`, thread hud-review).
- Amendment: `fit-interim-amend-1.md` (`d17c483e…`), approved; pre-registration `fit-interim-prereg.md` (`8094bdd1…`).
- Script: `interim94/queue2.zsh`, `460ebb48…`, re-hashed on the Mac right before launch.

## Precondition, re-checked at 16:44:04

- `/Users/james/dev/idm-data/runs/resume-confirm.exit` exists (16:01). Only `ls` was used; nothing in `idm-data` was touched.
- No `idm`, `range_bc` or queue process (`pgrep -f`), and no heavy process in `ps -r`.
- Neither out directory nor `queue2.status` existed.

## Verified from the Mac, not from the launcher (16:44:25)

| Item | State |
|---|---|
| `interim94/queue2.status` | `RUNNING 2026-09-25T16:44:16` |
| `interim94/queue2.pid` | 52931: `zsh -l …/queue2.zsh`, parent 1 (detached), nice 15 |
| Trainer | pid 52937, `…/code-5d2ec29/.venv/bin/python3 -m policy.range_bc.train`, nice 15. Its full command line has `--seeds 0 1 2`, `--out …/runs/interim94-s012` and the five train step tables |
| `runs/interim94-s012/`, `runs/interim94-s012.log` | created |

Nice 15, not 10: the ssh session is at nice 0, and the remote shell is zsh, whose default `BG_NICE` option adds 5 to a
job started with `&`. So the queue runs at a lower priority than the brief asked for, not a higher one, and results are
unaffected. Queue 1's record shows the same launch form, so it probably ran at nice 15 too (not checked).

## The two invocations, in order

| # | Run | Train | Seeds |
|---|---|---|---|
| 1 | `runs/interim94-s012` | the five train sessions, 80.53 counted min | 0 1 2 |
| 2 | `runs/interim94-control47-s012` | 051828 + 200129, 33.59 min | 0 1 2 |

Everything else as `fit-interim-launch.md`: plumbing scope, MPS, both arms, 13 epochs, wd 1e-4, stride 64, lag 0,
batch 8, lr 3e-4, regimes normal, dev 171533 + 205528, parity `e9efe999…`, code `code-5d2ec29`, the seven caches of
`verify-7.json`.

Untouched: `interim94-seed0` (the determinism reference) and the failed `interim94-seed1` log and exit.

## Expected finish (from `interim94-seed0`'s uncontended epochs)

| Milestone | Estimate |
|---|---|
| `interim94-s012` exits | about **19:30 CDT** |
| `interim94-control47-s012` exits; queue DONE | about **20:40 CDT**, more if the Mac is shared |

## Monitoring

`poll2.sh` in my scratchpad: a copy of `interim94/poll.sh` pointed at `queue2.status` and the `*s012` logs, every 10
minutes, running in the background, log `poll2.log` in my scratchpad. On DONE: collect, run `judge.py`, write
`fit-interim.md`. On FAILED or a dead queue: report BLOCKED with the `.exit` and `.log`, and do not relaunch.
