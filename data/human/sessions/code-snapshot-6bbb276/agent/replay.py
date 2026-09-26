"""Run the brain over a recorded JSONL of States: intent timeline + simple metrics.

  uv run python -m agent.replay run.jsonl [--hz 10] [--json]
  uv run python -m agent.replay data/synthetic.jsonl --synth   # write a synthetic run first

One State per line (State.to_dict()). States arrive at capture rate; the replay
decimates to --hz, the rate the brain runs at live (a State is kept once it is at least 0.9/hz
after the last kept one, because a real recording's frame spacing jitters around 1/hz).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .brain import Memory, decide
from .intents import Combo
from .state import ANCHOR, ENEMY, PULL, SWING, UPPERCUT, Ability, Detection, State

DECIMATE_TOL = 0.9  # keep a State when it is at least this fraction of 1/hz after the last kept one
ATTACKS = ("engage", "combo", "pull", "webstrike")  # intents that mean "started fighting"


def load(path):
    states = []
    for n, line in enumerate(Path(path).read_text().splitlines(), 1):
        if line.strip():
            try:
                states.append(State.from_dict(json.loads(line)))
            except (ValueError, KeyError, TypeError) as e:
                sys.exit(f"{path}:{n}: bad State line: {e!r}")
    return states


def label(intent):
    """Intent kind plus its one identifying argument; bbox/position changes are not a new segment."""
    kind = type(intent).__name__.lower()
    if isinstance(intent, Combo):
        return f"{kind}:{intent.name}"
    det = getattr(intent, "target", None) or getattr(intent, "anchor", None)
    return f"{kind}:{det.cls}" if det else kind


def run(states, hz=10.0):
    """[(state, intent label)] for the states the brain would see at `hz`."""
    memory, last, rows = Memory(), None, []
    for s in states:
        if last is None or s.t - last >= DECIMATE_TOL / hz:  # a recording's frame spacing jitters around 1/hz, so accept 90% of it
            last = s.t
            rows.append((s, label(decide(s, memory))))
    return rows


def timeline(rows):
    """[[label, start_t, end_t]] with consecutive equal labels merged."""
    segs = []
    for i, (s, lab) in enumerate(rows):
        end = rows[i + 1][0].t if i + 1 < len(rows) else s.t
        if segs and segs[-1][0] == lab:
            segs[-1][2] = end
        else:
            segs.append([lab, s.t, end])
    return segs


def metrics(rows, segs):
    n = len(rows)
    ts = [s.t for s, _ in rows]
    dur = ts[-1] - ts[0] if n else 0.0
    secs = Counter()
    for lab, a, b in segs:
        secs[lab.split(":")[0]] += b - a
    first = next((s.t - ts[0] for s, lab in rows if lab.split(":")[0] in ATTACKS), None)
    return {
        "ticks": n,
        "duration_s": round(dur, 2),
        "decisions_per_s": round((n - 1) / dur, 2) if dur else None,
        "switches": max(len(segs) - 1, 0),
        "segments_by_intent": dict(Counter(lab.split(":")[0] for lab, _, _ in segs)),  # disengage = retreats
        "seconds_by_intent": {k: round(v, 2) for k, v in sorted(secs.items())},
        "first_attack_s": None if first is None else round(first, 2),
        "max_gap_s": round(max((b - a for a, b in zip(ts, ts[1:])), default=0.0), 2),
        "unknown_frac": {  # share of ticks perception could not read
            "hp": round(sum(s.hp is None for s, _ in rows) / n, 3) if n else None,
            "detections": round(sum(s.detections is None for s, _ in rows) / n, 3) if n else None,
            "on_target": round(sum(s.on_target is None for s, _ in rows) / n, 3) if n else None,
        },
    }


def synthetic(hz=10):
    """A scripted story that walks the brain through every mode, the tracer branch and perception dropouts."""
    frame = (1280, 720)  # what L1 records and perception processes

    def enemy(h, x=640, tagged=None):  # h = bbox height px on a 720 px frame: 300 near, 150 mid, 45 far
        return Detection(ENEMY, (x - h / 4, 360 - h / 2, x + h / 4, 360 + h / 2), 0.9, tagged=tagged)

    anchor = Detection(ANCHOR, (900, 100, 950, 150), 0.8)
    ready = {SWING: Ability(True, 3), PULL: Ability(True), UPPERCUT: Ability(True, 2)}
    full = dict(hp=100, max_hp=100, abilities=ready, webs=3)
    story = [  # (seconds, State fields)
        (2.0, dict(full, detections=[], on_target=False)),                                        # nothing in view: search
        (3.0, dict(full, detections=[enemy(45, 450), anchor], on_target=False)),                  # far: swing in
        (1.0, dict(full, detections=[enemy(150, 550)], on_target=False)),                         # mid, tag unknown, unaimed: engage
        (1.0, dict(full, detections=[enemy(150, 550, True)], on_target=False)),                   # tag seen: web strike, no aim needed
        (2.0, dict(full, detections=[enemy(300, tagged=True)], on_target=True)),                  # close: engage, melee eats the tag
        (1.5, dict(full, detections=[enemy(150, tagged=False)], on_target=True, webs=0)),         # untagged, no ammo: pull
        (3.5, dict(full, detections=[enemy(150, tagged=False)], on_target=True)),                 # untagged, all ready: burst
        (2.0, dict(full, detections=[enemy(300)], on_target=True, hp=25)),                        # low hp: retreat
        (3.0, dict(detections=[enemy(300)], abilities=ready)),                                    # hud unreadable: stay retreating
        (3.0, dict(full, detections=[enemy(300)], on_target=True, hp=70)),                        # recovered: fight again
        (1.0, dict(full, detections=None, on_target=None)),                                       # detector down: idle
        (1.0, dict(full, detections=[enemy(150, tagged=False)], on_target=None)),                 # crosshair unreadable: geometry
        (0.3, dict(full, detections=[], on_target=False)),                                        # flicker: keep intent
        (1.0, dict(full, detections=[enemy(150, tagged=False)], on_target=True)),
        (2.0, dict(full, detections=[], on_target=False)),                                        # enemy gone: search
    ]
    states, t = [], 0.0
    for secs, fields in story:
        for _ in range(round(secs * hz)):
            states.append(State(t=round(t, 3), frame=frame, **fields))
            t += 1 / hz
    return states


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("path")
    p.add_argument("--hz", type=float, default=10.0)
    p.add_argument("--json", action="store_true", help="print metrics + timeline as JSON")
    p.add_argument("--synth", action="store_true", help="write a synthetic run to path, then replay it")
    a = p.parse_args(argv)
    if a.synth:
        Path(a.path).parent.mkdir(parents=True, exist_ok=True)
        Path(a.path).write_text("".join(json.dumps(s.to_dict()) + "\n" for s in synthetic()))
    rows = run(load(a.path), a.hz)
    segs = timeline(rows)
    m = metrics(rows, segs)
    if a.json:
        print(json.dumps({"metrics": m, "timeline": segs}, indent=1))
        return
    for lab, start, end in segs:
        print(f"{start:7.2f} - {end:7.2f}  {lab}")
    print()
    for k, v in m.items():
        print(f"{k:>20}: {v}")


if __name__ == "__main__":
    main()
