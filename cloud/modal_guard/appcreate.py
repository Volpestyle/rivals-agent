"""Reviewed a6 transport reduced to a workspace-wide, exact-attempt adapter.

Stable idempotency key only for explicit RESOURCE_EXHAUSTED; never retry an
unknown transport outcome, a completed AppCreate, or a paid function call.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import random
import time
import uuid

from .common import elapsed_time, SDK_VERSION, Refused, atomic, clock_id, lock, read, require

SPACING_SECONDS = 15
RPC_TIMEOUT_SECONDS = 15


class AppCreateGate:
    def __init__(self, original, attempts, attempt, *, exhausted, before_rpc,
                 wall=time.time, monotonic=elapsed_time, sleep=asyncio.sleep, uniform=random.uniform):
        self.original, self.attempts, self.attempt = original, attempts, attempt
        self.exhausted, self.before_rpc = exhausted, before_rpc
        self.wall, self.mono, self.sleep, self.uniform = wall, monotonic, sleep, uniform
        self.row = attempts.get(attempt)
        require(self.row["state"] == "READY", "fresh reserved attempt required")
        self.key, self.used = str(uuid.uuid4()), False
        self.root = Path(attempts.root)
        self.state = self.root / "appcreate-pacing.json"

    def remaining(self):
        self.attempts.startup_open(self.attempt, monotonic=self.mono)
        left = min(self.row["started_at"] + self.row["timing"]["startup_seconds"] - self.wall(),
                   self.row["started_monotonic"] + self.row["timing"]["startup_seconds"] - self.mono())
        require(left > 0, "AppCreate startup deadline")
        return left

    async def pause(self, seconds):
        end = self.mono() + seconds
        while self.mono() < end:
            await self.sleep(min(.1, self.remaining(), end - self.mono()))

    @asynccontextmanager
    async def serialized(self):
        # Queue for the whole startup window, not a fixed ten-second lock
        # timeout that would refuse the other arms of a five-app paced burst.
        while True:
            self.remaining()
            context = lock(self.root / "appcreate.lock", timeout=0)
            try:
                context.__enter__()
                break
            except Refused as exc:
                if str(exc) != "workspace lock timed out":
                    raise
                await self.pause(.1)
        try:
            yield
        finally:
            context.__exit__(None, None, None)

    async def __call__(self, request, **kwargs):
        require(not self.used, "logical AppCreate already used")
        self.used = True
        require(not kwargs and request.description == self.row["app_name"], "AppCreate name differs from approved attempt")
        # Each arm lives in its own process; the shared lock spans campaigns.
        async with self.serialized():
            if self.state.exists():
                previous = read(self.state)
                if previous["outcome"] in ("IN_FLIGHT", "UNKNOWN"):
                    require(self.attempts.get(previous["attempt_id"])["state"] == "ABSENT_RPC",
                            "uncertain prior AppCreate; reconcile first")
            count = 0
            while True:
                if self.state.exists():
                    previous = read(self.state)
                    require(previous.get("clock_id") == clock_id(), "pacing clock continuity lost")
                    require(self.mono() >= previous["monotonic"], "pacing clock moved backwards")
                    while self.mono() - previous["monotonic"] < SPACING_SECONDS:
                        await self.pause(max(.001, SPACING_SECONDS - (self.mono() - previous["monotonic"])))
                self.remaining()
                await asyncio.wait_for(self.before_rpc(), timeout=self.remaining())
                timeout = min(RPC_TIMEOUT_SECONDS, self.remaining())
                self.attempts.rpc(self.attempt, "CREATING")  # durable before any RPC; crash => unknown
                def record(outcome):
                    atomic(self.state, {"attempt_id": self.attempt, "logical_request_id": self.key,
                                        "outcome": outcome, "wall": self.wall(),
                                        "monotonic": self.mono(), "clock_id": clock_id()})
                record("IN_FLIGHT")
                try:
                    response = await asyncio.wait_for(self.original(
                        request, retry=None, timeout=timeout,
                        metadata=[("x-idempotency-key", self.key), ("x-retry-attempt", str(count)),
                                  ("x-throttle-retry-attempt", str(count)),
                                  ("x-modal-timestamp", str(self.wall()))]), timeout=timeout)
                except self.exhausted:
                    self.attempts.rpc(self.attempt, "REJECTED")
                    record("REJECTED")
                    maximum = min(60, 5 * 2 ** min(count, 10))
                    delay = self.uniform(maximum / 2, maximum)
                    require(maximum / 2 <= delay <= maximum, "invalid jitter")
                    count += 1
                    await self.pause(delay)
                    continue
                except BaseException:
                    self.attempts.rpc(self.attempt, "UNKNOWN")
                    record("UNKNOWN")
                    raise
                # A bad/late response leaves CREATING/IN_FLIGHT, never a retry.
                from .lifecycle import warning
                try:
                    self.attempts.rpc(self.attempt, "RUNNING", app_id=response.app_id)
                    record("CREATED")
                except Exception as exc:
                    # IN_FLIGHT continues blocking new apps, but recording failure
                    # must not destroy this known detached app or hide its ID.
                    warning("AppCreate receipt pending for " + response.app_id + ": " + repr(exc))
                return response


def install(client, attempts, attempt, *, before_rpc):
    """No historical suffix allowlist. Identity/spec is the reserved exact attempt."""
    import modal
    import modal.exception
    from modal._grpc_client import UnaryUnaryWrapper
    from modal._utils.async_utils import synchronizer
    require(modal.__version__ == SDK_VERSION, "unreviewed SDK version")
    internal = synchronizer._translate_in(client)
    original = internal.stub.AppCreate
    require(isinstance(original, UnaryUnaryWrapper)
            and original.name == "/modal.client.ModalClient/AppCreate", "unreviewed SDK RPC seam")
    gate = AppCreateGate(original, attempts, attempt, exhausted=modal.exception.ResourceExhaustedError,
                         before_rpc=before_rpc)
    internal.stub.AppCreate = gate

    def restore():
        require(internal.stub.AppCreate is gate, "AppCreate stub changed")
        internal.stub.AppCreate = original
    return restore
