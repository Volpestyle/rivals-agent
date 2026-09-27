"""Small, strict primitives shared by the launcher and its evidence readers."""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import time
import uuid
import functools
import subprocess
import sys

IDENTITY = {"profile": "rivals", "workspace": "volpestyle",
            "workspace_id": "ac-kMLf5bJKqF5CAlSbfNhGh0"}
SDK_VERSION = "1.5.5"
DEFAULT_ROOT = Path.home() / "dev/modal_guard/volpestyle"


def elapsed_time():
    """Suspend-inclusive clock. Darwin RAW maps to mach_continuous_time.

    Apple Libc gen/clock_gettime.c distinguishes this from CLOCK_UPTIME_RAW and
    Python time.monotonic(), which use mach_absolute_time and pause in sleep.
    """
    if sys.platform == "darwin":
        return time.clock_gettime(time.CLOCK_MONOTONIC_RAW)
    if sys.platform.startswith("linux"):
        return time.clock_gettime(time.CLOCK_BOOTTIME)
    return time.monotonic()  # offline Windows only; paid runner refuses Windows


@contextmanager
def caffeinated():
    """Prevent Mac idle sleep for this owner process, including its teardown."""
    require(sys.platform == "darwin", "paid control requires the Mac")
    child = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())])
    try:
        require(child.poll() is None, "caffeinate failed")
        yield child
    finally:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=2)


@functools.lru_cache(maxsize=1)
def clock_id():
    """Identify the host boot, not a wall/uptime subtraction that NTP can change.

    Paid launch is Mac-only. Other platforms support offline tests; the Windows
    fallback deliberately cannot establish continuity across fresh processes.
    """
    if sys.platform == "darwin":
        boot = subprocess.check_output(["/usr/sbin/sysctl", "-n", "kern.bootsessionuuid"], timeout=2).decode().strip()
    elif sys.platform.startswith("linux"):
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    else:
        boot = "offline-process-" + uuid.uuid4().hex
    # uuid.getnode() can fall back to a fresh random value in each Mac process.
    # The kernel boot-session UUID is already host/boot unique and NTP-independent.
    return hashlib.sha256(("suspend-inclusive-v1:" + sys.platform + boot).encode()).hexdigest()


class Refused(RuntimeError):
    """No further paid work is permitted; existing holds are retained."""


def require(ok, message):
    if not ok:
        raise Refused(message)


def number(value, name="number", *, positive=False):
    require(type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0), "invalid " + name)
    return value


def usd(value):
    require(type(value) in (str, int, float, Decimal), "invalid dollars")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise Refused("invalid dollars") from exc
    require(result.is_finite() and result >= 0, "invalid dollars")
    return result


def cost(seconds, rate, overhead="0"):
    return str((Decimal(str(number(seconds))) * usd(rate) + usd(overhead)).quantize(
        Decimal("0.000001"), rounding=ROUND_CEILING))


def name(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", value),
            "invalid identifier")
    return value


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def read(path):
    return json.loads(Path(path).read_bytes())


def pin(path):
    return {"path": str(Path(path).resolve()), "sha256": sha256(path)}


def pinned(ref):
    require(set(ref) == {"path", "sha256"} and sha256(ref["path"]) == ref["sha256"],
            "evidence hash mismatch")
    return read(ref["path"])


def atomic(path, value, *, fresh=False):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    if fresh:
        # Hard-link publication refuses overwrite, including a concurrent publisher.
        os.link(temporary, path)
        temporary.unlink()
    else:
        os.replace(temporary, path)


def artifact(root, relative):
    require(isinstance(relative, str) and "\\" not in relative and ":" not in relative,
            "invalid artifact path")
    rel = PurePosixPath(relative)
    require(not rel.is_absolute() and rel.parts and ".." not in rel.parts
            and str(rel) == relative, "artifact escapes root")
    root = Path(root).resolve(strict=True)
    path = root.joinpath(*rel.parts)
    require(not any(p.is_symlink() for p in [path, *path.parents] if p != root)
            and path.resolve().is_relative_to(root), "symlink/escaping artifact")
    return path


@contextmanager
def lock(path, *, timeout=10):
    """Host-local advisory lock; all launchers use the same Mac root, never a Volume."""
    end = elapsed_time() + timeout
    with Path(path).open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            def acquire():
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            def release():
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            def acquire():
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            def release():
                fcntl.flock(stream, fcntl.LOCK_UN)
        while True:
            try:
                acquire()
                break
            except OSError:
                require(elapsed_time() < end, "workspace lock timed out")
                time.sleep(.02)
        try:
            yield
        finally:
            release()
