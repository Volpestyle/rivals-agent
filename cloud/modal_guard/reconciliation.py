"""Conservative terminal billing coverage; no credit from partial per-app totals."""
from datetime import datetime, timezone
import hashlib

from .common import Refused, json_bytes, require, usd
from .provider import billing_values, snapshot_values, unpack


def timestamp(value, *, utc_default=False):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        require(utc_default, "terminal timestamp lacks timezone")
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def hourly_report(report, month):
    """Only the exact UTC, unsplit native report command establishes coverage."""
    command = report["command"]
    require(len(command) == 14 and command[1:4] == ["billing", "report", "--start"]
            and command[5] == "--end" and command[7:] ==
            ["--resolution", "h", "--tag-names", "lane,run", "--profile", "rivals", "--json"],
            "unrecognized hourly query")
    start, end = (timestamp(command[i], utc_default=True) for i in (4, 6))
    require(start < end and start % 3600 == end % 3600 == 0
            and end - start <= 7 * 86400 and command[4].startswith(month + "-"),
            "invalid hourly range")
    require(end <= report["queried_at"] <= report["completed_at"], "hourly range not closed")
    rows = unpack(report)
    require(type(rows) is list, "invalid hourly rows")
    indexed = {}
    for row in rows:
        hour = timestamp(row["interval_start"], utc_default=True)
        key = (row["object_id"], hour)
        require(start <= hour < end and hour % 3600 == 0 and key not in indexed,
                "duplicate/out-of-range billing bucket")
        indexed[key] = usd(row["cost"])
    return start, end, indexed


def terminal_actuals(billing, attempts):
    """Return included actuals only for fully covered, authenticated terminal apps.

    A query must include every occupied hour and one *closed* hour after the
    stopping hour. An absent occupied bucket is unknown, never zero. The trailing
    hour needs range coverage, not a fabricated zero-cost row for a stopped app.
    The one-hour buffer is an explicit policy, not a provider finality guarantee.
    No durable credit is stored: loss of evidence restores the retained allowance.
    """
    billing_values(billing)  # includes these very report dollars in the floor
    reports = []
    for report in billing["raw"]["reports"]:
        try:
            reports.append((report, hourly_report(report, billing["month"])))
        except (Refused, KeyError, TypeError, ValueError, IndexError):
            continue  # legacy/daily/partial evidence cannot release an allowance
    actuals = {}
    for attempt, row in attempts.items():
        if row["state"] != "TERMINAL" or not row.get("app_id"):
            continue
        try:
            # App billing cannot prove that non-app storage/setup overhead is
            # included. Missing/invalid legacy overhead means no reconciliation.
            overhead = usd(row["hold"]["overhead_usd"])
            proof = row["proof"]
            require(proof["kind"] == "TERMINAL" and proof["attempt_id"] == attempt
                    and proof["app_name"] == row["app_name"], "no bound terminal proof")
            snapshot = proof["snapshots"][-1]
            apps, containers = snapshot_values(snapshot)
            owned = [a for a in apps if a["app_id"] == row["app_id"]
                     or a["description"] == row["app_name"]]
            require(len(owned) == 1 and owned[0]["app_id"] == row["app_id"]
                    and owned[0]["description"] == row["app_name"]
                    and owned[0]["state"] == "stopped" and str(owned[0]["tasks"]) == "0"
                    and not any(c["app_id"] == row["app_id"] for c in containers), "not terminal")
            created = timestamp(owned[0]["created_at"])
            stopped = timestamp(owned[0]["stopped_at"])
            require(created <= stopped <= snapshot["checked_at"], "invalid terminal times")
            first, last = int(created // 3600) * 3600, int(stopped // 3600) * 3600
            for report, (start, end, indexed) in reports:
                if not (start <= first and last + 7200 <= end):
                    continue
                hours = range(first, last + 3600, 3600)
                if not all((row["app_id"], hour) in indexed for hour in hours):
                    continue
                # Include any extra reported app rows too; never cap actuals at
                # the old estimate. Report total, not summary overlap, proves inclusion.
                amount = sum((v for (app, _), v in indexed.items() if app == row["app_id"]), usd("0"))
                actuals[attempt] = {"app_id": row["app_id"], "actual_usd": str(amount),
                                    "retained_overhead_usd": str(overhead),
                                    "created_at": created, "stopped_at": stopped,
                                    "coverage_start": start, "coverage_end": end,
                                    "report_sha256": hashlib.sha256(json_bytes(report)).hexdigest()}
                break
        except (Refused, KeyError, TypeError, ValueError, IndexError):
            continue
    return actuals
