import hashlib
import json
import time

import pytest

from cloud.modal_guard.common import IDENTITY, json_bytes
from cloud.modal_guard.holds import derive
from cloud.modal_guard.ledger import Ledger


class Clock:
    def __init__(self):
        self.now = 1790542000.0  # September 2026 UTC
        self.mono = time.monotonic()

    def wall(self):
        return self.now

    def monotonic(self):
        return self.mono

    def advance(self, seconds):
        self.now += seconds
        self.mono += seconds

    async def sleep(self, seconds):
        self.advance(seconds)


def raw(value, now):
    text = json.dumps(value)
    return {"stdout": text, "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "returncode": 0, "queried_at": now, "completed_at": now}


def billing(clock, spent="48.25", apps=None):
    rows = [{"object_id": key, "cost": value, "interval_start": "2026-09-27T18:00:00"}
            for key, value in (apps or {}).items()]
    return {"identity": IDENTITY, "month": "2026-09", "queried_at": clock.wall(),
            "raw": {"identity": raw(IDENTITY, clock.wall()),
                    "summary": raw({"metered_cost": spent, "billed_cost": "18.05"}, clock.wall()),
                    "reports": [raw(rows, clock.wall())]}}


def snapshot(clock, apps=(), containers=()):
    return {"identity": IDENTITY, "checked_at": clock.wall(), "complete": True,
            "raw": {"identity": raw(IDENTITY, clock.wall()),
                    "apps": raw(list(apps), clock.wall()), "containers": raw(list(containers), clock.wall())}}


def spec(attempt="fresh-04", *, rate="0.01"):
    samples = [{"workload": "tiny", "concurrency": 5, "complete": True,
                "startup_seconds": 10, "work_seconds": 10, "cleanup_seconds": 10} for _ in range(20)]
    return {"attempt_id": attempt, "app_name": "rivals-" + attempt, "lane": "unit-tests",
            "hold": derive(samples, workload="tiny", concurrency=5, factor=1.5,
                           margin_seconds=60, rate_usd_second=rate,
                           evidence_sha256=hashlib.sha256(json_bytes({"samples": samples})).hexdigest())}


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def ledger(tmp_path, clock):
    return Ledger.initialize(tmp_path / "2026-09.sqlite3", billing(clock), wall=clock.wall,
                             monotonic=clock.monotonic)
