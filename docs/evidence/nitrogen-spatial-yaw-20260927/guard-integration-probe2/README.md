# Fresh six-app probe2 integration

Exact accepted guard: commit19625721e676addc6ec760596f2b02b61d0cb9ba,
release a17c52ca2c7a65db58612e29f5dca737f4232afb3ec4d6216f624c214dcc7cfe.
The exact reviewer JSON is installed at the canonical reviews/<release>.json;
SHA34b14b302bea12c290354433454437049740f9b597b5b913fe87660d68f3d271.
The .lead.json records herdr-lead,2026-09-27, workspace100/explore24/IDM7,
no extra budget; SHAdab8c7fff9ab0fff4bc6c5f7ba9bf1a236c4f07a2e79cb25dd8b0299870e8cbc.
acceptance-installed.json records release.reviewed verification after authenticated
rivals/volpestyle identity check. No journal reinitialization or historical edit.

## Exact launch closure

Mac packet root:
/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/probe-02

assembly.json pins all six absolute spec paths and hashes; source-inventory.json
pins all83 code files (82cloud plus host-only scripts/job_status.py). Inventory SHA
7f3160033c8c6848956e35c1e0e6d484f528e731fe8d1beb2848a466e334b896.
All source bytes are canonical LF git blobs. Guard bytes are exactly the reviewed
release, with the unchanged workload at3902167. Bridge cloud.yaw_entry.run hashes
its manifest/payload before importing policy.range_bc.spatial_yaw_probe.run_probe.
Input volume, four-block spec and probe110s are unchanged. All output volumes,
attempts and app names use fresh yaw-probe2 identifiers supplied by explore-policy.

Existing image im-FNjy4v5u4XYF29SBGvT0KD plus immutable native source mount: no
Image.build, nested build or new image. native-mount-proof.json verifies the real
SDK1.5.5 entrypoint mount, every cloud file including RELEASE.json, all six final
specs and worker interface. The earlier base metadata proof remains unchanged.
Three assembler tests and Ruff pass. This is not a successful cloud run.

## Envelope and prior consumption

Each arm: startup210 / work180 / cleanup120 =510 seconds, L40S8CPU32GiB,
rate0.0007178888888888888888888888889 plus overhead0.05. Accepted cost() rounds
UP to0.416124 per arm, not0.416123. Six slots reserve2.496744. Original slot02
consumed0.480734 despite never-created settlement; cumulative2.977478 remains
under the original3 probe allocation. New campaign cap2.519266 explicitly reserves
only the original remaining allocation. No p95 claim, ID reuse or refund of a slot.

The assembler pins and checks the prior NEVER_CREATED reconciliation result from
commit6d22573 (SHA01c35d2c4ade17479baf79acc5cbceb6aa584d296d745ce8ef8dcdac03e0535d).
Actual per-slot startup includes pacing/SDK setup;135s after five nominal15s gaps
is arithmetic headroom, not an observed startup promise. Exceeding a clock leaves
an incomplete attempt; there are no automatic paid retries.

## Owner execution

Explore-policy owns the coordinated AppCreate window, wrapper, logs, collector
and operational verdict. Use the unchanged isolated_batch API and SDK Python:
/Users/james/.local/share/uv/tools/modal/bin/python.
Set parent cwd AND PYTHONPATH to <packet>/code; import shared isolated_batch there.
Build each command from assembly.json.specs:
[sys.executable, '-m', 'cloud.modal_guard', 'run', ref['path'], ref['sha256'], assembly['release_sha256']].
The source mount is derived from that isolated tree, so do not run from another
checkout or allow its cloud/scripts modules to shadow these files. The shared
guard owns billing coalescing, original deadlines, pacing, caffeinate, teardown
and settlement. Collector artifacts remain probe.json and probe-yaw.pt.

Modal-port created no Apps, images or volumes. Fresh packet transport is
fcef21beeed6c0a901670e704e2e098738dedea30dd16d77475277c7ecaafc64,
verified on both machines. Old integration/failure packets are untouched.
Lead's real-shakedown deadline remains18:30CDT; fallback selection is owner/lead's.
