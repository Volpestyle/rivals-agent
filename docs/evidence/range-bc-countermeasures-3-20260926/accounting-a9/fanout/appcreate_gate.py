"""DRAFT: serialize AppCreate only; never dispatch or retry a fit.

Installed only in each fresh task process, around the verified Modal client's
AppCreate stub. Existing reservations, clocks, guards and cleanup are unchanged.
"""
import asyncio
import fcntl
import json
import math
import pathlib
import random
import time
import uuid

IDENTITY = {"profile": "rivals", "workspace": "volpestyle",
            "workspace_id": "ac-kMLf5bJKqF5CAlSbfNhGh0"}
POLICY = {"spacing_seconds": 15.0, "base_backoff_seconds": 5.0,
          "maximum_backoff_seconds": 60.0, "rpc_timeout_seconds": 15.0,
          "poll_seconds": 0.1, "startup_seconds": 300}
SDK_VERSION = "1.5.5"


class CreationStopped(RuntimeError):
    pass


def read(path):
    return json.loads(pathlib.Path(path).read_bytes())


def atomic(path, value):
    path = pathlib.Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.flush()
        import os
        os.fsync(f.fileno())
    temporary.replace(path)


class AppCreateGate:
    def __init__(self, original, local, funded, *, exhausted, policy=None,
                 monotonic=time.monotonic, wall=time.time, sleep=asyncio.sleep,
                 uniform=None, before_rpc=None):
        self.original = original
        self.before_rpc = before_rpc
        self.local = pathlib.Path(local)
        self.funded = funded
        self.exhausted = exhausted
        self.policy = dict(POLICY if policy is None else policy)
        for name, value in self.policy.items():
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError("invalid pacing policy: " + name)
        self.mono, self.wall, self.sleep = monotonic, wall, sleep
        self.uniform = uniform or random.SystemRandom().uniform
        self.inv = read(self.local / "inventory.json")
        if self.inv["identity"] != IDENTITY:
            raise CreationStopped("unverified AppCreate identity")
        bound = self.inv["bounds"]
        if bound["hold"]["startup_seconds"] != self.policy["startup_seconds"]:
            raise CreationStopped("startup allocation changed")
        self.end_mono = min(bound["stop_monotonic"],
                            bound["started_monotonic"] + self.policy["startup_seconds"])
        self.end_wall = min(bound["stop_at_unix"],
                            bound["started_at_unix"] + self.policy["startup_seconds"])
        self.key = str(uuid.uuid4())
        self.used = False
        self.app_id = None
        self.attempt = 0
        self.events = self.local / "appcreate-events"
        self.events.mkdir(exist_ok=False)
        self.state = self.local.parent / "appcreate-rate-state.json"
        self.lock = self.local.parent / "appcreate-rate.lock"
        self.started_wall = self.wall()
        self.last_outcome = "NOT_SUBMITTED"
        self._record("NOT_SUBMITTED")

    def _remaining(self):
        self.funded()
        remaining = min(self.end_mono - self.mono(), self.end_wall - self.wall())
        if remaining <= 0:
            raise CreationStopped("AppCreate startup budget exhausted")
        return remaining

    def _record(self, status, **fields):
        atomic(self.local / "appcreate.json", {
            "format": "cm3-appcreate-journal-v1", "identity": IDENTITY,
            "attempt_id": self.inv["attempt_id"], "app_name": self.inv["app_name"],
            "logical_request_id": self.key, "status": status,
            "last_rpc_outcome": self.last_outcome,
            "app_id": self.app_id, "rpc_count": self.attempt,
            "started_at_unix": self.started_wall, "recorded_at_unix": self.wall(),
            "startup_deadline_unix": self.end_wall,
            "startup_deadline_monotonic": self.end_mono,
            "reservation": self.inv["reservation"], **fields})

    def _event(self, suffix, status, **fields):
        value = {"format": "cm3-appcreate-rpc-event-v1", "identity": IDENTITY,
                 "attempt_id": self.inv["attempt_id"], "app_name": self.inv["app_name"],
                 "logical_request_id": self.key, "rpc_number": self.attempt,
                 "status": status, "at_unix": self.wall(),
                 "at_monotonic": self.mono(), **fields}
        with (self.events / ("%04d-%s.json" % (self.attempt, suffix))).open("x") as f:
            json.dump(value, f, indent=2, allow_nan=False)
            f.flush()
            import os
            os.fsync(f.fileno())

    async def _pause(self, seconds):
        # Both monotonic and wall deadlines remain active while queued/backing off.
        end = self.mono() + seconds
        while self.mono() < end:
            left = self._remaining()
            await self.sleep(min(self.policy["poll_seconds"], left, end - self.mono()))
        self._remaining()

    async def __call__(self, request, **kwargs):
        if self.used or self.app_id:
            raise CreationStopped("logical AppCreate already invoked; no app/fit replay")
        self.used = True
        if kwargs or request.description != self.inv["app_name"]:
            raise CreationStopped("unexpected AppCreate request")
        if self.inv.get("apps") or self.inv.get("creation_finished"):
            raise CreationStopped("app already exists")
        try:
            # Separate file descriptions serialize across all task processes.
            with self.lock.open("a") as lock:
                while True:
                    self._remaining()
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        await self._pause(self.policy["poll_seconds"])
                try:
                    return await self._locked(request)
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)
        except BaseException as exc:
            self._record("INCOMPLETE", error_type=type(exc).__name__,
                         reason=str(exc)[:1000])
            raise

    async def _locked(self, request):
        if self.state.exists():
            previous = read(self.state)
            if previous["identity"] != IDENTITY:
                raise CreationStopped("pacing identity changed")
            if previous["outcome"] in ("IN_FLIGHT", "UNKNOWN"):
                raise CreationStopped("prior AppCreate outcome unknown; reconciliation required")
        while True:
            self._remaining()
            if self.state.exists():
                previous = read(self.state)
                spacing = max(previous["at_monotonic"] + self.policy["spacing_seconds"] - self.mono(),
                              previous["at_unix"] + self.policy["spacing_seconds"] - self.wall(), 0)
                if spacing:
                    await self._pause(spacing)
            if self.before_rpc is not None:
                await asyncio.wait_for(self.before_rpc(), timeout=self._remaining())
            timeout = min(self.policy["rpc_timeout_seconds"], self._remaining())
            self.attempt += 1
            self.last_outcome = "UNKNOWN"
            self._event("start", "IN_FLIGHT", timeout_seconds=timeout)
            self._record("IN_FLIGHT")
            def shared(outcome):
                atomic(self.state, {"identity": IDENTITY, "outcome": outcome,
                       "logical_request_id": self.key, "attempt_id": self.inv["attempt_id"],
                       "at_monotonic": self.mono(), "at_unix": self.wall()})
            shared("IN_FLIGHT")
            metadata = [("x-idempotency-key", self.key),
                        ("x-retry-attempt", str(self.attempt - 1)),
                        ("x-throttle-retry-attempt", str(self.attempt - 1)),
                        ("x-modal-timestamp", str(self.wall()))]
            try:
                # Disable hidden SDK retries for this RPC only. Unknown transport
                # outcomes/timeouts are never retried. Stable key across rejection retries.
                response = await asyncio.wait_for(
                    self.original(request, retry=None, timeout=timeout, metadata=metadata),
                    timeout=timeout)
            except self.exhausted as exc:
                self.last_outcome = "REJECTED_RESOURCE_EXHAUSTED"
                self._event("end", self.last_outcome, error_type=type(exc).__name__,
                            message=str(exc)[:1000])
                self._record("BACKOFF")
                shared(self.last_outcome)
                maximum = min(self.policy["maximum_backoff_seconds"],
                              self.policy["base_backoff_seconds"] * (2 ** min(self.attempt - 1, 10)))
                delay = self.uniform(maximum / 2, maximum)
                if not math.isfinite(delay) or not maximum / 2 <= delay <= maximum:
                    raise CreationStopped("invalid jitter")
                await self._pause(delay)
                continue
            except BaseException as exc:
                self.last_outcome = "UNKNOWN"
                self._event("end", "UNKNOWN", error_type=type(exc).__name__,
                            message=str(exc)[:1000])
                self._record("INCOMPLETE")
                shared("UNKNOWN")
                raise
            self.app_id = response.app_id
            # Capture success immediately, before app setup/publish/fit dispatch.
            # Even a malformed or late response is never an invitation to retry.
            self.last_outcome = "CREATED"
            self._event("end", "CREATED", app_id=self.app_id)
            from lifecycle import update_inventory
            update_inventory(self.local, lambda x: x.update(
                apps=sorted(set(x["apps"]) | {self.app_id}), creation_finished=True))
            self._record("CREATED")
            shared("CREATED")
            if not isinstance(self.app_id, str) or not self.app_id.startswith("ap-"):
                raise CreationStopped("invalid returned app ID")
            self._remaining()
            return response


def install(client, local, funded, plan):
    """Private SDK seam is version-pinned; only AppCreate is replaced."""
    import modal
    import modal.client
    import modal.exception
    from modal._grpc_client import UnaryUnaryWrapper
    from modal._utils.async_utils import synchronizer
    if modal.__version__ != SDK_VERSION:
        raise CreationStopped("unreviewed SDK version")
    internal = synchronizer._translate_in(client)
    original = internal.stub.AppCreate
    if not isinstance(original, UnaryUnaryWrapper) or original.name != "/modal.client.ModalClient/AppCreate":
        raise CreationStopped("unreviewed AppCreate RPC seam")
    inv = read(pathlib.Path(local) / "inventory.json")
    if not inv["attempt_id"].startswith("r3p1-") or not inv["attempt_id"].endswith("-02"):
        raise CreationStopped("draft permits fresh -02 IDs only")
    async def live_admission():
        from late_app_guard import admit_async
        await admit_async(plan, pathlib.Path(local) / "admission-watch",
                          "before-AppCreate-RPC", client=internal)
    gate = AppCreateGate(original, local, funded,
                         exhausted=modal.exception.ResourceExhaustedError,
                         before_rpc=live_admission)
    internal.stub.AppCreate = gate
    def restore():
        if internal.stub.AppCreate is not gate:
            raise CreationStopped("AppCreate stub changed")
        internal.stub.AppCreate = original
    return restore
