"""Nearest-rank measured p95 plus explicit margin; never inferred from mean throughput."""
from __future__ import annotations

import math

from .common import cost, json_bytes, name, number, pinned, require, usd
import hashlib


def bootstrap(envelope):
    """Explicit exploratory timeout envelope. No empirical/p95 claim is made."""
    require(envelope["mode"] == "EXPLORATORY_BOOTSTRAP", "invalid bootstrap mode")
    name(envelope["campaign_id"])
    require(isinstance(envelope["workload"], str) and envelope["workload"], "workload required")
    ids = envelope["attempt_ids"]
    require(type(ids) is list and ids and len(set(ids)) == len(ids), "unique finite bootstrap slots required")
    for attempt in ids:
        name(attempt)
    require(type(envelope["concurrency"]) is int and 0 < envelope["concurrency"] <= len(ids),
            "invalid bootstrap concurrency")
    limits = {p + "_seconds": envelope[p + "_seconds"] for p in ("startup", "work", "cleanup")}
    for value in limits.values():
        require(type(value) is int and value > 0, "positive integer bootstrap duration required")
    require(usd(envelope["rate_usd_second"]) > 0, "positive all-resource rate required")
    total = sum(limits.values())
    reserved = cost(total, envelope["rate_usd_second"], envelope["overhead_usd"])
    require(usd(envelope["campaign_cap_usd"]) > 0 and
            len(ids) * usd(reserved) <= usd(envelope["campaign_cap_usd"]), "bootstrap campaign cap exceeded")
    return {**limits, "total_seconds": total, "rate_usd_second": str(usd(envelope["rate_usd_second"])),
            "overhead_usd": str(usd(envelope["overhead_usd"])), "reserved_usd": reserved,
            "bootstrap": envelope, "envelope_sha256": hashlib.sha256(json_bytes(envelope)).hexdigest()}


def validate_spec(spec):
    """Both modes use pinned evidence; a probe can never masquerade as fit p95."""
    hold = spec["hold"]
    if "bootstrap" in hold:
        require("measurement_ref" not in spec, "bootstrap cannot claim measured p95")
        envelope = pinned(spec["bootstrap_ref"])
        require(bootstrap(envelope) == hold and spec["attempt_id"] in envelope["attempt_ids"],
                "bootstrap differs from pinned envelope/slot")
    else:
        require("bootstrap_ref" not in spec, "ambiguous admission mode")
        measurement = pinned(spec["measurement_ref"])
        m = hold["measurement"]
        require(spec["measurement_ref"]["sha256"] == m["sha256"], "measurement reference mismatch")
        require(derive(measurement["samples"], workload=m["workload"], concurrency=m["concurrency"],
                       factor=m["factor"], margin_seconds=m["margin_seconds"],
                       rate_usd_second=hold["rate_usd_second"], overhead_usd=hold["overhead_usd"],
                       evidence_sha256=m["sha256"]) == hold, "hold differs from measured evidence")


def derive(samples, *, workload, concurrency, factor=1.25, margin_seconds=30,
           rate_usd_second, overhead_usd="0", evidence_sha256):
    """Rows must measure startup, whole work and terminal cleanup at target fan-out.

    Include input reads, hashing, evaluation and serialization in work_seconds.
    Timeout/censored samples are lower bounds, not completed latency measurements.
    At least 20 successful samples are required for an empirical 95th percentile.
    The separate cheap launcher shakedown is authorized/budgeted by its owner.
    """
    require(isinstance(workload, str) and workload, "workload required")
    require(type(concurrency) is int and concurrency > 0, "concurrency required")
    require(isinstance(evidence_sha256, str) and len(evidence_sha256) == 64
            and all(c in "0123456789abcdef" for c in evidence_sha256), "measurement pin required")
    require(len(samples) >= 20, "p95 requires at least 20 measured samples")
    number(factor, "factor", positive=True)
    require(factor > 1 and number(margin_seconds, "margin", positive=True) > 0,
            "positive p95 margin required")
    require(usd(rate_usd_second) > 0, "positive all-resource rate required")
    usd(overhead_usd)
    for row in samples:
        require(row["workload"] == workload and row["concurrency"] == concurrency
                and row["complete"] is True, "mismatched/censored measurement")
    measured, limits = {}, {}
    for phase in ("startup", "work", "cleanup"):
        values = sorted(number(r[phase + "_seconds"], phase, positive=True) for r in samples)
        measured[phase] = values[math.ceil(.95 * len(values)) - 1]
        limits[phase + "_seconds"] = math.ceil(measured[phase] * factor + margin_seconds)
    limits["total_seconds"] = sum(limits.values())
    return {**limits, "rate_usd_second": str(usd(rate_usd_second)),
            "overhead_usd": str(usd(overhead_usd)),
            "reserved_usd": cost(limits["total_seconds"], rate_usd_second, overhead_usd),
            "measurement": {"workload": workload, "concurrency": concurrency,
                            "count": len(samples), "p95": measured, "factor": factor,
                            "margin_seconds": margin_seconds, "sha256": evidence_sha256}}


def validate(hold):
    if "bootstrap" in hold:
        require(bootstrap(hold["bootstrap"]) == hold, "modified bootstrap hold")
        return
    for key in ("startup_seconds", "work_seconds", "cleanup_seconds", "total_seconds"):
        require(type(hold[key]) is int and hold[key] > 0, "positive integer duration required")
    require(hold["total_seconds"] == sum(hold[p + "_seconds"] for p in ("startup", "work", "cleanup")),
            "hold does not cover all phases")
    require(usd(hold["rate_usd_second"]) > 0 and usd(hold["reserved_usd"]) >= usd(
        cost(hold["total_seconds"], hold["rate_usd_second"], hold["overhead_usd"])), "underfunded hold")
    m = hold["measurement"]
    require(type(m["count"]) is int and m["count"] >= 20 and m["factor"] > 1
            and number(m["margin_seconds"], positive=True) > 0, "invalid p95 provenance")
    for phase in ("startup", "work", "cleanup"):
        expected = math.ceil(number(m["p95"][phase], positive=True) * number(m["factor"]) + m["margin_seconds"])
        require(hold[phase + "_seconds"] == expected, "duration differs from pinned p95 formula")
