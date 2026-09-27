"""Thin one-app/one-arm launch path. Call once in each fresh host process."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import importlib
import os
from pathlib import Path
import subprocess
import sys
import time

from . import release
from .appcreate import install
from .common import DEFAULT_ROOT, Refused, atomic, caffeinated, name, pinned, require, usd
from .ledger import Ledger
from .lifecycle import teardown
from .provider import Provider, connect, environment, month_at


def execute_stages(deadline, identity, stages, output_root, output_volume, release_sha256):
    """Modal worker entry. Application compute functions return 0 and write artifacts.

    Stage modules come from the caller's immutable prebuilt image; no dynamic
    download/build here. A caller must pin that image/code and admitted inputs.
    """
    import modal
    from .stages import run
    release.verify(Path(__file__).parent, release_sha256)
    require(deadline == identity["deadline_unix"], "deadline changed on redelivery")
    require(Path(output_root).is_absolute() and Path(output_root).is_relative_to("/outputs"),
            "stage output outside owned mount")
    volume = modal.Volume.from_name(output_volume)
    volume.hydrate()
    require(volume.object_id == identity["output_volume_id"], "output volume changed")
    results = []
    require(len({s["name"] for s in stages}) == len(stages) and stages, "unique stages required")
    for stage in stages:
        require(time.time() < deadline, "original funded deadline expired")
        compute = getattr(importlib.import_module(stage["module"]), stage["function"])
        results.append(run(Path(output_root) / name(stage["name"]), stage["name"], identity,
                           stage["artifacts"], lambda root: compute(root, **stage.get("kwargs", {})),
                           commit=volume.commit, reload=volume.reload))
    return {"status": "COMPLETE", "stages": results}


def run_arm(spec_ref, release_sha256, *, workspace_root=DEFAULT_ROOT):
    # The inhibitor spans preparation, paid execution and final teardown.
    with caffeinated() as inhibitor:
        return _run_arm(spec_ref, release_sha256, workspace_root=workspace_root, inhibitor=inhibitor)


def _run_arm(spec_ref, release_sha256, *, workspace_root, inhibitor):
    """Paid entry: pinned spec/release, accepted guard, billing, reserve, watch, run.

    All campaigns on the Mac MUST share workspace_root. Explicit alternate roots
    are for disposable offline tests only and cannot enter this paid path.
    """
    root = Path(workspace_root).resolve()
    require(sys.platform == "darwin", "paid launch requires the Mac boot clock")
    require(root == DEFAULT_ROOT.resolve(), "paid launches require canonical workspace root")
    release.verify(Path(__file__).parent, release_sha256)
    release.reviewed(root, release_sha256)
    spec = pinned(spec_ref)
    require(spec["release_sha256"] == release_sha256, "spec pins another library")
    require(usd(spec["run_cap_usd"]) > 0 and usd(spec["hold"]["reserved_usd"]) <= usd(spec["run_cap_usd"]),
            "per-run cap exceeded")
    client = connect()  # selects and authenticates rivals before app creation
    provider = Provider()
    ledger = Ledger(root / (month_at(time.time()) + ".sqlite3"))
    ledger.refresh(provider.billing(month_at(time.time())))  # any failure => no reservation/RPC
    rate, rate_evidence = provider.rates()
    require(usd(spec["hold"]["rate_usd_second"]) >= rate, "underpriced GPU/CPU/RAM bound")
    from .holds import validate_spec
    validate_spec(spec)
    row = ledger.reserve(spec, provider.snapshot())
    attempt = spec["attempt_id"]
    local = root / "attempts" / attempt
    local.mkdir(parents=True, exist_ok=False)
    atomic(local / "spec.json", spec, fresh=True)
    atomic(local / "rates.json", rate_evidence, fresh=True)
    from scripts.job_status import write
    write(attempt, owner=spec["lane"], host="modal", stage="running", started=time.time(),
          evidence=str(local / "result.json"), progress="Guarded startup", eta=None)
    guard = None
    restore = None
    result, error = None, None
    try:
        with (local / "watchdog.log").open("x") as log:
            guard = subprocess.Popen([sys.executable, "-m", "cloud.modal_guard", "watch",
                                      str(ledger.path), attempt, str(os.getpid())],
                                     env=environment(), stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
        ready = local / "watchdog-ready.json"
        for _ in range(100):
            require(guard.poll() is None, "watchdog exited before admission")
            if ready.exists():
                break
            time.sleep(.1)
        require(ready.exists(), "watchdog readiness missing")

        async def before_rpc():
            require(inhibitor.poll() is None, "caffeinate exited")
            require(guard.poll() is None, "watchdog died")
            ledger.funded(attempt)
            ledger.check_absent_names(await asyncio.to_thread(provider.snapshot))

        import modal
        image = modal.Image.from_id(spec["image_id"], client=client)
        outputs = modal.Volume.from_name(spec["output_volume"], create_if_missing=False)
        outputs.hydrate(client=client)
        require(outputs.object_id == spec["stage_identity"]["output_volume_id"], "output mount identity mismatch")
        require(spec["stage_identity"]["attempt_id"] == attempt, "stage attempt mismatch")
        inputs = modal.Volume.from_name(spec["input_volume"], create_if_missing=False)
        inputs.hydrate(client=client)
        require(inputs.object_id == spec["input_volume_id"], "input mount identity mismatch")
        app = modal.App(spec["app_name"], tags={"lane": spec["lane"], "run": attempt})
        function = app.function(image=image, gpu="L40S", cpu=(8, 8), memory=(32768, 32768),
                                volumes={"/inputs": inputs.read_only(), "/outputs": outputs},
                                retries=0, timeout=spec["hold"]["work_seconds"],
                                startup_timeout=spec["hold"]["startup_seconds"],
                                min_containers=0, max_containers=1, buffer_containers=0,
                                scaledown_window=10, single_use_containers=True)(execute_stages)
        restore = install(client, ledger, attempt, before_rpc=before_rpc)
        with app.run(client=client):
            ledger.funded(attempt)
            identity = {**spec["stage_identity"], "deadline_unix": row["stop_at"]}
            call = function.spawn(row["stop_at"], identity, spec["stages"], spec["output_root"],
                                  spec["output_volume"], release_sha256)
            atomic(local / "call.json", {"call_id": call.object_id}, fresh=True)
            while result is None:
                require(inhibitor.poll() is None, "caffeinate exited")
                require(guard.poll() is None, "watchdog died")
                ledger.funded(attempt)
                try:
                    result = call.get(timeout=1)
                except TimeoutError:
                    pass
                if int(time.time()) % 30 == 0:
                    write(attempt, progress="Running within original funded deadline")
    except BaseException as exc:
        error = repr(exc)
    finally:
        if restore:
            restore()
        # Main and watchdog may both request cleanup; settlement is idempotent at
        # the driver boundary. Neither retries paid work nor removes partial files.
        current = ledger.get(attempt)
        if current["state"] not in ("TERMINAL", "NEVER_CREATED", "ABSENT_RPC"):
            proof = teardown(ledger, attempt, provider)
            atomic(local / "teardown.json", proof)
            if proof["kind"] != "INCOMPLETE_CLEANUP":
                if ledger.get(attempt)["state"] == "FENCED":
                    ledger.settle(attempt, proof)
            else:
                error = (error or "") + " teardown unproven; allowance retained"
        final = {"status": "INCOMPLETE" if error or not result else "COMPLETE",
                 "error": error, "result": result, "attempt_id": attempt,
                 "accounting": ledger.get(attempt)}
        atomic(local / "result.json", final, fresh=True)
        write(attempt, stage="failed" if final["status"] == "INCOMPLETE" else "done",
              progress=final["status"] + "; " + final["accounting"]["state"])
    return final


def isolated_batch(commands, *, run=subprocess.run):
    """Independent process per arm; one scientific failure never cancels siblings.

    Each process has its own ledger-funded watchdog. A workspace-wide cap/identity
    problem is seen independently by every watchdog. No child is retried here.
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
