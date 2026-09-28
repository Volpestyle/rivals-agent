# Dropout fits launched, 2026-09-28 03:45 UTC

This is a launch record, not a scientific result. The three seed-specific fits use
the frozen fit-01 packet from a31a446, the accepted v1.0.5 release and the unchanged
image/source closure. The preceding shakedown passed and settled at $0.273254
(5fca492). IDM's recovery02 creation was 03:44:29.827252 UTC; its window was released
before these creates.

| Seed | App | Single-RPC creation, UTC | Work stop, UTC |
|---|---|---|---|
| 1 | ap-xp8Zo6tUkkjrD6UCR4zr9T | 03:45:35.117268 | 04:20:32.787096 |
| 3 | ap-0fRwzgw3rUuKCyKBBSVdYG | 03:45:51.793272 | 04:20:32.796182 |
| 2 | ap-Aed2egLWCTD3A4iYd6zOeq | 03:46:08.643639 | 04:20:32.792776 |

The parent is Mac PID 26223, running niced, with logs under
`/Users/james/dev/range-bc-data/explore/nitrogen-yaw-dropout-20260928/fit-launch-01`.
The guard owns deadlines, teardown and settlement. Each hold is $1.643714;
all three plus settled probes are $5.204396, below the new $6.25 hard cap.
Counting original probe holds instead gives the driver's stricter $6.154122.
No retries or new attempts are authorized.

At 03:51:08 UTC the last 150–180 s measured rates were 20.094, 17.293 and 17.000
updates/s for seeds 1/2/3. Training-only projected endpoints were 04:00:16,
04:02:42 and 04:02:48. Prior control receipts bound all time outside the fit
(startup, verification, evaluation, teardown together) at 324.19 s maximum;
adding that entire amount again yields latest projected completion ~04:08:13,
over 12 min before work stop. This is a projection from current rates and three
historical controls, not a p95 guarantee. No guard was extended.

The lead explicitly approved retaining the measured 4x4 direct-Volume reader,
matching the completed control. The new local-disk rule targets unmeasured or
large random-read workloads. Nothing about seeds, order, epoch endpoint, labels,
base weights, cutoffs or evaluation changes.

Collection after terminal receipts:

```sh
cd /Users/james/dev/range-bc-data/explore/nitrogen-yaw-dropout-20260928/fit-01/code
PYTHONPATH=. /Users/james/.local/share/uv/tools/modal/bin/python ../../collect-final.py .. ../../fit-results-01
```

The collector is pinned at SHA-256
`5e02cdafcdc8c9a8f85484a84a1d730d4a6d2ec6e6fe7f1f8e7caf2609b4de11`.
It authenticates terminal proofs, stages, output IDs and final artifacts, and
retains fit/status.json via two stable reads. Transfer only that completed packet,
hash-check it, then run report.py against grid4-results-02 and fit-curves-20260928/grid4.
The report compares fixed epoch 26, preserves all 26 curve points, and refuses
mismatched recipes, base evaluations, cutoffs or action/pitch retention.

Report validation: 10 synthetic pairing tests pass. A schema dry-run using the
completed control duplicated as a synthetic candidate passed all three seed
pairings and 156 curve rows. This dry-run used no dropout result.
The schema check found and fixed the head-parameter field's nesting under
recipe.encoder_explore before collection.

The reused metadata-only completion watcher reads final host receipts, writes job
status and wakes explore-policy via Herdr. It does not read metrics or mutate the
cloud or ledger. A failure or missing terminal receipts triggers owner inspection;
it grants no retry authority. The owner still must collect, report and settle.
