# Local-disk 8×8 timing probe — EXPLORATORY

The probe completed successfully on the pinned CUDA/L40S stack. Local disk delivered **4.012709 updates/s**, compared with the prior volume-backed arms' final sustained **1.058824–1.655629/s**. The second-epoch sample delivered **4.191938/s**. This is a practical speedup measurement from one app, not a full-fit p95 or evidence that I/O was the only bottleneck.

It used the actual shuffled `SpatialBatches` path, seed 1, window 96, stride 64, batch 8 and the unchanged 26-epoch/15,288-update learning-rate schedule. The first 588 batches traversed every one of the 4,697 TRAIN windows exactly once; another 128 batches exercised the second epoch. All ten sessions' 4×4 and 8×8 arrays were copied, source-hashed and independently destination-hashed: 107,013,598,154 bytes including labels and receipts, with 99.18 GiB of feature arrays. The sample therefore did not reuse a small RAM-resident batch. Steady timing excludes the first 32 updates, the epoch boundary and the final snapshot.

| Component | Seconds |
|---|---:|
| Copy plus source/destination hash | 283.977 |
| Normal dataset load and verification | 191.238 |
| 15,288 steps projected at the slower measured rate | 3,809.895 |
| 26 epoch boundaries, removing one included step each | 240.714 |
| Actual final evaluator | 15.888 |
| Additional evaluation reload allowance (full training load time) | 191.238 |
| Model setup and volume checkpoint allowance | 120.000 |
| Total projected work | **4,852.949 (80.9 min)** |

The lead-approved work envelope is 6,300 seconds, leaving 1,447 seconds (29.8%) beyond this projection, plus 300 seconds startup and 120 seconds cleanup. The proposed local adapter must keep both fit and evaluation on the verified local cache. Volume checkpoint writes were not measured by this probe (its diagnostic checkpoint was ephemeral); the explicit allowance and work margin cover that uncertainty, but do not guarantee completion. Three concurrent copies may differ from this single-app measurement. Each fresh fit must restart from its original frozen base; no partial-fit resume is permitted.

At the accepted all-resource rate and $0.05 overhead, each proposed hold is **$4.874214**, three **$14.622642**. Settled campaign spend is **$10.052912**, with **zero outstanding yaw holds** at collection; settled plus all three proposed holds is **$24.675554**, inside the lead-amended $25 cap. These are conservative lane accounting bounds, not a provider balance. The lead first approved reallocating the remaining budget within $24, then explicitly raised the campaign cap by $1 to $25 and work from 5,500 to 6,300 seconds to accommodate variance across containers. The three fresh fits are authorized; warn at $24. The workspace $100 cap is unchanged. `report.py` reproduces the timing and arithmetic.

App `ap-2tMjxFgdV6CM32Uitcn7G1` was created by one RPC at 2026-09-28 01:29:29.699046 UTC. The accepted v1.0.4 guard settled it at **$0.547570** with validated terminal/zero-container proof. The collector authenticated the completed stage identity and both artifact hashes before downloading them. `probe.json` SHA-256 is `4211b09ff07dc5981187d547bf8c66e1157c1b19110e5b962d9af6326755f7a0`; `copy.json` is `d98a3912cc14e5b83147600c9451a23f5763441f5616123b85ad85a71c81f07d`. Raw artifacts and teardown receipts are in `collected/`.

The diagnostic weights were partial, stayed on ephemeral disk and were never retained or used for a scientific comparison. The actual evaluator was timed, then its metrics discarded. The completed 4×4 result remains negative versus the frozen base (mean yaw MAE 1.908168 vs 1.772851; zero 1.735184), with exact action/pitch retention; see `../grid4-results-02/report.md`. Incomplete 8×8 fits neither support nor reject finer features. No grid comparison is claimed.
