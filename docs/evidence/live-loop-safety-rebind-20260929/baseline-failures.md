# Broad-suite failure reconciliation, 2026-09-29

All **45 distinct failing/error node IDs** below reproduce with the 8331c45 loop and no camera integration patch. Other lanes' current files remain present, as requested. No code outside this lane was fixed.

## Failures caused by this lane

**None outstanding.** Owner safety tests pass (331), combined patch tests pass (521), and the same combined tests in an isolated stdlib environment pass (512, 9 dependency-related skips). During development the new PID requirement exposed old fake CLI fixtures; those owned fixtures and a fake-clock default in the new safety helper were corrected before these final checks.

## Pre-existing failures

The final stdlib run uses an isolated environment and no `--ignore`; its output is `stdlib-suite.txt`. It finished with **28 failures, 12 setup errors, 2690 passes and 138 skips** after commit 657020d (3m20s). All 40 bad node IDs reproduce on the baseline in `baseline-stdlib-failures.txt`.

The completed perception run (`perception-suite.txt`) had 30 failures, 12 setup errors, 4267 passes and 229 skips in 32m42s. It excluded `test_spatial_yaw_local.py` because that module then failed collection. Commit 657020d subsequently fixed collection; full perception collection now succeeds with 4561 tests (`perception-full-collection.txt`). The entire 32-minute perception suite was not repeated after that test-only fix and other concurrent additions; these are reused results for unchanged test inputs, not a claim of a fresh full-suite pass.

Baseline perception replay gives 26 failures, 12 errors and 4 passes (`baseline-perception-failures.txt`). The four isolated passes are the live-range CLI cases: run after `test_intake_streaming.py`, all four fail identically on the baseline (`baseline-perception-order.txt`). That earlier test leaves the snapshot path active, so the later import finds a snapshot missing its reviewed test file.

No listed failure is explained by the 8331c45 CRLF rewrite. `crlf-baseline.json` proves the rewritten controller/startup/capture/record/l4_measure sources equal their parent after LF normalization. Missing dependencies, snapshot files, fixture fields and HUD assertions are independent of line endings. The denylist failures use an LF-normalized hash and changed membership/stale consumer pins, not those five runtime bytes.

The two former collection failures (NumPy in stdlib, Torch in perception) also reproduced on baseline, but are **resolved by another lane in 657020d** and are not in the current failure list. Their logs are retained as historical diagnostics. Initial runs in the shared `.venv` inadvertently included installed optional packages; those incomplete attempts were stopped and are not used for a stdlib result.

| Exact node ID | Suite | Reproduced on baseline | Cause; CRLF explanation |
|---|---|---|---|
| `tests/test_live_range_bc.py::test_cli_defaults_remain_cpu_and_original_preprocessor` | perception | Yes | Earlier intake test leaves snapshot import path active; CRLF: no |
| `tests/test_live_range_bc.py::test_review_receipt_must_match_all_loaded_and_running_files` | perception | Yes | Earlier intake test leaves snapshot import path active; CRLF: no |
| `tests/test_live_range_bc.py::test_settle_default_and_excluded_interval` | perception | Yes | Earlier intake test leaves snapshot import path active; CRLF: no |
| `tests/test_live_range_bc.py::test_v1_review_cannot_authorize_new_inference_dependency` | perception | Yes | Earlier intake test leaves snapshot import path active; CRLF: no |
| `tests/test_measure_inference_fps.py::test_desktop_main_requires_startup_before_ready_or_measurement[False]` | stdlib | Yes | Optional NumPy import in the stdlib environment; CRLF: no |
| `tests/test_measure_inference_fps.py::test_desktop_main_requires_startup_before_ready_or_measurement[True]` | stdlib | Yes | Optional NumPy import in the stdlib environment; CRLF: no |
| `tests/test_measure_inference_fps.py::test_fresh_process_import_audit_blocks_actuators_and_desktop_opening` | stdlib | Yes | Optional NumPy import in the stdlib environment; CRLF: no |
| `tests/test_replay_hud.py::test_identify_order_on_james_is_his` | perception | Yes | HUD slot-mapping assertion: observed 5, expected 0; CRLF: no |
| `tests/test_sealed_denylist_v2.py::test_every_consumer_pins_v2` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_sealed_denylist_v2.py::test_v1_is_unchanged_and_v2_is_a_superset_of_it` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_spatial_yaw_fallback.py::test_completed_fit_resumes_evaluation_without_refit` | stdlib/perception | Yes | Incomplete stage identity in test fixture; CRLF: no |
| `tests/test_spatial_yaw_fallback.py::test_partial_fit_never_recomputed` | stdlib/perception | Yes | Incomplete stage identity in test fixture; CRLF: no |
| `tests/test_tally_default.py::test_the_default_snapshot_is_committed_and_validates_the_live_registry` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_a_binder_outside_any_session_blocks_deletion_and_is_named[data/human/calibration/x/notes.md-sha256]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_a_binder_outside_any_session_blocks_deletion_and_is_named[data/human/skill-event-candidates/051828-request-timing-v1/artifact-hashes.json-sha256]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_a_binder_outside_any_session_blocks_deletion_and_is_named[docs/evidence/range-request-human-fit-20260922/README.md-path]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_a_pixel_format_change_fails_verification` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_an_interrupt_between_the_renames_still_leaves_a_receipt` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_an_interrupted_encode_leaves_no_partial` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_any_transcode_is_refused_while_the_game_or_obs_runs[running0-marvel-win64-shipping.exe running-hevc_nvenc]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_any_transcode_is_refused_while_the_game_or_obs_runs[running0-marvel-win64-shipping.exe running-libx265]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_any_transcode_is_refused_while_the_game_or_obs_runs[running1-obs64.exe running-hevc_nvenc]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_any_transcode_is_refused_while_the_game_or_obs_runs[running1-obs64.exe running-libx265]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_any_transcode_is_refused_while_the_game_or_obs_runs[running2-obs-ffmpeg-mux.exe running-hevc_nvenc]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_any_transcode_is_refused_while_the_game_or_obs_runs[running2-obs-ffmpeg-mux.exe running-libx265]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_delete_after_the_relocation_is_recorded` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_delete_is_refused_while_the_takes_own_session_holds_no_relocation` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_delete_refuses_a_receipt_intake_would_refuse` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_delete_refuses_a_relocation_that_does_not_hold[changed receipt-load_transcode_receipt\|another receipt\|changed]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_delete_refuses_a_relocation_that_does_not_hold[other receipt-another receipt]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_delete_refuses_a_relocation_that_does_not_hold[tampered output-no longer matches its receipt]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_delete_refuses_a_relocation_that_does_not_hold[unpinned-not pinned by the session's freeze]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_end_to_end_preserves_every_timestamp_and_writes_the_receipt` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_every_binder_must_resolve_to_a_relocated_session` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_intakes_media_hash_check_must_hold` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_plan_all_pairs_by_metadata_and_never_opens_the_sealed_folder` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_plan_only_checks_everything_and_writes_nothing` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_rounded_timestamps_fail_verification_and_leave_nothing` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_the_game_starting_mid_encode_kills_a_cpu_encode` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_the_receipt_loads_through_intakes_contract` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_the_run_lowers_its_priority_first` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_the_sealed_media_is_refused_by_path_as_a_string[C:/USERS/VOLPE/VIDEOS/2026-09-23 00-36-16.MKV]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_the_sealed_media_is_refused_by_path_as_a_string[C:/Users/volpe/Videos/2026-09-23 00-36-16.mkv]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_the_sealed_media_is_refused_by_path_as_a_string[C:\\Users\\volpe\\Videos\\2026-09-23 00-36-16.mkv]` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |
| `tests/test_transcode_recording.py::test_the_sealed_session_is_refused_by_id_before_anything_is_opened` | stdlib/perception | Yes | Denylist content/pin mismatch (LF-normalized pin); CRLF: no |

Reproduce with `verify_baseline.py --root . --nodes-json stdlib-failure-nodes.json` in the isolated stdlib environment, and the corresponding perception JSON in the perception environment. Use `perception-order-failure-nodes.json` for the four order-dependent cases. All paths are packet-relative for these JSON arguments. No real pad, desktop input, GPU job or corpus opt-in is involved.
