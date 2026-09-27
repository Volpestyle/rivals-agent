# Probe3: accepted v1.0.4 native integration

Guard commit:80d944bd8732103f2de1ad67dd83c4009b6bb7f2.
Release:5c0e979227738363bfceaef792d9852d2578fcc149f77d2f9cde61510dc8a8fd.
Reviewer receipt installed exactly at the canonical reviews/<release>.json:
9c87e6f6e397252ae164a5482765d7f9c29ac0c87ca8f4eb9c5dec7e9089bd2d.
Lead record SHA05403dabddb1e425f9546690728d3e98721341db1686d50c563c30cbf3175587
records herdr-lead, 2026-09-27, workspace $100, explore $24 ($6 bootstrap / $18 fits),
IDM $7 and no extra budget. acceptance-installed.json records identity and
release.reviewed verification. No journal initialization or old packet changes.

## Exact packet

Mac runtime root:
/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/probe-03

assembly.json pins every absolute spec path and SHA256. All six fresh output
volumes and attempt names use yaw-probe3, supplied by explore-policy. The code
inventory SHA is ee4d6efcfcb2391cc56c39ff2fef3296744d959b8c665875da6301d7213b8858.
SDK1.5.5 native-mount proof validates all 82 cloud files, including RELEASE.json,
plus host-only scripts/job_status.py; every spec validates against its envelope.

The existing image im-FNjy4v5u4XYF29SBGvT0KD and native immutable source mount
remain the no-build route. Workload source is unchanged canonical Git3902167;
cloud.yaw_entry.run hashes the payload before invoking the original 110-second
policy.range_bc.spatial_yaw_probe.run_probe. Artifacts are probe.json/probe-yaw.pt.
The accepted v104 package includes WAL/read-only journal operations and Volume-safe
exclusive stage receipts, fixing both exact probe2 causes. No nested image build.

## Allocation and prior attempts

Each fixed exploratory envelope is startup300 / work180 / cleanup120 =600seconds.
Accepted guard rate and overhead derive $0.480734 per slot, $2.884404 for six.
The new finite campaign cap is $3.022522 = $6 minus $2.977478 consumed previously.
Cumulative reservation allocation is $5.861882. Actual charges and released
allowances are separate: settled attempts still consume their bootstrap slots.

The assembler checks all seven pinned prior settlement records from commits
6d22573/b184688 and the lead-approved campaign-ledger-a1.json at b184688. No old
IDs, outputs, runtime packets or allowances are reused. No full-fit p95 claim;
a timeout is incomplete. The three assembly tests and Ruff pass; native closure
proof is offline and does not establish a successful cloud shakedown.

## Owner execution

Explore-policy owns AppCreate coordination, the batch wrapper, logs, collection,
operational verdict and reconciliation. Use SDK Python
/Users/james/.local/share/uv/tools/modal/bin/python with both cwd and PYTHONPATH
set to <packet>/code. Import the unchanged shared isolated_batch there. Commands
come from assembly.json.specs:
[sys.executable, '-m', 'cloud.modal_guard', 'run', ref['path'], ref['sha256'], assembly['release_sha256']].
No Modal calls were made by the assembler/native source inspector. Modal-port
installed the accepted host receipt and told explore-policy to run after the lead's
direct instruction; it created no Apps, images or volumes and did not mutate the
workspace journal. The packet is an authorized launch input, not a result.

Transport archive16c3fb1942a83c0bbef69798c99b8106bcaee9307b13500e8f9f85e9995f82fa
was verified at both ends. The owner reports the actual shakedown outcome separately.
Lead's 18:30 CDT real-shakedown time-box remains in force.
