"""Bounded diagnostic-line preservation; never copies arbitrary stderr tails."""
import hashlib
import json
import os
import stat

MAX_TAIL_BYTES = 262144
MAX_LINE_BYTES = 16384
MAX_MATCHES = 4

def validate_contract(contract):
    if not isinstance(contract, dict):
        raise ValueError("missing reviewed diagnostic contract")
    prefix = contract.get("prefix")
    if not isinstance(prefix, str) or not 1 <= len(prefix) <= 128:
        raise ValueError("missing reviewed diagnostic prefix")
    if not prefix.isascii() or any(ord(c) < 32 or ord(c) > 126 for c in prefix):
        raise ValueError("invalid diagnostic prefix")
    if contract.get("tail_bytes") != MAX_TAIL_BYTES or contract.get("max_line_bytes") != MAX_LINE_BYTES:
        raise ValueError("diagnostic bounds differ")
    if prefix != "CM3_RUNTIME_MISMATCH " or contract.get("schema") != "cm3-runtime-mismatch-v1":
        raise ValueError("diagnostic protocol differs")
    return prefix.encode("ascii")

def capture_diagnostic(path, contract):
    prefix = validate_contract(contract)
    result = {"status": "NOT_FOUND", "source": str(path), "channel": "owner stderr merged into runner.log",
              "tail_bytes_limit": MAX_TAIL_BYTES, "line_bytes_limit": MAX_LINE_BYTES,
              "tail_truncated": False, "lines": [], "oversize_matches": 0, "omitted_matches": 0}
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                result["status"] = "UNSAFE_LOG_TYPE"
                return result
            start = max(0, info.st_size - MAX_TAIL_BYTES)
            stream.seek(start)
            data = stream.read(MAX_TAIL_BYTES)
            result.update(log_bytes=info.st_size, read_bytes=len(data), tail_truncated=start > 0)
        if start:
            # Discard potentially partial first line, even if it happens to resemble a prefix.
            cut = data.find(b"\n")
            if cut < 0:
                result["status"] = "NO_COMPLETE_LINE_IN_TAIL"
                return result
            data = data[cut + 1:]
        for raw in data.splitlines(keepends=True):
            if not raw.startswith(prefix):
                continue
            if len(raw) > MAX_LINE_BYTES:
                result["oversize_matches"] += 1
                continue
            try:
                line = raw.decode("ascii", errors="strict")
            except UnicodeDecodeError:
                result["status"] = "INVALID_UTF8_DIAGNOSTIC"
                continue
            try:
                payload = json.loads(raw[len(prefix):])
                json_valid = True
                protocol_valid = isinstance(payload, dict) and payload.get("format") == contract["schema"] and payload.get("kind") in ("software", "hardware")
            except (ValueError, UnicodeDecodeError):
                json_valid = False
                protocol_valid = False
            result["lines"].append({"line": line, "bytes": len(raw),
                                    "sha256": hashlib.sha256(raw).hexdigest(), "json_payload_valid": json_valid, "protocol_valid": protocol_valid,
                                    "complete_line": raw.endswith(b"\n")})
            if len(result["lines"]) > MAX_MATCHES:
                result["lines"].pop(0)
                result["omitted_matches"] += 1
        if result["lines"]:
            result["status"] = "CAPTURED"
        elif result["oversize_matches"]:
            result["status"] = "OVERSIZE_DIAGNOSTIC"
        return result
    except FileNotFoundError:
        result["status"] = "LOG_ABSENT"
        return result
    except OSError as exc:
        result.update(status="LOG_READ_ERROR", error_type=type(exc).__name__)
        return result
