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

from .common import elapsed_time, IDENTITY, clock_id, cost, json_bytes, name, number, require, usd
from .holds import validate
from .provider import billing_values, month_at, snapshot_values

MAX_CAP_USD = "150"
DEFAULT_CAP_USD = "100"
BILLING_MAX_AGE = 120


def billing_clock(billing, now):
    raw = billing["raw"]["identity"]
    require(raw.get("clock_id") == clock_id(), "billing clock continuity lost; query again")
    require(0 <= now - raw["queried_monotonic"] <= BILLING_MAX_AGE, "billing stale; no paid work")
    return raw["queried_monotonic"]


class Ledger:
    def __init__(self, path, *, wall=time.time, monotonic=elapsed_time):
        self.path, self.wall, self.monotonic = Path(path), wall, monotonic
        self.control_deadline = None

    @contextmanager
    def bounded(self, end):
        """Journal waits may consume only the caller's original remaining clock."""
        previous = self.control_deadline
        self.control_deadline = min(previous, end) if previous is not None else end
        try:
            yield
        finally:
            self.control_deadline = previous

    def connect(self):
        require(self.path.is_file(), "workspace ledger not initialized")
        wait = 30 if self.control_deadline is None else max(0, min(30, self.control_deadline - self.monotonic()))
        db = sqlite3.connect(self.path, timeout=wait)
        try:
            db.execute("PRAGMA busy_timeout=" + str(int(wait * 1000)))
            # WAL persists on the database; migrate legacy journals without
            # resetting state. Readers never compete for the writer's lock.
            if db.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
                require(db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal", "WAL unavailable")
            return db
        except BaseException:
            db.close()
            raise

    @contextmanager
    def reading(self):
        db = self.connect()
        try:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            yield json.loads(db.execute("SELECT value FROM state WHERE id=1").fetchone()[0])
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        db = self.connect()
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
                   monotonic=elapsed_time):
        path = Path(path)
        require(usd(cap_usd) > 0 and usd(cap_usd) <= usd(MAX_CAP_USD), "unauthorized cap")
        require(billing["month"] == month_at(wall()), "wrong billing month")
        floor, _ = billing_values(billing)
        billing_clock(billing, monotonic())
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
        db = sqlite3.connect(path, timeout=30)
        try:
            db.execute("PRAGMA busy_timeout=30000")
            require(db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal", "WAL unavailable")
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
            queried = billing_clock(billing, self.monotonic())
            prior = s["billing"]["raw"]["identity"]
            require(prior.get("clock_id") != clock_id() or
                    queried >= prior["queried_monotonic"], "stale billing query")
            s["floor_usd"] = str(max(usd(s["floor_usd"]), floor))
            s["billing"] = billing
            self._event(s, "BILLING", evidence_sha256=hashlib.sha256(json_bytes(billing)).hexdigest())

    def _totals(self, s):
        require(s["identity"] == IDENTITY and s["month"] == month_at(self.wall()), "ledger identity/month mismatch")
        billing_clock(s["billing"], self.monotonic())
        # Separate summary/report queries cannot prove overlap. Keep the entire
        # allowance; actuals remain reporting evidence, never automatic credit.
        outstanding = sum((usd(x["usd"]) for x in s["external_holds"].values()), usd("0"))
        for row in s["attempts"].values():
            outstanding += usd(row["bound_usd"])
        floor = usd(s["floor_usd"])
        return {"month": s["month"], "metered_floor_usd": str(floor),
                "outstanding_usd": str(outstanding), "committed_usd": str(floor + outstanding),
                "cap_usd": s["cap_usd"], "headroom_usd": str(usd(s["cap_usd"]) - floor - outstanding),
                "weekend_uses_same_monthly_pool": True}

    def totals(self):
        with self.reading() as s:
            return self._totals(s)

    def reserve(self, spec, snapshot):
        validate(spec["hold"])
        attempt, app_name = name(spec["attempt_id"]), name(spec["app_name"])
        name(spec["lane"])
        apps, _ = snapshot_values(snapshot)
        now = self.wall()
        require(snapshot.get("clock_id") == clock_id() and
                0 <= self.monotonic() - snapshot["checked_monotonic"] <= 30, "stale admission inventory")
        with self.transaction() as s:
            totals = self._totals(s)
            require(not any(r["state"] == "FENCED" for r in s["attempts"].values()),
                    "unresolved teardown blocks admission")
            require(attempt not in s["attempts"], "attempt ID already used; no retry")
            require(not any(r["app_name"] == app_name for r in s["attempts"].values()), "app name reused")
            observed = {r["description"] for r in apps}
            for row in s["attempts"].values():
                require(not (row["state"] in ("NEVER_CREATED", "ABSENT_RPC") and row["app_name"] in observed),
                        "late app appeared after absence settlement")
            require(app_name not in observed, "owned app already exists")
            require(usd(totals["committed_usd"]) + usd(spec["hold"]["reserved_usd"]) <= usd(s["cap_usd"]),
                    "workspace cap would be crossed")
            if "bootstrap" in spec["hold"]:
                envelope = spec["hold"]["bootstrap"]
                require(attempt in envelope["attempt_ids"], "attempt outside bootstrap slots")
                peers = [r for r in s["attempts"].values()
                         if r["hold"].get("bootstrap", {}).get("campaign_id") == envelope["campaign_id"]]
                require(all(r["hold"] == spec["hold"] for r in peers), "bootstrap campaign redefined")
                require(sum((usd(r["hold"]["reserved_usd"]) for r in peers), usd("0"))
                        + usd(spec["hold"]["reserved_usd"]) <= usd(envelope["campaign_cap_usd"]),
                        "bootstrap cumulative cap exceeded")
                require(sum(r["state"] not in ("TERMINAL", "NEVER_CREATED", "ABSENT_RPC") for r in peers)
                        < envelope["concurrency"], "bootstrap concurrency exceeded")
            end = now + spec["hold"]["total_seconds"]
            require(month_at(end) == s["month"], "attempt crosses billing reset; split/reconcile first")
            row = {**spec, "month": s["month"], "state": "RESERVED", "started_at": now, "started_monotonic": self.monotonic(),
                   "stop_at": end - spec["hold"]["cleanup_seconds"], "funded_until": end,
                   "clock_id": clock_id(), "rpc_count": 0, "app_id": None,
                   "bound_usd": spec["hold"]["reserved_usd"]}
            s["attempts"][attempt] = row
            self._event(s, "RESERVE", attempt_id=attempt, bound_usd=row["bound_usd"])
            return row

    def get(self, attempt):
        with self.reading() as s:
            return s["attempts"][attempt]

    def check_absent_names(self, snapshot):
        apps, _ = snapshot_values(snapshot)
        require(snapshot.get("clock_id") == clock_id() and
                0 <= self.monotonic() - snapshot["checked_monotonic"] <= 30, "stale app inventory")
        observed = {r["description"] for r in apps}
        with self.reading() as s:
            require(not any(r["state"] in ("NEVER_CREATED", "ABSENT_RPC") and r["app_name"] in observed
                            for r in s["attempts"].values()), "late app appeared after absence settlement")

    def funded(self, attempt, *, monotonic=elapsed_time):
        with self.reading() as s:
            row = s["attempts"][attempt]
            require(row["state"] in ("RESERVED", "CREATING", "REJECTED", "RUNNING"), "attempt fenced")
            require(row.get("clock_id") == clock_id(), "clock continuity lost")
            elapsed = number(monotonic() - row["started_monotonic"], "monotonic elapsed")
            require(self.wall() < row["stop_at"] and elapsed < row["hold"]["total_seconds"]
                    - row["hold"]["cleanup_seconds"], "funded deadline")
            totals = self._totals(s)
            require(usd(totals["committed_usd"]) <= usd(s["cap_usd"]), "workspace spend stop")
            return row

    def rpc(self, attempt, outcome, *, app_id=None):
        with self.transaction() as s:
            r = s["attempts"][attempt]
            if outcome == "CREATING":
                require(r["state"] in ("RESERVED", "REJECTED"), "AppCreate not permitted")
                require(r.get("clock_id") == clock_id() and
                        0 <= self.monotonic() - r["started_monotonic"] < r["hold"]["startup_seconds"],
                        "startup deadline/clock continuity")
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
                r["fenced_monotonic"] = self.monotonic()
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
                continuous = (r.get("clock_id") == clock_id()
                              and self.monotonic() >= r["started_monotonic"])
                # Settlement reads the trusted host clock itself, rather than
                # accepting a caller-supplied elapsed duration. Legacy/rebooted
                # rows cannot release their original conservative allowance.
                seconds = (max(0, self.wall() - r["started_at"],
                               self.monotonic() - r["started_monotonic"]) if continuous else None)
                bound = (cost(seconds, r["hold"]["rate_usd_second"], r["hold"]["overhead_usd"])
                         if continuous else r["bound_usd"])
                state = "TERMINAL"
            r.update(state=state, bound_usd=bound, terminal_seconds=seconds, proof=proof)
            self._event(s, "SETTLE", attempt_id=attempt, settled_state=state, measured_bound_usd=bound)
            # Report actuals separately; summary/report overlap is not proven.
            _, billed = billing_values(s["billing"])
            return {"state": state, "actual_usd": str(billed.get(r.get("app_id"), usd("0"))),
                    "unbilled_allowance_usd": str(usd(bound)),
                    "measured_upper_usd": bound}
