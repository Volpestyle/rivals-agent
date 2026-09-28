# Range-to-match diagnostic: fixed comparison and preparation

EXPLORATORY, idm-owner / VUH-1353, 2026-09-28. Lead priority after evaluator check-in 11:15 CDT: before any next refit or policy pilot, compare frozen full03, the prior model and zero camera motion against logged truth on bounded admitted matches outside both fits. This packet records preparation, not an accuracy result. The Mac heavy slot is reserved to IDM; no paid compute is authorized or launched here.

## Fixed scope

Exactly five admitted `idm_train` sources: -7, -8, -10, -11, -12. Current authority12 already covers their canonical accepted receipts (LAND 6ac019f); no authority, source role or sealed contract changes. Target construction and table/PTS validation completed for all five using the existing accepted match consumer. Originals were PC-only, confirmed by admission-codex. No DayMR, archive, test or sealed source is opened.

For each source, select the first 900 and last 900 rows from qualifying contiguous, admitted, normal-regime runs with complete ±8-tick context. Refuse insufficient/overlapping blocks. This gives 30 seconds per match, 150 seconds / 9,000 rows total. All exact IDs/times were fixed from metadata in `selection.json` before inference. No selection uses camera error, action positives or model confidence. The original target files and split registry remain unchanged.

| Session suffix | First block target IDs | Last block target IDs |
|---|---|---|
| -7 | 2570–3469 | 29056–29955 |
| -8 | 540–1439 | 22100–22999 |
| -10 | 942–1841 | 28618–29517 |
| -11 | 314–1213 | 19516–20415 |
| -12 | 22–921 | 27896–28795 |

Frozen full03 checkpoint `f681da9f3a4b8db6f7d19566172b02db776e4bcfac3381be744786179aa55dde` versus prior `1b9bcc6a6f909d0e5cbd1cb5fb64c71c89a6cc5320c8c8989ac51cb952cbf541`, both hash-verified on the Mac. The diagnostic additionally refuses any selected source found in either checkpoint's target provenance. Both models infer on the same Mac MPS device; this does not erase their different training backends. Zero means no camera motion, not a learned zero-visual ablation. No buttons are exported or evaluated by this diagnostic.

Retain existing `idm_eval.camera_metrics`: per-axis absolute error, still/moving slices, direction agreement, gain/speed strata, coverage and 15-/60-interval absolute accumulated errors. Report per-source and pooled results. Also report both models and zero on the common per-axis answered rows so coverage differences do not hide a comparison. That same mask makes the one-second eligible windows identical. Pooling rebases sparse row IDs and namespaces runs, preventing source collisions.

`policy/idm/match_diagnostic.py` performs no fit, threshold tuning, input, split mutation or cloud launch. This is reuse of accepted TRAIN for exploratory diagnosis, not a new confirm holdout or Gate 2 read. Derived pitch and the limited first/last-window coverage must remain explicit.

## Preparation and current work

The five originals total 26,503,257,009 bytes. Relocation copies immutable originals, three logger files, steps and imported demo to `/Users/james/dev/idm-match-data/{originals,sessions}`. Source hashes are checked against current receipts and frozen raw pins; pre-existing destinations must match; new destinations publish only after full destination hash verification. One BelowNormal supervisor (PID 93900) runs the copies serially, with a 4 GiB free-RAM floor and owned-process memory checks. The checked adapter comes from admission's -4/-6 copier, with an explicit five-source roster and a new temporary suffix; admission-owned files were not edited. At this packet freeze, -7 and -8 relocations were complete and verified; -10 was copying. Completion is established by each relocation receipt, not directory existence.

Full native stores are prepared using the existing Mac-only decoder so they can also support later authorized work. Predicted store sizes from target/PTS metadata total 18,032,580,096 bytes. Decode remains serial, niced, CPU, two threads. Targets, source tables, media and PTS are pinned by the unchanged decoder and current admission checks. Store sample inspection precedes scientific inference.

The first attempt `/Users/james/dev/idm-data/range-to-match-20260928` exited before reading media: importing the diagnostic roster indirectly imported PyTorch, absent from the decode-only environment. The roster import is now lazy; a subprocess regression refuses every torch import while importing the roster successfully. A second attempt `...-a1` failed before FFmpeg could start because a Windows-generated wrapper had CRLF in its shebang. The `...-a2` wrapper is LF-only and passes native `ffmpeg -version` before launch. The intermediate a1 launch script also encountered CRLF before execution and was normalized. Failed folders/logs are retained; no partial store is reused.

Current -7 worker is under `/Users/james/dev/idm-data/range-to-match-20260928-a2`, launcher PID 67763. Its frame output was observed growing. Packet archive SHA256 `1063f2d06673a39e7cbad9eaca3336cca285172e08c5e7a2996130946ab286cb`, inventory SHA256 `9bd1cb9c88e512b1bebe88b959bf3ce399b7aa59e6ea56c053f849082c206527`, single-session manifest SHA256 `d777045e785ba0675822296d188e8a765c01ae81bdb369130839a7123b29e1cf`. A completion watcher (PID 65696) reads only exit/result metadata and retries SSH failures; it neither launches a next job nor releases the slot. Transfer completion separately prompts the owner.

## Checks and next action

30 tests passed: the seven new diagnostic checks plus the existing camera evaluator suite. Checks cover full temporal context, gaps/segments, first/last overlap refusal, immutable TRAIN role, source pooling, common-axis/window denominators and importing the roster without PyTorch. Ruff was unavailable in the local environment; no lint success is claimed. Table preparation and all five fixed selections passed against actual admitted metadata without reading pixels.

Next owner action: verify/inspect the completed -7 store, then build the four remaining stores serially from verified relocations; freeze their manifests into the inference packet, run both fixed checkpoints, collect predictions and report transfer slices to herdr-lead before any next fit or pilot. No paid step without telling the lead. Explicitly release the Mac when work is complete. Retain the existing full03 cloud input/output volumes per lead correction. The result and remaining Gate 2 limitations will be reconciled on VUH-1353 by the lead, with readback.
