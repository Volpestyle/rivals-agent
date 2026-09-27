# Six-app shared-guard shakedown

Lead authorized execution after modal_guard v1.0.2 LAND and installed acceptance,
within the existing $24 campaign / $3 shakedown allocations. Acceptance verified on
Mac through `release.reviewed()`: receipt SHA256
`72f392278527f38332c3a74b30f388fc3ab683f6c870faccf75ab8df3f8310ec`.
Release `732dc08f9d0351b3a601a0a613dbc31f5c2476b6eaddc8cb49e1575d004b78ce`,
commit `c6004073f2bcefce006f28422b42170442ca8b60`.

Workload source **3902167**: `policy.range_bc.spatial_yaw_probe.run_probe` takes
`root` plus keyword `slot` (1..6), `input_spec`, `input_spec_sha256`, `seconds=110`.
Artifacts: `probe.json`, `probe-yaw.pt`. The guard owns stage completion/hash receipts.
Input-spec SHA256 `c7061ddbe65a4d13dbb1cec6876b7df4fc6e20c84ced4bb5ea7d724c8025fe2d`.

The workload reads and hashes only global/crop byte blocks for two already-eligible
TRAIN frames (original cache positions 7/8, session 20260923T051828-422Z-33696-1).
Their eligibility and source identity come from the retained encoder feature receipt
`1fa3bc21adf5f829ad4cd4a2c899944dd56d78dd6950de34421ab7b3c3d3f465`.
A small, niced Mac read generated these four reference block hashes; it did not run
extraction, decode video, fit, or occupy the heavy-job queue. No sealed source was read.

Both grids run the actual frozen-base/yaw code with **synthetic tokens and an untrained
base**, at batch 8 and window 96 on L40S. Each runs at least four optimizer updates,
then continues for a 110-second workload interval. It asserts exact action/pitch logits,
unchanged frozen tensors and no base gradients, writes/reloads the yaw state, and
reports timing and memory. These are plumbing checks, not a scientific experiment,
vision evaluation, cache throughput benchmark, or full-fit p95 observation.

The intended fixed bootstrap envelope is startup 300 s, work 180 s, cleanup 120 s,
six named slots, .05 USD overhead per slot: **$2.884404 reserved**, below $3.
The 180 s work bound contains imports/checks, 110 s workload and serialization.
All six must show an overlapping active-work interval: max(start) < min(end).
Six successful sequential probes do not satisfy this check. A failure is reported;
no slot is recycled and there is no automatic retry or fallback launcher.

Input volume: `rivals-explore-chunks-20260927`, `vo-K5FeMtunP9vFG2mx8HVn0p`, read-only.
Six fresh empty output volumes were created after authenticated name-absence checks:

| Slot | Volume name | ID |
|---|---|---|
| 1 | rivals-yaw-probe-20260927-01-outputs | vo-JtNIL2hBuJ0chN1ivHaHvO |
| 2 | rivals-yaw-probe-20260927-02-outputs | vo-7keXkVX85cPjrXfkpaRbPu |
| 3 | rivals-yaw-probe-20260927-03-outputs | vo-lPqlhxx4pXb6EQdvLPvppV |
| 4 | rivals-yaw-probe-20260927-04-outputs | vo-fD4OBnkoMIWOdfOSACNmn6 |
| 5 | rivals-yaw-probe-20260927-05-outputs | vo-U0WUaIRo6SczX7SwQ9qF7m |
| 6 | rivals-yaw-probe-20260927-06-outputs | vo-DiruadWnofHeucZjXZuGhL |

Receipt on Mac: `/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/probe-volumes.json`.
No AppCreate was issued during that preparation. No existing volume was mutated.

modal-port owns `guard-integration/`, including exact source closure/spec assembly.
It is proving the accepted runner's native SDK source mount: existing immutable base
image `im-FNjy4v5u4XYF29SBGvT0KD` plus content-addressed cloud package containing the
exact guard, RELEASE.json and hash-checked workload bridge/payload. This avoids a
separate unguarded builder app. It is **not** described as a newly baked image.
The final integration receipt must prove the actual mounted inventory; assertions
about a desired package list are not enough.

`collect_probe.py` verifies guard terminal proof, collects only hash-pinned expected
artifacts, reads creation events without changing the journal and checks six-way
overlap. Preserve incomplete results and their remaining allowances. Report the
shakedown verdict before fits; full fits still wait for verified dual-grid caches
and their separately funded finite bootstrap envelope. IDM retains the Mac slot.
