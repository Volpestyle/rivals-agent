# scoreboard-fix: IDM plumbing on the Mac, steps 7-9 done (RELEASE idm-mps) (VUH-1353)

2026-09-24.
- **Code:** worktree `rivals-agent-worktrees/idm` at `1df31e7`, clean. Every report records `git_commit`
  `1df31e7…`, `tracked_changes: false`, and a 26-module code closure.
- **Scope:** `gate1-dev` for the LOSO runs, `smoke` for the smoke runs. **None of this is a gate result.** The
  held-out sessions are train-split recordings, and this is 3 epochs of one seed.
- **Not done:** no commits, no Linear, no edits beyond one lane-doc entry, no game input.

## Step 7: the MPS smoke (twice, 512 examples, 1 epoch, dev held out)

- **Exit:** 0, about 74 s for both runs. **MPS runs under `use_deterministic_algorithms(True)`,** with no refusal.
- **The two checkpoints are byte-identical:**
  `2b97875dbc4bbabcabf92d9f8d419c771528630ebbb2d24602fb694892e467aa`, and the train loss is identical (1.2922974).
- **Timing:** 0.00605 s/example on run a (with MPS warm-up) and 0.00324 on run b. Dev prediction ran at about
  620 rows/s.
- **EPOCHS = 3:** the cap. The budget was 510k × 3 × 0.00605 = 2.6 h plus predictions, about 2.7 h, under 4 h.

## Step 8: leave-one-session-out, EPOCHS 3, seed 0, MPS, nice 10

- **Launch and duration:** launched at 14:21 CDT (Mac pid 88996), exit 0 after **81 min**, less than a third of the
  budget.
- **The real rate** was 0.0029 s/example. The smoke's first-run figure included warm-up, and the stores stayed in the
  page cache.

| Held out | Train examples | Missing frames | Train loss by epoch | Fit | Checkpoint sha256 |
|---|---|---|---|---|---|
| 171533 (dev) | 160,772 | 0 | 0.670 / 0.441 / 0.280 | 1,413 s | `676369216b608910…` |
| 051828 | 144,932 | 0 | 0.679 / 0.520 / 0.369 | 1,273 s | `11d0b912241aaaa2…` |
| 205528 | 130,180 | 0 | 0.746 / 0.543 / 0.407 | 1,145 s | `982ce32ff7669b9a…` |
| 200129 | 74,212 | 0 | 0.742 / 0.579 / 0.479 | 654 s | `e2f84a62de645bd9…` |

**Unsupported, from each fold's train counts:** melee, simple_swing and ultimate, as expected.

## Step 9: collected and verified

- **Location:** everything is in `C:\Users\volpe\repos\rivals-agent\data\idm\runs\`, gitignored: `smoke-a`,
  `smoke-b`, `loso-{171533,051828,205528,200129}`, the four store manifests (`<id>.frames.json`), and every job's
  `.log` and `.exit`.
- **Twelve files were hash-checked** across the wire (six `report.json` and six `idm-seed0.pt`), all equal:

| Run | report.json | checkpoint |
|---|---|---|
| smoke-a | `bb8cc823dc75021d…` | `2b97875dbc4bbabc…` |
| smoke-b | `e947b3027ffb0935…` | `2b97875dbc4bbabc…` |
| loso-171533 | `dfbfc7420a8cfedd…` | `676369216b608910…` |
| loso-051828 | `7249186ca7f5ef73…` | `11d0b912241aaaa2…` |
| loso-205528 | `621ad66e3a13c8f1…` | `982ce32ff7669b9a…` |
| loso-200129 | `aa048e3006c5974a…` | `e2f84a62de645bd9…` |

**Store manifests (frames.json sha256):**

| Session | sha256 |
|---|---|
| 171533 | `8780ea7c10884a94…` |
| 051828 | `457637aa99f61327…` |
| 205528 | `14190df6abcf0b8a…` |
| 200129 | `a111ba075390634d…` |

## What the plumbing run shows (read as plumbing)

**Camera: the model beats zero in every fold, is far short of persistence, and yaw direction collapses on three
folds.**

Each cell reads: moving median error / direction agreement / 1 s summed-error median / abstention.

| Held out | Yaw: model | Yaw: zero | Yaw: persistence | Yaw model median, calibrated / extrapolated | Pitch: model | Pitch: zero |
|---|---|---|---|---|---|---|
| 171533 | 0.35° / 0.96 / 3.4° / 4 % | 1.22° / – / 12.6° | 0.20° / 0.99 / 0.4° | 0.03° / 0.38° | 0.51° / 0.86 / 2.4° | 0.89° / – / 3.7° |
| 051828 | 0.85° / **0.54** / 4.0° / 27 % | 1.42° / – / 28.8° | 0.20° / 0.99 / 0.8° | 0.08° / 0.79° | 0.56° / 0.85 / 7.4° | 0.93° / – / 13.9° |
| 205528 | 0.74° / **0.47** / 3.0° / 38 % | 1.46° / – / 28.4° | 0.20° / 0.99 / 0.7° | 0.05° / 0.69° | 0.68° / 0.82 / 5.5° | 0.93° / – / 10.3° |
| 200129 | 0.85° / **0.51** / 6.4° / 26 % | 1.39° / – / 26.3° | 0.20° / 0.99 / 0.8° | 0.07° / 0.85° | 0.82° / 0.69 / 9.1° | 0.93° / – / 10.9° |

- **Persistence is a ceiling built from labels,** not a floor: it repeats the previous interval's **true** rotation.
- **Open, not explained:** yaw direction agreement on moving, answered rows is 0.96 on 171533 but **0.47–0.54 on the
  other three**, which is chance.
  - The three are the fast-heavy sessions: 40–43 % of their rows are above the calibrated band, against 23 % for
    171533.
  - Their yaw abstention is also higher (26–38 %, against 4 %).
  - The reports hold aggregates only, so I cannot split direction agreement by speed.
- **A hypothesis, not a finding:** a turn faster than the conv's receptive field per interval leaves its direction
  ambiguous to a small conv with global average pooling.
- **The stated total std under-covers above the calibrated band** (yaw within 1σ / 2σ, per true regime):
  - calibrated: 0.67–0.88 / 0.90–0.98;
  - extrapolated: **0.29–0.73 / 0.74–0.95**, with 14–78 % of extrapolated yaw rows abstained.

**Edges: no usable skill at this scale.**
- For almost every supported action the model predicts no onset. Precision is undefined and recall 0, with F1 0
  against both baselines' F1 0.
- **Jump** fires nearly everywhere: precision 0.02–0.06, recall 0.59–0.94, F1 0.05–0.11, onset error 0.
- **Spider Power** scores F1 0.04 on 205528.
- Held-out positives decide for up to 11 actions per fold. For example, 200129 has jump 846, move_right 530 and
  move_forward 472.

## Suggested next steps (not done; each needs your go)

1. **Per-row predictions for one fast-heavy fold** (for example `loso-051828`'s checkpoint on its held-out store):
   direction agreement by speed band and gain regime, and a sign check at a ±k-interval lag.
   - This settles whether the yaw collapse is speed (the model) or a per-session sign or offset (the data).
   - Minutes of Mac time, on the MPS or CPU the release allows.
2. **The edge head.** Before more epochs, look at why it collapses to "no onset" (pos_weight clamp 100, threshold
   0.5, the abstention band) against jump's always-on. A 3-epoch plumbing fit is not the verdict.
3. **Nothing here should feed a replay label.** Gate 1 has not been run at scope, and the camera head fails its own
   stated-std check above the calibrated band.

## Also

- **Lane doc:** one measured entry, "2026-09-24: first IDM plumbing run on the Mac".
  `docs/lanes/inverse-dynamics.md` is now `8a89f9904903fe08533680765ec897860584ab389f23a624a06fccb66c9cd3a4`
  (+28 lines, uncommitted).
- **The Mac holds** `/Users/james/dev/idm-data/` (stores 26 GB, inputs, jobs, runs) and the worktree. Nothing is
  running there now.
- **The swarm envelopes** for RELEASE idm-mac and idm-mps never reached me through `swarm_inbox`. I acted on your chat
  copies both times.
