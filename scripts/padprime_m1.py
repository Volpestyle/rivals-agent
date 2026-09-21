"""M1: does ONE camera-only pulse end the attach drift, and how early can it go out? (VUH-1314)

  python scripts/padprime_m1.py --at earliest     # the earliest guarded send after the pad attaches
  python scripts/padprime_m1.py --at 0.1          # or 0.1 / 0.3 s after the attach

One pad session per invocation, no retries, no brain. In the Practice Range, from the supervised arrival's end pose, with the native
screen recording running: controller.Live proves the range HUD before the pad opens; after the attach a fresh frame acquired after it is
proven (range HUD, no idle banner); at the scheduled time the pulse goes out through Live.send / Live.hold (right stick rx 0.45, every
other axis, trigger and button neutral, 0.3 s; re-proven, whitelisted and leased at every write), then neutral, then 3 s of frames only,
then Live.close and the device goes with the process. Any guard failure or refusal ends it with the pad neutral and exit 1.

Prints one JSON line: perf_counter and wall-clock times of the constructor start, the attach (VX360Gamepad returned), the post-attach
proof, the first and last non-neutral writes, the release, the close; the yaw is read from the recording (rivals-l4's method). A nominal
"earliest" still waits for capture and proof: that latency is what it measures. This script is input-path code: review before live use.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.controller import NEUTRAL, Live  # noqa: E402  (puts scripts/ on sys.path)
from agent.startup import START_TURN_RX, START_TURN_S, watch_pad  # noqa: E402

OBSERVE_S = 3.0


def run(at, live_factory=Live, make_pad=None, clock=time.perf_counter, wall=time.time, sleep=time.sleep, guard=None, idle=None):
    if guard is None or idle is None:
        from record import idle_warning, in_range
        guard, idle = guard or in_range, idle or idle_warning
    if make_pad is None:
        import vgamepad as vg
        make_pad = vg.VX360Gamepad
    stamps, rec = {}, {}

    def stamp(name):
        stamps[name] = {"perf": round(clock(), 4), "wall": round(wall(), 4)}

    def pad():
        p = make_pad()
        stamp("attached")                                              # the constructor has returned: the drift starts about now
        rec.update(watch_pad(p, clock))
        return p

    def proven_frame(after):
        f = live.fresh()
        if live.frame_t <= after:
            raise RuntimeError("no frame acquired after the pad attached")
        if not guard(f) or idle(f):
            raise RuntimeError("the range HUD is gone or the idle banner is up")
        return f

    stamp("constructor_start")
    live = live_factory(pad_factory=pad, settle_s=0)                   # proves the range HUD before the pad opens
    try:
        attached = stamps["attached"]["perf"]
        if at != "earliest":
            while clock() < attached + float(at):
                sleep(0.001)
        proven_frame(attached)
        stamp("proven")
        pulse, sent = {**NEUTRAL, "rx": START_TURN_RX}, clock()
        live.send(**pulse)
        live.hold(max(0.0, START_TURN_S - (clock() - sent)), **pulse)
        stamp("released")
        end = clock() + OBSERVE_S
        last = live.frame_t
        while clock() < end:                                           # frames only: the drift, if any, shows in the recording
            proven_frame(last)
            last = live.frame_t
            sleep(0.02)
        outcome = "ok"
    except Exception as e:                                             # noqa: BLE001 - reported, not retried
        outcome = f"stopped: {type(e).__name__}: {e}"
    finally:
        live.close()
        stamp("closed")
    reports = rec.get("reports", [])
    active = [t for t, on in reports if on]
    return {"at": at, "outcome": outcome, "stamps": stamps,
            "first_non_neutral_write": round(active[0], 4) if active else None,
            "last_non_neutral_write": round(active[-1], 4) if active else None,
            "first_neutral_after": round(next((t for t, on in reports if active and t > active[-1] and not on), 0.0), 4) or None,
            "reports": len(reports)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--at", required=True, choices=("earliest", "0.1", "0.3"))
    out = run(ap.parse_args(argv).at)
    print(json.dumps(out))
    return 0 if out["outcome"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
