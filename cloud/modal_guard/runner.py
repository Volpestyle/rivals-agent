"""Thin one-app/one-arm launch path. Call once in each fresh host process."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib
from pathlib import Path
import subprocess
import sys
import time

from . import release
from .appcreate import install
from .common import DEFAULT_ROOT, atomic, caffeinated, name, pinned, read, require
from .lifecycle import teardown
from .provider import Provider, connect, environment


def status(attempt, **fields):
    """Dashboard failure must never prevent execution or cleanup."""
    try:
        from scripts.job_status import write
        return write(attempt, **fields)
    except Exception as exc:
        print("modal_guard status unavailable: " + repr(exc), file=sys.stderr)


def execute_stages(identity, stages, output_root, output_volume, release_sha256):
    """Modal worker entry. Application compute functions return 0 and write artifacts.

    Stage modules come from the pinned image/native source mount; no dynamic
    download/build here. A caller must pin that image/code and admitted inputs.
    """
    import modal
    from .stages import run
    from . import staging
    release.verify(Path(__file__).parent, release_sha256)
    require(Path(output_root).is_absolute() and Path(output_root).is_relative_to("/outputs"),
            "stage output outside owned mount")
    volume = modal.Volume.from_name(output_volume)
    volume.hydrate()
    require(volume.object_id == identity["output_volume_id"], "output volume changed")
    results = []
    require(len({s["name"] for s in stages}) == len(stages) and stages, "unique stages required")
    for stage in stages:
        compute = getattr(importlib.import_module(stage["module"]), stage["function"])
        mode = staging.validate(stage)
        kwargs = dict(stage.get("kwargs", {}))
        if mode == "local":
            kwargs[stage["data_access"]["argument"]] = str(staging.prepare(stage["data_access"]))
        if stage.get("commit_argument"):
            kwargs[stage["commit_argument"]] = volume.commit
        resume = None
        if stage.get("resume"):
            descriptor = stage["resume"]
            validator = getattr(importlib.import_module(descriptor["module"]), descriptor["function"])
            resume_kwargs = dict(descriptor.get("kwargs", {}))
            if descriptor.get("source_ref"):
                pinned(descriptor["source_ref"])
                resume_kwargs["source_ref"] = descriptor["source_ref"]
            def resume(root):
                return validator(root, **resume_kwargs)
        results.append(run(Path(output_root) / name(stage["name"]), stage["name"], identity,
                           stage["artifacts"], lambda root, **state: compute(root, **kwargs, **state),
                           commit=volume.commit, reload=volume.reload, resume=resume,
                           resume_source=bool(stage.get("resume", {}).get("source_ref"))))
    return {"status": "COMPLETE", "stages": results}


def observe(call, *, timeout_errors=(), sleep=time.sleep, warn=print):
    """A lost observation returns PENDING; it never cancels or replaces the call."""
    while True:
        try:
            value = call.get(timeout=1)
            return {"execution": value.get("execution", "SUCCEEDED"), "result": value}
        except timeout_errors as exc:
            return {"execution": "FAILED", "error": repr(exc), "native_timeout": True}
        except TimeoutError:
            sleep(.1)
        except Exception as exc:
            warn("Call observation pending; detached app left running: " + repr(exc))
            return {"execution": "PENDING", "error": repr(exc)}


def execute_checked(*args):
    """Return workload failures as terminal results, not ambiguous client errors."""
    try:
        return {"execution": "SUCCEEDED", **execute_stages(*args)}
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return {"execution": "FAILED", "error": repr(exc)}



def run_arm(spec_ref, release_sha256, *, workspace_root=DEFAULT_ROOT):
    with caffeinated():
        return _run_arm(spec_ref, release_sha256, workspace_root=workspace_root)


def _run_arm(spec_ref, release_sha256, *, workspace_root):
    """Mac-only, identity and pacing then detached work. No custom deadline, billing or spend ledger."""
    from . import staging, timing
    from .attempt import Attempt
    from .lifecycle import save, warning
    root = Path(workspace_root).resolve()
    require(sys.platform == "darwin", "launch requires the Mac")
    require(root == DEFAULT_ROOT.resolve(), "launch requires canonical root")
    release.verify(Path(__file__).parent, release_sha256)
    release.reviewed(root, release_sha256)
    spec = pinned(spec_ref)
    require(spec["release_sha256"] == release_sha256, "wrong release")
    timing.validate_spec(spec)
    for stage in spec["stages"]:
        staging.validate(stage)
    client = connect()
    provider = Provider()
    inventory = provider.snapshot()
    from .provider import snapshot_values
    apps, _ = snapshot_values(inventory)
    require(not any(a["description"] == spec["app_name"] for a in apps), "app name already exists")
    attempt = name(spec["attempt_id"])
    attempts = Attempt(root)
    row = attempts.create(spec)
    local = attempts.path(attempt).parent
    atomic(local / "spec.json", spec, fresh=True)
    status(attempt, owner=spec["lane"], host="modal", stage="running", evidence=str(local / "result.json"), progress="Starting")
    import modal
    image = modal.Image.from_id(spec["image_id"], client=client)
    outputs = modal.Volume.from_name(spec["output_volume"], create_if_missing=False)
    outputs.hydrate(client=client)
    inputs = modal.Volume.from_name(spec["input_volume"], create_if_missing=False)
    inputs.hydrate(client=client)
    require(outputs.object_id == spec["stage_identity"]["output_volume_id"] and inputs.object_id == spec["input_volume_id"],
            "mount identity mismatch")
    require(spec["stage_identity"]["attempt_id"] == attempt, "stage attempt mismatch")
    volumes = {"/inputs": inputs.read_only(), "/outputs": outputs}
    if spec.get("resume_volume"):
        prior = modal.Volume.from_name(spec["resume_volume"], create_if_missing=False)
        prior.hydrate(client=client)
        require(prior.object_id == spec["resume_volume_id"], "prior checkpoint volume identity mismatch")
        volumes["/resume"] = prior.read_only()
    app = modal.App(spec["app_name"], tags={"lane": spec["lane"], "run": attempt})
    function = app.function(image=image, gpu="L40S", cpu=(8, 8), memory=(32768, 32768),
                            volumes=volumes, retries=0,
                            timeout=spec["timing"]["work_seconds"], startup_timeout=spec["timing"]["startup_seconds"],
                            min_containers=0, max_containers=1, buffer_containers=0,
                            scaledown_window=10, single_use_containers=True)(execute_checked)
    async def before_rpc():
        attempts.startup_open(attempt)
    restore = install(client, attempts, attempt, before_rpc=before_rpc)
    result, error, proof = None, None, None
    try:
        # DETACHED is essential: a host exception/disconnection must not cancel
        # healthy remote work. Modal alone enforces the function timeout.
        with app.run(client=client, detach=True):
            row = {**row, "app_id": app.app_id}
            warning("Detached app ID: " + app.app_id)
            save(local / "app.json", {"app_id": app.app_id, "app_name": spec["app_name"]})
            call = function.spawn(spec["stage_identity"], spec["stages"], spec["output_root"],
                                  spec["output_volume"], release_sha256)
            warning("Detached call ID: " + call.object_id)
            save(local / "call.json", {"call_id": call.object_id})
            from modal.exception import FunctionTimeoutError
            result = observe(call, timeout_errors=(FunctionTimeoutError,), warn=warning)
            if result["execution"] != "PENDING":
                proof = teardown(row, provider, reason="COMPLETED_CALL")
                save(local / "teardown.json", proof)
    except BaseException as exc:
        error = repr(exc)
        warning("Client failure; detached app remains under native timeout: " + error)
    finally:
        try:
            restore()
        except Exception as exc:
            warning(exc)
    # Execution evidence does not depend on collection, billing or teardown.
    final = {"execution": result["execution"] if result else "PENDING",
             "collection": "NOT_COLLECTED", "accounting": "LEAD_PROCESS",
             "attempt_id": attempt, "result": result, "error": error, "teardown": proof}
    save(local / "result.json", final)
    status(attempt, stage="done" if final["execution"] == "SUCCEEDED" else "failed",
           progress=final["execution"])

    return final


def isolated_batch(commands, *, run=subprocess.run):
    """Independent process per arm; one scientific failure never cancels siblings.

    Each app has its native function timeout. No child failure cancels a sibling.
    No child is retried here.
    """
    def one(command):
        try:
            result = run(command, check=False)
            return {"status": "COMPLETE" if result.returncode == 0 else "INCOMPLETE",
                    "returncode": result.returncode}
        except Exception as exc:
            return {"status": "INCOMPLETE", "error": repr(exc)}
    require(commands, "empty batch")
    with ThreadPoolExecutor(max_workers=len(commands)) as pool:
        return list(pool.map(one, commands))


def reattach(attempt, release_sha256, *, cleanup=True, workspace_root=DEFAULT_ROOT):
    """Recover an existing call; never creates an app, spawn or replacement input."""
    from .attempt import Attempt
    from .lifecycle import save, warning
    require(sys.platform == "darwin", "recovery requires the Mac")
    root = Path(workspace_root).resolve()
    require(root == DEFAULT_ROOT.resolve(), "recovery requires canonical root")
    release.verify(Path(__file__).parent, release_sha256)
    row = Attempt(root).get(attempt)
    require(row["release_sha256"] == release_sha256, "wrong recovery release")
    local = Attempt(root).path(attempt).parent
    app = read(local / "app.json")
    require(app["app_name"] == row["app_name"], "recovery app mismatch")
    row["app_id"] = app["app_id"]
    client = connect()
    import modal
    from modal.exception import FunctionTimeoutError
    call = modal.FunctionCall.from_id(read(local / "call.json")["call_id"], client=client)
    result = observe(call, timeout_errors=(FunctionTimeoutError,), warn=warning)
    proof = None
    if cleanup and result["execution"] != "PENDING":
        proof = teardown(row, Provider(), reason="COMPLETED_CALL")
        save(local / "teardown.json", proof)
    final = {**result, "attempt_id": attempt, "collection": "NOT_COLLECTED",
             "accounting": "LEAD_PROCESS", "teardown": proof}
    save(local / "recovered.json", final)
    return final
