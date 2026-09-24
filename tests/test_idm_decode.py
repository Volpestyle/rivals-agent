"""policy/idm/decode.py: the IDM frame store built from a synthetic lossless FFV1 original (range_bc's fixture video,
solid colours per frame), with its step table, imported-demo frame table and target file. Never a human recording.

    uv run --group execution pytest tests/test_idm_decode.py     (skipped without torch, numpy or ffmpeg)
"""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
torch = pytest.importorskip("torch")
pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                                reason="ffmpeg/ffprobe not on PATH")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from policy import idm_targets as T  # noqa: E402
from policy.idm import decode as D, frames as FR, model as M, train as TR  # noqa: E402
from policy.range_bc import cache, fixture, steps, vocab  # noqa: E402

N, DT = vocab.N, 16_666_667
FRAMES, ROWS = 160, 60


def recording(tmp_path, *, pts_shift=None, media=None, sid="c"):
    """(targets path, steps path, demo path, video, pts): one synthetic recording's three pinned inputs.
    pts_shift: a frame whose pts the demo's table puts one tick off."""
    video = tmp_path / "v.mkv"
    if not video.exists():
        fixture.write_video(video, FRAMES)
    tb, pts = fixture.probe_pts(video)
    media = media or cache.file_sha256(video)
    header, rows = fixture.session(sid, runs=(12, 10), video_path=str(video), timebase=tb, pts_of=lambda n: pts[n])
    header.update(video_size=[640, 360], media_sha256=media)
    (tmp_path / f"{sid}.jsonl").unlink(missing_ok=True)
    steps_path = fixture.write(tmp_path / f"{sid}.jsonl", header, rows)
    demo = tmp_path / "imported-demo.jsonl"
    demo.write_text(json.dumps({"media_sha256": media}) + "\n" + json.dumps(
        {"decoded": {"timebase_num": tb[0], "timebase_den": tb[1],
                     "pts": [p + (1 if n == pts_shift else 0) for n, p in enumerate(pts)]}}) + "\n",
        encoding="utf-8")
    cal = {"kind": "slow_turn_constant", "yaw_deg_per_count": 0.033, "pitch_deg_per_count": 0.033,
           "pitch": {"kind": "derived_equal_sensitivity"}}
    th = {"format": T.FORMAT, "session_id": sid, "media_sha256": media, "session_group": sid, "split": "train",
          "parent_step_ns": 33_333_333, "frame_period_ns": 8_333_333, "actions": list(vocab.NAMES), "bindings": {},
          "swing_mode": {}, "accel_on": True, "patch": "p", "settings_hash": "h", "pad_envelope": dict(T.PAD_ENVELOPE),
          "calibration": cal,
          "source": {"steps": {"path": "s", "sha256": T.sha256(steps_path)},
                     "imported_demo": {"path": "d", "sha256": T.sha256(demo)}, "builder": {"path": "b", "sha256": "x"}}}
    trows = []                                                          # odd frames, as the range fixture's anchors
    for k in range(ROWS):
        rate, regime = T.gain_regime(30, 0, DT)
        yaw, pitch, beyond = T.degrees(30, 0, cal, DT)
        trows.append({"i": k, "parent": k // 2, "half": k % 2, "run": "r0", "segment": "s", "suitability": "accepted",
                      "regime": "normal", "gap_free": True, "t0_ns": k * DT, "t1_ns": (k + 1) * DT,
                      "frame0": {"frame_index": 2 * k + 1, "pts": pts[2 * k + 1], "composition_ns": k * DT},
                      "frame1": {"frame_index": 2 * k + 3, "pts": pts[2 * k + 3], "composition_ns": (k + 1) * DT},
                      "mouse_dx": 30, "mouse_dy": 0, "yaw_deg": yaw, "pitch_deg": pitch, "beyond_pad_envelope": beyond,
                      "mouse_rate_cps": round(rate, 3), "gain_regime": regime, "held_start": [0] * N,
                      "held_end": [0] * N, "held_known": [True] * N, "press": [0] * N, "release": [0] * N})
    targets = tmp_path / f"{sid}.idm.jsonl"
    T.write(targets, th, trows)
    return targets, steps_path, demo, video, pts


def build(tmp_path, out="store", **kw):
    targets, steps_path, demo, _, _ = recording(tmp_path, **{k: kw.pop(k) for k in ("pts_shift", "media") if k in kw})
    return D.build(targets, steps_path, demo, tmp_path / out, any_platform=True, **kw), targets


def test_the_store_holds_every_window_frame_with_its_pts_and_pixels(tmp_path):
    m, targets_path = build(tmp_path)
    _, pts = fixture.probe_pts(tmp_path / "v.mkv")
    t = T.load(targets_path)
    want = sorted({o for r in t.rows for o in [r["frame1"]["frame_index"] + 2 * k for k in range(-8, 9)]
                   + [r["frame0"]["frame_index"]] if 0 <= o < FRAMES})
    assert m["frame_indices"] == want and m["frame_pts"] == [pts[o] for o in want]
    assert (m["width"], m["height"]) == (448, 252) and "bitexact" in m["decode"]["graph"]
    store = FR.FrameStore(tmp_path / "store", verify=True)
    TR.bind(t, store)
    for o in (want[0], want[len(want) // 2], want[-1]):
        (bg, fg), k = fixture.frame_colours(o), store._at(o)
        g = np.asarray(store.frames[k])
        close = lambda a, b: abs(int(a) - int(b)) <= 2
        assert close(g[0, 0], D.grey(np.array(bg, np.uint8))) and close(g[126, 224], D.grey(np.array(fg, np.uint8)))
        h = np.asarray(store.huds[k])
        assert all(close(u, v) for u, v in zip(h[10, 100], bg)) and all(close(u, v) for u, v in zip(h[60, 20], bg))
        assert h[60, 150].tolist() == [0, 0, 0]                           # padding
    ex = TR.Examples([(t, store)], M.Config(), {a: a == "jump" for a in vocab.NAMES})
    assert len(ex) == ROWS - 7 and ex.missing == 7                      # rows 0-6: their windows start before 0
    motion, hud = ex.inputs([0])
    assert motion.shape == (1, 16, 252, 448) and hud.shape == (1, 6, 80, 200)


def test_the_hud_crop_is_byte_identical_to_the_range_caches(tmp_path):
    m, _ = build(tmp_path)
    session = steps.load(tmp_path / "c.jsonl")
    cm = cache.build(session, tmp_path / "cache", any_platform=True)
    _, _, hud, row_frame, _ = cache.open_cache(tmp_path / "cache", session)
    store = FR.FrameStore(tmp_path / "store")
    compared = 0
    for r, pos in zip(session.rows, row_frame):
        k = store._at(r["frame"]["frame_index"])
        if k is not None:
            assert np.array_equal(np.asarray(store.huds[k]), np.asarray(hud[pos]))
            compared += 1
    assert compared >= 10 and cm["graph"] != m["decode"]["graph"]


def test_a_rebuild_is_byte_identical(tmp_path):
    a, _ = build(tmp_path, "s1")
    b = D.build(tmp_path / "c.idm.jsonl", tmp_path / "c.jsonl", tmp_path / "imported-demo.jsonl", tmp_path / "s2",
                any_platform=True)
    assert (a["frames_sha256"], a["hud_sha256"]) == (b["frames_sha256"], b["hud_sha256"])


def test_stores_are_built_on_the_mac_only(tmp_path):
    targets, steps_path, demo, _, _ = recording(tmp_path)
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        pytest.skip("this is the Mac")
    with pytest.raises(D.DecodeError, match="Mac only"):
        D.build(targets, steps_path, demo, tmp_path / "store")
    assert not (tmp_path / "store").exists()


@pytest.mark.parametrize("frame, message", [(61, "target row 29 frame1 61 has pts"),      # a row's frame
                                            (135, "ordinal 135 has pts")])               # a window-only frame
def test_a_pts_the_demo_table_disagrees_with_is_refused(tmp_path, frame, message):
    with pytest.raises(D.DecodeError, match=message):
        build(tmp_path, pts_shift=frame)


def test_other_media_and_unpinned_inputs_are_refused(tmp_path):
    with pytest.raises(D.DecodeError, match="differs from the session's original"):
        build(tmp_path, "s1", media="0" * 64)
    targets, steps_path, demo, _, _ = recording(tmp_path)
    other = tmp_path / "other.jsonl"
    other.write_bytes(steps_path.read_bytes() + b"\n")
    with pytest.raises(D.DecodeError, match="step table differs"):
        D.build(targets, other, demo, tmp_path / "s2", any_platform=True)
    demo.write_bytes(demo.read_bytes() + b"\n")
    with pytest.raises(D.DecodeError, match="imported demo differs"):
        D.build(targets, steps_path, demo, tmp_path / "s3", any_platform=True)


def test_a_sealed_session_is_refused_before_anything_is_decoded(tmp_path, monkeypatch):
    targets, steps_path, demo, video, _ = recording(tmp_path)
    monkeypatch.setattr(D, "_decode", lambda *a, **k: pytest.fail("decoded a sealed session"))
    for row in ({"session_id": "c", "media_sha256": "f" * 64},
                {"session_id": "other", "media_sha256": cache.file_sha256(video)}):
        with pytest.raises(T.TargetError, match="sealed"):
            D.build(targets, steps_path, demo, tmp_path / "s", any_platform=True, denylist={"sessions": [row]})
        assert not (tmp_path / "s").exists()


def test_the_store_manifest_is_written_last(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise D.DecodeError("interrupted")
    monkeypatch.setattr(D, "_decode", boom)
    with pytest.raises(D.DecodeError):
        build(tmp_path)
    assert not (tmp_path / "store" / "frames.json").exists()
    with pytest.raises(FileNotFoundError):
        FR.FrameStore(tmp_path / "store")
    assert hashlib.sha256(b"").hexdigest()                               # (nothing else to check: no manifest)


def test_the_cli_builds_and_inspect_writes_viewable_samples(tmp_path, monkeypatch):
    targets, steps_path, demo, _, _ = recording(tmp_path)
    real = D.build
    monkeypatch.setattr(D, "build", lambda *a, **k: real(*a, **{**k, "any_platform": True}))
    assert D.main(["build", str(targets), str(steps_path), str(demo), str(tmp_path / "store"),
                   "--video-root", str(tmp_path)]) == 0
    picks = D.inspect(tmp_path / "store", tmp_path / "look", count=3)
    assert len(picks) == 3
    import struct
    import zlib
    store = FR.FrameStore(tmp_path / "store")
    for name, want in (("grey", np.asarray(store.window(picks[0], [0])[0])), ("hud", np.asarray(store.hud([picks[0]])[0]))):
        png = (tmp_path / "look" / f"{picks[0]}-{name}.png").read_bytes()
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        w, h = struct.unpack(">II", png[16:24])
        n = struct.unpack(">I", png[33:37])[0]                             # the IDAT chunk follows IHDR
        raw = zlib.decompress(png[41:41 + n])
        stride = len(raw) // h
        pixels = np.frombuffer(b"".join(raw[y * stride + 1:(y + 1) * stride] for y in range(h)), np.uint8)
        assert (h, w) == want.shape[:2] and np.array_equal(pixels, want.reshape(-1))   # the image is the store's
    assert (tmp_path / "look" / f"{picks[0]}-diff.png").exists()
    with pytest.raises(D.DecodeError, match="usage"):
        D.main([str(targets)])
