# fit-countermeasures-launch (VUH-1346): the countermeasures test is running

**A plumbing-scope test on dev, not the real fit. Nothing from it is a policy acceptance or a live-pilot candidate.**

- **Pre-registration:** `fit-countermeasures-prereg.md` (`078d5351…`, amendment 1; v1 `de00d589…`), approved by the
  lead with fit-review's LAND verdict (`review-fit-countermeasures-2.md`, `4e9671e1…`).
- **The lead's tightening:** the code is only a `git archive` of the landed commit `807d35f`.

## Launch

**Queue started 2026-09-25 22:37:56 CDT** on the Mac:
- command: `nohup nice -n 10 zsh -l /Users/james/dev/range-bc-data/countermeasures/queue.zsh`, pid **9791**, nice 15
  (zsh's `BG_NICE` adds 5, as before);
- launched from Git Bash ssh.

**Code:** `/Users/james/dev/range-bc-data/code-807d35f`:
- a `git archive` of `807d35f` (tar `2f45086c…` on both ends);
- `train.py` `dbfd8b1d…` and `metrics.py` `ff8ec178…` LF-checked on the Mac;
- its own `uv sync --offline --locked --group execution`: torch 2.14.0, MPS available.

**Scripts:**
- `countermeasures/queue.zsh`: `0093fc05f88c0664b482876282eb8a2a01bf86b1dca60df76debd15287cf5a65`, the same bytes
  in `handoff/countermeasures/queue.zsh`;
- `repro_metrics.py`: `2eb3f58b…`.

## The queue's three steps, verified from the Mac, not from the launcher

| Step | Result |
|---|---|
| 1. Cache verification: all seven caches re-hashed in full (`verify_caches.py`, `open_cache(verify_hashes=True)`) and required equal to `interim94/verify-7.json` | **passed** 22:37:56 → 22:38:12, exit 0. `countermeasures/verify-cm.json` is byte-identical to `verify-7.json` (`d23b8b9efee7faeea469d3f10b4bf4ed5d765d00ceded4a2645edf9417a889d7`) |
| 2. Arm A: `interim94-s012`'s six checkpoints re-evaluated with this code | **passed** 22:38:12 → 22:41:28, exit 0. All stored blocks and the gates are byte-identical; the only new keys are the two new blocks. `countermeasures/A-reread.json` `8a13a3fd…` is byte-identical to the pre-launch v2 re-read |
| 3. Arms B and C: `runs/cm-s012`, running since **22:41:28** | trainer pid 12790, from `code-807d35f/.venv`. Seed 0 of C (`model_nohud`, self-conditioned) is at epoch 1 (581 s) as of 22:51:50 |

**Step 3's command:** as pre-registered, `--arms model_nohud --frames-only-nohud --self-condition 0.5
--self-condition-ramp 0.5 --prev-dropout 0.2 --seeds 0 1 2`, with the interim recipe (13 epochs, wd 1e-4, stride 64,
lag 0, batch 8, lr 3e-4, normal, MPS, plumbing; the five train sessions; dev 171533 + 205528; parity `e9efe999…`).

**Records:**
- status: `countermeasures/queue.status` (`RUNNING <step> <time>`, `DONE <time>` or `FAILED <step>`);
- per step: `.exit` files, `verify-cm.{json,err,exit}`, `A-reread.{json,log,exit}`, `runs/cm-s012.{log,exit}`.

## ETA

| Part | Basis | Estimate |
|---|---|---|
| C: 3 seeds × 13 epochs | about 290 s per epoch (epochs 0-1), against 240 s for plain no-HUD. The self-conditioning pass plus contention | about 3.1 h |
| B: 3 seeds × 13 epochs | the no-HUD encoders without history, about 240-260 s per epoch | about 2.6-2.8 h |
| Evaluation of six models on dev | as the interim | about 5 min |
| **Queue DONE** | from 22:41:28 | **about 04:30 CDT on 2026-09-26; allow to 05:15** |

**Contention.** An Xcode iOS build (many `clang -cc1` processes at nice 0), and then an iOS simulator, were running on
the Mac at launch. They are not ours and not the rivals-agent's. Being niced, our queue yields CPU to them. This changes
wall time only; MPS training is deterministic.

## Next

**No PC background poll.** The lead wakes me at the ETA. Then:
1. check `queue.status`;
2. collect `cm-s012/report.json` and the logs, and hash the report and all six checkpoints on both ends;
3. write and test the judge against `A-reread.json` and a stored report before reading;
4. judge by the pre-registered rules;
5. write `fit-countermeasures.md`.

**If `FAILED` or the queue is dead:** BLOCKED with the `.exit` and log; no relaunch without the lead.
