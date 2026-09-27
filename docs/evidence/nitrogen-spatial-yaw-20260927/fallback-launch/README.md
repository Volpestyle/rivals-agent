# Conditional yaw fallback

Prepared under the lead's 2026-09-27 time-box. **No launch performed.** If the
shared modal_guard has not passed a real shakedown by **18:30 CDT / 23:30 UTC**,
use the NitroGen confirm launcher lineage here. The driver refuses before that
time and requires an owner-written `activation.json` recording the missed gate
and completed Mac caches. IDM still owns the Mac until explicit release.

The budget's four functions are AST-identical to the reviewed confirm guard.
Only the cap is $2.50 and the input-volume name comes from the run configuration.
The AppCreate gate, identity/teardown/watchdog, mount checks and inventory adapter
are unchanged. Each of the six fits has a fresh output volume and app. All six
directories share one parent, so the original gate serializes them at >=15 s.
Other lanes still require explicit global window coordination: separate campaign
parents do not share this old lock. No automatic launch or retry is implemented.

Six fit caps total **$15** within the unchanged **$24** campaign cap, warning at
**$20**. The approved $3 shakedown allocation, $1 setup and $2 storage/tail fit
within that cap with $3 unallocated. These are subdivisions, not extra funding.
Prior attempts, actual charges and retained allowances must be included in the
bindings' `other_campaign_bound_usd`; `prepare.py` refuses a total above $24.
Before dispatch, report cumulative campaign exposure and notify the lead if
spend reaches $20. Never reset the campaign by switching launcher families.

`prepare.py` creates six immutable manifests from a completed code archive and
explicit volume/checkpoint/cutoff bindings. It requires the scientific
`policy.range_bc.spatial_yaw_train` callback and exact v1.0.2 stage-helper release
in the archive. It does not manufacture missing input IDs or data hashes. The
immutable base image remains `im-FNjy4v5u4XYF29SBGvT0KD` with the confirm stack.
There is no new image build.

The worker's stage order is `fit` then `evaluate`. A fit completion requires both
`epoch-26.pt` and `fit.json` to be committed and hash-bound before publishing the
completion receipt. On redelivery, complete verified fits are reused before
evaluation. Complete evaluation is replayed. A partial fit or evaluation, changed
identity, changed original deadline or corrupted artifact refuses; it never
refits. The accepted v1.0.2 `stages` helpers provide only these durability checks;
the shared paid runner and billing journal are not called by this fallback.

Owner verification: four CPU-only tests cover unchanged guard functions and
transport, the cap/runtime envelope, complete-fit/evaluation reuse, corruption
and partial-fit refusal. No corpus, GPU or cloud calls were used by the tests.

Still required for either launch route: IDM's explicit Mac release, completed
and verified dual-grid caches, the scientific fit/evaluation callback and its
tests, an immutable archive containing it, and fresh fit volume bindings. This
is tested fallback launch plumbing; it is not a claim that the yaw fits or their
input caches already exist. Original confirm packets are unchanged.

Example materialization (no paid calls):

```sh
python prepare.py --root /absolute/new/fallback-fits --archive /absolute/code.tar \
  --bindings /absolute/verified-fit-bindings.json --commit SOURCE_COMMIT
```

Each `bindings.runs` row names `grid`, `seed`, `output_volume`,
`output_volume_id`, `checkpoint_sha256` and `cutoff_sha256`, plus callback recipe
paths. Top-level bindings supply `input_volume`, `input_volume_id`,
`input_manifest_sha256` and `other_campaign_bound_usd`. Output names are exactly
`rivals-yaw-fallback-g{4|8}-s{1|2|3}-20260927-01-outputs`.
