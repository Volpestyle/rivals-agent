# VUH-1384 FPS startup repair

Owner: live-fps. Consumer/integration owner: live-loop. Authorized files are
`scripts/measure_inference_fps.py`, its tests, this new lane and the
[repair evidence](../evidence/live-fps-repair-20260927/README.md). The original
live-fps lane and sitting failure evidence remain unchanged. No actuator,
desktop operation, video decode, training or sealed-source access was performed.

The runner had no forward before B. Saved-PNG CUDA replay reproduced a 774.9 ms
cold forward against its 250 ms steady deadline, followed by 27.5–30.9 ms warm
forwards. After 40.003 s without inference, all six prediction ages remained
25.1–34.0 ms. This supports the cold-start repair without attributing the original
unfinished forward to a particular internal kernel or preprocessing stage.

The earlier startup stale proof was 128.0 ms, including 32.9 ms capture and
95.1 ms proof/postcapture overhead. DXCAM-only causation is not established.
Priming now requires two fresh positive proofs; stale priming frames are
discarded, and steady freshness remains 100 ms. The same worker then performs
one cold prediction (5 s bound) plus three predictions under the unchanged
250 ms bound, within a 10 s total startup allowance. A1 begins only when ready.
Guards continue during warmup, outputs are discarded, and startup is excluded
from A/B/A phase clocks and manual overlay samples.

Owner verification: 51 CPU/fake tests passed in 3.77 s, guarded CPU native-PNG
replay passed, and the single explicitly authorized guarded CUDA replay exited
0 (`qualified_offline`), peak RSS 1.159 GB. Exact as-run sources, pinned failures,
timings and job receipts are in the packet. Qualified source SHA256:
`8a97a7604db9ede4cdc12835e879648cf4a11ef93f686e17031385e34b4f0b36`.
No independent review is required for this actuator-free measurement repair per
lead/James's rule. No Linear writes from this worker.

Ready for an explicitly authorized lead-driven retry, not a game-FPS result.
Acceptance still needs ready startup, all six timed intervals complete,
unchanged freshness/age guards, drained native evidence and manual FPS annotation.
No automatic retries or further GPU work are queued. Current GPU hold applies.
The named 195110 sealed-test video/logger/frames remain excluded from all access.
