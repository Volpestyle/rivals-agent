# EXPLORATORY dropout launcher shakedown: PASS

All three seed-specific synthetic workers completed on the accepted v1.0.5 guard,
with **25.758113 seconds of actual three-way work overlap**. Each verified its
frozen base, unchanged action/pitch outputs and gradients, enabled hidden dropout
while training and disabled it for evaluation, and round-tripped the yaw checkpoint.
This exercises the launch path; repeated synthetic tokens establish neither real-data
I/O throughput nor full-fit p95.

All three apps have validated terminal teardown proofs and zero active holds.
Conservative settled bounds: seed 1 $0.103155, seed 2 $0.092766, seed 3 $0.077333;
**total $0.273254**. These are lane bounds, not a provider balance.

AppCreates, one RPC each, UTC 2026-09-28:

| Seed | App | Creation event |
|---|---|---|
| 3 | ap-6Dl7cjGkqqQ4f3TPurjS92 | 03:39:45.272410 |
| 2 | ap-CjWEJxyEcdzRl91dqM3KDs | 03:40:02.106513 |
| 1 | ap-QVeLevoayFdWqPzS95UUaK | 03:40:18.869555 |

The collector authenticated stage identity, hashes, output volume IDs, accepted
release and teardown proof. Collection SHA-256:
`ad413a1a662371ec16f541732de0988a1cb789bbc3589bebf56d9f6a9bc5260c`.
Collector SHA-256:
`5e02cdafcdc8c9a8f85484a84a1d730d4a6d2ec6e6fe7f1f8e7caf2609b4de11`.
Transferred raw collection/launch archive SHA-256:
`21c97f4dba4eda5de5cf2a78c258f48f0865b14e839b94e3dc6c7d5cfd315c66`.

Lead received PASS before the fits. IDM recovery02 then created at
03:44:29.827252 and released its window. The three approved fits launched
afterward under packet commit a31a446, with $4.931142 total reserved.
Probe settled plus fit holds = $5.204396, within the new $6.25 campaign cap.
The driver more conservatively counts the full original probe holds, yielding
$6.154122. No prior yaw holds remain; prior yaw settlement is $18.666509.

The lead explicitly retained the measured 4x4 direct-Volume reader to match
the completed control (~17.7 updates/s). The local-disk rule concerns unmeasured
or large random-read workloads; this is a documented measured-path exception.
No old input, output or frozen packet was modified.
