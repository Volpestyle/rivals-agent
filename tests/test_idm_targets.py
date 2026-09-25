"""policy/idm_targets.py: the IDM's 60 Hz training targets, split from admitted 30 Hz step rows.

    uv run pytest tests/test_idm_targets.py

Synthetic recordings only (the intake's own event and held-state types); stdlib.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent import human_demos as hd  # noqa: E402
from agent import human_intake as hi  # noqa: E402
from policy import idm_targets as T  # noqa: E402
from policy.range_bc import steps, vocab  # noqa: E402

STEP, PERIOD, A = 33_333_333, 8_333_333, 1_000_000_000
W = hd.PhysicalKey(device=1, vk=87, scan=17, flags=0)
N = len(vocab.NAMES)


def header(**over):
    bindings = {name: f"key:{100 + c}:0" for c, name in enumerate(vocab.NAMES)}
    bindings["move_forward"] = "key:17:0"
    bindings["spider_power"] = "mouse:1"
    h = {"format": "rivals-range-steps-v1", "session_id": "s", "media_sha256": "0" * 64, "session_group": "s",
         "split": "train", "step_ns": STEP, "frame_period_ns": PERIOD, "actions": list(vocab.NAMES),
         "bindings": bindings, "swing_mode": {"automatic_swing": False, "hold_to_swing": True}, "accel_on": True,
         "patch": "p", "settings_hash": "h",
         "calibration": {"kind": "slow_turn_constant", "yaw_deg_per_count": 0.0330738, "pitch_deg_per_count": 0.0330738,
                         "pitch": {"kind": "derived_equal_sensitivity"}, "source": "test"}}
    h.update(over)
    return h


def ev(t, kind, **payload):
    return hd.InputEvent(t_ns=t, seq=t, type=kind, payload_json=json.dumps(payload))


def key(t, down):
    return ev(t, "key", device=1, vk=87, scan=17, flags=0 if down else 1, down=down)


def mouse(t, dx, dy=0, down=(), up=(), relative=True):
    return ev(t, "mouse", device=2, dx=dx, dy=dy, relative=relative, buttons_down=list(down), buttons_up=list(up),
              wheel_vertical=0, wheel_horizontal=0)


def recording(events, held):
    """events with the HeldState after each (held: per event, the set of held keys and mouse buttons)."""
    states = [hd.HeldState(keys=tuple(k for k in ks if isinstance(k, hd.PhysicalKey)),
                           mouse_buttons=tuple(b for b in ks if isinstance(b, int)), observed=True) for ks in held]
    frames = [hd.FrameRef(video_path="v.mkv", frame_index=i, pts=i, timebase_num=1, timebase_den=120, packet_index=i,
                          composition_ns=A - 2 * PERIOD + i * PERIOD) for i in range(20)]
    return events, states, frames


def parent(**over):
    r = {"i": 0, "run": "r0000", "anchor_ns": A, "segment": "seg", "suitability": "accepted", "regime": "normal",
         "gap_free": True, "held_start": [0] * N, "held_end": [0] * N, "held_known": [True] * N,
         "press": [0] * N, "release": [0] * N, "mouse_dx": 0, "mouse_dy": 0, "relative_known": True}
    r.update(over)
    return r


def split(events_held, row, h=None):
    events, states, frames = recording(*events_held)
    return T.build_rows(h or header(), [row], events, states, frames, hi, empty_state=hd.HeldState(observed=True))


def one_hot(c, v=1):
    x = [0] * N
    x[c] = v
    return x


FWD, SP = vocab.INDEX["move_forward"], vocab.INDEX["spider_power"]


def test_a_row_splits_into_two_intervals_that_add_up_to_it():
    """W pressed at +5 ms and released at +25 ms; mouse 10 counts at +3 ms and 7 at +20 ms: the press and the first
    counts land in the first 60 Hz interval, the release and the rest in the second."""
    events = [mouse(A + 3_000_000, 10, 4), key(A + 5_000_000, True), mouse(A + 20_000_000, 7, -1),
              key(A + 25_000_000, False)]
    held = [set(), {W}, {W}, set()]
    rows = split((events, held), parent(press=one_hot(FWD), release=one_hot(FWD), mouse_dx=17, mouse_dy=3))
    one, two = rows
    assert (one["half"], two["half"]) == (0, 1) and one["t1_ns"] == two["t0_ns"] == A + STEP // 2
    assert one["press"][FWD] == 1 and one["release"][FWD] == 0 and one["held_end"][FWD] == 1
    assert two["press"][FWD] == 0 and two["release"][FWD] == 1 and two["held_start"][FWD] == 1
    assert (one["mouse_dx"], one["mouse_dy"], two["mouse_dx"], two["mouse_dy"]) == (10, 4, 7, -1)
    assert one["yaw_deg"] == pytest.approx(10 * 0.0330738) and one["pitch_deg"] == pytest.approx(4 * 0.0330738)
    assert one["frame0"]["composition_ns"] <= one["t0_ns"] and one["frame1"]["composition_ns"] <= one["t1_ns"]


def test_a_mouse_button_press_is_an_edge_of_its_bound_action():
    events = [mouse(A + 22_000_000, 0, down=[1])]
    rows = split((events, [{1}]), parent(press=one_hot(SP), held_end=one_hot(SP)))
    assert rows[0]["press"][SP] == 0 and rows[1]["press"][SP] == 1 and rows[1]["held_end"][SP] == 1


def test_halves_that_do_not_add_up_to_the_admitted_row_are_refused():
    events = [mouse(A + 3_000_000, 10)]
    with pytest.raises(T.TargetError, match="mouse counts differ"):
        split((events, [set()]), parent(mouse_dx=11))
    with pytest.raises(T.TargetError, match="presses differ"):
        split((events, [set()]), parent(mouse_dx=10, press=one_hot(FWD)))


def test_a_non_relative_mouse_packet_makes_the_counts_unknown():
    events = [mouse(A + 3_000_000, 10), mouse(A + 20_000_000, 0, relative=False)]
    rows = split((events, [set(), set()]), parent(mouse_dx=None, mouse_dy=None, relative_known=False))
    assert rows[0]["mouse_dx"] == 10 and rows[1]["mouse_dx"] is None and rows[1]["yaw_deg"] is None


def test_a_fast_interval_is_flagged_beyond_the_pad_envelope_and_kept():
    """415 deg/s over 16.7 ms is 6.9 deg: 250 counts (8.3 deg) is beyond it and is kept, not clipped."""
    events = [mouse(A + 3_000_000, 250)]
    rows = split((events, [set()]), parent(mouse_dx=250))
    assert rows[0]["beyond_pad_envelope"] is True and rows[0]["yaw_deg"] == pytest.approx(250 * 0.0330738)
    assert rows[1]["beyond_pad_envelope"] is False


def test_an_interval_whose_frame_is_stale_is_not_written():
    events, states, frames = recording([mouse(A + 3_000_000, 1)], [set()])
    frames = frames[:2]                       # the last frame is far older than the second interval's end
    rows = T.build_rows(header(), [parent(mouse_dx=1)], events, states, frames, hi,
                        empty_state=hd.HeldState(observed=True))
    assert rows == []


def _file(tmp_path, rows, h=None, name="s.idm.jsonl"):
    h = h or T.header_from(header(), steps_path=__file__, demo_path=__file__, demo_sha256="1" * 64)
    path = tmp_path / name
    T.write(path, h, rows)
    return path


def _rows():
    events = [mouse(A + 3_000_000, 10, 4), key(A + 5_000_000, True), mouse(A + 20_000_000, 7, -1),
              key(A + 25_000_000, False)]
    return split((events, [set(), {W}, {W}, set()]),
                 parent(press=one_hot(FWD), release=one_hot(FWD), mouse_dx=17, mouse_dy=3))


def test_the_reader_round_trips_and_checks_degrees(tmp_path):
    t = T.load(_file(tmp_path, _rows()))
    assert len(t.rows) == 2 and t.header["format"] == T.FORMAT and t.header["accel_on"] is True
    bad = _rows()
    bad[0]["yaw_deg"] += 0.5
    with pytest.raises(T.TargetError, match="degrees disagree"):
        T.load(_file(tmp_path, bad, name="bad.idm.jsonl"))


def test_the_reader_refuses_a_test_split_before_any_row(tmp_path):
    h = T.header_from(header(), steps_path=__file__, demo_path=__file__, demo_sha256="1" * 64)
    h["split"] = "test"
    path = tmp_path / "t.idm.jsonl"
    path.write_text(json.dumps(h) + "\nnot json\n", encoding="utf-8")
    with pytest.raises(T.TargetError, match="sealed"):
        T.load(path)
    with pytest.raises(T.TargetError, match="sealed session"):
        T.header_from(header(split="test"), steps_path=__file__, demo_path=__file__, demo_sha256="1" * 64)


def test_unsupported_actions_are_unknown_never_no(tmp_path):
    """F2: an action under the minimum training presses, or declared unsupported, is unknown in every target."""
    t = T.load(_file(tmp_path, _rows()))
    support, counts = T.supported_actions([t], min_positives=1, declared={"goh_targeting": "test declaration"})
    assert counts["move_forward"] == 1 and support["move_forward"] is True
    assert support["ultimate"] is False and support["goh_targeting"] is False
    target = T.target(t.rows[0], support)
    assert target["edges"]["move_forward"] == {"press": 1, "held": 1}
    assert target["edges"]["ultimate"] == {"press": None, "held": None}
    assert target["edges"]["goh_targeting"]["press"] is None
    assert target["camera_known"] is True and target["pitch_known"] is True
    strict, _ = T.supported_actions([t])                       # the pre-registered 50
    assert strict["move_forward"] is False


def test_a_val_file_does_not_count_toward_support(tmp_path):
    h = T.header_from(header(split="val"), steps_path=__file__, demo_path=__file__, demo_sha256="1" * 64)
    t = T.load(_file(tmp_path, _rows(), h=h))
    support, counts = T.supported_actions([t], min_positives=1)
    assert counts["move_forward"] == 0 and support["move_forward"] is False


# --- review-idm-data.md: S1 sealed before any read, S2 usable only, S3 gain regime, S4 decisions pinned

SEALED_ID = "20260923T053616-779Z-33696-2"
SEALED_MEDIA = "ea49d523bddf86b97c4307aae99198a374e011a4ef1eb5df8d4b90de6b6053bf"


def _watch_opens(monkeypatch, root):
    """Record every file opened under `root` (builtins.open and Path.open/read_text/read_bytes)."""
    import builtins
    opened = []
    real_open, real_path_open = builtins.open, Path.open

    def spy(file, *a, **k):
        if str(Path(file)).startswith(str(root)):
            opened.append(str(file))
        return real_open(file, *a, **k)

    def path_open(self, *a, **k):
        if str(self).startswith(str(root)):
            opened.append(str(self))
        return real_path_open(self, *a, **k)
    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(Path, "open", path_open)
    return opened


def test_a_sealed_session_is_refused_before_any_file_is_opened(tmp_path, monkeypatch):
    """S1: the pinned denylist names 053616; a folder with its id is refused with nothing under it read."""
    d = tmp_path / SEALED_ID
    d.mkdir()
    (d / f"{SEALED_ID}.steps.jsonl").write_text("would be read\n", encoding="utf-8")
    (d / "imported-demo.jsonl").write_text("would be read\n", encoding="utf-8")
    opened = _watch_opens(monkeypatch, tmp_path)
    with pytest.raises(T.TargetError, match="sealed by the denylist"):
        T.build(SEALED_ID, tmp_path / "out", sessions=tmp_path)
    assert opened == []


def test_a_sealed_media_hash_is_refused_after_the_header_line_only(tmp_path, monkeypatch):
    """S1: another id whose step header names the sealed media: refused before rows, the demo or the registry."""
    sid = "20990101T000000-000Z-1-1"
    d = tmp_path / sid
    d.mkdir()
    steps = d / f"{sid}.steps.jsonl"
    steps.write_text(json.dumps(header(session_id=sid, media_sha256=SEALED_MEDIA)) + "\n{not json\n", encoding="utf-8")
    (d / "imported-demo.jsonl").write_text("would be read\n", encoding="utf-8")
    opened = _watch_opens(monkeypatch, tmp_path)
    with pytest.raises(T.TargetError, match="sealed by the denylist"):
        T.build(sid, tmp_path / "out", sessions=tmp_path)
    assert opened == [str(steps)]                              # the header line, nothing else


def test_the_reader_refuses_a_sealed_file(tmp_path):
    h = T.header_from(header(media_sha256=SEALED_MEDIA), steps_path=__file__, demo_path=__file__,
                      demo_sha256="1" * 64)
    with pytest.raises(T.TargetError, match="sealed by the denylist"):
        T.load(_file(tmp_path, _rows(), h=h))


def test_the_gain_regime_follows_the_calibrated_speed_band():
    """S3: under 1,400 counts/s the gain is measured; above it, extrapolated. 16.7 ms intervals: 23 counts is ~1,380
    counts/s, 24 is ~1,440."""
    slow = split(([mouse(A + 3_000_000, 23)], [set()]), parent(mouse_dx=23))
    fast = split(([mouse(A + 3_000_000, 24)], [set()]), parent(mouse_dx=24))
    assert slow[0]["gain_regime"] == "calibrated" and fast[0]["gain_regime"] == "extrapolated"
    assert slow[1]["gain_regime"] == "calibrated" and slow[1]["mouse_rate_cps"] == 0
    unknown = split(([mouse(A + 20_000_000, 0, relative=False)], [set()]),
                    parent(mouse_dx=None, mouse_dy=None, relative_known=False))
    assert unknown[1]["gain_regime"] is None and unknown[1]["mouse_rate_cps"] is None


def test_extrapolated_degrees_carry_a_wider_uncertainty_and_the_degree_kind(tmp_path):
    rows = split(([mouse(A + 3_000_000, 200), mouse(A + 20_000_000, 5)], [set(), set()]), parent(mouse_dx=205))
    t = T.load(_file(tmp_path, rows))
    support, _ = T.supported_actions([t], min_positives=1)
    fast, slow = (T.target(r, support, t.header) for r in t.rows)
    gain = 0.0330738
    assert fast["gain_regime"] == "extrapolated" and fast["yaw_sigma_deg"] == pytest.approx(0.5 * gain + 0.2 * 200 * gain)
    assert slow["gain_regime"] == "calibrated" and slow["yaw_sigma_deg"] == pytest.approx(0.5 * gain)
    assert fast["degrees_kind"] == "slow_turn_constant" and fast["pitch_derived"] is True


def test_a_regime_that_disagrees_with_the_counts_is_refused(tmp_path):
    rows = _rows()
    rows[0]["gain_regime"] = "extrapolated"
    with pytest.raises(T.TargetError, match="gain regime disagrees"):
        T.load(_file(tmp_path, rows))


def test_targets_are_given_for_usable_rows_only(tmp_path):
    """S2: a rejected or unresolved interval is never a training target."""
    rows = _rows()
    rows[1]["suitability"] = "rejected"
    t = T.load(_file(tmp_path, rows))
    assert [r["i"] for r in T.training_rows(t)] == [0]
    support, _ = T.supported_actions([t], min_positives=1)
    with pytest.raises(T.TargetError, match="not usable"):
        T.target(rows[1], support, t.header)


def test_the_lead_decisions_on_support_are_pinned():
    """S4: nothing is declared unsupported (goh_targeting is supported by the floor, team_up by its presses), and the
    pre-registered floor is 50."""
    assert T.DECLARED_UNSUPPORTED == {} and T.MIN_POSITIVES == 50
    rows = [dict(r) for r in _rows()]
    for r in rows:
        r["press"] = list(r["press"])
    tu, goh = vocab.INDEX["team_up"], vocab.INDEX["goh_targeting"]
    rows[0]["press"][tu] = rows[0]["press"][goh] = 1
    rows[0]["release"] = list(rows[0]["release"])
    t = T.Targets({"split": "train"}, rows)
    support, counts = T.supported_actions([t], min_positives=1)
    assert counts["team_up"] == 1 and support["team_up"] and support["goh_targeting"]


# ---- builds grouped by kit version (lead decision 2026-09-24, patch-equivalence-design.md) -------------------------

OLD, NEW, OTHER = "1.1.3870120/build25364676", "1.1.3892207/build25501035", "1.1.9999999/build99999999"
KIT = "Season 10, Version 20260911"


def equivalence_file(tmp_path, kits=None, name="patch-equivalence.json", crlf=False):
    """A patch-equivalence file in the design's schema; returns (path, its LF sha256)."""
    import hashlib
    kits = kits if kits is not None else {KIT: {"builds": [OLD, NEW], "evidence": ["https://example.invalid/notes"],
                                                "decided_by": "lead", "decided_on": "2026-09-24"}}
    text = json.dumps({"format": T.PATCH_EQUIVALENCE_FORMAT, "kit_versions": kits}, indent=1) + "\n"
    path = tmp_path / name
    path.write_bytes(text.replace("\n", "\r\n").encode() if crlf else text.encode())
    return path, hashlib.sha256(text.encode()).hexdigest()


def cohort_header(sid, patch, **over):
    h = {"session_id": sid, "media_sha256": f"media-{sid}", "patch": patch, "settings_hash": "s", "bindings": {"W": "w"},
         "swing_mode": {"hold_to_swing": True}, "accel_on": True, "parent_step_ns": STEP, "frame_period_ns": PERIOD,
         "calibration": {"yaw_deg_per_count": 0.033}}
    return T.Targets({**h, **over}, [])


def test_the_equivalence_file_is_pinned_and_validated(tmp_path):
    path, sha = equivalence_file(tmp_path)
    eq = T.load_patch_equivalence(path, sha)
    assert eq.kit_of == {OLD: KIT, NEW: KIT} and eq.sha256 == sha
    crlf, _ = equivalence_file(tmp_path, name="crlf.json", crlf=True)
    assert T.load_patch_equivalence(crlf, sha).kit_of == eq.kit_of         # the pin is the LF form
    with pytest.raises(T.TargetError, match="must be pinned"):
        T.load_patch_equivalence(path, None)
    with pytest.raises(T.TargetError, match="differs from its pinned"):
        T.load_patch_equivalence(path, "0" * 64)
    two, s2 = equivalence_file(tmp_path, name="two.json", kits={
        "a": {"builds": [OLD], "evidence": ["e"], "decided_by": "lead", "decided_on": "2026-09-24"},
        "b": {"builds": [OLD], "evidence": ["e"], "decided_by": "lead", "decided_on": "2026-09-24"}})
    with pytest.raises(T.TargetError, match="under two kit versions"):
        T.load_patch_equivalence(two, s2)
    bare, s3 = equivalence_file(tmp_path, name="bare.json", kits={
        KIT: {"builds": [OLD], "evidence": [], "decided_by": "lead", "decided_on": "2026-09-24"}})
    with pytest.raises(T.TargetError, match="needs its evidence"):
        T.load_patch_equivalence(bare, s3)
    empty, s4 = equivalence_file(tmp_path, name="empty.json", kits={})
    with pytest.raises(T.TargetError, match="no kit version"):
        T.load_patch_equivalence(empty, s4)
    assert T.PATCH_EQUIVALENCE_SHA256 == steps.PATCH_EQUIVALENCE_SHA256 and T.PATCH_EQUIVALENCE_SHA256   # one pin


def test_a_cohort_compares_builds_by_kit_version_and_keeps_the_real_builds(tmp_path):
    eq = T.load_patch_equivalence(*equivalence_file(tmp_path))
    got = T.check_cohort([cohort_header("a", OLD), cohort_header("b", NEW)], eq)
    assert got["kit_version"] == KIT and got["builds"] == {"a": OLD, "b": NEW}      # the real builds, recorded
    assert got["patch_equivalence"]["sha256"] == eq.sha256
    with pytest.raises(T.TargetError, match="adding a build to a kit version is a lead decision"):
        T.check_cohort([cohort_header("a", OLD), cohort_header("c", OTHER)], eq)
    with pytest.raises(T.TargetError, match="adding a build to a kit version is a lead decision"):
        T.kit_version(OTHER, eq)


def test_a_cohort_is_one_kit_version_and_one_identity(tmp_path):
    kits = {KIT: {"builds": [OLD], "evidence": ["e"], "decided_by": "lead", "decided_on": "2026-09-24"},
            "Season 11": {"builds": [OTHER], "evidence": ["e"], "decided_by": "lead", "decided_on": "2026-09-24"}}
    eq = T.load_patch_equivalence(*equivalence_file(tmp_path, kits=kits))
    with pytest.raises(T.TargetError, match="span kit versions"):
        T.check_cohort([cohort_header("a", OLD), cohort_header("b", OTHER)], eq)
    for key, value in (("settings_hash", "t"), ("bindings", {"W": "x"}), ("swing_mode", {"hold_to_swing": False}),
                       ("accel_on", False), ("frame_period_ns", 16_666_667), ("calibration", {"yaw_deg_per_count": 1})):
        with pytest.raises(T.TargetError, match=f"{key} differs"):
            T.check_cohort([cohort_header("a", OLD), cohort_header("b", OLD, **{key: value})], eq)
    with pytest.raises(T.TargetError, match="appears twice"):
        T.check_cohort([cohort_header("a", OLD), cohort_header("a", OLD)], eq)
    with pytest.raises(T.TargetError, match="same recording media"):
        T.check_cohort([cohort_header("a", OLD), cohort_header("b", OLD, media_sha256="media-a")], eq)
