"""Modal 1.5.5 identity, billing and inventory; explicit rivals profile everywhere."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .common import IDENTITY, SDK_VERSION, clock_id, require, usd

OVERRIDES = ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "MODAL_OAUTH_REFRESH_TOKEN",
             "MODAL_OAUTH_CLIENT_ID", "MODAL_OAUTH_CLIENT_SECRET", "MODAL_CONFIG_PATH",
             "MODAL_SERVER_URL", "MODAL_ENVIRONMENT")


def environment():
    env = dict(os.environ, MODAL_PROFILE="rivals")
    for key in OVERRIDES:
        env.pop(key, None)
    return env


def connect():
    """Only in a fresh launch/identity process; never reuse another profile's client."""
    for key in OVERRIDES:
        os.environ.pop(key, None)
    os.environ["MODAL_PROFILE"] = "rivals"
    import modal
    import modal.client
    import modal.config
    from modal._utils.async_utils import synchronizer
    from modal_proto import api_pb2
    require(modal.__version__ == SDK_VERSION, "unreviewed Modal SDK")
    require(modal.client._Client._client_from_env is None, "fresh SDK process required")
    modal.config._set_profile("rivals")
    client = modal.Client.from_env()

    @synchronizer.create_blocking
    async def inspect():
        result = await client.stub.TokenInfoGet(api_pb2.TokenInfoGetRequest())
        return {"profile": "rivals", "workspace": result.workspace_name,
                "workspace_id": result.workspace_id}

    require(inspect() == IDENTITY, "authenticated workspace mismatch")
    return client


class Provider:
    def __init__(self, cli=None, *, wall=time.time, monotonic=time.monotonic):
        self.cli = cli or str(Path.home() / ".local/bin/modal")
        self.wall = wall
        self.monotonic = monotonic

    def budget(self, timeout):
        end = self.monotonic() + timeout
        def remaining():
            value = end - self.monotonic()
            require(value > 0, "control query budget exhausted")
            return value
        return remaining

    def _run(self, args, timeout=10):
        started = self.wall()
        started_monotonic = self.monotonic()
        p = subprocess.run(args, env=environment(), capture_output=True, text=True, timeout=timeout)
        require(p.returncode == 0, "Modal query failed: " + p.stderr[-500:])
        return {"command": args, "stdout": p.stdout, "returncode": p.returncode,
                "sha256": hashlib.sha256(p.stdout.encode()).hexdigest(),
                "queried_at": started, "completed_at": self.wall(),
                "queried_monotonic": started_monotonic, "completed_monotonic": self.monotonic(),
                "clock_id": clock_id()}

    def identity(self, timeout=10):
        raw = self._run([sys.executable, "-m", "cloud.modal_guard.provider", "identity"], timeout)
        require(json.loads(raw["stdout"]) == IDENTITY, "identity probe failed")
        return raw

    def snapshot(self, timeout=10):
        remaining = self.budget(timeout)
        identity = self.identity(remaining())
        apps = self._run([self.cli, "app", "list", "--profile", "rivals", "--json"], remaining())
        containers = self._run([self.cli, "container", "list", "--profile", "rivals", "--json"], remaining())
        return {"identity": IDENTITY, "checked_at": self.wall(), "complete": True,
                "checked_monotonic": self.monotonic(), "clock_id": clock_id(),
                "raw": {"identity": identity, "apps": apps, "containers": containers}}

    def billing(self, month):
        require(month == month_at(self.wall()), "query current billing month only")
        identity = self.identity()
        summary = self._run([self.cli, "billing", "summary", "--for", month,
                             "--profile", "rivals", "--json"])
        # Hourly reports are limited to seven days in SDK 1.5.5. Combine disjoint
        # closed days with today's closed hours, never double-count a boundary.
        today = datetime.fromtimestamp(self.wall(), timezone.utc).strftime("%Y-%m-%d")
        reports = []
        if today != month + "-01":
            reports.append(self._run([self.cli, "billing", "report", "--start", month + "-01",
                                      "--end", today, "--resolution", "d", "--tag-names", "lane,run",
                                      "--profile", "rivals", "--json"]))
        reports.append(self._run([self.cli, "billing", "report", "--start", today,
                                  "--resolution", "h", "--tag-names", "lane,run",
                                  "--profile", "rivals", "--json"]))
        raw = {"identity": identity, "summary": summary, "reports": reports}
        value = {"identity": IDENTITY, "month": month, "queried_at": identity["queried_at"],
                 "raw": raw}
        billing_values(value)
        return value

    def stop(self, app_id, timeout=10):
        require(isinstance(app_id, str) and app_id.startswith("ap-"), "invalid owned app ID")
        remaining = self.budget(timeout)
        self.identity(min(remaining(), 1))
        return self._run([self.cli, "app", "stop", app_id, "--profile", "rivals", "--yes"], remaining())

    def rates(self):
        self.identity()
        raw = self._run([self.cli, "billing", "rates", "--profile", "rivals", "--json"])
        values = unpack(raw)
        # v1 deliberately supports the measured L40S / 8 CPU / 32 GiB class only.
        rate = (usd(values["gpu_hour_cost_l40s"]) + 8 * usd(values["cpu_hour_cost"])
                + 32 * usd(values["mem_gib_hour_cost"])) / 3600
        return rate, raw


def unpack(raw):
    require(raw["returncode"] == 0 and hashlib.sha256(raw["stdout"].encode()).hexdigest()
            == raw["sha256"], "query evidence mismatch")
    return json.loads(raw["stdout"])


def snapshot_values(value):
    require(value["identity"] == IDENTITY and value["complete"] is True
            and unpack(value["raw"]["identity"]) == IDENTITY, "incomplete/wrong-workspace inventory")
    apps, containers = unpack(value["raw"]["apps"]), unpack(value["raw"]["containers"])
    require(type(apps) is list and type(containers) is list, "invalid inventory")
    require(len({r["app_id"] for r in apps}) == len(apps), "duplicate app inventory")
    for row in apps:
        require(isinstance(row["app_id"], str) and row["app_id"].startswith("ap-")
                and isinstance(row["description"], str), "invalid app inventory row")
    for row in containers:
        require(isinstance(row["app_id"], str) and row["app_id"].startswith("ap-"),
                "invalid container inventory row")
    return apps, containers


def billing_values(value):
    require(value["identity"] == IDENTITY and unpack(value["raw"]["identity"]) == IDENTITY,
            "billing workspace mismatch")
    summary = unpack(value["raw"]["summary"])
    reports = value["raw"]["reports"]
    require(type(reports) is list and reports, "billing report unavailable")
    rows = []
    for report in reports:
        batch = unpack(report)
        require(type(batch) is list, "billing report unavailable")
        rows.extend(batch)
    by_app = {}
    for row in rows:
        require(row["interval_start"].startswith(value["month"] + "-"), "billing interval mismatch")
        key = row["object_id"]
        by_app[key] = by_app.get(key, usd("0")) + usd(row["cost"])
    # Metered, not net-of-credit billed dollars. Never let credits increase the cap.
    return max(usd(summary["metered_cost"]), sum(by_app.values(), usd("0"))), by_app


def month_at(now):
    return datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m")


if __name__ == "__main__":
    require(sys.argv[1:] == ["identity"], "identity probe only")
    connect()
    print(json.dumps(IDENTITY))
