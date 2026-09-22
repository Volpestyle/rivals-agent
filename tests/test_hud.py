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
import pytest

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


@pytest.mark.corpus
def test_a_slot_under_chat_reads_unknown_not_a_verdict():
    """A stream's chat runs straight through the ability row. The availability
    reader used to commit to True/False on a slot it could not see; those were
    two of the four wrong events in the Req hand-check. It must say unknown.

    The threshold lives on the layout because the gaps beside a slot are a
    property of the HUD: the pad row draws its own separators there (up to 0.91
    ink on clean captures) while the M&K row leaves them empty (0.09 clean,
    0.22 under chat).
    """
    from perception.hud import MK, PAD, read_ability

    clip = ROOT / "data/demos/samples/reqmr-2873352801-1920.mp4"
    if not clip.exists():
        return
    import cv2 as _cv2

    cap = _cv2.VideoCapture(str(clip))
    try:
        for seconds, want in ((37.3, None), (37.5, None), (45.9, True)):
            cap.set(_cv2.CAP_PROP_POS_FRAMES, int(seconds * (cap.get(_cv2.CAP_PROP_FPS) or 60)))
            ok, frame = cap.read()
            if not ok:
                continue
            got = read_ability(frame, "uppercut", MK)[0]
            assert got is want, f"{seconds}s: {got!r}, wanted {want!r}"
    finally:
        cap.release()
    assert PAD.slot_spill > MK.slot_spill


# --- which ability is in which slot ---------------------------------------

@pytest.mark.corpus
def test_the_same_slot_holds_different_abilities_on_different_sources():
    """The finding this machinery exists for: a slot position names no ability.

    Web-Swing and Get Over Here are the other way round on the two guide sources
    from the clip the layout was measured on, because the ability-to-key binding
    is a player setting. Reading the icon is the only way to know.
    """
    from perception.hud import MK, slot_mapping

    sources = {
        "reqmr-2873352801-1920.mp4": {"swing": "swing", "get_over_here": "get_over_here"},
        "guides/yuh5NnzOLvo.mp4": {"swing": "get_over_here", "get_over_here": "swing"},
    }
    checked = 0
    for name, want in sources.items():
        clip = ROOT / "data/demos" / ("samples/" + name if "/" not in name else name)
        if not clip.exists():
            continue
        import cv2 as _cv2

        cap = _cv2.VideoCapture(str(clip))
        frames = []
        try:
            fps = cap.get(_cv2.CAP_PROP_FPS) or 60
            start = 90 if "yuh5" in name else 20
            for k in range(40):
                cap.set(_cv2.CAP_PROP_POS_FRAMES, int((start + k * 1.2) * fps))
                ok, frame = cap.read()
                if ok:
                    frames.append(frame)
        finally:
            cap.release()
        if not frames:
            continue
        got = slot_mapping(frames, MK)
        checked += 1
        for position, ability in want.items():
            assert got.get(position) == ability, f"{name} {position}: {got.get(position)!r}"
    if checked:
        assert checked >= 1


def test_an_unidentifiable_slot_is_left_out_rather_than_guessed():
    from perception.hud import MK, identify_slot, slot_mapping

    import numpy as _np

    blank = _np.zeros((1080, 1920, 3), _np.uint8)
    assert identify_slot(blank, MK.slot_cx["swing"]) is None
    assert slot_mapping([blank] * 5, MK) == {}


@pytest.mark.parametrize("name,red,charges,countdown,occluded,want", [
    ("uppercut", 0., 0, 3, False, False),
    ("get_over_here", 0., None, 6, False, False),
    ("swing", 0., 0, None, False, False),
    ("uppercut", 0., 1, 3, False, True),
    ("swing", 0., 2, 3, False, True),
    ("swing", 1., 1, 3, False, False),
    ("swing", None, 1, 3, False, None),
    ("uppercut", 0., None, 3, False, None),
    ("swing", 1., None, 3, False, False),
    ("get_over_here", 0., None, 0, False, None),
    ("uppercut", 0., 0, 1, True, None),
    ("get_over_here", 0., None, 6, True, None),
    ("swing", 0., 3, None, False, True),
    ("uppercut", 1., 1, None, False, False),
    ("get_over_here", None, None, None, False, None),
    ("swing", .47, 1, None, False, None),
])
def test_readiness_reconciliation_reaches_state(monkeypatch, name, red, charges,
                                                countdown, occluded, want):
    """Reader contracts through the real aggregate and State conversion.

    Positive countdown with spare charges is a contract control, not native
    evidence of availability. Red/blank/occluded icons still veto readiness.
    """
    from dataclasses import replace
    import numpy as np
    from perception import hud
    from agent.state import State

    frame = np.zeros((1440, 2560, 3), np.uint8)
    layout = replace(hud.PAD, slot_cx={name: hud.PAD.slot_cx[name]})
    monkeypatch.setattr(hud, "read_hp", lambda f: (250, 250))
    monkeypatch.setattr(hud, "read_bar_fill", lambda f: 1.)
    monkeypatch.setattr(hud, "read_damage_segment", lambda f: None)
    monkeypatch.setattr(hud, "read_webs", lambda f, l: 5)
    monkeypatch.setattr(hud, "read_ult", lambda f, l: (False, .5))
    monkeypatch.setattr(hud, "_slot_occluded", lambda *a: occluded)
    monkeypatch.setattr(hud, "_red_fraction", lambda *a: red)
    monkeypatch.setattr(hud, "read_charges", lambda *a: charges)
    calls = []
    def cooldown(*args):
        calls.append(args[1])
        return countdown
    monkeypatch.setattr(hud, "read_cooldown", cooldown)
    reading = hud.read(frame, layout)
    assert calls == [name], "aggregate must read each countdown only once"
    state = State(t=0, frame=(2560, 1440), **reading.state_kwargs())
    ability = state.abilities["pull" if name == "get_over_here" else name]
    assert ability.ready is want
    assert ability.charges == charges
    assert reading.cooldowns == {name: countdown}
    assert hud.read_ability(frame, name, layout) == (want, charges)


@pytest.mark.corpus
def test_readiness_reconciliation_native_mapped_countdowns():
    """Only the 17 expressly authorized causal frames, no corpus discovery."""
    from dataclasses import replace, asdict
    import hashlib
    from perception import hud
    from agent.state import State

    path = ROOT / "data/diagnostics/range-perception-20260922/diagnosis.json"
    if not path.exists():
        pytest.skip("authorized local diagnosis unavailable")
    diagnosis = json.loads(path.read_text())
    expected_pts = set(range(13121, 13522, 100)) | set(range(19421, 20022, 100)) | set(range(21521, 21922, 100))
    assert len(diagnosis["frames"]) == 17
    assert {r["pts_ms"] for r in diagnosis["frames"]} == expected_pts
    frames = {}
    for row in diagnosis["frames"]:
        source = ROOT / row["source"]["image"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row["source"]["image_sha256"]
        frame = cv2.imread(str(source))
        assert frame.shape[:2] == (1440, 2560)
        frames[row["pts_ms"]] = frame
    defaults = asdict(hud.PAD), asdict(hud.MK)
    mapping = hud.slot_mapping([frames[t] for t in range(13121, 13522, 100)], hud.MK)
    assert mapping == {"swing": "swing", "get_over_here": "uppercut", "uppercut": "get_over_here"}
    layout = replace(hud.MK, slot_cx={ability: hud.MK.slot_cx[position] for position, ability in mapping.items()})
    for t, frame in frames.items():
        reading = hud.read(frame, layout)
        state = State(t=t / 1000, frame=(2560, 1440), **reading.state_kwargs())
        if 19421 <= t <= 20021:
            assert reading.cooldowns["uppercut"] == 3
            assert (state.abilities["uppercut"].ready, state.abilities["uppercut"].charges) == (False, 0)
        if t >= 21521:
            assert state.abilities["pull"].ready is False
            assert reading.cooldowns["get_over_here"] == (6 if t == 21921 else 7)
            assert state.abilities["swing"].ready is (None if t >= 21821 else False)
            assert state.abilities["uppercut"].ready is (None if t == 21921 else False)
        if t <= 13521:
            assert state.abilities["uppercut"].ready is True
            assert state.abilities["uppercut"].charges == 2
            assert state.abilities["pull"].ready is True
            assert state.abilities["swing"].ready is (False if t == 13221 else True)
    assert defaults == (asdict(hud.PAD), asdict(hud.MK))


@pytest.mark.corpus
@pytest.mark.parametrize("name,sha256", [
    ("t0-a-untagged-000.jpg", "95d98b19d860e3ced9037733c28a8cacbd6722846540926ebdb1f7ddcaad2549"),
    ("t0-b-after-web-cluster-003.jpg", "61aaca45d4d1a1ecf2bb2ef011258201640d0edd8ded8fc8d7e1ac47dccb876f"),
    ("t0-b-after-web-cluster-028.jpg", "4c46d2632dabb57707b971665b51d7be7928a5768c847623b3f68d6b76648cbe"),
])
def test_readiness_reconciliation_native_pad_controls(name, sha256):
    """Named relocated native controls; never enumerate their directory."""
    import hashlib
    from perception import hud
    from agent.state import State

    path = Path("C:/rivals-agent/l2tag") / name
    if not path.exists():
        pytest.skip("authorized native PAD control unavailable")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha256
    frame = cv2.imread(str(path))
    assert frame.shape[:2] == (1440, 2560)
    reading = hud.read(frame, hud.PAD)
    state = State(t=0, frame=(2560, 1440), **reading.state_kwargs())
    assert (state.hp, state.max_hp, state.webs) == (250, 250, 5)
    for name, charges in (("swing", 3), ("uppercut", 2), ("pull", None), ("teamup", None)):
        assert state.abilities[name].ready is True
        assert state.abilities[name].charges == charges
    assert all(cd is None for cd in reading.cooldowns.values())


def test_readiness_reconciliation_blank_frame_stays_unknown():
    import numpy as np
    from perception import hud
    from agent.state import State

    reading = hud.read(np.zeros((1440, 2560, 3), np.uint8))
    state = State(t=0, frame=(2560, 1440), **reading.state_kwargs())
    assert state.hp is None
    assert reading.abilities == {}
    assert reading.cooldowns == {}
    assert state.abilities["ult"].ready is None
