# Bounded unchanged-reader cost check

Root CPU measurement on three already-inspected saved runtime JPEGs, eight repeated calls each. No model, Loop, Controller, capture, pad or GPU use. Existing OpenCV4.13.0 reported32 threads; the original live process thread counts were not recorded.

| Saved frame | Full HUD median ms | All reflex-box tags median ms |
| --- | ---: | ---: |
| 000066.jpg | 13.338 | 7.166 |
| 000069.jpg | 13.508 | 7.149 |
| 000071.jpg | 13.642 | 6.918 |

This establishes about20 ms of sequential reader work on these saved images. JPEG compression and reflex-row boxes differ from the original decision inputs; concurrent live contention and the full40?48 ms decision cost are not reproduced. No direct attribution to Torch, queue delay or a specific thread configuration follows. Preserve actual stage timestamps in the next caller rather than subtracting this offline cost from live totals.

The script temporarily wraps subreaders in its own process to time complete calls, then restores them. It never edits production modules. Full component times, original decoded values, image hashes and code hash are retained in report.json; outputs are diagnostic, not new labels.
