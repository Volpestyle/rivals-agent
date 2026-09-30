"""One RL episode: agent.learned_runner, unchanged, with the policy wrapped in rl.online.explore.ExploringPolicy.

  python -m rl.online.episode --explore-temp 0.5 --explore-seed 3 -- <agent.learned_runner arguments>

Every live guard, lease, deadline and pad release is the learned runner's own; this entry only substitutes the policy
object, whose steps are the base policy's decode with sampled action gates (see explore.py). The exploration log is
written next to the runner's --out directory as <out>.explore.jsonl.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    ap.add_argument("--explore-temp", type=float, default=0.0)
    ap.add_argument("--explore-seed", type=int, default=0)
    ap.add_argument("--option-rate", type=float, default=0.0, help="exploration options started per second [0, 2]")
    ap.add_argument("runner_args", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    rest = a.runner_args[1:] if a.runner_args[:1] == ["--"] else a.runner_args
    if not math.isfinite(a.explore_temp) or not 0 <= a.explore_temp <= 2:
        ap.error("explore-temp must be in [0, 2]")
    if not math.isfinite(a.option_rate) or not 0 <= a.option_rate <= 2:
        ap.error("option-rate must be in [0, 2]")
    if "--out" not in rest:
        ap.error("the learned runner's --out is required")
    log_path = Path(rest[rest.index("--out") + 1] + ".explore.jsonl")
    if log_path.exists():
        ap.error(f"{log_path} exists; preserve the previous attempt")

    import policy.live_policy as live_policy
    from rl.online.explore import ExploringPolicy
    base_cls = live_policy.LivePolicy

    def exploring(*args, **kwargs):
        return ExploringPolicy(base_cls(*args, **kwargs), temperature=a.explore_temp, seed=a.explore_seed,
                               log_path=log_path, option_rate_hz=a.option_rate)

    live_policy.LivePolicy = exploring        # learned_runner imports LivePolicy inside main(); nothing else changes
    try:
        from agent import learned_runner
        return learned_runner.main(rest)
    finally:
        live_policy.LivePolicy = base_cls


if __name__ == "__main__":
    raise SystemExit(main())
