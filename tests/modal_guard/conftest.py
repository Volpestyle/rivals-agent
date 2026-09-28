import hashlib
import json

import pytest

from cloud.modal_guard.common import IDENTITY, clock_id, elapsed_time, json_bytes
from cloud.modal_guard.timing import derive
from cloud.modal_guard.attempt import Attempt


class Clock:
    def __init__(self):
        self.now = 1790542000.0  # September 2026 UTC
        self.mono = elapsed_time()

    def wall(self):
        return self.now

    def monotonic(self):
        return self.mono

    def advance(self, seconds):
        self.now += seconds
        self.mono += seconds

    async def sleep(self, seconds):
        self.advance(seconds)


def raw(value, now, mono=None):
    text = json.dumps(value)
    return {"stdout": text, "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "returncode": 0, "queried_at": now, "completed_at": now,
            "queried_monotonic": mono if mono is not None else elapsed_time(),
            "completed_monotonic": mono if mono is not None else elapsed_time(), "clock_id": clock_id()}


def snapshot(clock, apps=(), containers=()):
    return {"identity": IDENTITY, "checked_at": clock.wall(), "complete": True,
            "checked_monotonic": clock.monotonic(), "clock_id": clock_id(),
            "raw": {"identity": raw(IDENTITY, clock.wall(), clock.monotonic()),
                    "apps": raw(list(apps), clock.wall(), clock.monotonic()), "containers": raw(list(containers), clock.wall(), clock.monotonic())}}


def spec(attempt="fresh-04"):
    samples = [{"workload": "tiny", "concurrency": 5, "complete": True,
                "startup_seconds": 10, "work_seconds": 10, "cleanup_seconds": 10} for _ in range(20)]
    return {"attempt_id": attempt, "app_name": "rivals-" + attempt, "lane": "unit-tests",
            "timing": derive(samples, workload="tiny", concurrency=5, factor=1.5,
                           margin_seconds=60,
                           evidence_sha256=hashlib.sha256(json_bytes({"samples": samples})).hexdigest())}


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def attempts(tmp_path, clock):
    return Attempt(tmp_path, wall=clock.wall, monotonic=clock.monotonic)
