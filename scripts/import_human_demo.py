"""Import one explicitly reviewed OBS session, or export causal KBM samples."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.human_demos import DemoError, export_dataset, import_session, load_dataset


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("import", help="Validate logs and actual decoded file PTS")
    ingest.add_argument("--session", type=Path, required=True)
    ingest.add_argument("--review", type=Path, required=True)
    ingest.add_argument("--ffprobe", default="ffprobe")
    export = commands.add_parser("export", help="Export causal samples; training alignment gate is on")
    export.add_argument("--dataset", type=Path, required=True)
    export.add_argument("--history-ns", type=int, default=500_000_000)
    export.add_argument("--frame-step-ns", type=int, default=100_000_000)
    export.add_argument("--bin-ns", type=int, default=100_000_000)
    export.add_argument("--bins", type=int, default=5)
    export.add_argument("--stride-ns", type=int, default=100_000_000)
    export.add_argument("--inspection-only", action="store_true",
                        help="Allow uncalibrated inspection/evaluation; not training authorization")
    for command in (ingest, export):
        command.add_argument("--splits", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--unseal-test", action="store_true",
                             help="Explicit test payload access (requires separate project authorization)")
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            dataset = import_session(args.session, review=args.review, splits=args.splits,
                output=args.output, unseal=args.unseal_test, ffprobe=args.ffprobe)
            report = {"session_id": dataset.placement.session_id,
                      "audit": json.loads(dataset.audit_json), "output": str(args.output)}
        else:
            dataset = load_dataset(args.dataset, splits=args.splits, unseal=args.unseal_test)
            count = export_dataset(dataset, args.output, history_ns=args.history_ns,
                frame_step_ns=args.frame_step_ns, bin_ns=args.bin_ns, bins=args.bins,
                stride_ns=args.stride_ns, for_training=not args.inspection_only)
            report = {"samples": count, "output": str(args.output),
                      "for_training": not args.inspection_only}
        print(json.dumps(report, indent=2))
        return 0
    except (DemoError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
