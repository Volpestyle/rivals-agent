"""Explicit CLI; no default action and no automatic paid retries."""
import argparse
import json
from pathlib import Path
import time

from .common import DEFAULT_ROOT, atomic, caffeinated, read
from .ledger import Ledger
from .lifecycle import watch
from .provider import Provider, month_at


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    launch = sub.add_parser("run")
    launch.add_argument("spec")
    launch.add_argument("spec_sha256")
    launch.add_argument("release_sha256")
    guard = sub.add_parser("watch")
    guard.add_argument("ledger")
    guard.add_argument("attempt")
    guard.add_argument("driver_pid", type=int)
    initialize = sub.add_parser("init", help="Read-only billing query; create fresh monthly local journal")
    initialize.add_argument("reports", help="JSON with reports and external_holds; estimates stay annotations")
    initialize.add_argument("--cap", default="100")
    sub.add_parser("status", help="Refresh provider actuals and show shared monthly/weekend headroom")
    policy = sub.add_parser("configure-policy", help="Apply installed lead acceptance to existing journal")
    policy.add_argument("release_sha256")
    args = parser.parse_args()
    if args.command == "configure-policy":
        ledger = Ledger(DEFAULT_ROOT / (month_at(time.time()) + ".sqlite3"))
        ledger.configure_policy(args.release_sha256)
        print(json.dumps({"configured": True, "release_sha256": args.release_sha256}))
        return 0
    if args.command in ("init", "status"):
        month = month_at(time.time())
        path = DEFAULT_ROOT / (month + ".sqlite3")
        billing = Provider().billing(month)
        if args.command == "init":
            reports = read(args.reports)
            ledger = Ledger.initialize(path, billing, cap_usd=args.cap,
                                       reports=reports["reports"], external_holds=reports["external_holds"])
        else:
            ledger = Ledger(path)
            ledger.refresh(billing)
        print(json.dumps(ledger.totals(), indent=2))
        return 0
    if args.command == "run":
        from .runner import run_arm
        result = run_arm({"path": args.spec, "sha256": args.spec_sha256}, args.release_sha256)
        return 0 if result["status"] == "COMPLETE" else 1
    ledger = Ledger(args.ledger)
    provider = Provider()
    with caffeinated():
        provider.identity()
        # Never advertise readiness before acquiring the initial funded row.
        row = ledger.get(args.attempt)
        ledger.funded(args.attempt)
        atomic(Path(args.ledger).parent / "attempts" / args.attempt / "watchdog-ready.json",
               {"identity_verified": True, "idle_sleep_inhibited": True}, fresh=True)
        watch(ledger, args.attempt, provider, args.driver_pid, initial_row=row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
