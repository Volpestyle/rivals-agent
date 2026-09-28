"""One app's creation receipt and fixed clock. No money, holds or workspace ledger."""
from pathlib import Path
import time

from .common import atomic, clock_id, elapsed_time, name, read, require


class Attempt:
    def __init__(self, root, *, wall=time.time, monotonic=elapsed_time):
        self.root, self.wall, self.monotonic = Path(root), wall, monotonic

    def path(self, attempt):
        return self.root / "attempts-v2" / name(attempt) / "attempt.json"

    def create(self, spec):
        path = self.path(spec["attempt_id"])
        path.parent.mkdir(parents=True, exist_ok=False)
        now, mono = self.wall(), self.monotonic()
        row = {**spec, "state": "READY", "rpc_count": 0, "app_id": None,
               "started_at": now, "started_monotonic": mono, "clock_id": clock_id()}
        atomic(path, row, fresh=True)
        return row

    def get(self, attempt):
        return read(self.path(attempt))

    def startup_open(self, attempt, *, monotonic=None):
        row = self.get(attempt)
        mono = (monotonic or self.monotonic)()
        require(row["clock_id"] == clock_id() and mono >= row["started_monotonic"], "startup clock changed")
        require(max(self.wall() - row["started_at"], mono - row["started_monotonic"])
                < row["timing"]["startup_seconds"], "startup deadline")
        return row

    def rpc(self, attempt, outcome, *, app_id=None):
        row = self.get(attempt)
        if outcome == "CREATING":
            require(row["state"] in ("READY", "REJECTED"), "AppCreate already attempted")
            self.startup_open(attempt)
            row["rpc_count"] += 1
        else:
            require(row["state"] == "CREATING" and outcome in ("RUNNING", "REJECTED", "UNKNOWN"),
                    "invalid AppCreate transition")
        if app_id is not None:
            require(app_id.startswith("ap-"), "invalid app ID")
            row["app_id"] = app_id
        row["state"] = outcome
        atomic(self.path(attempt), row)
