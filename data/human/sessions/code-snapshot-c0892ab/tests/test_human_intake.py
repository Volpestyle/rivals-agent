"""Synthetic whole-session intake tests; never discover or open the corpus."""
import json

import pytest

from agent import human_demos as hd
from agent import human_intake as hi
from agent.human_demos import DemoError

S = 1_000_000_000
BASE = 10**17 + 7  # beyond float-exact integers, as the importer's tests use
MS = 1_000_000


def t(seconds):
    return BASE + round(seconds * S)


def hud(start, end, present=True, every=0.2):
    n = round((end - start) / every)
    return [(t(start + i * every), present) for i in range(n)]


def propose(*args, **kw):
    kw.setdefault("focus_settle_ns", 0)   # only the focus-settle test exercises it
    segs, _ = hi.propose_segments(*args, **kw)
    return segs


def reasons(segs):
    return [s["machine_reason"] for s in segs]


def test_proposer_tiles_focus_and_never_accepts():
    focus = [(t(0), t(30))]
    samples = hud(0.1, 10) + hud(10, 14, False) + hud(14, 29)
    segs = propose(focus, samples)
    assert [(s["machine_reason"], s["proposal"]) for s in segs] == [
        ("unsampled_edge", "rejected"), ("range_hud_present", "unresolved"), ("no_range_hud", "rejected"),
        ("range_hud_present", "unresolved"), ("unsampled_edge", "rejected")]
    assert segs[0]["start_ns"] == t(0) and segs[-1]["end_ns"] == t(30)
    assert all(a["end_ns"] == b["start_ns"] for a, b in zip(segs, segs[1:]))
    assert "imitation_suitability" not in json.dumps(segs)
    # both gameplay edges are HUD-present samples: no absent sample inside gameplay
    absent = [ts for ts, p in samples if p is False]
    play = [s for s in segs if s["machine_reason"] == hi.GAMEPLAY]
    assert not any(s["start_ns"] <= ts < s["end_ns"] for s in play for ts in absent)
    assert all((s["start_ns"], True) in samples and (s["end_ns"] - 1, True) in samples for s in play)


def test_short_reader_misses_stay_inside_gameplay_and_unread_is_not_absent():
    segs = propose([(t(0), t(10))], hud(0, 4) + hud(4, 5, None) + hud(5, 5.6, False) + hud(5.6, 10))
    assert reasons(segs) == [hi.GAMEPLAY, "unsampled_edge"]
    segs = propose([(t(0), t(12))], hud(0, 3) + hud(3, 8, None) + hud(8, 12))
    assert reasons(segs) == [hi.GAMEPLAY, "hud_unknown", hi.GAMEPLAY, "unsampled_edge"]


def test_ui_key_cut_ends_gameplay_at_or_before_the_key():
    segs = propose([(t(0), t(20))], hud(0, 20), ui_keys=[(t(5.05), 72)])  # H: change hero
    play = [s for s in segs if s["machine_reason"] == hi.GAMEPLAY]
    assert play[0]["end_ns"] <= t(5.05) and play[0]["end_ns"] == t(5.0) + 1
    ui = [s for s in segs if s["machine_reason"] == "ui_key"]
    assert ui and ui[0]["start_ns"] <= t(5.05) and ui[0]["end_ns"] >= t(5.05) + hi.UI_SETTLE_NS
    assert play[1]["start_ns"] >= t(5.05) + hi.UI_SETTLE_NS
    assert "Esc" in hi.UI_KEYS.values() and "F1" in hi.UI_KEYS.values()


def test_esc_ends_acceptance_for_the_rest_of_the_session():
    segs, flags = hi.propose_segments([(t(0), t(20)), (t(25), t(40))], hud(0, 20) + hud(25, 40),
                                      ui_keys=[(t(8), 27)])
    assert flags and flags[0]["flag"] == "settings_menu_opened"
    after = [s for s in segs if s["start_ns"] >= t(8)]
    assert hi.GAMEPLAY not in reasons(after)
    assert "settings_menu" in reasons(after) and "after_settings_menu" in reasons(after)
    later = [s for s in after if s["machine_reason"] == "after_settings_menu"]
    assert all(s["proposal"] == "unresolved" for s in later if s["start_ns"] >= t(25))
    verdict = dict(suitability="accepted", reason="looks like play", reviewer="r", reviewed_at="now", evidence="x",
                   frames=[dict(frame_index=1, composition_ns=later[-1]["start_ns"], decoded_bgr_sha256="a" * 64)])
    with pytest.raises(DemoError, match="cannot accept"):
        hi.review_segments(segs, {later[-1]["segment_id"]: verdict})


def test_afk_span_is_rejected():
    controls = [t(x / 10) for x in range(0, 50)] + [t(30 + x / 10) for x in range(0, 50)]
    segs = propose([(t(0), t(40))], hud(0, 40), controls=controls)
    afk = [s for s in segs if s["machine_reason"] == "afk"]
    assert len(afk) == 1 and afk[0]["start_ns"] <= t(4.9) + 1 and afk[0]["end_ns"] >= t(30)
    assert afk[0]["proposal"] == "rejected"
    assert all(not (s["start_ns"] < t(20) < s["end_ns"]) for s in segs if s["machine_reason"] == hi.GAMEPLAY)


def test_gameplay_waits_for_the_focus_settle_after_every_focus_start():
    segs = propose([(t(0), t(5)), (t(8), t(12))], hud(0, 12), focus_settle_ns=hi.FOCUS_SETTLE_NS)
    play = [s for s in segs if s["machine_reason"] == hi.GAMEPLAY]
    assert [s["start_ns"] for s in play] == [t(0.4), t(8.4)]   # first HUD sample at or after start + 250 ms
    assert [s["machine_reason"] for s in segs if s["start_ns"] in (t(0), t(8))] == ["focus_transition"] * 2
    native = {("start", t(8.4)): [(t(8) + i * 8_333_333, True) for i in range(49)]}
    refined = [s for s in propose([(t(0), t(5)), (t(8), t(12))], hud(0, 12), native=native,
                                  focus_settle_ns=hi.FOCUS_SETTLE_NS)
               if s["machine_reason"] == hi.GAMEPLAY]
    assert refined[1]["start_ns"] >= t(8.25)                  # refinement never enters the settle span


def test_capture_gap_and_regime_cut_gameplay():
    segs = propose([(t(0), t(20))], hud(0, 20), gaps=[(t(5.1), t(5.5))],
                   regime_spans=[(t(12.1), t(15), "no_cooldown"), (t(0), t(20), "normal")])
    assert "capture_gap" in reasons(segs) and "regime_differs_from_session" in reasons(segs)
    assert all(a["end_ns"] == b["start_ns"] for a, b in zip(segs, segs[1:]))


def test_native_refinement_is_conservative_and_bounded():
    samples = hud(0, 1, False) + hud(1, 5) + hud(5, 6, False)
    segs = propose([(t(0), t(6))], samples)
    play = [s for s in segs if s["machine_reason"] == hi.GAMEPLAY][0]
    first, last = play["edges"]["start"]["sample_ns"], play["edges"]["end"]["sample_ns"]
    frames_start = [(t(0.8) + i * 8_333_333, i >= 12) for i in range(25)]      # HUD appears between samples
    frames_end = [(t(4.8) + i * 8_333_333, i <= 9) for i in range(25)]         # disappears after 10 frames
    segs2 = propose([(t(0), t(6))], samples, native={("start", first): frames_start, ("end", last): frames_end})
    p2 = [s for s in segs2 if s["machine_reason"] == hi.GAMEPLAY][0]
    assert p2["start_ns"] == t(0.8) + 12 * 8_333_333 and p2["end_ns"] == t(4.8) + 9 * 8_333_333 + 1
    assert p2["start_ns"] > t(0.8) and p2["end_ns"] < t(5.0)  # never onto the absent samples
    assert hi._tiles([(s["start_ns"], s["end_ns"]) for s in segs2], [(t(0), t(6))])


def test_every_focus_interval_is_tiled_and_unfocused_time_is_not():
    focus = [(t(0), t(5)), (t(8), t(12))]
    segs = propose(focus, hud(0, 12))
    assert hi._tiles([(s["start_ns"], s["end_ns"]) for s in segs], focus)
    assert not any(t(5) <= s["start_ns"] < t(8) for s in segs)


def frames_in(seg):
    return [dict(frame_index=7, composition_ns=seg["start_ns"], decoded_bgr_sha256="b" * 64)]


def verdict(seg, suit="accepted", **kw):
    return dict(dict(suitability=suit, reason="inspected range play", reviewer="admission-owner",
                     reviewed_at="2026-09-23T20:00:00Z", evidence="sheet.png", frames=frames_in(seg)), **kw)


def test_accepted_only_from_a_full_verdict_record_and_missing_is_unresolved():
    segs = propose([(t(0), t(10))], hud(0, 5) + hud(5, 10, False))
    rows = hi.review_segments(segs, {"seg-000": verdict(segs[0])})
    assert rows[0]["imitation_suitability"] == "accepted" and rows[0]["reviewed_gameplay"] is True
    assert [r["imitation_suitability"] for r in rows[1:]] == ["unresolved"] * (len(rows) - 1)
    for missing in ("frames", "reviewer", "reviewed_at"):
        bad = verdict(segs[0])
        del bad[missing]
        with pytest.raises(DemoError):
            hi.review_segments(segs, {"seg-000": bad})
    with pytest.raises(DemoError, match="native frames"):
        hi.review_segments(segs, {"seg-000": verdict(segs[0], frames=[dict(frames_in(segs[0])[0], decoded_bgr_sha256="x")])})
    with pytest.raises(DemoError, match="cannot accept"):
        hi.review_segments(segs, {"seg-001": verdict(segs[1])})


CITE = [{"path": "data/x.json", "sha256": "0" * 64}]
DENY = dict(schema_version=1, sessions=[dict(session_id="sealed-1", media_path="C:/v/sealed.mkv", media_sha256="d" * 64)])


def review_kwargs(segments, **change):
    settings = dict(dpi=800, horizontal_sensitivity=1.89, vertical_sensitivity=1.89, swing_mode="hold")
    prov = dict(hero="Spider-Man",
                settings=dict(value=settings, source="James", per_session_source="statement 2026-09-23", evidence=CITE),
                bindings=dict(value={"E": "uppercut"}, source="report", per_session_source="statement", evidence=CITE),
                game_patch=dict(value="1.1", source="steam log", evidence=CITE),
                cooldown_regime=dict(value="normal", source="regime scan", evidence=CITE))
    kw = dict(session_id="s1", media_sha256="e" * 64, reviewer="admission-owner", reviewed_at="2026-09-23T00:00:00Z",
              device_scope=dict(kind="single_keyboard_mouse", source="input profile", no_pad_attestation="James: no pad"),
              pts_anchor=dict(kind="independent_muxer_offset", offset_num=21, offset_den=1000, source="calibration",
                              evidence=CITE),
              provenance=prov, alignment=dict(kind="assumption", statement="composition clock", source="lead"),
              segments=segments, session_start_ns=t(0) - 1, session_end_ns=t(10) + 1, focused=[(t(0), t(10))],
              denylist=DENY, independent_review=dict(path="data/r.md", sha256="c" * 64, reviewer="admission-review"))
    kw.update(change)
    return kw


def test_assemble_review_requirements():
    segs = propose([(t(0), t(10))], hud(0, 5) + hud(5, 10, False))
    rows = hi.review_segments(segs, {"seg-000": verdict(segs[0])})
    review = hi.assemble_review(**review_kwargs(rows))
    assert review["segments"][0]["imitation_suitability"] == "accepted"
    anchor = dict(review_kwargs(rows)["pts_anchor"])
    del anchor["evidence"]
    with pytest.raises(DemoError, match="pts_anchor"):
        hi.assemble_review(**review_kwargs(rows, pts_anchor=anchor))
    with pytest.raises(DemoError, match="alignment"):
        hi.assemble_review(**review_kwargs(rows, alignment={"kind": "uncalibrated"}))
    with pytest.raises(DemoError, match="tile"):
        hi.assemble_review(**review_kwargs(rows[:1]))
    with pytest.raises(DemoError, match="independent"):
        hi.assemble_review(**review_kwargs(rows, independent_review=None))
    with pytest.raises(DemoError, match="sealed"):
        hi.assemble_review(**review_kwargs(rows, session_id="sealed-1"))
    with pytest.raises(DemoError, match="sealed"):
        hi.assemble_review(**review_kwargs(rows, media_sha256="d" * 64))
    with pytest.raises(DemoError, match="no-controller"):
        hi.assemble_review(**review_kwargs(rows, device_scope=dict(kind="single_keyboard_mouse", source="x")))


def test_assembly_refuses_null_motor_fields_and_fit_refuses_mixed_motor():
    segs = propose([(t(0), t(10))], hud(0, 10))
    rows = hi.review_segments(segs, {})
    for field in hi.MOTOR_SETTINGS:
        kw = review_kwargs(rows)
        kw["provenance"]["settings"]["value"][field] = None
        with pytest.raises(DemoError, match="motor settings unknown"):
            hi.assemble_review(**kw)
    kw = review_kwargs(rows)
    kw["provenance"]["bindings"]["value"] = {"E": None}
    with pytest.raises(DemoError, match="bindings"):
        hi.assemble_review(**kw)
    a = hi.assemble_review(**review_kwargs(rows))
    kw = review_kwargs(rows)
    kw["provenance"]["settings"]["value"]["dpi"] = 1600
    b = hi.assemble_review(**kw)
    assert hi.check_motor_consistency([a, a])
    with pytest.raises(DemoError, match="mixed motor"):
        hi.check_motor_consistency([a, b])


def test_minutes_trainable_and_unknown_tags():
    segs = propose([(t(0), t(120))], hud(0, 90) + hud(90, 120, False))
    rows = hi.review_segments(segs, {"seg-000": verdict(segs[0])})
    m = hi.session_minutes(session_start_ns=t(0), session_end_ns=t(130), focused=[(t(0), t(120))], segments=rows,
                           tag_spans=[(t(0), t(30), "range", "near")], eligible_anchors=2600, stride_ns=33_333_333)
    assert m["accepted_s"] == pytest.approx(89.8, abs=1e-6) and m["admitted_minutes"] == pytest.approx(89.8 / 60)
    assert m["trainable_minutes"] == pytest.approx(2600 * 33_333_333 / 6e10)
    assert m["unfocused_s"] == pytest.approx(10)
    assert m["tags_s"]["range"] == {"near": pytest.approx(30), "unknown": pytest.approx(59.8, abs=1e-6)}
    with pytest.raises(DemoError, match="stride"):
        hi.session_minutes(session_start_ns=t(0), session_end_ns=t(130), focused=[(t(0), t(120))], segments=rows,
                           eligible_anchors=10)


def test_tally_headline_per_regime_train_only_and_sealed_adds_nothing():
    adm = dict(status="admitted", stride_ns=33_333_333)
    rows = [dict(session="a", split="train", regime="normal", admitted_min=2.5, trainable_min=2.0, **adm),
            dict(session="n", split="train", regime="no_cooldown", admitted_min=1.0, trainable_min=0.8, **adm),
            dict(session="v", split="val", regime="normal", admitted_min=3.0, trainable_min=2.5, **adm),
            dict(session="sealed-1", split="test", status="sealed", regime="normal", admitted_min=99),
            dict(session="c", split="train", status="held", reason="motor settings unknown", admitted_min=4),
            dict(session="d", split=None, status="not_range", reason="calibration")]
    out = hi.tally(rows, denylist=DENY)
    assert out["headline_train_by_regime"]["normal"]["admitted_min"] == 2.5
    assert out["headline_train_by_regime"]["no_cooldown"]["admitted_min"] == 1.0
    assert out["val_by_regime"]["normal"]["admitted_min"] == 3.0
    assert [r["admitted_min"] for r in out["rows"]] == [2.5, 1.0, 3.0, None, None, None]
    md = hi.render_tally(out)
    assert "normal, train: 2.50 admitted / 2.00 trainable of 180" in md and "held: motor settings unknown" in md
    with pytest.raises(DemoError):
        hi.tally([dict(session="x", split="test", status="admitted", admitted_min=1)])
    with pytest.raises(DemoError, match="denylisted"):
        hi.tally([dict(session="sealed-1", split="train", status="held", reason="x")], denylist=DENY)


def write_registry(tmp_path, rows):
    reg = tmp_path / "splits.json"
    reg.write_text(json.dumps(dict(schema_version=1, sessions=rows)))
    return reg


def test_registry_naming_the_sealed_take_as_train_is_refused(tmp_path):
    deny = tmp_path / "deny.json"
    deny.write_text(json.dumps(dict(schema_version=1, sessions=[dict(
        session_id="20260923T053616-779Z-33696-2", media_path=str(tmp_path / "v.mkv"), media_sha256="d" * 64)])))
    denylist = hi.load_denylist(deny, sha256_pin=hi.sha256(deny))
    ok = write_registry(tmp_path, [dict(session_id="a", session_group="g1", split="train", video_path="a.mkv"),
                                   dict(session_id="20260923T053616-779Z-33696-2", session_group="g2", split="test",
                                        sealed=True, video_path="v.mkv")])
    assert set(hi.check_registry(ok, denylist=denylist)) == {"a", "20260923T053616-779Z-33696-2"}
    for row in (dict(session_id="20260923T053616-779Z-33696-2", session_group="g2", split="train", video_path="x.mkv"),
                dict(session_id="renamed", session_group="g2", split="train", video_path="v.mkv"),
                dict(session_id="copied", session_group="g2", split="train", video_path="y.mkv",
                     recorded_video_path="C:/v.mkv", expected_media_sha256="d" * 64)):
        with pytest.raises(DemoError, match="denylisted"):
            hi.check_registry(write_registry(tmp_path, [row]), denylist=denylist)
    with pytest.raises(DemoError, match="pinned"):
        hi.load_denylist(deny, sha256_pin="0" * 64)


def test_freeze_and_manifest_detect_drift(tmp_path):
    folder = tmp_path / "sessions" / "s1"
    folder.mkdir(parents=True)
    (folder / "sampling.json").write_text(json.dumps(dict(stride_ns=1, export_digest="f" * 64)))
    ext = tmp_path / "ext.bin"
    ext.write_bytes(b"x")
    hi.freeze(folder, root=tmp_path, external=[ext])
    assert hi.check_freeze(folder, root=tmp_path) == []
    with pytest.raises(DemoError):
        hi.freeze(folder, root=tmp_path)
    reg, deny = tmp_path / "reg.json", tmp_path / "deny.json"
    reg.write_text("{}")
    deny.write_text("{}")
    doc = hi.manifest([folder], root=tmp_path, registry=reg, denylist_path=deny)
    assert hi.check_manifest(doc, root=tmp_path) == []
    ext.write_bytes(b"y")
    (folder / "b.json").write_text("2")
    assert hi.check_freeze(folder, root=tmp_path) == ["ext.bin", "sessions/s1/b.json"]
    reg.write_text("{ }")
    assert "reg.json" in hi.check_manifest(doc, root=tmp_path)


# ---- the importer's own samples never learn a UI key (R1) ------------------------------------------------

STEP = 10 * MS


def session_payload(tmp_path, esc_at_ms, total_ms=3000):
    video = tmp_path / "original.mkv"
    video.write_bytes(b"synthetic")
    ev = [dict(type="raw_input_status", t_ns=BASE, ok=True), dict(type="focus", t_ns=BASE, active=True, held_vk=[])]
    for ms in range(20, total_ms - 20, 20):
        ev.append(dict(type="mouse", t_ns=BASE + ms * MS, device=22, dx=3, dy=-1, motion_flags=0, button_flags=0,
                       wheel_data=0, relative=True, buttons_down=[], buttons_up=[], wheel_vertical=0, wheel_horizontal=0))
    ev += [dict(type="key", t_ns=BASE + esc_at_ms * MS + 1, device=12, vk=27, scan=1, flags=0, down=True),
           dict(type="key", t_ns=BASE + esc_at_ms * MS + 5 * MS + 1, device=12, vk=27, scan=1, flags=1, down=False)]
    ev.sort(key=lambda e: e["t_ns"])
    for i, row in enumerate(ev):
        row["seq"] = i
    n = total_ms // 10
    packets = []
    for i in range(n):
        row = dict.fromkeys(hd.FRAME_COLUMNS, 0)
        row.update(event_seq=len(ev) + i, packet_index=i, pts=i * 10, dts=i * 10, timebase_num=1, timebase_den=1000,
                   composition_ns=BASE + i * STEP)
        packets.append(row)
    meta = dict(schema_version=1, control_type="keyboard_mouse", status="complete", complete=True, clean_stop=True,
                writer_failed=False, queue_dropped_events=0, raw_input_errors=0, first_queue_drop_ns=0,
                last_queue_drop_ns=0, frames_without_composition_timestamp=0, events_attempted=len(ev) + n,
                video_packets=n, input_events=sum(e["type"] in ("key", "mouse") for e in ev), start_ns=BASE,
                end_ns=BASE + n * STEP, width=640, height=360, fps_num=100, fps_den=1, capture_latency_calibrated=False,
                session_id="s1", video_path=str(video.resolve()), target_executable="Marvel-Win64-Shipping.exe")
    return dict(metadata=meta, events=ev, packets=packets,
                decoded=dict(timebase_num=1, timebase_den=1000, pts=[21 + i * 10 for i in range(n)], width=640, height=360))


OPTIONS = dict(history_ns=100 * MS, frame_step_ns=STEP, bin_ns=50 * MS, bins=5, stride_ns=STEP)


def samples_for(data, segments):
    meta = data["metadata"]
    data["review"] = dict(schema_version=1, session_id="s1", reviewer="r", reviewed_at="now",
        device_scope={"kind": "single_keyboard_mouse", "source": "synthetic"},
        pts_anchor={"kind": "independent_muxer_offset", "offset_num": 21, "offset_den": 1000, "source": "synthetic"},
        provenance={"hero": "Spider-Man", **{k: {"value": "v", "source": "s"} for k in
                                            ("settings", "bindings", "game_patch", "cooldown_regime")}},
        alignment={"kind": "assumption", "statement": "CTS clock", "source": "synthetic"}, segments=segments)
    dataset = hd._build(data, hd.Placement("s1", "g", "train", meta["video_path"]), "a" * 64)
    return list(dataset.samples(**OPTIONS))


def future_vks(samples):
    return {e.payload.get("vk") for s in samples for b in s.future for e in b.events if e.type == "key"}


def intake_rows(data):
    meta = data["metadata"]
    focus = hi.focus_intervals(data["events"], meta["start_ns"], meta["end_ns"])
    # worst case: the menu keeps the HUD, so HUD samples stay present straight through the Esc
    samples = [(p["composition_ns"], True) for p in data["packets"][::5]]
    segs, flags = hi.propose_segments(focus, samples, ui_keys=hi.ui_key_presses(data["events"]),
                                      controls=hi.control_times(data["events"]), ui_settle_ns=200 * MS)
    play = [s for s in segs if s["machine_reason"] == hi.GAMEPLAY]
    rows = hi.review_segments(segs, {s["segment_id"]: verdict(s) for s in play})
    return rows, flags


@pytest.mark.parametrize("esc_at_ms", [1500, 2900])  # Esc inside an accepted span, and at its end
def test_esc_never_appears_in_a_future_bin(tmp_path, esc_at_ms):
    data = session_payload(tmp_path, esc_at_ms)
    rows, flags = intake_rows(data)
    assert flags and any(r["imitation_suitability"] == "accepted" for r in rows)
    samples = samples_for(data, rows)
    assert samples, "the accepted span still yields rows"
    assert 27 not in future_vks(samples)
    assert all(s.anchor_ns + 5 * 50 * MS <= BASE + esc_at_ms * MS + 1 for s in samples)
    # control: a HUD-only boundary (first absent sample after the key) does leak Esc into targets
    naive_end = BASE + (esc_at_ms + 50) * MS
    naive = [dict(segment_id="naive", start_ns=BASE, end_ns=naive_end, reviewed_gameplay=True,
                  imitation_suitability="accepted", suitability_reason="naive", evidence="x"),
             dict(segment_id="rest", start_ns=naive_end, end_ns=data["metadata"]["end_ns"], reviewed_gameplay=True,
                  imitation_suitability="rejected", suitability_reason="menu", evidence="x")]
    assert 27 in future_vks(samples_for(data, naive))


# ---- fit-lane requirements (fit-design-final.md) -----------------------------------------------------------

def key_event(ms, vk, scan, down, device=12):
    return dict(type="key", t_ns=BASE + ms * MS, device=device, vk=vk, scan=scan, flags=0 if down else 1, down=down)


def mouse_event(ms, device=22, **kw):
    row = dict(type="mouse", t_ns=BASE + ms * MS, device=device, dx=0, dy=0, motion_flags=0, button_flags=0, wheel_data=0,
               relative=True, buttons_down=[], buttons_up=[], wheel_vertical=0, wheel_horizontal=0)
    row.update(kw)
    return row


def test_device_scope_injected_control_refused_and_inert_reported():
    ok = [key_event(1, 87, 17, True), mouse_event(2, dx=3), mouse_event(3, device=0)]  # handle-0 zero-effect packet
    for i, row in enumerate(ok):
        row["seq"] = i
    rep = hi.device_scope_report(ok)
    assert rep["injected_control_packets"] == 0 and rep["injected_zero_effect_packets"] == 1
    hi.assert_human_device_scope(rep)
    with pytest.raises(DemoError, match="injected"):
        hi.assert_human_device_scope(hi.device_scope_report(ok + [dict(mouse_event(4, device=0, dx=5), seq=9)]))
    with pytest.raises(DemoError, match="more than one"):
        hi.assert_human_device_scope(hi.device_scope_report(ok + [dict(mouse_event(4, device=23, dx=5), seq=9)]))


def test_regime_note_cross_check_and_settings_identity():
    assert hi.regime_cross_check(None, "normal")["status"] == "no_note"
    assert hi.regime_cross_check("no_cooldown", "normal")["agreement"] is False
    settings = dict(dpi=800, horizontal_sensitivity=1.89, vertical_sensitivity=1.89, swing_mode="hold")
    a = hi.settings_identity(settings, {"E": "uppercut", "C": "team-up"})
    assert a != hi.settings_identity(settings, {"E": "uppercut", "C": "something else"})
    with pytest.raises(DemoError):
        hi.settings_identity(dict(settings, dpi=None), {"E": "uppercut"})
    with pytest.raises(DemoError):
        hi.settings_identity(settings, {"C": None})


def test_split_assignment_by_minutes_before_inspection():
    groups = {"g1": ("train", 10.0), "sealed": ("test", 2.1)}
    assert hi.assign_split(groups, "g1", 5) == "train"          # an existing group keeps its split
    assert hi.assign_split(groups, "g2", 3) == "val"            # val is furthest below 15 %
    assert hi.assign_split({"g1": ("train", 1.0)}, "g2", 20) == "train"


def test_counted_minutes_need_accepted_focused_runs_of_at_least_1_6_s():
    seg = lambda a, b, s: dict(start_ns=t(a), end_ns=t(b), imitation_suitability=s)
    segments = [seg(0, 10, "accepted"), seg(10, 12, "rejected"), seg(12, 13, "accepted"), seg(13, 30, "accepted")]
    out = hi.counted_minutes([(t(0), t(20))], segments, [(t(4), t(4.1)), (t(14), t(14.05))])
    # accepted ∩ focus: [0,10), [12,13), [13,20); gaps split into [0,4) [4.1,10) [12,13) [13,14) [14.05,20)
    assert out["runs"] == 5 and out["counted_runs"] == 3
    assert out["counted_minutes"] == pytest.approx((4 + 5.9 + 5.95) / 60)


def steps_payload(tmp_path):
    data = session_payload(tmp_path, esc_at_ms=2900)
    extra = [key_event(100, 87, 17, True), key_event(150, 87, 17, True), key_event(400, 87, 17, False),
             mouse_event(500, button_flags=4, buttons_down=[2]), mouse_event(600, button_flags=8, buttons_up=[2]),
             key_event(700, 67, 46, True), key_event(720, 67, 46, False),  # C: outside the vocabulary
             mouse_event(800, button_flags=64, buttons_down=[4]), mouse_event(810, button_flags=128, buttons_up=[4])]
    events = sorted([e for e in data["events"]] + extra, key=lambda e: e["t_ns"])
    return rebuild(data, events)


def rebuild(data, events):
    for i, row in enumerate(events):
        row["seq"] = i
    n = len(data["packets"])
    for i, p in enumerate(data["packets"]):
        p["event_seq"] = len(events) + i
    data["events"] = events
    data["metadata"].update(events_attempted=len(events) + n,
                            input_events=sum(e["type"] in ("key", "mouse") for e in events))
    return data


def dataset_with(data, segments):
    samples_for(data, segments)  # builds the review into data
    meta = data["metadata"]
    return hd._build(data, hd.Placement("s1", "g", "train", meta["video_path"]), "a" * 64)


def test_step_table_columns_presses_holds_runs_and_flags(tmp_path):
    data = steps_payload(tmp_path)
    end = data["metadata"]["end_ns"]
    segs = [dict(segment_id="a", start_ns=BASE, end_ns=BASE + 2000 * MS, reviewed_gameplay=True,
                 imitation_suitability="accepted", suitability_reason="r", evidence="e"),
            dict(segment_id="b", start_ns=BASE + 2000 * MS, end_ns=end, reviewed_gameplay=True,
                 imitation_suitability="rejected", suitability_reason="r", evidence="e")]
    short = hi.step_table(dataset_with(data, segs), stride_ns=100 * MS, step_ns=50 * MS)
    assert short["header"]["stride_ns"] == 100 * MS and short["header"]["step_ns"] == 50 * MS
    table = hi.step_table(dataset_with(data, segs), stride_ns=100 * MS)
    c = table["columns"]
    assert all(len(v) == len(c["anchor_ns"]) for v in c.values())
    assert sum(c["W_press_count"]) == 1 and sum(c["W_release_count"]) == 1  # the repeat make is not a press
    assert sum(c["RMB_press_count"]) == 1 and sum(c["RMB_release_count"]) == 1
    i = c["anchor_ns"].index(BASE + 200 * MS)
    assert c["W_held_start"][i] is True and c["W_held_end"][i] is True
    assert any(u and "key:46:0:67" in u for u in c["unsupported"]) and any(u and "button:4" in u for u in c["unsupported"])
    assert set(c["suitability"]) == {"accepted", "rejected"} and len(set(c["run_id"])) == 2
    assert all(0 <= age < 10 * MS for age in c["frame_age_ns"])
    assert all(x < y for x, y in zip(c["frame_index"], c["frame_index"][1:]))
    assert all(a + 100 * MS < BASE + 2000 * MS for a, s in zip(c["anchor_ns"], c["segment_id"]) if s == "a")
    accepted = hi.step_table(dataset_with(data, segs), stride_ns=100 * MS, all_segments=False)
    assert set(accepted["columns"]["suitability"]) == {"accepted"}


def test_step_table_capture_gap_starts_a_new_run(tmp_path):
    data = session_payload(tmp_path, esc_at_ms=2900)
    for p in data["packets"][100:]:
        p["composition_ns"] += 100 * MS   # a 110 ms capture gap after frame 99
    data["metadata"]["end_ns"] += 100 * MS
    seg = [dict(segment_id="a", start_ns=BASE, end_ns=data["metadata"]["end_ns"], reviewed_gameplay=True,
                imitation_suitability="accepted", suitability_reason="r", evidence="e")]
    c = hi.step_table(dataset_with(data, seg), stride_ns=100 * MS)["columns"]
    assert len(set(c["run_id"])) == 2 and False in c["gap_free"]
