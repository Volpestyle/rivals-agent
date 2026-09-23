# Mac fit readiness for the next Web-Cluster request fit

Checked 2026-09-23 for VUH-1346. **Ready.** The Mac can train the next admitted
`web-cluster-request-v1` packet on MPS as soon as the lead admits it. Both recorded fits re-ran on
their original admitted inputs at `0f71336`. The request checkpoint reproduced byte for byte. The
reverse path, Mac→PC `scp` then Windows CPU reload, also passed at `0f71336`.

Three things still depend on the packet or the operator, not the Mac:
- the new fit driver has to be written from the admitted packet's hashes;
- two Windows verifier pitfalls must be avoided (see [Not ready or at risk](#not-ready-or-at-risk));
- the training cohort accepts one exact `SourceIdentity`.

No model was selected, and no game input was sent on either machine.

## Mac state

| Item | State |
|---|---|
| Host | `james`, Darwin arm64, macOS 27.0, Apple M5 Max, 128 GiB; idle when checked (no training, GPU or ML job) |
| Tools | `git`, `uv` 0.11.32, `ffmpeg`/`ffprobe` 8.1.2. System `python3` is 3.9.6 and unused; each `.venv` is Python 3.12.13 |
| `/Users/james/dev/rivals-agent` | `main`, was clean at `83c6739`. Fast-forwarded (`--ff-only`) to `0f71336d7aad2c9d775e8636c42da6e9cd79347f`. Clean |
| `/Users/james/dev/rivals-agent-worktrees/human-execution` | Where both previous fits ran. Was clean, detached at `7feee7b`. Advanced to detached `0f71336` (`7feee7b` is an ancestor). Clean. Its previous run directories and inputs under `data/` are unchanged |
| `/Users/james/dev/rivals-agent-worktrees/fit-dryrun-20260923` | New disposable detached worktree at `0f71336`, holding today's dry run. Remove with `git worktree remove --force` when no longer needed |
| Other worktrees | `loaderfmt5`, `rangeproof`, `tracker`, `writerfix`: untouched |

The training code is byte-identical between the previous fit commit `7feee7b` and `0f71336`: `git diff 7feee7b 0f71336 -- policy/ agent/state.py pyproject.toml uv.lock` is empty. So the recorded driver's pin on `policy/range_skill_policy.py` (`d6b62274…`) still holds.

## Environment

In `human-execution` and the dry-run worktree:

```zsh
uv sync --offline --locked --group execution     # no-op, cache warm, 0 s
uv run --offline --locked --group execution python -c 'import torch; print(torch.__version__); print(torch.backends.mps.is_built(), torch.backends.mps.is_available()); x=torch.arange(4.,device="mps",requires_grad=True); x.square().sum().backward(); torch.mps.synchronize(); print(x.grad.cpu().tolist())'
# 2.14.0 / True True / [0.0, 2.0, 4.0, 6.0]
nice -n 10 uv run --offline --locked --group execution pytest -q tests/test_range_skill_policy.py tests/test_range_policy.py tests/test_execution.py
# 235 passed in 2.42 s
```

## Dry run on the previously admitted inputs

Setup:
- Inputs: Mac-local copies of the 14 admitted numerical inputs and receipts, plus the two executed drivers, copied from `human-execution` into the dry-run worktree. No source media.
- Hashes: every file matched the hash pinned in its driver: `fit.py` `6a3ff6b2…` for request and `875c5562…` for v2.
- Execution: the drivers ran unmodified in one `nohup nice -n 10` job that wrote a log and exit status. Both exited 0 with about 3 s wall time each.

| Fit | Checkpoint | Predictions and metrics | Notes |
|---|---|---|---|
| Request (`range-request-human-fit-20260922`) | `6ee388070599e3df042ea73876e391340bf228a9e626cc212c60875d8191aeef`, **byte-identical** to the recorded one | All five known rows identical (137 no, 141 start, 144/200/206 no); all four metric blocks identical | `fit_seconds` 2.60 (recorded 1.90). Report differs only in `git_commit` and `fit_seconds` |
| Six-label v2 (`range-event-human-fit-v2-20260922`) | `254c92c7…`, differs from `da29a97f…` | Weights **bit-identical** (`torch.equal` on every tensor); probabilities and metrics identical | The only differing payload field is `code_sha256`. v2 was trained at `8f78ae9`, before `range_skill_policy.py` gained the request revision (`582e3f08…` → `d6b62274…`) |

Dry-run artifacts are under `fit-dryrun-20260923/data/diagnostics/`: `fit-readiness-20260923/`, which holds `job.zsh`, `exit-codes.txt` and one log per fit, and each fit's `run-1/`.

## Hand-back to Windows

**Transfer.** `scp` returned the dry-run request checkpoint to this PC's scratchpad. SHA-256 on arrival was `6ee38807…`.

**Reload.** To avoid touching the shared checkout, I ran the reload in an isolated `git clone --shared` at `0f71336`. That clone was staged with:
- the transferred checkpoint;
- the recorded `mac-report.json` (`9d763f7c…`);
- the recorded numerical inputs.

**Request verifier.** The unmodified `verify_windows.py` exited 0 with `uv run --offline --no-project --with torch==2.14.0`. Its report has identical `known_rows` and identical `train_metrics`, and its maximum delta from Mac CPU is 1.630e-9, all matching the recorded `windows-report.json`. It differs only in `git_commit` and in `code_checks`, because the clone's `agent/state.py` is LF rather than CRLF.

**v2 checkpoint (`da29a97f…`).** The recorded verifier cannot pass at any commit after `8f78ae9`. By design, it requires the Windows `range_skill_policy.py` bytes to equal the Mac commit's blob, and that file has since changed. Instead I ran a reload-only check at `0f71336` on torch 2.14.0+cpu, with the verifier's own hash, identity, prediction and metric assertions minus the code-bytes pin. Predictions were identical, and probabilities differed from the recorded Windows report by 0.0. Metrics equal the Mac CPU reload.

## Runbook for the next fit

Placeholders:
- `<PACKET>`: the admitted materialization directory, for example `data/human/skill-events/051828-request-…/`.
- `<RUN>`: a new name, for example `range-request-human-fit-v2-20260923`.
- `<COMMIT>`: the pushed commit the lead fits on.
- `H=/Users/james/dev/rivals-agent-worktrees/human-execution`.

1. **Driver (Windows).** Copy `docs/evidence/range-request-human-fit-20260922/fit.py` to `data/diagnostics/<RUN>/fit.py`. Edit only:
   - `EXPECTED`: the new `examples.json`, every decision, receipt, review, profile, dependency and validation file the admission names, and the `policy/range_skill_policy.py` hash at `<COMMIT>`.
   - The `packet["status"]` value.
   - The evidence-digest literal.
   - The known `(grid_index, label)` list, the row count and the known count.
   - The same-ammo contrast assertion: drop it, or update it to the new bins.
   - `scope` and `limits`.

   Keep the configuration unless the lead changes it: MPS, hidden 8, 100 epochs, batch 2, learning rate 0.01, seed 7, no silent CPU fallback. The driver refuses to overwrite `run-1`.
2. **Package (Windows).** Write `transfer-manifest.json` mapping each relative path to its SHA-256, the driver included. Build the zip with forward-slash member names. On 2026-09-22 the first archive was rejected because its names used backslashes.
   ```powershell
   $H = '/Users/james/dev/rivals-agent-worktrees/human-execution'
   uv run --no-project python -c "import json,zipfile,sys; m=json.load(open(sys.argv[1])); z=zipfile.ZipFile(sys.argv[2],'x'); [z.write(p, p.replace('\\','/')) for p in [*m, sys.argv[1]]]" data/diagnostics/<RUN>/transfer-manifest.json data/diagnostics/<RUN>/transfer.zip
   ssh mac "mkdir -p $H/data/diagnostics/<RUN>"
   scp -o BatchMode=yes data/diagnostics/<RUN>/transfer.zip mac:$H/data/diagnostics/<RUN>/transfer.zip
   ```
3. **Checkout and unpack (Mac, through `mac.ps1`).**
   ```zsh
   H=/Users/james/dev/rivals-agent-worktrees/human-execution
   cd $H && test -z "$(git status --porcelain)" && git fetch origin && git checkout --detach <COMMIT>
   uv sync --offline --locked --group execution   # drop --offline only if uv.lock changed
   unzip -n data/diagnostics/<RUN>/transfer.zip
   uv run --offline --locked python -c "import json,hashlib; m=json.load(open('data/diagnostics/<RUN>/transfer-manifest.json')); bad=[p for p,d in m.items() if hashlib.sha256(open(p,'rb').read()).hexdigest()!=d]; print('BAD', bad) if bad else print('all', len(m), 'hashes match')"
   ```
   Stop if any hash differs. Run the MPS probe from [Environment](#environment).
4. **Fit (Mac).** This is the same durable job shape as `range-request-human-fit-20260922/run.sh`:
   ```zsh
   cat > data/diagnostics/<RUN>/run.sh <<'EOF'
   #!/bin/zsh
   cd /Users/james/dev/rivals-agent-worktrees/human-execution
   uv run --offline --locked --group execution python -B data/diagnostics/<RUN>/fit.py >data/diagnostics/<RUN>/fit.log 2>&1
   job_rc=$?; printf "%s\n" "$job_rc" >data/diagnostics/<RUN>/exit.txt; exit "$job_rc"
   EOF
   nohup nice -n 10 zsh data/diagnostics/<RUN>/run.sh >/dev/null 2>&1 & echo $! > data/diagnostics/<RUN>/pid.txt
   ```
   Report from `exit.txt`, `fit.log` and `run-1/mac-report.json`, not from the launch response. Check first that no other Mac GPU job is running: `nice` does not lower GPU priority.
5. **Return (Windows).** Copy the artifacts back and compare `Get-FileHash -Algorithm SHA256` with `checkpoint_sha256` in the report:
   ```powershell
   $H = '/Users/james/dev/rivals-agent-worktrees/human-execution'
   scp -o BatchMode=yes mac:$H/data/diagnostics/<RUN>/run-1/model.pt data/diagnostics/<RUN>/run-1/model.pt
   scp -o BatchMode=yes mac:$H/data/diagnostics/<RUN>/run-1/mac-report.json data/diagnostics/<RUN>/run-1/mac-report.json
   ```
6. **Windows CPU reload.**
   1. Copy `docs/evidence/range-request-human-fit-20260922/verify_windows.py` to `data/diagnostics/<RUN>/`.
   2. Update its pinned `mac-report.json` SHA-256, the checkpoint SHA-256 and the packet path.
   3. Run it from a checkout whose `policy/*.py` are LF, with torch pinned:
   ```powershell
   uv run --offline --no-project --with torch==2.14.0 python -B data/diagnostics/<RUN>/verify_windows.py
   ```

### Expected runtime

**Measured today:**
- transfer: seconds (the previous packet's zip was 29 KB);
- environment: 0 s, since it is already synced;
- MPS probe: about 2 s;
- fit job: about 3 s wall for 5 known rows;
- Windows verifier: about 4 s.

**Extrapolated:** training runs ⌈K/2⌉ × 100 optimizer steps on MPS, for K known rows. The four measured fits took 3.5–9 ms per step (`fit_seconds` / 300 steps). That is roughly 0.2–0.45 × K seconds: under a minute for 100 known rows, and under 8 min for 1,000. Masked rows only count toward coverage.

## Not ready or at risk

- **No driver exists for the new packet.** Step 1 must be done from the admitted packet's actual hashes. The driver decides what enters training, so it needs the lead's check before launch.
- **Unpinned Windows torch drifts.** Today, `uv run --offline --no-project --with torch` resolved **torch 2.6.0+cu124** from this PC's uv cache instead of the recorded 2.14.0+cpu. The verifier still passed: predictions were identical and probabilities within 1.4e-9. Pin `--with torch==2.14.0`, which is now cached, for a like-for-like report.
- **A fresh Windows checkout fails the verifier's code pin.** `core.autocrlf=true` in the system gitconfig writes `policy/*.py` as CRLF, and the verifier allows CRLF only for `agent/state.py`. The shared checkout currently has LF policy files (`git ls-files --eol`: `w/lf`). For an isolated checkout, use `git -c core.autocrlf=false`.
- **Training accepts exactly one `SourceIdentity`.** Every training row must share patch, regime, source-profile hash, perception hash and selector hash. `cohort()` refuses anything else before training starts. Rows from `051828` cannot pool with the `032454` rows unless all five match. A perception change, such as the HUD calibration work currently uncommitted in `perception/hud.py`, changes the perception hash. `evaluate()` tolerates a different source profile across sessions but still requires the same patch, regime, perception and selector hashes. No human train+validation driver has been executed yet, so an evaluation in the same job would be new driver code needing review.
- **A newer `<COMMIT>` means redoing the checks.** If the packet requires code newer than `0f71336`, repeat the clean-worktree check, `git checkout --detach`, the environment check and the policy-hash pin.
