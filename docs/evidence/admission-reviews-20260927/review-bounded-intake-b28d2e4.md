# bd95447 + b28d2e4 changed-boundary review — LAND WITH FIXES

Independent fit-review (Codex), 2026-09-27. Scope: bounded exact-PTS decoding, streamed proofs/review writes, the new snapshot's DiskFrames spool and two decoder threads, pre-launch guards and the owning PowerShell watchdog. **One nonblocking fix-forward finding; no demonstrated data/numerical or sealed-access regression.** Native video parity and operational resource peaks remain pending the producer's decoder slot; this review does not claim them.

## F1 — watchdog abandons descendants when its parent exits

`data/admission-codex/run_intake.ps1:33` monitors only while `$p.HasExited` is false. In the catch block at lines 58-60, tree termination also runs only when the parent is still alive. A previously observed ffmpeg or worker descendant may therefore survive its parent's exit without further game/RAM monitoring or cleanup. An intake/scan exception with an outstanding ffmpeg pipe is a relevant failure path; the spool's exclusive directory creation can also fail after scan has already launched ffmpeg.

Independent synthetic reproduction executed the committed wrapper's actual `$peak`/try/catch/finally block with process enumeration, sleeping, receipt writes and taskkill mocked. First poll observed root PID 100 and child PID 101; Refresh then reported root exited while child stayed live. With root exit 1, the wrapper recorded the intake failure but issued zero kills; with root exit 0, it recorded no failure and issued zero kills. Both recorded the child's observed 20,000,000-byte peak and then abandoned it. No real process was launched or stopped in this probe.

Fix forward: keep ownership of observed descendants through parent exit (including creation-time identity to avoid PID-reuse mistakes), and reconcile/terminate surviving owned descendants on both failure and unexpected parent completion. A Windows Job Object with kill-on-close is another suitable implementation. Mark cleanup failures explicitly; do not report done while owned descendants remain. Add parent-exits-with-live-child tests for both exit codes, and a control proving unrelated processes are untouched. This is a local resource/teardown gap, not a demonstrated wrong-data, changed-numerics or cloud-hard-cap finding; under the supplied rule it is LAND WITH FIXES.

## Passing evidence

- Independently verified all 140 new snapshot files against their manifest's SHA256 and size. Verified the predecessor manifest pin. Exactly one file differs from `code-snapshot-f8fd92c-08c36e68`: the stated regime-scan/scan.py. The other 139 compare byte-identical. No frozen predecessor was changed by this review.
- The scan delta changes storage from a native-array list to ordered individual NPY files with allow_pickle=False, then replays them through the unchanged slot_mapping and per-frame passes. Successful cleanup removes those files. Two independent synthetic round-trip passes preserved shape, dtype, order and every value. Existing fixture pixel/mapping parity is inherited producer evidence.
- The decode delta retains exact PTS selection, sorted/deduplicated targets and per-window byte-count refusal. Independent lazy-decoder probes produced windows [8,8,2], ordered identical pixel values and exactly three pre-window guard calls. Creating the generator decoded nothing. The two-thread command was checked. NumPy views retain the backing raw bytes safely; consumers reduce each frame to scalar proof/receipt data instead of retaining all arrays.
- Static review of streamed proof and review writes finds the same frame selection, filenames, hashing, resize/JPEG settings, guard calls and per-segment ordering for the existing one-to-one timestamp mapping. No reader, vote threshold, split selection or label rule changed.
- Independent mocked guards: exactly 2 GiB free is allowed; one byte less refuses; failed memory query refuses; Marvel process and obs64 each refuse. A blocked _scan launches no child. No game input or game process was touched.
- Wrapper scope is restricted to six named night sessions and vote/scan/regime/motor/propose/evidence. Its normal live-parent process walk is descendant-based, and the 2.8-billion-byte threshold is per process as documented. No unrelated process was targeted by this review.

## Pins and limits

Current files match b28d2e4 after LF normalization. Raw SHA256:

- intake_session.py: `3bfe623e866d26462153f8241f5daaa5908f8359a1877d7710b1b91ab4107cf3`
- run_intake.ps1: `fa759bb19bd27d97cbf9999c139164a3b411bc8e0cff90f92085bcd8b928a8ba`
- test_intake_streaming.py: `52289b13143f2b0327cc386a85de00150e443c7f94d5c6855efe64ef9130e507`
- bounded snapshot manifest: `f557495b3c2723c4577c6ca570af5d423abeedd5df64b948ca9a47b8d3781260`
- bounded scan.py: `84365dd5392b5e90109111930cf200a17eb1296dd5e2d6e5674e38a4c6bc93ae`

The producer's 30 focused tests and native JPEG-fixture mapping parity are reused, not claimed as independently rerun. The private fit-review environment lacks cv2; independent probes used stdlib/NumPy and mocked process boundaries. No video decode, slot acquisition, training, admission assembly, sealed payload read, receipt acceptance, owner-path edit, commit or real process termination occurred. The producer reports no own decode yet. Native video pixel parity after changed seek-window partitioning and measured full-run peaks still need the producer's operational evidence when its slot is available.
