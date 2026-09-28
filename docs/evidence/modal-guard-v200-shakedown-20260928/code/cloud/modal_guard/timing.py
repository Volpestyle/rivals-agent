"""Measured timing only. Billing, dollar budgets and notice policy belong to the lead."""
import math

from .common import number, pinned, require


def derive(samples, *, workload, concurrency, factor=1.25, margin_seconds=30, evidence_sha256):
    require(len(samples) >= 20, "p95 requires at least 20 complete samples")
    require(number(factor, positive=True) > 1 and number(margin_seconds, positive=True) > 0, "positive p95 margin required")
    require(type(concurrency) is int and concurrency > 0 and bool(workload), "workload/concurrency required")
    require(all(r["complete"] is True and r["workload"] == workload and r["concurrency"] == concurrency for r in samples),
            "mismatched/censored measurement")
    limits, measured = {}, {}
    for phase in ("startup", "work", "cleanup"):
        values = sorted(number(r[phase + "_seconds"], phase, positive=True) for r in samples)
        measured[phase] = values[math.ceil(.95 * len(values)) - 1]
        limits[phase + "_seconds"] = math.ceil(measured[phase] * factor + margin_seconds)
    require(limits["work_seconds"] <= 86400, "Modal function timeout maximum exceeded")
    return {**limits, "measurement": {"workload": workload, "concurrency": concurrency,
                                     "p95": measured, "factor": factor, "margin_seconds": margin_seconds,
                                     "sha256": evidence_sha256}}


def validate_spec(spec):
    timing = spec["timing"]
    if timing.get("mode") == "measured-projection":
        # Explicit lead-approved extrapolation, never labelled whole-fit p95.
        projection = pinned(spec["measurement_ref"])
        require(projection["kind"] == "measured-projection" and bool(projection["basis"])
                and projection["accepted_by"] == "herdr-lead", "accepted projection basis required")
        require(projection["evidence_refs"], "projection evidence required")
        for ref in projection["evidence_refs"]:
            pinned(ref)
        seconds = number(projection["projected_work_seconds"], positive=True)
        margin = number(projection["factor"], positive=True)
        require(margin > 1 and timing["work_seconds"] == math.ceil(seconds * margin),
                "projection plus margin mismatch")
        require(all(type(timing[k]) is int and timing[k] > 0 for k in
                    ("startup_seconds", "work_seconds", "cleanup_seconds"))
                and timing["work_seconds"] <= 86400, "invalid native projection timeouts")
        require(timing["startup_seconds"] == projection["startup_seconds"]
                and timing["cleanup_seconds"] == projection["cleanup_seconds"], "projection overhead timing mismatch")
        return
    if timing.get("mode") == "v2-shakedown":
        require(spec["lane"] == "modal-port" and all(s.get("kind") == "diagnostic" for s in spec["stages"]),
                "bootstrap exception is diagnostic only")
        require(all(type(timing[k]) is int for k in ("work_seconds", "startup_seconds", "cleanup_seconds")), "integer native timeouts required")
        require(0 < number(timing["work_seconds"], positive=True) <= 180
                and 0 < number(timing["startup_seconds"], positive=True) <= 300
                and 0 < number(timing["cleanup_seconds"], positive=True) <= 120,
                "shakedown native timing envelope exceeded")
        require(bool(timing.get("basis")), "exploratory timing basis required; no p95 claim")
        return
    evidence = pinned(spec["measurement_ref"])
    m = timing["measurement"]
    require(spec["measurement_ref"]["sha256"] == m["sha256"], "measurement reference mismatch")
    require(derive(evidence["samples"], workload=m["workload"], concurrency=m["concurrency"],
                   factor=m["factor"], margin_seconds=m["margin_seconds"], evidence_sha256=m["sha256"]) == timing,
            "timeouts differ from measured p95 plus margin")
