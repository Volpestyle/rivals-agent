"""Cleanup only after confirmed native call completion; no administrative timer.

No billing, workspace ledger, driver-liveness kill, or mutable spend polling.
"""
import time

from .common import atomic, elapsed_time, require
from .provider import snapshot_values


def warning(message):
    try:
        print("modal_guard warning: " + str(message), flush=True)
    except Exception:
        pass


def save(path, value):
    try:
        atomic(path, value)
    except Exception as exc:
        warning("evidence write pending: " + repr(exc))


def terminal(row, snapshot):
    apps, containers = snapshot_values(snapshot)
    owned = [a for a in apps if a["description"] == row["app_name"]]
    require(len(owned) <= 1, "duplicate owned app name")
    if row.get("app_id"):
        require(owned and owned[0]["app_id"] == row["app_id"], "owned app ID missing")
    return (bool(owned) and owned[0]["state"] == "stopped" and int(owned[0]["tasks"]) == 0
            and not any(c["app_id"] == owned[0]["app_id"] for c in containers))


def teardown(row, provider, *, reason, sleep=time.sleep, monotonic=elapsed_time):
    # No timeout/billing/host-health trigger is accepted here.
    require(reason == "COMPLETED_CALL", "no other early stop is permitted")
    end = monotonic() + row["timing"]["cleanup_seconds"]
    snapshots, errors = [], []
    app_id = row.get("app_id")
    while monotonic() < end:
        try:
            if app_id:
                provider.stop(app_id, timeout=min(5, max(.001, end - monotonic())))
            snap = provider.snapshot(timeout=min(5, max(.001, end - monotonic())))
            snapshots.append(snap)
            if terminal(row, snap):
                return {"kind": "TERMINAL", "attempt_id": row["attempt_id"], "app_name": row["app_name"],
                        "reason": reason, "snapshots": snapshots, "errors": errors}
            apps, _ = snapshot_values(snap)
            owned = [a for a in apps if a["description"] == row["app_name"]]
            require(len(owned) <= 1, "duplicate owned name")
            if owned:
                app_id = owned[0]["app_id"]
            elif row["rpc_count"] == 0:
                return {"kind": "NEVER_CREATED", "attempt_id": row["attempt_id"],
                        "reason": reason, "snapshots": snapshots, "errors": errors}
        except Exception as exc:
            errors.append(repr(exc))
            # Already-stopped errors are followed by inventory next iteration.
            try:
                snap = provider.snapshot(timeout=min(5, max(.001, end - monotonic())))
                snapshots.append(snap)
                if terminal(row, snap):
                    return {"kind": "TERMINAL", "attempt_id": row["attempt_id"], "app_name": row["app_name"],
                            "reason": reason, "snapshots": snapshots, "errors": errors}
            except Exception as inner:
                errors.append(repr(inner))
        sleep(min(1, max(0, end - monotonic())))
    return {"kind": "UNPROVEN", "attempt_id": row["attempt_id"], "reason": reason,
            "snapshots": snapshots, "errors": errors}

