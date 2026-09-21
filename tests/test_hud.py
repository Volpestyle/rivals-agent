"""Score perception.hud against the hand-checked set in perception/hud_truth.json.

    uv run --no-project --with opencv-python-headless --with numpy python -m tests.test_hud

Prints per-field coverage, wrong-read counts and per-frame latency, then
asserts. A field whose key
is missing from a truth entry is not scored; an explicit null means "the reader
should say it cannot read this", and answering None scores correct.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import cv2

from perception.hud import SLOT_CX, read, read_tagged

ROOT = Path(__file__).resolve().parent.parent
TRUTH = ROOT / "perception" / "hud_truth.json"

# Two numbers per field, because they mean different things to the agent.
#
#   coverage - frames where the reader produced the right value. A miss here is
#              a frame the reader declined to read; at 10 fps the next frame
#              usually carries the same value, so this is a throughput number.
#   wrong    - frames where the reader produced a value that disagrees with the
#              truth. This is the one that can make the agent act on a fiction,
#              and the readers are built so it stays at zero.
#
# Digits are exact-match; the bar is within 2 pp.
COVERAGE_FLOOR = 0.95
# Max hp is the dimmest text on the HUD — small, grey, and drawn over whatever
# the camera is pointing at. Its remaining misses are frames where the digits
# never surface as glyphs under any of the nine mask passes, not frames where
# they were misread; adding templates past this point changes nothing.
FLOOR_OVERRIDES = {"max_hp": 0.93}
MAX_WRONG = 0
# Generous on purpose: this Mac runs several lanes at once, and the spread is
# contention rather than the readers. Measured quiet: ~4.3 ms median.
MAX_MEDIAN_MS = 12.0


def _fields(hud):
    out = {
        "hp": hud.hp, "max_hp": hud.max_hp, "webs": hud.webs,
        "bar_fill": hud.bar_fill, "ult_ready": hud.ult_ready,
    }
    for name in SLOT_CX:
        ready, charges = hud.abilities.get(name, (None, None))
        out[f"{name}.ready"] = ready
        out[f"{name}.charges"] = charges
    return out


def _flat_truth(entry):
    out = {k: entry[k] for k in ("hp", "max_hp", "webs", "bar_fill", "ult_ready") if k in entry}
    for name, ab in (entry.get("abilities") or {}).items():
        for k in ("ready", "charges"):
            if k in ab:
                out[f"{name}.{k}"] = ab[k]
    return out


def _match(field, got, want):
    if want is None or got is None:
        return got is want
    if field == "bar_fill":
        return abs(got - want) <= 0.02
    return got == want


def main():
    if not TRUTH.exists():
        print(f"no truth file at {TRUTH}")
        return 1
    entries = json.loads(TRUTH.read_text())["frames"]
    scored: dict[str, list[int]] = {}
    wrong: dict[str, list[str]] = {}
    misses: list[str] = []
    latencies: list[float] = []
    missing_frames = 0

    for entry in entries:
        path = ROOT / entry["path"]
        frame = cv2.imread(str(path))
        if frame is None:
            missing_frames += 1
            continue
        t0 = time.perf_counter()
        hud = read(frame)
        latencies.append((time.perf_counter() - t0) * 1000)
        got = _fields(hud)
        for field, want in _flat_truth(entry).items():
            ok = _match(field, got[field], want)
            scored.setdefault(field, []).append(int(ok))
            if not ok:
                misses.append(f"  {path.name} {field}: read {got[field]!r}, truth {want!r}")
                if got[field] is not None and want is not None:
                    wrong.setdefault(field, []).append(path.name)

    if missing_frames:
        print(f"{missing_frames}/{len(entries)} labelled frames are not on disk "
              f"(they live under data/, which git ignores)")
    if not latencies:
        print("no frames read")
        return 1

    print(f"\n{len(latencies)} frames\n")
    print(f"{'field':<18}{'n':>5}{'coverage':>10}{'wrong':>7}")
    failures = []
    for field in sorted(scored):
        hits = scored[field]
        cov = sum(hits) / len(hits)
        n_wrong = len(wrong.get(field, ()))
        floor = FLOOR_OVERRIDES.get(field, COVERAGE_FLOOR)
        flag = "" if cov >= floor and n_wrong <= MAX_WRONG else "   FAIL"
        print(f"{field:<18}{len(hits):>5}{cov:>10.3f}{n_wrong:>7}{flag}")
        if cov < floor:
            failures.append(f"{field} coverage {cov:.3f} < {floor:.2f}")
        if n_wrong > MAX_WRONG:
            failures.append(f"{field} wrong on {', '.join(wrong[field])}")

    med = statistics.median(latencies)
    p95 = sorted(latencies)[int(0.95 * (len(latencies) - 1))]
    print(f"\nlatency: median {med:.2f} ms, p95 {p95:.2f} ms, max {max(latencies):.2f} ms")

    if misses:
        print(f"\n{len(misses)} misses:")
        print("\n".join(misses[:40]))

    assert not failures, "below floor: " + "; ".join(failures)
    assert med <= MAX_MEDIAN_MS, f"median latency {med:.2f} ms > {MAX_MEDIAN_MS} ms"
    assert len(latencies) >= 50, f"only {len(latencies)} labelled frames, want >= 50"
    print("\nOK")
    return 0


# The Spider-Tracer lands on the bot at frame 71 of run trial1 and the camera
# has drifted off this box by frame 87. The box is the bot's, read off the
# frame by hand; the point of the check is the flip, and that nothing before
# the hit reports a tracer.
TAGGED_BOX = (645, 342, 695, 442)
TAGGED = {63: False, 65: False, 69: False, 71: True, 75: True, 85: True}


def test_read_tagged():
    for i, want in TAGGED.items():
        frame = cv2.imread(str(ROOT / f"data/l2/{i:06d}.jpg"))
        if frame is None:
            continue
        got = read_tagged(frame, TAGGED_BOX)
        assert got is want, f"frame {i}: read_tagged {got!r}, truth {want!r}"


def test_tagged_band_off_screen_is_unknown():
    frame = cv2.imread(str(ROOT / "data/l2/000071.jpg"))
    if frame is not None:
        # A box against the top of the screen leaves no band to search.
        assert read_tagged(frame, (600, 0, 660, 40)) is None


def test_hud_accuracy():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())


# --- the tracer at native resolution --------------------------------------

TAGGED_DIR = ROOT / "data/l4tag"   # L4's tagged-native frames, pulled from the PC


def _tagged_truth(name):
    """L4 filmed ten untagged frames then 28-29 after a web-cluster hit. The
    marker is up from 003; it is still up on 028, which the delivered note put
    at 027 -- checked by eye on t0-b-after-web-cluster-028."""
    import re

    if "-a-untagged-" in name:
        return False
    return 3 <= int(re.search(r"-(\d+)\.jpg", name).group(1)) <= 28


def test_tracer_reads_at_native_resolution():
    """2560-wide frames, the size the game actually renders.

    Guards the bug this test was written for: the marker template was cut from a
    1280-wide capture and searched at a fixed 0.7-1.5 ladder, so at native it was
    off the top of the ladder and read_tagged answered False -- confidently
    wrong -- on every tagged frame. Recall was 0.000 before the ladder was made
    relative to the frame width.
    """
    import glob

    from perception.outline import detect

    paths = sorted(glob.glob(str(TAGGED_DIR / "*.jpg")))
    if not paths:
        return
    tp = fp = fn = 0
    for path in paths:
        frame = cv2.imread(path)
        seen = [read_tagged(frame, d.bbox) for d in detect(frame)]
        got = True if any(v is True for v in seen) else (
            None if not seen or all(v is None for v in seen) else False)
        want = _tagged_truth(Path(path).name)
        if got is True and want:
            tp += 1
        elif got is True and not want:
            fp += 1
        elif got is False and want:
            fn += 1
    assert fp == 0, f"{fp} frames called tagged that are not"
    assert tp / (tp + fn) >= 0.90, f"recall {tp / (tp + fn):.3f}"
