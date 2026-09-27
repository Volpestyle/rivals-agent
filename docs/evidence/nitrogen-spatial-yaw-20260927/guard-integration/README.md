# Accepted guard integration for the six-app yaw shakedown

The v1.0.2 reviewer receipt is installed byte-exact on the Mac and verified by
release.reviewed. acceptance-installed.json records the canonical path/hash and
herdr-lead's 2026-09-27 acceptance in its companion .lead.json. Existing limits
remain $24 for explore (warning $20), $3 for these probes and $100 workspace.

## Existing image plus immutable source mount

The accepted runner has no build-only branch. SDK 1.5.5 Image.build requires an
already initialized App; its resolver sends ImageGetOrCreate with that App ID.
A nested build would therefore need separate bounded ownership, not an untracked
call inside a worker. This packet performs no build. Read-only ImageFromId
confirmed existing base im-FNjy4v5u4XYF29SBGvT0KD (Python 3.11.12, torch 2.14.0).
Image.hydrate is explicitly unsupported and was not used to create anything.

The unchanged run_arm defines execute_stages with SDK include_source=True. Its
native entrypoint mount includes the entire top-level cloud package, including
non-Python RELEASE.json. The isolated launch tree holds exact c6004073 guard bytes
plus cloud/yaw_entry.py and cloud/yaw_payload. Payload Python comes from a git
archive of 3902167; the four-block input-spec JSON is also from that commit. The
archive command sets core.autocrlf=false for that invocation, because plain Git
archive on this Windows checkout converted blobs to CRLF. All archived bytes are
now the requested canonical Git/LF pins. FrozenBaseYaw matches b2010fd exactly.
Only source code and the four-block specification travel in this tree, no dataset.

The bridge hashes every payload file before importing the pinned worker and then
calls policy.range_bc.spatial_yaw_probe.run_probe. It does not replace or modify
any shared guard code. Per-stage identity and output verification remain native
to the accepted runner. The worker reads only the named pre-existing input volume;
explore-policy created the six fresh -outputs volumes and supplied their IDs.

native-mount-proof.json is an offline check against installed SDK 1.5.5: exactly
82 expected cloud files, including every source hash and RELEASE.json, plus the
separate host-only scripts/job_status.py. It also verifies all six final specs and
the bridge/worker signature. There were zero AppCreates and image builds in this
check. A source mount is not a new baked image; the closure is explicitly the base
image ID plus immutable native source content. Image-build compute charge is $0;
mount/storage costs still fall under the existing campaign/workspace allowances.

## Final packet and invocation

Mac packet:
/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/probe-01/

- assembly.json: six absolute spec paths and SHA256 values.
- source-inventory.json: all 83 launch-tree files, SHA 0408a07c1d030f147c50c63be0ee26aa8de586ccce685450177c685a6fd83734.
- code/: exact isolated host and SDK source-mount tree.
- bootstrap.json: six immutable slots, startup 300 / work 180 / cleanup 120 seconds.
- specs/: output-volume IDs, immutable input bindings and stage parameters.

Stage module/function: cloud.yaw_entry.run. Worker: policy.range_bc.spatial_yaw_probe.run_probe.
Artifacts: probe.json and probe-yaw.pt. Native active-work interval 110 seconds,
within the 180 second function budget; actual six-way overlap is measured by the
owner's collector, never assumed. Each conservative hold is $0.480734; total is
$2.884404, under $3. This is launcher evidence, not full-fit p95 or a science result.

Recommended owner wrapper (no wrapper was executed by modal-port):

```python
import json, os, pathlib, sys
packet = pathlib.Path("/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/probe-01")
os.chdir(packet / "code")
os.environ["PYTHONPATH"] = str(packet / "code")
sys.path.insert(0, str(packet / "code"))
from cloud.modal_guard.runner import isolated_batch
assembly = json.loads((packet / "assembly.json").read_bytes())
commands = [[sys.executable, "-m", "cloud.modal_guard", "run", ref["path"],
             ref["sha256"], assembly["release_sha256"]] for ref in assembly["specs"]]
results = isolated_batch(commands)
```

Use /Users/james/.local/share/uv/tools/modal/bin/python (SDK 1.5.5) for that parent.
Both cwd and PYTHONPATH are intentional: scripts.job_status is a host import,
and every child/watchdog must find this exact guard tree. The accepted runner
handles fresh billing, reservation, native pacing, caffeinate, independent guard,
teardown and settlement. No journal reinitialization, retries, cap edits or new
spend guard are introduced here. The owner announces the coordinated AppCreate
window and owns logs/exit status/collection. Modal-port reserves no window.

## Checks and ownership

Three offline integration tests pass: exact canonical archive pins and unresolved
draft behavior; concrete bindings/unique specs and corruption/overwrite refusal;
corrupt bridge payload refusal before importing it. Ruff passes. Native Mac SDK
closure proof passes with no cloud execution. Base metadata lookup and receipt
installation were the only Modal-related preparation (lookup read-only; receipt
is host-local). No app creation, image build, dataset copy or volume write by this
lane. This directory is modal-port's; workload code and collector remain owned by
explore-policy. The shared guard and previous frozen packets are unchanged.

Sources: [Modal image local-source semantics](https://modal.com/docs/guide/images#add-local-files-with-add_local_dir-and-add_local_file).
The exact SDK 1.5.5 source inspection is recorded in sdk-semantics.json.
