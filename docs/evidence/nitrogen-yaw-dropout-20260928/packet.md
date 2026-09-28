# Frozen launch closure — no image build or feature extraction

Science source `51db7ea` (production dropout from `602b32a`, probe timing refinement).
Guard `7ead52f0845fb83b4db0ebf9fc274c6a5adb760b`, release
`4a4d57d5ec2b97566b5bc59f212c8f4b9357198fe0eb7270874902079bdd8af6`.
Installed reviewer receipt SHA `91aaa8c36d02e5aab84a4bc92b05d6a62b4feacff18b1a0ab90f3af68dcbfdc5`.
Installed original lead receipt SHA `541dc7f88085ccb05ef5846d1ecf4ace9376d782bf637e2d758cfcf948dd4737`;
adjacent correction SHA `095cbbec3132c9b6c3519796c3d3d8998172aeb8fd5ca48665c466a9487f6d84`
records prior yaw settled18.666509, no active holds, new6.25, max24.916509.

Mac root `/Users/james/dev/range-bc-data/explore/nitrogen-yaw-dropout-20260928`.
Fresh packets `probe-01` and `fit-01`; both use cwd/PYTHONPATH=`<packet>/code`
and SDK Python `/Users/james/.local/share/uv/tools/modal/bin/python`.
Native SDK1.5.5 mount proofs PASS for all106 cloud files, including exact guard
package+RELEASE.json and workload source. Identical source inventory SHA
`d7358e063c2da613ab4f039d25f18443856989dedba927c5d1d2fc5641fe2568`.
The immutable base image remains `im-FNjy4v5u4XYF29SBGvT0KD`, torch2.14.0+cu130 /
CUDA13. This is an existing image plus verified immutable source mount, not a
new baked image. Input volume `vo-ujapSF2Htu9GfKAXEyXH70` is read-only.

Transferred packet archive SHAs:
- probe `28c9589c7ac7c4f43461387631b7893b9b5175bb71d50ea7dcef7deee3bc47aa`
- fit `4975fb52c67fb2ebd2b318dda32c0a61857987d151e2adbc7f6763a4e32f431b`

The three probe and three fit outputs are fresh, with IDs bound in their specs.
No existing app/volume was modified. AppCreate still awaits IDM's exact first
creation/release and global15s spacing. Driver invokes accepted isolated_batch;
no wrapper retries. Fits require all three probes COMPLETE, proven terminal,
collected/hash-verified and showing actual three-way work overlap. Report that
result before fits. Short synthetic probes make no full-fit p95 claim.

`collect.py` authenticates final stage/teardown/source identity and hashes.
For fits it also double-reads final status and pins its 26-epoch curve as
supplementary collection evidence. Partial fits cannot produce a scientific
report. Full $6.154122 holds are counted against $6.25 even if probe actuals
settle lower; no recycled allowance or extra attempts.
