"""Mac launch or reattachment. No billing, ledger or deadline daemon."""
import argparse
import json


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    launch = sub.add_parser("run")
    launch.add_argument("spec")
    launch.add_argument("spec_sha256")
    launch.add_argument("release_sha256")
    recover = sub.add_parser("reattach")
    recover.add_argument("attempt")
    recover.add_argument("release_sha256")
    recover.add_argument("--observe-only", action="store_true")
    args = parser.parse_args()
    if args.command == "run":
        from .runner import run_arm
        result = run_arm({"path": args.spec, "sha256": args.spec_sha256}, args.release_sha256)
    else:
        from .runner import reattach
        result = reattach(args.attempt, args.release_sha256, cleanup=not args.observe_only)
    print(json.dumps(result))
    return 0 if result["execution"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
