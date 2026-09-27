"""One host-local workspace journal. Billing actuals, active bounds and unbilled tails.

SQLite BEGIN IMMEDIATE makes concurrent check-and-reserve indivisible. Existing
round-3 packets/ledgers are not imported or rewritten. Reports are annotations.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from .common import IDENTITY, cost, json_bytes, name, number, require, usd
from .holds import validate
from .provider import billing_values, month_at, snapshot_values

MAX_CAP_USD = "150"
DEFAULT_CAP_USD = "100"
BILLING_MAX_AGE = 120


class Ledger:
    def __init__(self, path, *, wall=time.time, monotonic=time.monotonic):
        self.path, self.wall, self.monotonic = Path(path), wall, monotonic

    @contextmanager
    def transaction(self):
        require(self.path.is_file(), "workspace ledger not initialized")
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("BEGIN IMMEDIATE")
            state = json.loads(db.execute("SELECT value FROM state WHERE id=1").fetchone()[0])
            yield state
            db.execute("UPDATE state SET value=? WHERE id=1", (json_bytes(state).decode(),))
            db.commit()
        finally:
            db.close()  # rollback on exception, including cap refusal

    @classmethod
    def initialize(cls, path, billing, *, cap_usd=DEFAULT_CAP_USD, reports=(), external_holds=(), wall=time.time,
                   monotonic=time.monotonic):
        path = Path(path)
        require(usd(cap_usd) > 0 and usd(cap_usd) <= usd(MAX_CAP_USD), "unauthorized cap")
        require(billing["month"] == month_at(wall()), "wrong billing month")
        floor, _ = billing_values(billing)
        require(0 <= wall() - billing["queried_at"] <= BILLING_MAX_AGE, "stale billing")
        # No overwrite/reset or implicit month rollover. New month gets a new ledger.
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb"):
            pass
        state = {"version": 1, "identity": IDENTITY, "month": billing["month"],
                 "cap_usd": str(usd(cap_usd)), "billing": billing, "floor_usd": str(floor),
                 "reports": list(reports), "external_holds": {}, "attempts": {}, "events": []}
        for row in external_holds:
            key = name(row["id"])
            require(key not in state["external_holds"] and usd(row["usd"]) > 0,
                    "invalid external allowance")
            state["external_holds"][key] = row
        db = sqlite3.connect(path)
        try:
            db.execute("CREATE TABLE state(id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)")
            db.execute("INSERT INTO state VALUES(1,?)", (json_bytes(state).decode(),))
            db.commit()
        finally:
            db.close()
        return cls(path, wall=wall, monotonic=monotonic)

    def _event(self, state, event, **fields):
        previous = state["events"][-1]["sha256"] if state["events"] else None
        value = {"event": event, "at": self.wall(), "previous": previous, **fields}
        state["events"].append({**value, "sha256": hashlib.sha256(json_bytes(value)).hexdigest()})

    def refresh(self, billing):
        floor, _ = billing_values(billing)
        with self.transaction() as s:
            require(billing["month"] == s["month"] == month_at(self.wall()), "month rollover requires reconciliation")
            require(s["billing"]["queried_at"] <= billing["queried_at"] <= self.wall()
                    and self.wall() - billing["queried_at"] <= BILLING_MAX_AGE, "stale billing query")
            s["floor_usd"] = str(max(usd(s["floor_usd"]), floor))
            s["billing"] = billing
            self._event(s, "BILLING", evidence_sha256=hashlib.sha256(json_bytes(billing)).hexdigest())

    def _totals(self, s):
        require(s["identity"] == IDENTITY and s["month"] == month_at(self.wall()), "ledger identity/month mismatch")
        require(0 <= self.wall() - s["billing"]["queried_at"] <= BILLING_MAX_AGE, "billing stale; no paid work")
        _, reported = billing_values(s["billing"])
        outstanding = sum((max(usd("0"), usd(x["usd"]) - reported.get(x.get("app_id"), usd("0")))
                           for x in s["external_holds"].values()), usd("0"))
        for row in s["attempts"].values():
            # Actuals are already in the workspace floor: only subtract their
            # coverage from this app's upper bound, never from another app's hold.
            actual = reported.get(row.get("app_id"), usd("0"))
            outstanding += max(usd("0"), usd(row["bound_usd"]) - actual)
        floor = usd(s["floor_usd"])
        return {"month": s["month"], "metered_floor_usd": str(floor),
                "outstanding_usd": str(outstanding), "committed_usd": str(floor + outstanding),
                "cap_usd": s["cap_usd"], "headroom_usd": str(usd(s["cap_usd"]) - floor - outstanding),
                "weekend_uses_same_monthly_pool": True}

    def totals(self):
        with self.transaction() as s:
            return self._totals(s)

    def reserve(self, spec, snapshot):
        validate(spec["hold"])
        attempt, app_name = name(spec["attempt_id"]), name(spec["app_name"])
        name(spec["lane"])
        apps, _ = snapshot_values(snapshot)
        now = self.wall()
        require(0 <= now - snapshot["checked_at"] <= 30, "stale admission inventory")
        with self.transaction() as s:
            totals = self._totals(s)
            require(attempt not in s["attempts"], "attempt ID already used; no retry")
            require(not any(r["app_name"] == app_name for r in s["attempts"].values()), "app name reused")
            observed = {r["description"] for r in apps}
            for row in s["attempts"].values():
                require(not (row["state"] in ("NEVER_CREATED", "ABSENT_RPC") and row["app_name"] in observed),
                        "late app appeared after absence settlement")
            require(app_name not in observed, "owned app already exists")
            require(usd(totals["committed_usd"]) + usd(spec["hold"]["reserved_usd"]) <= usd(s["cap_usd"]),
                    "workspace cap would be crossed")
            end = now + spec["hold"]["total_seconds"]
            require(month_at(end) == s["month"], "attempt crosses billing reset; split/reconcile first")
            row = {**spec, "month": s["month"], "state": "RESERVED", "started_at": now, "started_monotonic": self.monotonic(),
                   "stop_at": end - spec["hold"]["cleanup_seconds"], "funded_until": end,
                   "rpc_count": 0, "app_id": None, "bound_usd": spec["hold"]["reserved_usd"]}
            s["attempts"][attempt] = row
            self._event(s, "RESERVE", attempt_id=attempt, bound_usd=row["bound_usd"])
            return row

    def get(self, attempt):
        with self.transaction() as s:
            return s["attempts"][attempt]

    def check_absent_names(self, snapshot):
        apps, _ = snapshot_values(snapshot)
        require(0 <= self.wall() - snapshot["checked_at"] <= 30, "stale app inventory")
        observed = {r["description"] for r in apps}
        with self.transaction() as s:
            require(not any(r["state"] in ("NEVER_CREATED", "ABSENT_RPC") and r["app_name"] in observed
                            for r in s["attempts"].values()), "late app appeared after absence settlement")

    def funded(self, attempt, *, monotonic=time.monotonic):
        with self.transaction() as s:
            totals = self._totals(s)
            row = s["attempts"][attempt]
            require(row["state"] in ("RESERVED", "CREATING", "REJECTED", "RUNNING"), "attempt fenced")
            require(usd(totals["committed_usd"]) <= usd(s["cap_usd"]), "workspace spend stop")
            elapsed = number(monotonic() - row["started_monotonic"], "monotonic elapsed")
            require(self.wall() < row["stop_at"] and elapsed < row["hold"]["total_seconds"]
                    - row["hold"]["cleanup_seconds"], "funded deadline")
            return row

    def rpc(self, attempt, outcome, *, app_id=None):
        with self.transaction() as s:
            r = s["attempts"][attempt]
            if outcome == "CREATING":
                require(r["state"] in ("RESERVED", "REJECTED"), "AppCreate not permitted")
                require(self.wall() < r["started_at"] + r["hold"]["startup_seconds"], "startup deadline")
                require(usd(self._totals(s)["committed_usd"]) <= usd(s["cap_usd"]), "workspace spend stop")
                r["rpc_count"] += 1
            else:
                require((r["state"] == "CREATING" or r["state"] == "FENCED"
                         and r["state_before_fence"] == "CREATING")
                        and outcome in ("RUNNING", "REJECTED", "UNKNOWN"),
                        "invalid RPC transition")
            if outcome == "RUNNING":
                require(isinstance(app_id, str) and app_id.startswith("ap-"), "invalid app ID")
                r["app_id"] = app_id
            if r["state"] != "FENCED":
                r["state"] = outcome
            self._event(s, outcome, attempt_id=attempt, app_id=app_id)

    def fence(self, attempt):
        """Atomically revoke creation authority; cannot race a later AppCreate start."""
        with self.transaction() as s:
            r = s["attempts"][attempt]
            if "fenced_at" not in r:
                r["fenced_at"], r["state_before_fence"] = self.wall(), r["state"]
                r["state"] = "FENCED"
                self._event(s, "FENCE", attempt_id=attempt)
            return r

    def settle(self, attempt, proof):
        from .lifecycle import validate_proof
        with self.transaction() as s:
            r = s["attempts"][attempt]
            require(r["state"] == "FENCED", "fence attempt before settlement")
            validate_proof(r, proof)
            if proof["kind"] == "NEVER_CREATED":
                bound, seconds = "0", 0
                state = "NEVER_CREATED"
            elif proof["kind"] == "ABSENT_RPC":
                bound, seconds = r["hold"]["reserved_usd"], r["hold"]["total_seconds"]
                state = "ABSENT_RPC"
            else:
                apps, _ = snapshot_values(proof["snapshots"][-1])
                owned = [a for a in apps if a["description"] == r["app_name"]]
                require(len(owned) == 1, "multiple apps for one logical attempt")
                r["app_id"] = owned[0]["app_id"]
                seconds = proof["checked_at"] - r["started_at"]
                bound = cost(seconds, r["hold"]["rate_usd_second"], r["hold"]["overhead_usd"])
                state = "TERMINAL"
            r.update(state=state, bound_usd=bound, terminal_seconds=seconds, proof=proof)
            self._event(s, "SETTLE", attempt_id=attempt, settled_state=state, measured_bound_usd=bound)
            # Terminal actuals are visible immediately; any reporting tail stays
            # as measured bound - reported actual, NOT the original full hold.
            _, billed = billing_values(s["billing"])
            return {"state": state, "actual_usd": str(billed.get(r.get("app_id"), usd("0"))),
                    "unbilled_allowance_usd": str(max(usd("0"), usd(bound) - billed.get(r.get("app_id"), usd("0")))),
                    "measured_upper_usd": bound}
