# Press diagnostic interruption and recovery boundary — 2026-09-27

Owner: idm-owner · VUH-1353 · **EXPLORATORY; no press result**

The fixed-checkpoint press diagnostic was interrupted before it persisted a complete prediction stage. A second worker entry refused `/outputs/press` with `FileExistsError`. This is not a measured failure of the press head, and there is no precision, chance or real-versus-zero result to report.

App `ap-qu8I6QJ2O03oHfzPibSLML` was created at 18:52:17.424236 UTC. The final retained progress receipt records 281,632 of 289,722 TRAIN rows at 19:14:21. GPU capacity messages recur at 19:15:28 and 19:16:14. Replacement container `ta-01M3J4R04X6S5WVXHGFRVGYB5R` enters at 19:16:26 and refuses the existing directory. The driver catches the failure at 19:16:33.987597. Terminal teardown verifies zero containers at 19:16:35.670665. Conservative charge: **$1.79872595** under the $4 hard cap. Together with the SSL smoke, the recorded conservative total is **$2.75555260**, below the $20 alert and $25 IDM hard ceiling.

Explore-policy independently reports capacity messages at 19:15:27 and 19:15:29 on its separate control/candidate apps, then the same existing-directory refusal on replacement entries. The capacity timestamps agree within two seconds. A shared rescheduling/redelivery event is strongly supported; the initiating cause is unknown. No explicit preemption or OOM label was found. Both lanes used `retries=0`; neither launched a user retry.

The retained output volume contains only `jobs/`, an empty `run.log` and `started.json`. It has no completed TRAIN probabilities, calibration, evaluation arrays or report. Original bytes remain unchanged. This attempt cannot use completed-artifact recovery; the input model being intact is not evidence that inference completed.

Local evidence: `data/idm/cloud-20260927/press-failure/`.

| File | SHA-256 |
|---|---|
| final.json | 6cbf9c61a8eeb58b37693974e50006e0011dfebf3640e73553641783e2aef774 |
| app-system.log | fbc0a052a7178f0570a481a701f99e2d32430147dc6edfaac85d7bc76d9d4b33 |

## Agreed recovery rule

Explore-policy and IDM use the same contract, implemented separately in each lane. A `stage-complete.json` is written atomically last, with version 1, stage, immutable identity, successful completion metadata and hashes/sizes of every artifact. Identity binds run config, source archive, input manifest, checkpoint, app name and output volume. Fits require the complete final epoch and step count; IDM's inference stages require exact rows, row order, shape, float32 dtype, finite probabilities and TRAIN-only calibration. A complete final result may be replayed only after every artifact and its payload metadata verifies. A completed TRAIN inference stage permits only remaining inference/scoring. Missing, partial, mismatched or corrupt stages refuse; no fitting entry point is called.

`policy/idm/press_stages.py` implements this for the diagnostic. `press_diagnostic.py` persists the three completed phases and explicitly skips verified complete phases on recovery. Existing top-level artifacts remain byte-preserved or are refused on disagreement. Synthetic tests verify no repeated inference for a completed phase, refusal before model reads for incomplete TRAIN recovery, every identity field, corruption, row order, shape/dtype and complete final-result replay. **21 tests pass.** Ruff is not installed in this environment; Python compilation and `git diff --check` pass.

The separate proposed worker is `data/idm/cloud-20260927/press_recovery_worker.py`; the deployed first-attempt worker and spend guard remain untouched. Nothing has launched. Any manual recovery uses a new receipt linking the original failure and exact stage/checkpoint hashes; original failure receipts are never rewritten as successful. A fresh inference attempt needs the lead's explicit approval and a new bounded deployment. The original press cap has $2.20127405 remaining; its setup/cleanup reservation leaves too little work time for the measured complete diagnostic. A proposed fresh $3 cap would consume at most $0.79872595 of the $2 reserve beyond the original press allocation while keeping IDM's $25 ceiling intact. Exact deployment and cap approval precede any new AppCreate.

Linear handoff (direct tools unavailable): current result is an interrupted press diagnostic, not a model verdict. Remaining acceptance is unchanged: no calibrated press precision/chance/visual-ablation result yet, no Gate 2 pass. Next action is idm-owner's owner-tested recovery deployment and the lead's explicit bounded recovery decision. The independent camera TRAIN illustration is delivered in `idm-camera-demo-20260927.md`; it does not change validation acceptance.
