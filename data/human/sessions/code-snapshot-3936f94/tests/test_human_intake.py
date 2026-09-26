"""Synthetic whole-session intake tests; never discover or open the corpus."""
import hashlib
import importlib.util
import json
from datetime import timedelta
from pathlib import Path

import pytest

from agent import human_demos as hd
from agent import human_intake as hi
from agent.human_demos import DemoError
from tests import human_intake_fixtures as FX
from tests.human_intake_fixtures import (STEP, build_dataset, key_event, mouse_event, rebuild, session_payload,
                                         steps_payload)

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
    segs = propose([(t(0), t(20))], hud(0, 20), ui_keys=[(t(5.05), 72), (t(8.05), 72)])  # H opens, H closes
    play = [s for s in segs if s["machine_reason"] == hi.GAMEPLAY]
    assert play[0]["end_ns"] <= t(5.05) and play[0]["end_ns"] == t(5.0) + 1
    ui = [s for s in segs if s["machine_reason"] == "ui_key"]
    assert ui and ui[0]["start_ns"] <= t(5.05) and ui[-1]["end_ns"] >= t(8.05) + hi.UI_SETTLE_NS
    assert play[1]["start_ns"] >= t(8.05) + hi.UI_SETTLE_NS
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


def test_timed_practice_cut_splits_gameplay_and_the_new_edges_stay_outside_it():
    segs = propose([(t(0), t(40))], hud(0, 40), timed_practice=[(t(10.05), t(20.05))])
    play = [s for s in segs if s["machine_reason"] == hi.GAMEPLAY]
    timed = [s for s in segs if s["machine_reason"] == "timed_practice"]
    assert len(play) == 2 and len(timed) == 1 and timed[0]["proposal"] == "rejected"
    assert play[0]["end_ns"] <= t(10.05) and play[1]["start_ns"] >= t(20.05)
    assert timed[0]["start_ns"] <= t(10.05) and timed[0]["end_ns"] >= t(20.05)
    assert all(a["end_ns"] == b["start_ns"] for a, b in zip(segs, segs[1:]))
    # an edge proven by native reads may move outward, but never into the cut
    first = play[1]["edges"]["start"]["sample_ns"]
    native = {("start", first): [(t(19.9) + i * 8_333_333, True) for i in range(40)]}
    again = [s for s in propose([(t(0), t(40))], hud(0, 40), timed_practice=[(t(10.05), t(20.05))], native=native)
             if s["machine_reason"] == hi.GAMEPLAY]
    assert again[1]["start_ns"] >= t(20.05)
    with pytest.raises(DemoError, match="timed practice spans"):
        propose([(t(0), t(40))], hud(0, 40), timed_practice=[(t(20), t(10))])


def test_settings_change_span_ends_after_the_declared_esc_press_and_ignores_auto_repeat():
    keys = [(t(4.09), 27, True), (t(4.12), 27, True), (t(4.2), 27, False),     # one press with an auto-repeat down
            (t(5.44), 27, True), (t(5.5), 27, False), (t(900), 27, True), (t(900.1), 27, False)]
    cut, presses = hi.settings_change_span(keys, t(0), esc_presses=2)
    assert presses == [t(4.09), t(5.44)] and cut == (t(0), t(5.44) + hi.UI_SETTLE_NS)
    with pytest.raises(DemoError, match="declared 4 Esc presses, the take has 3"):
        hi.settings_change_span(keys, t(0), esc_presses=4)
    with pytest.raises(DemoError, match="positive integer"):
        hi.settings_change_span(keys, t(0), esc_presses=0)


def test_settings_change_cut_exempts_its_esc_presses_from_r3_but_not_a_later_esc():
    keys = [(t(4.09), 27, True), (t(4.2), 27, False), (t(5.44), 27, True), (t(5.5), 27, False)]
    cut, _ = hi.settings_change_span(keys, t(0), esc_presses=2)
    segs, flags = hi.propose_segments([(t(0.4), t(40))], hud(0, 40), ui_keys=keys, settings_change=[cut],
                                      focus_settle_ns=0)
    assert not flags and "after_settings_menu" not in reasons(segs)
    play = [s for s in segs if s["machine_reason"] == hi.GAMEPLAY]
    assert len(play) == 1 and play[0]["start_ns"] >= cut[1]
    assert [s["machine_reason"] for s in segs if s["end_ns"] <= cut[1]] == ["settings_change"]
    assert all(a["end_ns"] == b["start_ns"] for a, b in zip(segs, segs[1:]))
    later = keys + [(t(30), 27, True), (t(30.1), 27, False)]      # an Esc after the declared change keeps R3
    segs2, flags2 = hi.propose_segments([(t(0.4), t(40))], hud(0, 40), ui_keys=later, settings_change=[cut],
                                        focus_settle_ns=0)
    assert [f["flag"] for f in flags2] == ["settings_menu_opened"] and flags2[0]["t_ns"] == t(30)
    assert "after_settings_menu" in reasons(segs2)
    # without the declared change, the opening Esc holds the whole take (R3, unchanged)
    _, flags3 = hi.propose_segments([(t(0.4), t(40))], hud(0, 40), ui_keys=keys, focus_settle_ns=0)
    assert flags3[0]["t_ns"] == t(4.09)


def test_a_dated_motor_statement_covers_only_its_named_sessions_and_a_session_override_replaces_it():
    A = assemble_module()
    log = (ROOT / "docs/recording-log.md").read_text(encoding="utf-8")
    base = dict(TAKE_0924, started_utc="2026-09-25T21:26:46.322Z")
    val = A.motor_statement(dict(base, session_id="20260925T212646-322Z-49728-6"), hi, log)
    assert sorted(val) == ["bindings", "date", "log_quotes", "settings"] and "fbe6693" in val["settings"]
    late = A.motor_statement(dict(base, session_id="20260926T035932-508Z-63684-14",
                                  started_utc="2026-09-26T03:59:32.508Z"), hi, log)
    assert late["date"] == "2026-09-25" and "83c05f1" in late["settings"] and late["log_quotes"][0].startswith(
        "2026-09-25 (late): ")
    alt = A.motor_statement(dict(base, session_id="20260926T045729-166Z-79780-1",
                                 started_utc="2026-09-26T04:57:29.166Z"), hi, log)   # 23:57:29 CDT keys 2026-09-25
    assert alt["date"] == "2026-09-25" and "3936f94" in alt["settings"]
    with pytest.raises(A.Refused, match="no per-session motor statement for 20260926T999999-000Z-1-1"):
        A.motor_statement(dict(base, session_id="20260926T999999-000Z-1-1", started_utc="2026-09-26T04:59:59.000Z"),
                          hi, log)


def test_timed_practice_span_is_conservative_and_refuses_ambiguity():
    f = lambda i: t(100) + i * 8_333_333   # noqa: E731
    start = [(f(i), "range") for i in range(10)] + [(f(10), None), (f(11), None)] + [(f(i), "timed") for i in range(12, 20)]
    end = [(f(i), "timed") for i in range(1000, 1010)] + [(f(1010), None)] + [(f(i), "range") for i in range(1011, 1020)]
    interior = [(f(i), "timed") for i in range(20, 1000, 100)] + [(f(500), None)]
    assert hi.timed_practice_span(start, end, interior) == (f(9) + 1, f(1011))   # unlabelled edge frames are cut
    with pytest.raises(DemoError, match="flickers back"):
        hi.timed_practice_span(start + [(f(15), "range")], end)
    with pytest.raises(DemoError, match="flickers back"):
        hi.timed_practice_span(start, end + [(f(1015), "timed")])
    with pytest.raises(DemoError, match="no PRACTICE RANGE frame before"):
        hi.timed_practice_span([(f(i), "timed") for i in range(5)], end)
    with pytest.raises(DemoError, match="no PRACTICE RANGE frame after"):
        hi.timed_practice_span(start, [(f(i), "timed") for i in range(1000, 1005)])
    with pytest.raises(DemoError, match="interior reads PRACTICE RANGE"):
        hi.timed_practice_span(start, end, interior + [(f(600), "range")])
    with pytest.raises(DemoError, match="range, timed or None"):
        hi.timed_practice_span(start, end, [(f(600), "menu")])


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
    settings = dict(FX.SETTINGS)
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





OPTIONS = dict(history_ns=100 * MS, frame_step_ns=STEP, bin_ns=50 * MS, bins=5, stride_ns=STEP)


def samples_for(data, segments):
    return list(build_dataset(data, segments).samples(**OPTIONS))


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
    settings = dict(FX.SETTINGS)
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






def dataset_with(data, segments):
    return build_dataset(data, segments)


def test_step_table_columns_presses_holds_runs_and_flags(tmp_path):
    data = steps_payload(tmp_path)
    end = data["metadata"]["end_ns"]
    segs = [dict(segment_id="a", start_ns=BASE, end_ns=BASE + 2000 * MS, reviewed_gameplay=True,
                 imitation_suitability="accepted", suitability_reason="r", evidence="e"),
            dict(segment_id="b", start_ns=BASE + 2000 * MS, end_ns=end, reviewed_gameplay=True,
                 imitation_suitability="rejected", suitability_reason="r", evidence="e")]
    short = hi.step_table(dataset_with(data, segs), denylist=FX.DENYLIST, stride_ns=100 * MS, step_ns=50 * MS)
    assert short["header"]["stride_ns"] == 100 * MS and short["header"]["step_ns"] == 50 * MS
    table = hi.step_table(dataset_with(data, segs), denylist=FX.DENYLIST, stride_ns=100 * MS)
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
    accepted = hi.step_table(dataset_with(data, segs), denylist=FX.DENYLIST, stride_ns=100 * MS, all_segments=False)
    assert set(accepted["columns"]["suitability"]) == {"accepted"}


def test_step_table_capture_gap_starts_a_new_run(tmp_path):
    data = session_payload(tmp_path, esc_at_ms=2900)
    for p in data["packets"][100:]:
        p["composition_ns"] += 100 * MS   # a 110 ms capture gap after frame 99
    data["metadata"]["end_ns"] += 100 * MS
    seg = [dict(segment_id="a", start_ns=BASE, end_ns=data["metadata"]["end_ns"], reviewed_gameplay=True,
                imitation_suitability="accepted", suitability_reason="r", evidence="e")]
    c = hi.step_table(dataset_with(data, seg), denylist=FX.DENYLIST, stride_ns=100 * MS)["columns"]
    assert len(set(c["run_id"])) == 2 and False in c["gap_free"]


# ---- the fit's step-file format, rivals-range-steps-v1 (K2) ------------------------------------------------

FIT_BINDINGS = {a: ids[0] if len(ids) == 1 else ids for a, ids in FX.BINDINGS.items() if a in hi.FIT_ACTIONS}
CALIBRATION = {"kind": "slow_turn_constant", "yaw_deg_per_count": 0.0330738, "pitch_deg_per_count": 0.0330738,
               "pitch": {"kind": "derived_equal_sensitivity"}, "source": "synthetic"}


def write_fit_steps(tmp_path, data, segs, name="s1.steps.jsonl", review=None, **kw):
    out = tmp_path / name
    args = dict(sitting="test-sitting", calibration=CALIBRATION, denylist=FX.DENYLIST, step_ns=100 * MS)
    args.update(kw)
    hi.write_steps(build_dataset(data, segs, **(review or {})), out, **args)
    lines = out.read_text(encoding="utf-8").splitlines()
    return json.loads(lines[0]), [json.loads(x) for x in lines[1:]]


def reader_invariants(h, rows):
    """The fit reader's row and sequence rules (policy/range_bc/steps.py), restated for this stdlib test."""
    n = len(h["actions"])
    for k, r in enumerate(rows):
        assert r["i"] == k and 0 <= r["anchor_ns"] - r["frame"]["composition_ns"] <= 2 * h["frame_period_ns"]
        for c in range(n):
            if r["held_known"][c]:
                assert r["press"][c] - r["release"][c] == r["held_end"][c] - r["held_start"][c]
        assert all(p not in h["bindings"].values() for p in r["unsupported"])
        if k and rows[k - 1]["run"] == r["run"]:
            p = rows[k - 1]
            assert r["anchor_ns"] - p["anchor_ns"] == h["step_ns"]
            assert r["frame"]["frame_index"] > p["frame"]["frame_index"]
            assert all(p["held_end"][c] == r["held_start"][c] for c in range(n)
                       if p["held_known"][c] and r["held_known"][c])
    runs = [r["run"] for r in rows]
    assert all(runs.index(x) == k or runs[k - 1] == x for k, x in enumerate(runs))   # a run never reappears


def two_segments(data):
    end = data["metadata"]["end_ns"]
    return [dict(segment_id="a", start_ns=BASE, end_ns=BASE + 2000 * MS, reviewed_gameplay=True,
                 imitation_suitability="accepted", suitability_reason="r", evidence="e"),
            dict(segment_id="b", start_ns=BASE + 2000 * MS, end_ns=end, reviewed_gameplay=True,
                 imitation_suitability="rejected", suitability_reason="r", evidence="e")]


def test_steps_v1_header_rows_and_reader_invariants(tmp_path):
    data = steps_payload(tmp_path)
    h, rows = write_fit_steps(tmp_path, data, two_segments(data))
    assert h["format"] == "rivals-range-steps-v1" and h["session_group"] == h["session_id"] == "s1"
    assert h["actions"] == list(hi.FIT_ACTIONS) and h["frame_period_ns"] == STEP and h["video_size"] == [640, 360]
    assert h["injected_events"] == 0 and h["device_scope"] == "single_keyboard_mouse" and h["patch"]
    reader_invariants(h, rows)
    w, rmb = hi.FIT_ACTIONS.index("move_forward"), hi.FIT_ACTIONS.index("web_cluster")
    assert sum(r["press"][w] for r in rows) == 1 and sum(r["release"][w] for r in rows) == 1   # repeat is no press
    assert sum(r["press"][rmb] for r in rows) == 1
    assert sum(r["press"][hi.FIT_ACTIONS.index("team_up")] for r in rows) == 1       # C is team_up, a real action
    unsupported = {}
    for r in rows:
        for pid, count in r["unsupported"].items():
            unsupported[pid] = unsupported.get(pid, 0) + count
    assert unsupported == {}   # X1 is goh_targeting now; the Esc lies past the last full step
    assert sum(r["press"][hi.FIT_ACTIONS.index("goh_targeting")] for r in rows) == 1
    assert {r["suitability"] for r in rows} == {"accepted", "rejected"} and len({r["run"] for r in rows}) == 2


def test_steps_v1_gap_ends_the_run_without_stale_frames(tmp_path):
    data = session_payload(tmp_path, esc_at_ms=2900)
    for p in data["packets"][100:]:
        p["composition_ns"] += 150 * MS          # frames stop for 160 ms after frame 99
    data["metadata"]["end_ns"] += 150 * MS
    seg = [dict(segment_id="a", start_ns=BASE, end_ns=data["metadata"]["end_ns"], reviewed_gameplay=True,
                imitation_suitability="accepted", suitability_reason="r", evidence="e")]
    h, rows = write_fit_steps(tmp_path, data, seg, step_ns=30 * MS)
    reader_invariants(h, rows)
    assert max(r["anchor_ns"] - r["frame"]["composition_ns"] for r in rows) <= 2 * h["frame_period_ns"]
    assert len({r["run"] for r in rows}) == 2 and False in [r["gap_free"] for r in rows]
    gap_start, gap_end = BASE + 990 * MS, BASE + 1150 * MS
    assert not any(gap_start + 2 * STEP < r["anchor_ns"] < gap_end for r in rows)   # no stale-frame anchor


def test_steps_v1_identity_comes_from_the_review_and_mismatches_are_refused(tmp_path):
    data = steps_payload(tmp_path)
    h, _ = write_fit_steps(tmp_path, data, two_segments(data))
    assert h["bindings"] == FIT_BINDINGS and h["patch"] == FX.PATCH and h["bindings"]["melee"] == ["key:47:0", "mouse:5"]
    assert h["accel_on"] is True
    assert h["swing_mode"] == FX.SETTINGS["swing_mode"]
    assert h["settings_hash"] == hi.settings_identity(FX.SETTINGS, FX.BINDINGS)
    swapped = dict(FIT_BINDINGS, get_over_here="key:18:0", amazing_combo="key:33:0")   # E/F swapped
    for n, (field, value) in enumerate((("bindings", swapped), ("settings_hash", "0" * 64), ("patch", "other"),
                                        ("regime", "no_ability_cooldown"),
                                        ("swing_mode", {"automatic_swing": True, "hold_to_swing": False}),
                                        ("aliases", {}),
                                        ("device_report", dict(injected_control_packets=0)))):
        with pytest.raises(DemoError, match="differs"):
            write_fit_steps(tmp_path, data, two_segments(data), name=f"m{n}.jsonl", **{field: value})


def test_steps_v1_refuses_injected_input_sealed_sessions_and_bad_reviews(tmp_path):
    data = steps_payload(tmp_path)
    for e in data["events"]:
        if e["type"] == "mouse":
            e["device"] = 0          # the only mouse is the injected handle: the importer admits one device
    with pytest.raises(DemoError, match="injected"):
        write_fit_steps(tmp_path, data, two_segments(data))
    data = steps_payload(tmp_path)
    sealed = dict(schema_version=1, sessions=[dict(session_id="s1", media_sha256="e" * 64)])
    with pytest.raises(DemoError, match="sealed"):
        write_fit_steps(tmp_path, data, two_segments(data), name="s.jsonl", denylist=sealed)
    partial = {k: v for k, v in FX.BINDINGS.items() if k != "melee"}
    with pytest.raises(DemoError, match="every fit action"):
        write_fit_steps(tmp_path, data, two_segments(data), name="p.jsonl", review=dict(bindings=partial, aliases={}))
    with pytest.raises(DemoError, match="swing_mode"):
        write_fit_steps(tmp_path, data, two_segments(data), name="w.jsonl",
                        review=dict(settings=dict(FX.SETTINGS, swing_mode="default")))
    assert not (tmp_path / "s.jsonl").exists()


def test_steps_v1_binding_alias_counts_action_level_edges(tmp_path):
    data = session_payload(tmp_path, esc_at_ms=2900)
    extra = [key_event(100, 86, 47, True), mouse_event(130, button_flags=256, buttons_down=[5]),   # V, then Mouse 5 too
             key_event(160, 86, 47, False), mouse_event(190, button_flags=512, buttons_up=[5]),   # both released
             mouse_event(500, button_flags=256, buttons_down=[5]), mouse_event(530, button_flags=512, buttons_up=[5])]
    data = rebuild(data, sorted(data["events"] + extra, key=lambda e: e["t_ns"]))
    h, rows = write_fit_steps(tmp_path, data, two_segments(data))
    reader_invariants(h, rows)
    melee = hi.FIT_ACTIONS.index("melee")
    assert h["bindings"]["melee"] == ["key:47:0", "mouse:5"]
    assert sum(r["press"][melee] for r in rows) == 2 and sum(r["release"][melee] for r in rows) == 2
    assert not any("mouse:5" in r["unsupported"] for r in rows)
    with pytest.raises(DemoError, match="aliases"):
        write_fit_steps(tmp_path, data, two_segments(data), name="bad.jsonl", review=dict(aliases={"key:9:0": "melee"}))


def test_chat_and_overlays_are_cut_from_opening_to_closing_packet():
    focus = [(t(0), t(40))]
    keys = [(t(5), 13, True), (t(6), 87, True), (t(9), 13, True),        # Enter ... typing ... Enter: chat 5-9 s
            (t(15), 112, True), (t(22), 112, True),                       # F1 overlay 15-22 s
            (t(28), 9, True), (t(31), 9, False),                          # Tab held 28-31 s
            (t(34), 13, True), (t(35), 27, True)]                          # chat closed by Esc: not the settings menu
    ui = [k for k in keys if k[1] in hi.UI_KEYS]
    segs, flags = hi.propose_segments(focus, hud(0, 40), ui_keys=ui, focus_settle_ns=0)
    play = [(s["start_ns"], s["end_ns"]) for s in segs if s["machine_reason"] == hi.GAMEPLAY]
    for opened, closed in ((5, 9), (15, 22), (28, 31), (34, 35)):
        assert not any(a < t(closed) + hi.UI_SETTLE_NS and t(opened) < b for a, b in play), (opened, closed)
    assert not flags and "settings_menu" not in reasons(segs)
    cuts, esc = hi.ui_cuts([(t(5), 13, True)], focus)                     # never closed: to the interval end
    assert cuts == [(t(5), t(40), "ui_key")] and esc == []
    cuts, esc = hi.ui_cuts([(t(5), 27, True)], focus)
    assert esc == [t(5)] and cuts[0][2] == "settings_menu"


# ---- media relocation: a verified transcode stands in for a deleted original -------------------------------

def receipt_for(tmp_path, original, output, *, session="s1", ok=True, name="t.transcode.json", **over):
    doc = dict(kind="recording-transcode-v1", session_id=session,
               original={"path": str(original), "sha256": hi.sha256(original), "bytes": original.stat().st_size},
               output={"path": str(output), "sha256": hi.sha256(output), "bytes": output.stat().st_size},
               verification=dict(ok=ok, decoded_frames=300, decoded_pts_sha256="c" * 64, packets={"0": {"count": 300}},
                                 frames_csv={"matched_frames": 300, "audit": {}}),
               original_deleted=False, encoder="hevc_nvenc", ffmpeg_version="ffmpeg 8.0.1")
    doc.update(over)
    path = tmp_path / name
    path.write_text(json.dumps(doc))
    return path


def test_media_checks_accept_the_original_or_its_recorded_transcode(tmp_path):
    original, output, other = tmp_path / "o.mkv", tmp_path / "t.mkv", tmp_path / "x.mkv"
    original.write_bytes(b"original"), output.write_bytes(b"transcode"), other.write_bytes(b"other")
    ident = hi.sha256(original)
    rec = hi.relocation_record(receipt_for(tmp_path, original, output), session_id="s1", identity_sha256=ident)
    assert hi.check_media(original, identity_sha256=ident, relocation=rec) == "original"
    assert hi.check_media(output, identity_sha256=ident, relocation=rec, session_id="s1") == "transcode"
    with pytest.raises(DemoError, match="neither"):
        hi.check_media(other, identity_sha256=ident, relocation=rec)
    with pytest.raises(DemoError, match="no relocation"):
        hi.check_media(output, identity_sha256=ident)
    with pytest.raises(DemoError, match="another session"):
        hi.check_media(output, identity_sha256=ident, relocation=rec, session_id="s2")
    with pytest.raises(DemoError, match="not clean"):
        hi.relocation_record(receipt_for(tmp_path, original, output, ok=False, name="bad.json"), session_id="s1",
                             identity_sha256=ident)
    with pytest.raises(DemoError, match="another session"):
        hi.relocation_record(receipt_for(tmp_path, original, output, name="o2.json"), session_id="s9", identity_sha256=ident)
    Path(rec["receipt"]["path"]).write_text("{}")
    with pytest.raises(DemoError, match="receipt changed"):
        hi.check_media(output, identity_sha256=ident, relocation=rec)


def test_a_relocated_session_loads_through_the_importer_build(tmp_path):
    data = steps_payload(tmp_path)
    meta = data["metadata"]
    original = Path(meta["video_path"])
    ident = hi.sha256(original)
    reg = tmp_path / "splits.json"
    reg.write_text(json.dumps(dict(schema_version=1, sessions=[dict(
        session_id="s1", session_group="s1", split="train", video_path=str(original),
        recorded_video_path=meta["video_path"], expected_media_sha256=ident)])))
    placement = hd.read_splits(reg)[0]
    data["review"] = FX.review_for(data, two_segments(data))
    body = json.dumps(dict(metadata=meta, review=data["review"], events=data["events"], packets=data["packets"],
                           decoded=data["decoded"]), sort_keys=True, separators=(",", ":"))
    from dataclasses import asdict
    header = dict(format=hd.FORMAT, **asdict(placement), sealed=False, media_sha256=ident,
                  payload_sha256=hashlib.sha256(body.encode()).hexdigest())
    artifact = tmp_path / "imported-demo.jsonl"
    artifact.write_text(json.dumps(header) + "\n" + body + "\n")
    assert hd.load_dataset(artifact, splits=reg).media_sha256 == ident          # the original loads as imported
    output = tmp_path / "original.hevc.mkv"
    output.write_bytes(b"verified transcode")
    rec = hi.relocation_record(receipt_for(tmp_path, original, output), session_id="s1", identity_sha256=ident)
    original.unlink()                                                             # only after the relocation exists
    with pytest.raises(Exception):
        hd.load_dataset(artifact, splits=reg)
    ds = hi.load_dataset_relocated(artifact, splits=reg, denylist=FX.DENYLIST, relocation=rec)
    assert ds.media_sha256 == ident and ds.frames[0].video_path == str(output.resolve())
    out = tmp_path / "s1.steps.jsonl"
    hi.write_steps(ds, out, sitting="x", calibration=CALIBRATION, denylist=FX.DENYLIST, step_ns=100 * MS)
    assert json.loads(out.read_text().splitlines()[0])["media_sha256"] == ident   # the identity stays the original
    sealed = dict(schema_version=1, sessions=[dict(session_id="s1", media_sha256="e" * 64)])
    with pytest.raises(DemoError, match="denylisted|sealed"):
        hi.load_dataset_relocated(artifact, splits=reg, denylist=sealed, relocation=rec)


def test_a_freeze_pinning_the_original_passes_only_with_a_pinned_relocation(tmp_path):
    folder = tmp_path / "sessions" / "s1"
    folder.mkdir(parents=True)
    original, output = tmp_path / "o.mkv", tmp_path / "t.mkv"
    original.write_bytes(b"original"), output.write_bytes(b"transcode")
    ident = hi.sha256(original)
    rec = hi.relocation_record(receipt_for(tmp_path, original, output), session_id="s1", identity_sha256=ident)
    (folder / "media-relocation.json").write_text(json.dumps(rec))
    hi.freeze(folder, root=tmp_path, external=[original])
    assert hi.check_freeze(folder, root=tmp_path) == []
    original.unlink()
    assert hi.check_freeze(folder, root=tmp_path) == []                            # the transcode stands in
    output.write_bytes(b"tampered")
    assert hi.check_freeze(folder, root=tmp_path) == ["o.mkv"]


def test_an_alt_tab_cut_never_spills_into_the_next_focus_interval():
    focus = [(t(0), t(5.9)), (t(6.8), t(20))]
    segs = propose(focus, hud(0, 20), ui_keys=[(t(5.85), 18, True)], focus_settle_ns=hi.FOCUS_SETTLE_NS)
    second = [s for s in segs if s["start_ns"] >= t(6.8)]
    assert second[0]["machine_reason"] == "focus_transition" and second[0]["end_ns"] == t(6.8) + hi.FOCUS_SETTLE_NS
    assert "ui_key" not in reasons(second)


def test_pins_survive_a_crlf_checkout(tmp_path):
    deny = tmp_path / "deny.json"
    deny.write_bytes(json.dumps(dict(schema_version=1, sessions=[dict(session_id="x", media_sha256="d" * 64)]),
                                indent=1).encode())
    pin = hi.sha256(deny)                                     # pinned from the LF file as written
    crlf = tmp_path / "deny-crlf.json"
    crlf.write_bytes(deny.read_bytes().replace(b"\n", b"\r\n"))
    assert hi.sha256(crlf) != pin and hi.lf_sha256(crlf) == pin
    assert hi.load_denylist(crlf, sha256_pin=pin)["sessions"][0]["session_id"] == "x"
    with pytest.raises(DemoError, match="pinned"):
        hi.load_denylist(crlf, sha256_pin="0" * 64)
    folder = tmp_path / "s"
    folder.mkdir()
    (folder / "review.json").write_bytes(b'{\n "a": 1\n}\n')
    (folder / "frame.jpg").write_bytes(b"\xff\xd8binary\n")
    hi.freeze(folder, root=tmp_path)
    (folder / "review.json").write_bytes((folder / "review.json").read_bytes().replace(b"\n", b"\r\n"))
    assert hi.check_freeze(folder, root=tmp_path) == []       # a CRLF text artefact still matches
    (folder / "frame.jpg").write_bytes(b"\xff\xd8binary\r\n")
    assert hi.check_freeze(folder, root=tmp_path) == ["s/frame.jpg"]   # binary pins stay raw


def test_a_death_is_cut_between_the_neighbouring_samples_and_the_fall_before_it_stays():
    samples = hud(0, 20)
    dead = [ts for ts, _ in samples if t(9.9) <= ts <= t(11.1)]           # HP read 0 from 10.0 to 11.0 s
    segs = propose([(t(0), t(20))], samples, dead=dead)
    cut = [s for s in segs if s["machine_reason"] == "dead"]
    assert len(cut) == 1 and cut[0]["start_ns"] == t(9.8) + 1 and cut[0]["end_ns"] == t(11.2) + hi.RESPAWN_SETTLE_NS
    play = [s for s in segs if s["machine_reason"] == hi.GAMEPLAY]
    assert play[0]["end_ns"] == t(9.8) + 1                                        # the fall up to 9.8 s is kept
    assert play[1]["start_ns"] == t(12.2)                                          # first sample after the respawn settle
    assert not any(s["start_ns"] <= d < s["end_ns"] for s in play for d in dead)


# ---- the recording's game build (lead decision 2026-09-24, patch-equivalence-design.md item 3) ----------------------
# Steam's own lines and values on this PC (content log, appmanifest, version.json), before and after the 06:15 update.

CDT = -5 * 3600
STEAM_LOG_0917 = (
    "[2026-09-17 12:15:39] AppID 2767030 update started : download 0/4246668320, store 0/0, reuse 0/262622430, "
    "delta 0/135746607, stage 0/4783234517 \n"
    '[2026-09-17 12:16:35] AppID 2767030 starting commit from "C:\\Program Files (x86)\\Steam\\steamapps\\downloading'
    '\\2767030" to "C:\\Program Files (x86)\\Steam\\steamapps\\common\\MarvelRivals" : 21 updated, 0 moved, 23 deleted files\n'
    "[2026-09-17 12:16:35] AppID 2767030 finished update, 2 mounted depots (BuildID 25364676) : "
    "2767031 (6449387869012127437),4406011 (4523644096164555972),\n"
    "[2026-09-17 12:16:35] AppID 2767030 scheduler finished : removed from schedule (result No Error, state 0xc) \n"
    "[2026-09-23 12:12:04] AppID 2767030 state changed : Fully Installed,App Running,\n")
STEAM_LOG_0924 = (
    "[2026-09-24 04:05:50] AppID 2767030 state changed : Update Required,Fully Installed, (Update delayed for 7753 secs)\n"
    "[2026-09-24 06:15:09] AppID 2767030 update started : download 0/2101406176, store 0/0, reuse 0/196706645, "
    "delta 0/124354901, stage 0/2515231161 \n"
    '[2026-09-24 06:15:31] AppID 2767030 starting commit from "C:\\Program Files (x86)\\Steam\\steamapps\\downloading'
    '\\2767030" to "C:\\Program Files (x86)\\Steam\\steamapps\\common\\MarvelRivals" : 16 updated, 0 moved, 0 deleted files\n'
    "[2026-09-24 06:15:31] AppID 2767030 finished update, 2 mounted depots (BuildID 25501035) : "
    "2767031 (3100206924004297687),4406011 (4356380312643998543),\n"
    "[2026-09-24 18:21:10] AppID 2767030 state changed : Fully Installed,App Running,\n")
TAKE_0924 = dict(started_utc="2026-09-24T23:23:04.169Z", start_ns=360059037430700, end_ns=360589929922700)   # 232304
TAKE_0923 = dict(started_utc="2026-09-23T20:55:28.900Z", start_ns=264804047318300, end_ns=265471947027400)   # 205528


def appmanifest(buildid, last_updated):
    return (f'"AppState"\n{{\n\t"appid"\t\t"2767030"\n\t"LastUpdated"\t\t"{last_updated}"\n\t"LastPlayed"\t\t"1790305587"\n'
            f'\t"buildid"\t\t"{buildid}"\n\t"TargetBuildID"\t\t"{buildid}"\n}}\n')


def steam(install, *, log_extra="", **override):
    """The evidence the provenance step parses: Steam as installed on 09-17 (build 25364676) or since 09-24 06:15."""
    files = dict(content_log=STEAM_LOG_0917, appmanifest=appmanifest("25364676", 1789665395),
                 version_json='{"version": "1.1.3870120", "changelist": 3870120}',
                 version_json_mtime_utc="2026-09-17T17:16:28.017550+00:00", utc_offset_s=CDT)
    if install == "0924":
        files.update(content_log=STEAM_LOG_0917 + STEAM_LOG_0924, appmanifest=appmanifest("25501035", 1790248531),
                     version_json='{"version": "1.1.3892207", "changelist": 3892207}',
                     version_json_mtime_utc="2026-09-24T11:15:10.109511+00:00")
    files.update(override)
    files["content_log"] += log_extra
    return hi.steam_build_evidence(**files)


def span(take):
    start = hi._utc(take["started_utc"])
    return dict(started_utc=start, ended_utc=start + timedelta(microseconds=(take["end_ns"] - take["start_ns"]) // 1000))


def test_a_session_on_the_new_build_records_it():
    got = hi.recorded_build(steam("0924"), **span(TAKE_0924))
    assert got["value"] == "1.1.3892207/build25501035"
    assert got["content_log_finished_update"] == {"local": "2026-09-24 06:15:31", "utc": "2026-09-24T11:15:31+00:00",
                                                  "build": "25501035"}
    assert got["installed_utc"] == "2026-09-24T11:15:31+00:00"   # appmanifest LastUpdated agrees with the log


def test_the_old_build_still_records_the_old_string():
    got = hi.recorded_build(steam("0917"), **span(TAKE_0923))
    assert got["value"] == "1.1.3870120/build25364676"   # the string every admitted step header carries


def test_a_download_after_the_recording_leaves_the_build_readable():
    later = "[2026-09-25 03:00:00] AppID 2767030 update started : download 0/1, store 0/0, reuse 0/0, delta 0/0, stage 0/1 \n"
    assert hi.recorded_build(steam("0924", log_extra=later), **span(TAKE_0924))["value"] == "1.1.3892207/build25501035"


@pytest.mark.parametrize("evidence, take, refusal", [
    (lambda: steam("0924"), TAKE_0923, "after the recording started"),       # an old take read from the new install
    (lambda: steam("0924", appmanifest='"AppState"\n{\n}\n'), TAKE_0924, "appmanifest"),
    (lambda: steam("0924", version_json="not json"), TAKE_0924, "version.json version"),
    (lambda: steam("0924", version_json='{"version": "1.1.3892207", "changelist": 3870120}'), TAKE_0924, "inconsistent"),
    (lambda: steam("0924", version_json_mtime_utc="2026-09-17T17:16:28Z"), TAKE_0924, "not written by the update"),
    (lambda: steam("0924", version_json_mtime_utc=None), TAKE_0924, "mtime unknown"),
    (lambda: steam("0924", log_extra="[2026-09-24 18:25:00] AppID 2767030 update started : download 0/1\n"),
     TAKE_0924, "during the recording"),
    (lambda: steam("0924", log_extra="[2026-09-24 19:00:00] AppID 2767030 starting commit from \"a\" to \"b\" : 1 updated\n"),
     TAKE_0924, "installed files after"),
    (lambda: steam("0924", content_log=STEAM_LOG_0917), TAKE_0924, "not the installed 25501035"),
])
def test_an_unreadable_build_is_refused(evidence, take, refusal):
    with pytest.raises(DemoError, match=refusal):
        hi.recorded_build(evidence(), **span(take))


def assemble_module():
    path = Path(__file__).resolve().parents[1] / "data/human/sessions/assemble_session.py"
    spec = importlib.util.spec_from_file_location("assemble_session_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_assembly_takes_the_build_from_the_intake_evidence_and_refuses_without_it(tmp_path):
    A = assemble_module()

    def provenance(build):
        (tmp_path / "provenance.json").write_text(json.dumps({"build": build}), encoding="utf-8")

    new = hi.recorded_build(steam("0924"), **span(TAKE_0924))
    provenance({"evidence": steam("0924"), "recorded": new})
    assert A.session_patch(tmp_path, TAKE_0924, hi)["value"] == "1.1.3892207/build25501035"
    provenance({"evidence": steam("0917"), "recorded": hi.recorded_build(steam("0917"), **span(TAKE_0923))})
    assert A.session_patch(tmp_path, TAKE_0923, hi)["value"] == "1.1.3870120/build25364676"
    provenance({"appmanifest_buildid": [["buildid", "25364676"]]})   # a provenance record from before 2026-09-24
    with pytest.raises(A.Refused, match="no Steam build evidence"):
        A.session_patch(tmp_path, TAKE_0924, hi)
    provenance({"evidence": steam("0924"), "recorded": {"value": None, "refused": "..."}})
    with pytest.raises(A.Refused, match="after the recording started"):
        A.session_patch(tmp_path, TAKE_0923, hi)
    provenance({"evidence": steam("0917"), "recorded": new})          # the record and its evidence disagree
    with pytest.raises(A.Refused, match="re-derived"):
        A.session_patch(tmp_path, TAKE_0924, hi)


# ---- per-date motor statements (review of the motor fix, M1-M3 and the zone) ------------------------------------

ROOT = Path(__file__).resolve().parents[1]
ADMITTED_0923 = ("20260923T051828-422Z-33696-1", "20260923T171533-187Z-33696-5", "20260923T200129-346Z-33696-6",
                 "20260923T205528-900Z-45572-3")


def intake_module():
    spec = importlib.util.spec_from_file_location("intake_session_under_test", ROOT / "data/human/sessions/intake_session.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("utc, day", [
    ("2026-09-25T02:13:20.371Z", "2026-09-24"),   # 021320: 21:13 CDT on 09-24
    ("2026-09-24T23:23:04.169Z", "2026-09-24"),   # 232304: 18:23 CDT
    ("2026-09-24T02:30:00Z", "2026-09-23"),       # an evening 09-23 take reads 09-23 on any machine (review minor)
    ("2026-09-24T04:59:59Z", "2026-09-23"), ("2026-09-24T05:00:00Z", "2026-09-24"),
    ("2026-03-08T05:30:00Z", "2026-03-07"),       # before the second Sunday of March 08:00 UTC: CST
    ("2026-03-09T05:30:00Z", "2026-03-09"),       # after it: CDT (CST would give 03-08)
    ("2026-11-02T05:30:00Z", "2026-11-01"),       # after the first Sunday of November 07:00 UTC: CST again
])
def test_the_recording_date_is_taken_in_america_chicago(utc, day):
    assert assemble_module().chicago_date(hi._utc(utc)) == day


def test_motor_statements_quote_the_committed_log_and_keep_the_admitted_wording():
    A = assemble_module()
    log = (ROOT / "docs/recording-log.md").read_text(encoding="utf-8")
    old = A.motor_statement(TAKE_0923, hi, log)
    assert old["settings"] == "James's dated statements of 2026-09-23, applied by the lead to every existing session"
    assert old["bindings"] == "James's dated statements of 2026-09-23 (docs/recording-log.md)"   # M1: the pinned text
    new = A.motor_statement(TAKE_0924, hi, log)
    assert "57d1f3d" in new["settings"] and "~22:40 CDT" in new["settings"] and "~22:10" not in new["settings"]   # M2
    assert all(q in log for q in new["log_quotes"]) and new["log_quotes"][0].startswith("2026-09-24: ")
    today = A.motor_statement(dict(TAKE_0924, started_utc="2026-09-25T21:26:46.322Z",
                                    session_id="20260925T212646-322Z-49728-6"), hi, log)
    assert today["date"] == "2026-09-25" and "fbe6693" in today["settings"] and "fbe6693" in today["bindings"] and "~16:50 CDT" in today["settings"]
    assert all(q in log for q in today["log_quotes"]) and today["log_quotes"][0].startswith("2026-09-25: ")
    for day in ("2026-09-22T20:00:00Z", "2026-09-26T20:00:00Z"):
        with pytest.raises(A.Refused, match="no per-session motor statement"):
            A.motor_statement(dict(TAKE_0924, started_utc=day), hi, log)
    with pytest.raises(A.Refused, match="lacks the 2026-09-24 motor statement"):
        A.motor_statement(TAKE_0924, hi, log.replace("~22:40 CDT", "~22:10 CDT"))


@pytest.mark.corpus   # step_motor hashes data/human/notes/2026-09-21-user-settings.json, which is not in the repo
def test_the_motor_step_quotes_the_recording_dates_own_statement_and_regenerates_only_on_purpose(tmp_path):
    from types import SimpleNamespace
    S = intake_module()
    A = S._assembly()
    (tmp_path / "provenance.json").write_text(json.dumps({"settings_receipt": {
        "sha256": "0" * 64, "equals_2026_09_22_receipt": {"1036": True, "0": True},
        "controls": {"1036": {"MouseHorizontalSensitivity": 1.89, "MouseVerticalSensitivity": 1.89}}}}), encoding="utf-8")
    (tmp_path / "slot-mapping.json").write_text("{}", encoding="utf-8")
    c = SimpleNamespace(sid="s", meta=TAKE_0924, hi=hi, out=tmp_path, supersedes=None)
    S.step_motor(c)
    doc = json.loads((tmp_path / "motor-settings.json").read_text(encoding="utf-8"))
    assert doc["settings"]["statement"]["date"] == "2026-09-24"
    assert doc["settings"]["statement"]["text"] == list(A.MOTOR_STATEMENTS["2026-09-24"]["log_quotes"])   # M3
    assert doc["settings"]["per_session_source"] == A.MOTOR_STATEMENTS["2026-09-24"]["settings"]
    assert doc["settings_identity"] == hi.settings_identity(A.MOTOR, A.BINDINGS)
    first = hashlib.sha256((tmp_path / "motor-settings.json").read_bytes()).hexdigest()
    with pytest.raises(S.Refused, match="already written"):
        S.step_motor(c)                                                      # write-once without --supersedes
    S.step_motor(SimpleNamespace(**dict(vars(c), supersedes="regenerated after review M2/M3")))
    again = json.loads((tmp_path / "motor-settings.json").read_text(encoding="utf-8"))
    assert again["supersedes"] == {"file": "motor-settings.v1.json", "sha256": first,
                                   "reason": "regenerated after review M2/M3"}
    assert hashlib.sha256((tmp_path / "motor-settings.v1.json").read_bytes()).hexdigest() == first
    c23 = SimpleNamespace(sid="s", meta=TAKE_0923, hi=hi, out=tmp_path / "d23", supersedes=None)
    c23.out.mkdir()
    for name in ("provenance.json", "slot-mapping.json"):
        (c23.out / name).write_bytes((tmp_path / name).read_bytes())
    S.step_motor(c23)
    old = json.loads((c23.out / "motor-settings.json").read_text(encoding="utf-8"))
    assert old["settings"]["statement"]["text"] == list(A.MOTOR_STATEMENTS["2026-09-23"]["log_quotes"])


@pytest.mark.corpus
def test_admitted_sessions_re_derive_their_pinned_per_session_sources():
    A = assemble_module()
    log = (ROOT / "docs/recording-log.md").read_text(encoding="utf-8")
    for sid in ADMITTED_0923:
        d = ROOT / "data/human/sessions" / sid
        meta = json.loads((d / "provenance.json").read_text(encoding="utf-8"))["metadata"]
        stored = json.loads((d / "settings.json").read_text(encoding="utf-8"))
        got = A.motor_statement(meta, hi, log)
        assert (got["settings"], got["bindings"]) == (stored["settings"]["per_session_source"],
                                                      stored["bindings"]["per_session_source"]), sid


# ---- the edge proof (lead decision 2026-09-25): an edge sits only on a frame the reads prove -------------------------

def _play(segs):
    return [s for s in segs if s["machine_reason"] == hi.GAMEPLAY]


def test_an_edge_sits_only_on_a_proven_frame():
    focus = [(t(0), t(10))]
    samples = hud(0, 3, present=False) + hud(3, 10)
    first, last = t(3), samples[-1][0]
    f = lambda base, k: base + k * 8_333_333
    # outward from a proven sample frame, over contiguous proven frames only (232304: f308-f309 fail, f310 holds)
    native = {("start", first): [(f(first, -3), False), (f(first, -2), False), (f(first, -1), True), (first, True)]}
    assert _play(propose(focus, samples, native=native))[0]["start_ns"] == f(first, -1)
    # the sample frame itself fails: the start moves inward to the first proven frame
    native = {("start", first): [(f(first, -1), True), (first, False), (f(first, 1), False), (f(first, 2), True)]}
    assert _play(propose(focus, samples, native=native))[0]["start_ns"] == f(first, 2)
    # the last sample frame fails (e.g. the HP bar under the guard's half-health test): the end moves inward
    native = {("end", last): [(f(last, -2), True), (f(last, -1), False), (last, False), (f(last, 1), True)]}
    assert _play(propose(focus, samples, native=native))[0]["end_ns"] == f(last, -2) + 1
    # no proven frame in the reads: refused, never left on an unproven frame
    native = {("start", first): [(first, False), (f(first, 1), False)]}
    with pytest.raises(DemoError, match="passes the edge proof"):
        propose(focus, samples, native=native)


def test_the_evidence_step_refuses_a_pre_rule_proposer_and_any_unproven_edge():
    from types import SimpleNamespace
    S = intake_module()
    S.require_edge_rule(hi, "this tree")                                  # the current proposer carries the rule
    with pytest.raises(S.Refused, match="predates the edge rule"):
        S.require_edge_rule(SimpleNamespace(), "code-snapshot-2ad0992")   # the pre-rule snapshot has no marker
    f = lambda k: t(3) + k * 8_333_333
    reads = [dict(frames=[dict(composition_ns=f(k), proof=k >= 2) for k in range(0, 4)]),
             dict(frames=[dict(composition_ns=t(9) - 1, proof=True)])]
    good = [dict(segment_id="seg-001", machine_reason=hi.GAMEPLAY, start_ns=f(2), end_ns=t(9))]
    S.require_proven_edges(good, reads, hi.GAMEPLAY)
    # what the pre-rule proposer did on an inward case: the edge left on the unproven sample frame
    bad = [dict(segment_id="seg-001", machine_reason=hi.GAMEPLAY, start_ns=f(0), end_ns=t(9))]
    with pytest.raises(S.Refused, match="seg-001 start edge"):
        S.require_proven_edges(bad, reads, hi.GAMEPLAY)
    unread = [dict(segment_id="seg-001", machine_reason=hi.GAMEPLAY, start_ns=f(2), end_ns=t(8))]
    with pytest.raises(S.Refused, match="seg-001 end edge"):
        S.require_proven_edges(unread, reads, hi.GAMEPLAY)
