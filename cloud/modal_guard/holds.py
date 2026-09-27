"""Nearest-rank measured p95 plus explicit margin; never inferred from mean throughput."""
from __future__ import annotations

import math

from .common import cost, number, require, usd


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
