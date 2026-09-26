**Verdict: FIX. The v2 seal, preserved freezes, consumer pins, unchanged tally, requested registry rows and calibration reproduction pass. Acceptance (3) is incomplete: the registry still accepts sealed identities outside their authorized category in the two cases below. No evidence of current corpus contamination was found.**

Independent reviewer: admission-review (Codex), VUH-1359, 2026-09-26T17:13:07.908593+00:00. Reviewed the uncommitted shared-checkout change described in `admission-test-take-20260926.md` (SHA256 `f58cfd10c3a606472b554cc272c92b010b1742453567ec884916d3a5ca782b86`) and its brief/addendum (`9c579713da57514fef0b38122234d40c0cd36d3f6eeffebfe47ae6468daf0a14`). No production files edited and no commits made.

## Blocking findings

**B1 — A denylisted test identity can enter an excluded list.** `agent/human_intake.py:544` checks only `doc['sessions']`. `agent/human_demos.py:236` checks excluded rows against the rows present in that same registry, without the independent denylist. A synthetic registry containing one harmless train row and an `evaluation_sessions` row naming **153835** is accepted by `check_registry(..., denylist=v2)`. The same happens in `calibration_sessions`. I reproduced acceptance by session ID, original media path and media hash separately: **six accepted cases**. The sealed test row was absent from these synthetic registries. No source content was opened.

This does not make excluded rows into train placements, but it defeats the claim that the independent seal refuses any registry use outside test, and permits sealed footage to be presented as reader-development or calibration input. The present canonical registry has the correct test row and its ordinary collision checks help; the independent denylist must also protect a partial, replaced or alternate registry.

Required correction: apply the independent seal to all supported registry lists before returning placements. Reject test identities in calibration/evaluation lists by ID, path and hash. Add positive controls for unrelated excluded rows and regressions for these six cases. A test should fail when that validation is removed.

**B2 — Known gate2 identity can be relabeled train when the sealed row is absent.** The independent v2 denylist contains test identities only. A synthetic train row naming the pair-2 live recording **20260926T002851-659Z-63684-3** is accepted by `check_registry`, separately by its ID, its original path and its media hash: **three accepted cases**. A lone train row with the known ID, an unrelated group/path and no `sealed` field is enough. These tests exercise registry validation only; no artifact body, logger folder or video was opened.

Keeping the original gate2 row and adding a train alias by path or hash **does** fail with media split leakage. Existing fit-reader tests also correctly refuse artifacts that still declare `split='gate2'`. Those protections do not satisfy the specifically requested identity check when a registry replaces the gate2 placement with train. This is an existing boundary limitation exposed by the requested check, not a regression introduced by the pin substitutions.

Required correction: enforce authoritative sealed split membership independently of the candidate registry (including allowed split `gate2`, rather than treating gate2 as test). Cover ID/path/hash attempts to reclassify each sealed kind, plus valid test/gate2 controls. Keep this separate from artifact-header refusal. The new v2 test file currently tests the two new **test** identities, including attempts to label them gate2; that is not a test of a **gate2** identity relabeled train.

## Checks that pass

| Requested check | Independent result |
|---|---|
| v2 superset; v1 unchanged | PASS. v1 raw SHA256 `57cfe01f29f6e1a55293f968ec697aa293c268bd87d7cf247ef648279e2fba7c`, bytes exactly equal `git show HEAD:data/human/sealed-denylist.json`. v2 `aab214ebe1290f02428ac1e39617f1378b0f1b1f69c42582add38dbb4ee70e27`, old row unchanged and first; both additions carry ID/path/hash/date/reason. Supersedes points to v1's correct pin. |
| All 11 admitted freezes | PASS. Real `check_freeze` returned an empty mismatch list for every admitted session, with chunked hash reads. Results saved per session in `audit.json`. No freeze rewritten. |
| All 7 direct consumers | PASS. `idm_targets`, `range_bc/steps`, `transcode_recording`, `assemble_session`, `intake_session`, `relocate_session`, `tally` all use the v2 path and exact pin. Intake evidence records the v2 path. The cache/train/verify/IDM-decode defaults follow the shared pin. Historical snapshots intentionally retain their old bytes. |
| New test identities refused outside test | PASS for split rows. ID/path/hash crossed with train/val/gate2 and both new identities: all 18 cases reject. Their test placements remain valid. B1 covers the missing excluded-list check. |
| Guard-removal test | PASS. Removing only the denylist refusal in an in-memory copy of `check_registry` makes all 18 rejection tests fail (`DID NOT RAISE`); no source edit. |
| Tally | PASS. Recomputed tally equals saved tally; **180.56902055553334 train minutes in 10 sessions**, **15.58458271005 val minutes in 1 session**. Rounded headline **180.57 / 15.58**, unchanged. Train/val registry rows equal HEAD exactly. |
| Fit cohort | PASS. v2-backed reader loads the same 11 step tables, 10 train and 1 val. No corpus test suite was invoked. |
| Gate2 pair 2 | PASS as registered: whole `19-28-51.mkv`, both Thebes and Hall of Djalia, and `10-57-37.mkv` share `gate2-20260925-hall-of-djalia-1949`, sealed true. Live row removed from `evaluation_sessions`; no window restriction. |
| Heart of Heaven | PASS: replay **161008** is `evaluation_sessions/reader_development`, paired to live **010620** (`20-06-20`), which is already reader_development in HEAD. Neither is a split row. The hand-back correctly corrects the addendum's stale match_dev label. |
| Left calibration / false start | PASS as registered: **162648** appears only in calibration_sessions; **162623** is absent from split/calibration/evaluation rows and appears as not_range in the tally. |

The live registry validates with **20 split rows: 12 train, 1 val, 3 test, 4 gate2**. The 12 registered train rows include held, unadmitted sessions; only 10 count. Today's test rows are sealed in the tally; gate2, reader development, calibration and the false start contribute no train/val minutes.

Focused tests: **163 passed, 1 skipped** across `test_sealed_denylist_v2.py`, `test_gate2_split.py`, `test_range_bc.py`, `test_recording_watch.py`. The mutation run reports **18 failed, 5 deselected**, the expected outcome when the test-denylist guard is removed. Corpus tests were not enabled. Synthetic failure demonstrations are recorded in `audit.json` and reproducible from the registry-only section of `audit.py`.

## Left-turn calibration reproduction

Re-derived `plan.json` from the authorized **162648** input log, then independently decoded that calibration alone with the frozen 030045 measurement method, CPU/four threads/below-normal priority and the OBS/Marvel guard. The plan and complete result object **exactly equal** the owner's records, including `controls_ok=false`. There was one review decoder at a time. I visually inspected the four turn-endpoint stills; the hero and stationary range landmarks agree with a stationary turn measurement. Earlier 030045 method validation remains unchanged evidence; it was not decoded again.

| Counts/s | Counts between endpoint frames | Counts per 360 | Difference from 0.0330738 | ±0.08% |
|---:|---:|---:|---:|---|
| 1148 | -10884 | 10884.60239844 | +0.0013436832% | pass |
| 2111 | -10865 | 10885.42455271 | -0.0062092176% | pass |
| 4051 | -10915 | 10880.55746119 | +0.0385200100% | pass |

Mean gain **0.033077510271320144 degrees/count**, **+0.011218158542836143%** versus calibration. The leftward formula is correctly `360 - estimator_yaw`, with positive count magnitude in the denominator. These measurements support direction symmetry within the tested gain tolerance and speeds; they are not a separate pitch calibration.

**F1 — non-blocking wording correction:** only **one** of the two pitch-sweep controls fails the script's strict `abs(yaw)<0.05` criterion. The -0.1338518672-degree control fails; +0.0378813376 degrees passes. Four controls around yaw turns have magnitudes at most 0.0013594 degrees and 1,279–1,341 inliers. The hand-back and calibration note attribute `controls_ok=false` to both pitch-sweep controls; make the distinction precise. The yaw estimates reproduce and are unaffected.

Calibration pins verified: `calibration.json` `3ba8e40c55437a23c72e205c806b6273ee7bda59338fd0daf0a309a03c507a96`, `turncal.json` `beea4e04a2318be49d7fb97c37bdcbe27eb69f827ec4d71fdaf86f0848cb2d11`, `plan.json` `c54e6201b0b368d79e988e621eeaa8a2eb0b4188c7b264ee4b41a35ed38d03e6`. All calibration record file pins match.

## Reviewer resource incident and scope

At approximately 12:07–12:09, reviewer PID **116676** violated the memory budget. My broad hand-back table parser mistakenly included the **13,624,013,936-byte test MKV** among text-pin inputs. It called `Path.read_bytes()` and then `.replace(b'\r\n', b'\n')`, allocating the original video plus another large binary copy. The lead observed about **26 GB private memory**, commit charge **54/56 GB** and **112 MB free RAM**, and interrupted the run. This was my implementation error; no claim of compliance with the 3 GB limit is made for that process.

It was hashing bytes, not decoding frames. The test/153812 logger folders were never opened or listed, and no test/153812 frames were decoded or viewed. The completed raw test-video SHA256 matches **58ddc1de73e0bcfbbe3e21076c0edc7d54c3345edd48942386ae723f4fe76310**. The earlier `pins.json` LF-normalized binary hash is an invalid comparison, not evidence of media corruption; `final-checks.json` explicitly corrects its interpretation. The held Recycle Bin video's hash is owner evidence, not independently recomputed in this review.

By the time my stop command reached PID 116676 it had already exited. I stopped remaining owned review workers and closed their tool sessions. Completed results were reused; no corpus checks, whole-video hash or decode was rerun. Subsequent final checks ran sequentially with a **hard Windows job per-process commit limit of 2 GiB**, bounded text reads below 16 MiB and 4 MiB streaming hash blocks. No whole video or NPZ was loaded after the interruption.

No game input, external publication, Mac work, commits or checkout/session edits. Only review scratch and this report were written. The protected logger folders and sealed frames stayed closed. The current change should be returned to admission-owner for B1/B2, then independently re-reviewed on that delta.

## Evidence

Scratch directory: `review-test-take-work/` beside this report. Key artifacts:

| Artifact | SHA256 |
|---|---|
| audit.json | `cdec9d35d3b6078d6abe578747eaf84693645ba9fdf6ba2c869213cd6eff07ec` |
| audit.py | `e6198c0d23c3180a11013a02e06893f16dae0f3974827f2d81340ee0d90e383f` |
| tests.txt | `1c03a1faef77a39b58da4e7fecc60480e067027543fedb35c2b3e1f4fc0ae6fb` |
| mutation.txt | `af0776d258dfcad20094326d11e84ce773bfbc8671c4cbf530c8a9023366b969` |
| test_runner.py | `7cd946a0d3adef7c67cb2d54d7399fc85488375b4871da048de4b688b090178c` |
| pins.json | `6a64cef185f68993482ebac9dda9297de29a27edb30c462fac620bfe1e8654ff` |
| final-checks.json | `1ba7ad0941df7f6c1a047c1f8ec9ec0b7999c775a99b3e79823307d0b01ff42d` |
| final_checks.py | `371adccd8d7e7331ec37167fa2c216443f98820391af5dbb0a0bd2af035ad0e9` |
| cal/plan.json | `c54e6201b0b368d79e988e621eeaa8a2eb0b4188c7b264ee4b41a35ed38d03e6` |
| cal/turncal.json | `beea4e04a2318be49d7fb97c37bdcbe27eb69f827ec4d71fdaf86f0848cb2d11` |
| guarded_turncal.py | `4835a29673dc1cc426ba918a831144a6e3058b699e8a5c65566112eb4aa73588` |
| live_guard.py | `377510729bb74badc78465d43b6c689e88b37ed4084bd6882ae0eb16076c515c` |

Reviewed production LF pins are recorded in `final-checks.json`; all listed text-file pins matched the owner hand-back at final verification.
