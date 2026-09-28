"""Modal 1.5.5 identity and inventory; explicit rivals profile everywhere."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .common import elapsed_time, IDENTITY, SDK_VERSION, clock_id, require

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
    def __init__(self, cli=None, *, wall=time.time, monotonic=elapsed_time):
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

    def stop(self, app_id, timeout=10):
        require(isinstance(app_id, str) and app_id.startswith("ap-"), "invalid owned app ID")
        remaining = self.budget(timeout)
        self.identity(min(remaining(), 1))
        return self._run([self.cli, "app", "stop", app_id, "--profile", "rivals", "--yes"], remaining())


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


if __name__ == "__main__":
    require(sys.argv[1:] == ["identity"], "identity probe only")
    connect()
    print(json.dumps(IDENTITY))
