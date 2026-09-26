"""Gate 2 step 1: the pre-registered validation draw (lane doc section 3fc13f3b, seed 20260926). Run once, before any
validation frame is decoded. Reads only container durations (ffprobe) and, for the replay, the landed operator timeline.

Per recording, an ORDERED candidate list (seed order): the first N are the registered windows; the rest are the top-ups
taken in order only if the minimum support is short (up to 15 windows per recording and kind).
Windows of the same kind never overlap; a timer window may overlap a kill-feed window (separate readers, separate
labels). v2: v1 (sha256 4a12666e..., discarded before anything was decoded) kept every window apart from every other,
so the timer top-ups crowded the 60 s kill-feed windows out (20-25-52 got 1 of 3).
"""
import json
import random
import subprocess
import sys
from pathlib import Path

SEED = 20260927
FIRST = json.load(open(str(Path(__file__).with_name('sample.json'))))   # the first draw (seed 20260926): spent
MARGIN = 60.0
V = "C:/Users/volpe/Videos/"
LIVE = {"21-13-21": "2026-09-25 21-13-21.mkv", "22-48-05": "2026-09-25 22-48-05.mkv"}   # addendum to amendment 3: fresh live sources
REPLAY = "2026-09-23 00-43-25.mkv"
REPLAY_STRETCHES = [(1071.0, 1510.6), (1893.9, 2046.5)]
TIMELINE = Path("C:/Users/volpe/repos/rivals-agent/data/demos/replays/daymr-20260923-004325/logger_timeline.json")
MAX_WINDOWS = 15


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def operator_times():
    ev = json.loads(TIMELINE.read_text(encoding="utf-8"))["events"]
    return [e["t"] for e in ev if e.get("t") is not None and ("key" in e or "mouse_down" in e or "focus" in e)]


def overlaps(a, b):
    return a[0] < b[1] and b[0] < a[1]


USED = {"19-53-04": (9, 3), "20-25-52": (9, 3), "20-56-10": (9, 3), "daymr-r2r4": (4, 2), "21-13-21": (0, 0), "22-48-05": (0, 0)}   # first-draw windows decoded


def first_windows(key):
    """The first-draw windows that were decoded and labelled (the registered ones and the top-ups used)."""
    if key not in FIRST["recordings"]:
        return []                              # never in the first draw
    r = FIRST["recordings"][key]
    nt, nf = USED[key]
    return [tuple(w) for w in r["timer_windows"][:nt] + r["feed_windows"][:nf]]


def draw(rng, spans, length, taken, n, guard=(), avoid=()):
    """n windows of `length` s, starts uniform over the union of spans (each span shortened by the length), no overlap
    with `taken`, none within 1 s of a guard time."""
    out, tries = [], 0
    total = sum(max(0.0, b - a - length) for a, b in spans)
    while len(out) < n and tries < 100000:
        tries += 1
        u = rng.uniform(0, total)
        for a, b in spans:
            w = max(0.0, b - a - length)
            if u <= w:
                s = a + u
                break
            u -= w
        win = (round(s, 3), round(s + length, 3))
        if any(overlaps(win, t) for t in taken + out):
            continue
        if any(win[0] - 1.0 <= g <= win[1] + 1.0 for g in guard):
            continue
        if any(win[0] < b + MARGIN and a - MARGIN < win[1] for a, b in avoid):     # >= 60 s from any first-draw window
            continue
        out.append(win)
    return out


def main(out_path):
    rng = random.Random(SEED)
    plan = {"seed": SEED, "section": "3fc13f3b + amendments 3 (9d8ad8f2) and 4 (51a2733c)",
            "note": "first N of each list are the registered windows; the rest are top-ups in order", "recordings": {}}
    for key, name in LIVE.items():
        d = duration(V + name)
        spans = [(30.0, d - 30.0)]
        timer = draw(rng, spans, 10.0, [], MAX_WINDOWS, avoid=first_windows(key))
        feed = draw(rng, spans, 60.0, [], MAX_WINDOWS, avoid=first_windows(key))
        values, tries = [], 0
        avoid = first_windows(key)
        while len(values) < 150 and tries < 100000:
            tries += 1
            t = round(rng.uniform(0.0, d - 0.05), 3)
            if not any(a - MARGIN <= t <= b + MARGIN for a, b in avoid):
                values.append(t)
        values.sort()
        plan["recordings"][key] = {"video": name, "duration_s": d, "timer_windows": timer, "timer_n": 4,
                                   "feed_windows": feed, "feed_n": 3, "value_frames_s": values}
    Path(out_path).write_text(json.dumps(plan, indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main(sys.argv[1])
