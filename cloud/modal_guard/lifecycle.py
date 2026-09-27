"""Bounded owned-app teardown and typed absence evidence; no blanket workspace stop."""
from __future__ import annotations

import os
import time
import queue
import threading

from .common import elapsed_time, clock_id, number, require
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
    previous = row["fenced_monotonic"]
    for snap in snapshots:
        require(snap["clock_id"] == clock_id() and snap["checked_monotonic"] >= previous,
                "stale teardown snapshot/clock continuity")
        for raw in snap["raw"].values():
            require(raw["clock_id"] == clock_id() and raw["queried_monotonic"] >= row["fenced_monotonic"]
                    and raw["queried_monotonic"] <= raw["completed_monotonic"] <= snap["checked_monotonic"], "stale raw evidence")
        previous = snap["checked_monotonic"]
    apps, containers = owned(row, snapshots[-1])
    require(not containers, "owned containers remain")
    if proof["kind"] in ("NEVER_CREATED", "ABSENT_RPC"):
        if proof["kind"] == "NEVER_CREATED":
            require(row["rpc_count"] == 0 and row.get("app_id") is None
                    and row["state_before_fence"] == "RESERVED", "not a pre-RPC refusal")
        else:
            require(row["rpc_count"] > 0 and row.get("app_id") is None
                    and row["state_before_fence"] in ("CREATING", "REJECTED", "UNKNOWN"), "not an uncertain RPC")
            require(row.get("clock_id") == clock_id() and snapshots[0]["checked_monotonic"]
                    > row["started_monotonic"] + row["hold"]["startup_seconds"],
                    "RPC absence before startup bound")
        require(len(snapshots) >= 2 and snapshots[-1]["checked_monotonic"] - snapshots[0]["checked_monotonic"] >= 60,
                "repeated absence over 60 seconds required")
        require(all(not owned(row, s)[0] and not owned(row, s)[1] for s in snapshots), "app exists")
    else:
        require(proof["kind"] == "TERMINAL" and apps, "terminal app inventory required")
        require(all(a["state"] == "stopped" and int(a["tasks"]) == 0 for a in apps), "app not terminal")
    number(snapshots[-1]["checked_monotonic"] - row["fenced_monotonic"], "measured cleanup duration")


def teardown(ledger, attempt, provider, *, sleep=time.sleep, wall=time.time,
             monotonic=elapsed_time, cached_row=None):
    """Stop first; use only the original remaining funding, never a fresh hold.

    Emergency stopping after a lost clock/expired envelope is explicitly unfunded
    and never presented as proof of cleanup. The unresolved fence blocks admission.
    """
    row = cached_row or ledger.get(attempt)
    errors, snapshots = [], []
    continuous = row.get("clock_id") == clock_id() and monotonic() >= row["started_monotonic"]
    end = row["started_monotonic"] + row["hold"]["total_seconds"] if continuous else monotonic()
    # Known owned IDs need no potentially slow list/billing query before stop.
    if row.get("app_id"):
        try:
            provider.stop(row["app_id"], timeout=min(5, max(.001, end - monotonic()))
                          if monotonic() < end else 2)
        except Exception as exc:
            errors.append({"at": wall(), "error": str(exc)})
    try:
        row = ledger.fence(attempt)
    except Exception as exc:
        errors.append({"at": wall(), "error": "fence failed: " + str(exc)})
        end = monotonic()  # cannot prove revocation; do not release an allowance
    while monotonic() < end:
        try:
            snap = provider.snapshot(timeout=min(5, end - monotonic()))
            require(monotonic() <= end, "provider exceeded original funded envelope")
            snapshots.append(snap)
            apps, containers = owned(row, snap)
            kind = None
            if apps and not containers and all(a["state"] == "stopped" and int(a["tasks"]) == 0 for a in apps):
                kind = "TERMINAL"
            elif not apps and not containers and len(snapshots) >= 2:
                if snapshots[-1]["checked_monotonic"] - snapshots[0]["checked_monotonic"] >= 60:
                    if row["rpc_count"] == 0:
                        kind = "NEVER_CREATED"
                    elif snapshots[0]["checked_monotonic"] > row["started_monotonic"] + row["hold"]["startup_seconds"]:
                        kind = "ABSENT_RPC"
            if kind:
                proof = {"kind": kind, "attempt_id": attempt, "app_name": row["app_name"],
                         "checked_at": snap["checked_at"], "snapshots": snapshots, "errors": errors}
                validate_proof(row, proof)
                return proof
            for app in apps:
                require(monotonic() < end, "cleanup budget exhausted")
                provider.stop(app["app_id"], timeout=min(5, end - monotonic()))
        except Exception as exc:
            errors.append({"at": wall(), "error": str(exc)})
        sleep(min(.25, max(0, end - monotonic())))
    return {"kind": "INCOMPLETE_CLEANUP", "attempt_id": attempt, "app_name": row["app_name"],
            "checked_at": wall(), "snapshots": snapshots, "errors": errors,
            "original_funded_until": row["funded_until"], "new_funding_granted": False}


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


class BillingRefresh:
    """One daemon reader, no ledger writes and no join on the deadline path."""
    def __init__(self, provider, month):
        self.results = queue.Queue(maxsize=1)
        def read():
            try:
                self.results.put((provider.billing(month), None))
            except Exception as exc:
                self.results.put((None, exc))
        threading.Thread(target=read, daemon=True, name="modal-billing").start()

    def poll(self):
        try:
            return self.results.get_nowait()
        except queue.Empty:
            return None


def watch(ledger, attempt, provider, driver_pid, *, sleep=time.sleep,
          wall=time.time, monotonic=elapsed_time, refresh_factory=BillingRefresh):
    """Independent host process. No network billing wait on the stop path."""
    refreshed, pending = float("-inf"), None
    row = ledger.get(attempt)
    while True:
        try:
            require(row.get("clock_id") == clock_id(), "clock continuity lost")
            stop = row["started_monotonic"] + row["hold"]["total_seconds"] - row["hold"]["cleanup_seconds"]
            require(monotonic() < stop, "funded deadline")
            require(alive(driver_pid), "driver exited")
            row = ledger.get(attempt)  # nonblocking SQLite; failure triggers stop
            if row["state"] in ("TERMINAL", "NEVER_CREATED", "ABSENT_RPC"):
                return
            ledger.funded(attempt, monotonic=monotonic)
            if pending is not None:
                completed = pending.poll()
                if completed is not None:
                    value, error = completed
                    require(error is None, "billing refresh failed: " + str(error))
                    require(monotonic() < stop, "funded deadline")
                    ledger.refresh(value)
                    pending, refreshed = None, monotonic()
            elif monotonic() - refreshed >= 60:
                pending = refresh_factory(provider, row["month"])
        except Exception:
            proof = teardown(ledger, attempt, provider, sleep=sleep, wall=wall,
                             monotonic=monotonic, cached_row=row)
            if proof["kind"] != "INCOMPLETE_CLEANUP":
                try:
                    ledger.settle(attempt, proof)
                except Exception:
                    pass  # no release; caller/journal retains the unresolved fence
            return proof
        sleep(min(.25, max(0, stop - monotonic())))
