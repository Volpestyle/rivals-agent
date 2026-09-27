# First IDM refit launched, 2026-09-27

Owner: idm-owner, VUH-1353. EXPLORATORY. This continues the frozen [run plan](idm-first-explore-run-20260927.md); no original review packet was edited.

The lead explicitly released the Mac on Swarm thread `idm-first-explore-run`, message `d6e3450d-7efc-4380-a582-d11be8e90f4a`, and authorized smoke then the three-epoch interim range refit. The earlier instruction to wait for H1 is superseded by that release. No watcher or concurrent H1 job was launched by this lane.

## Preflight and smoke

The staged `code-54bae68` and private environment passed a real torch 2.14.0 MPS gradient check (`[0,2,4,6]`). The pinned manifest, wrapper and all seven target files passed preflight. Runtime verified the reused camera/HUD stores. There was no media decode, DINO extraction, source-role change or access to V-C/V-Q/sealed Gate 2 payloads.

Smoke attempt 01 failed before training with exit 2: `options` is a special zsh parameter, so the launcher expanded shell on/off settings into Python arguments. Its console/exit files are preserved and the dashboard records failure. The corrective **launcher-only** delta is `run-refit-v2.zsh`, variable `idm_run_args`, with a fresh smoke job name. Exact argument expansion and shell syntax were tested before retry. This delta is provisional under the compute protocol's fix/run/review-after rule; independent review is still required before accepting results. It changes no model, loss, metric, source selection, seed or numeric setting. The original wrapper remains unchanged.

Attempt 02 (`idm-refit-interim-smoke-20260927-02`) **completed, exit 0**, at 11:02:19 UTC / 06:02:19 CDT:

- One epoch on the explicit 5,000-example prefix; fit time 20.282 s; finite training loss 3.64299.
- Complete heldout diagnostic returned; checkpoint bytes match the report's SHA256. This is a pipeline smoke, not an accuracy acceptance result.
- Total elapsed 187.15 s, including checks and heldout scoring.
- Peak RSS 57,510,576,128 bytes (53.56 GiB); peak process footprint 4,004,488,184 bytes (3.73 GiB). The first estimate understated RSS, which includes the mapped native stores. These are process measures, not measured MPS allocation. `time -l` recorded zero process swaps; macOS memory-pressure query reported 69% system-wide free during scoring. Global swap was already substantial, so its total cannot be attributed to this run.

Smoke report: [local verified copy](../../data/idm/explore-20260927/smoke-result/report.json), SHA256 `dc6f8c6812efa557fab5c4b7583d75e5f112fa25759d66e245b991ffaf09d268`. Checkpoint remains on Mac, SHA256 `13ba9474232d9c861f19bcbf6de2bb3ab9848f77899feb9b45dca05c00ab5fc9`.

## Refit in progress

Job `idm-refit-interim-seed0-20260927-01` started at **11:02:53 UTC / 06:02:53 CDT**. Wrapper PID 2891; Python PID 2896. It uses MPS, two CPU threads, seed 0, three epochs, the unchanged five-session 80.53-minute training population, and the two frozen dev sessions held out. There is no smoke prefix limit in this run. The wrapper is niced; Python's observed nice value is 19. The 90-minute cooperative budget remains unchanged.

Training was confirmed at 11:04:14 UTC: **4,800 / 869,166** example presentations, with a fresh running dashboard receipt. The first two full-run progress intervals are about 6.2 s per 1,600 examples, consistent with the initial estimate.

Smoke throughput projects 3,525.7 s (58.8 min) of fitting for the estimated 289,722 context-valid train rows across three epochs. Initial whole-job ETA: **60–75 minutes from launch, roughly 07:05–07:20 CDT**. This is an estimate from a small prefix and must be revised from full-run progress; random access over the full stores may be slower. Completion requires exit 0 and the final report/checkpoint, not elapsed ETA or a full progress bar.

Mac root: `/Users/james/dev/idm-data/explore-20260927/`. Runtime log: `idm-refit-interim-seed0-20260927-01/run.log`; console/resource log: `idm-refit-interim-seed0-20260927-01.console.log`; exit receipt: the same stem with `.exit`. Dashboard receipt: `/Users/james/dev/jobs/idm-refit-interim-seed0-20260927-01.status.json`, owner `idm-owner`, host `mac`. Training progress is written by the runner. The helper's ETA field stays null; the forecast above is not a measured whole-job ETA.

Launch used `nohup nice -n 10 /bin/zsh run-refit-v2.zsh --mac-released full` after validating smoke success, finite history, report identity and checkpoint hash. Exact manifest SHA256 remains `ba6e7fe44d8ec7977c4c34f36ef07c7adc63f6f6b71374855f99bd90080211c3`. Corrected wrapper SHA256 is `fc4c5c00db1c962855d7fe741c459e1d69c788f21b22c1666ea31a1fe1c18e1f`.

The expanded match refit remains a separate prerequisite chain; this run does not claim match coverage. The optional Combo context experiment still waits for DINO assets. No commit, cloud spend, live input or source deletion was performed.
