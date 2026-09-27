"""Bounded owned-app teardown and typed absence evidence; no blanket workspace stop."""
from __future__ import annotations

import os
import time

from .common import number, require
from .provider import snapshot_values


def owned(row, snapshot):
    apps, containers = snapshot_values(snapshot)
    matches = [a for a in apps if a["description"] == row["app_name"]]
    ids = {a["app_id"] for a in matches}
    if row.get("app_id"):
        require(row["app_id"] in ids, "known owned app missing from inventory")
    return matches, [c for c in containers if c["app_id"] in ids]


def validate_proof(row, proof):
    require(proof["attempt_id"] == row["attempt_id"] and proof["app_name"] == row["app_name"],
            "teardown binding mismatch")
    snapshots = proof["snapshots"]
    require(snapshots and proof["checked_at"] == snapshots[-1]["checked_at"], "proof clock mismatch")
    previous = row["fenced_at"]
    for snap in snapshots:
        require(snap["checked_at"] >= previous, "stale teardown snapshot")
        for raw in snap["raw"].values():
            require(raw["queried_at"] >= row["fenced_at"]
                    and raw["queried_at"] <= raw["completed_at"] <= snap["checked_at"], "stale raw evidence")
        previous = snap["checked_at"]
    apps, containers = owned(row, snapshots[-1])
    require(not containers, "owned containers remain")
    if proof["kind"] in ("NEVER_CREATED", "ABSENT_RPC"):
        if proof["kind"] == "NEVER_CREATED":
            require(row["rpc_count"] == 0 and row.get("app_id") is None
                    and row["state_before_fence"] == "RESERVED", "not a pre-RPC refusal")
        else:
            require(row["rpc_count"] > 0 and row.get("app_id") is None
                    and row["state_before_fence"] in ("CREATING", "REJECTED", "UNKNOWN"), "not an uncertain RPC")
            require(snapshots[0]["checked_at"] > row["started_at"] + row["hold"]["startup_seconds"],
                    "RPC absence before startup bound")
        require(len(snapshots) >= 2 and snapshots[-1]["checked_at"] - snapshots[0]["checked_at"] >= 60,
                "repeated absence over 60 seconds required")
        require(all(not owned(row, s)[0] and not owned(row, s)[1] for s in snapshots), "app exists")
    else:
        require(proof["kind"] == "TERMINAL" and apps, "terminal app inventory required")
        require(all(a["state"] == "stopped" and int(a["tasks"]) == 0 for a in apps), "app not terminal")
    number(proof["checked_at"] - row["started_at"], "measured cleanup duration")


def teardown(ledger, attempt, provider, *, sleep=time.sleep, wall=time.time, monotonic=time.monotonic):
    row = ledger.fence(attempt)
    end = monotonic() + max(row["hold"]["cleanup_seconds"], 75 if row["rpc_count"] == 0 else 0)
    snapshots, errors = [], []
    # Stop only exact owned IDs discovered using the same authenticated workspace.
    while monotonic() < end:
        try:
            budget = max(.1, min(10, (end - monotonic()) / 4))
            snap = provider.snapshot(timeout=budget)
            snapshots.append(snap)
            apps, containers = owned(row, snap)
            kind = None
            if apps and not containers and all(a["state"] == "stopped" and int(a["tasks"]) == 0 for a in apps):
                kind = "TERMINAL"
            elif not apps and not containers and len(snapshots) >= 2:
                if snapshots[-1]["checked_at"] - snapshots[0]["checked_at"] >= 60:
                    if row["rpc_count"] == 0:
                        kind = "NEVER_CREATED"
                    elif snapshots[0]["checked_at"] > row["started_at"] + row["hold"]["startup_seconds"]:
                        kind = "ABSENT_RPC"
            if kind:
                proof = {"kind": kind, "attempt_id": attempt, "app_name": row["app_name"],
                         "checked_at": snap["checked_at"], "snapshots": snapshots, "errors": errors}
                validate_proof(row, proof)
                return proof
            for app in apps:
                require(monotonic() < end, "cleanup budget exhausted")
                provider.stop(app["app_id"], timeout=max(.1, min(5, (end - monotonic()) / 3)))
        except Exception as exc:
            errors.append({"at": wall(), "error": str(exc)})
        sleep(min(2, max(0, end - monotonic())))
    return {"kind": "INCOMPLETE_CLEANUP", "attempt_id": attempt, "app_name": row["app_name"],
            "checked_at": wall(), "snapshots": snapshots, "errors": errors}


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def watch(ledger, attempt, provider, driver_pid, *, sleep=time.sleep):
    """Run in an independent process; deadline survives driver death/redelivery."""
    refreshed = 0
    while True:
        row = ledger.get(attempt)
        if row["state"] in ("TERMINAL", "NEVER_CREATED", "ABSENT_RPC"):
            return
        try:
            require(alive(driver_pid), "driver exited")
            if time.monotonic() - refreshed >= 60:
                ledger.refresh(provider.billing(ledger.get(attempt)["month"]))
                refreshed = time.monotonic()
            ledger.funded(attempt)
        except Exception:
            proof = teardown(ledger, attempt, provider)
            if proof["kind"] != "INCOMPLETE_CLEANUP":
                ledger.settle(attempt, proof)
            return proof
        sleep(1)
