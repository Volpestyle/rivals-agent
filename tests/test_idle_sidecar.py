"""Synthetic physical-idle exclusions and fail-closed reader contracts; no corpus."""
from array import array
import json

import pytest

from policy.range_bc import idle_sidecar as idle


def event(kind, t, **kw):
    return {"type": kind, "t_ns": t, **kw}


def mouse(t, **kw):
    return event("mouse", t, **{"device": 1, "dx": 0, "dy": 0, "motion_flags": 0,
                               "button_flags": 0, "wheel_data": 0, "relative": True,
                               "buttons_down": [], "buttons_up": [],
                               "wheel_vertical": 0, "wheel_horizontal": 0, **kw})


def key(t, down=True, **kw):
    return event("key", t, **{"device": 1, "vk": 90, "scan": 44, "flags": 0 if down else 1,
                             "down": down, **kw})


def cursor(events=(), held=()):
    records = [event("raw_input_status", 0, ok=True), event("focus", 0, active=True, held_vk=list(held)),
               *events]
    return idle.RawCursor({**e, "seq": i} for i, e in enumerate(records))


def classify(events=(), held=(), anchor=10, step=10):
    return cursor(events, held).classify(anchor, step)[0]


def test_idle_and_zero_relative_packet_are_true():
    assert classify() is True
    assert classify([mouse(15)]) is True


@pytest.mark.parametrize("events", [
    [key(5)],                                    # unsupported held key
    [key(12), key(13, False)],                    # within-step tap
    [key(5), key(12)],                            # repeat make
    [key(15, False)],                            # release without observed press
    [mouse(5, button_flags=256, buttons_down=[5])],
    [mouse(12, button_flags=1, buttons_down=[1]), mouse(13, button_flags=2, buttons_up=[1])],
    [mouse(12, dx=1)],                            # below camera quantization bin
    [mouse(12, dy=-1)],
    [mouse(12, dx=4), mouse(13, dx=-4)],            # net-zero opposing packets
    [mouse(12, dy=4), mouse(13, dy=-4)],
    [mouse(12, button_flags=1024, wheel_data=120, wheel_vertical=120)],
    [mouse(12, button_flags=2048, wheel_data=-120, wheel_horizontal=-120)],
    [mouse(12, button_flags=4096)],                 # unsupported control-affecting flag
    [key(10)],                                    # down AT anchor => held at anchor
    [key(20)],                                    # edge AT right endpoint is included
])
def test_physical_activity_defeats_idle(events):
    assert classify(events) is False


@pytest.mark.parametrize("events,held", [
    ([], [87]),                                    # ambiguous focus keyboard snapshot
    ([event("focus", 12, active=False, held_vk=[])], []),
    ([event("focus", 12, active=False, held_vk=[]), event("focus", 13, active=True, held_vk=[])], []),
    ([event("focus", 12, active=True, held_vk=[])], []),
    ([event("pause", 12, paused=True), event("pause", 13, paused=False)], []),
    ([event("gap", 12, reason="device_change")], []),
    ([event("raw_input_status", 12, ok=False)], []),
    ([mouse(12, motion_flags=1, relative=False)], []),
    ([mouse(5, motion_flags=1, relative=False)], []),
    ([mouse(12, motion_flags=128)], []),
    ([mouse(12, motion_flags=4)], []),
    ([mouse(12, motion_flags=2)], []),
])
def test_unknown_exclusions_never_become_idle(events, held):
    assert classify(events, held) is None


def test_snapshot_mouse_is_held_and_generic_modifier_uncertainty_is_preserved():
    assert classify(held=[1]) is False
    assert classify([key(5, False, vk=16, scan=42)], held=[16]) is None
    assert classify([key(5, False, vk=87, scan=17)], held=[87]) is True


def test_release_at_anchor_and_events_after_right_endpoint():
    assert classify([key(5), key(10, False)]) is True
    assert classify([key(21)]) is True


def test_gap_state_stays_unknown_until_fresh_focus():
    c = cursor([event("gap", 12, reason="device_change"),
                event("focus", 35, active=True, held_vk=[])])
    assert c.classify(10, 10)[0] is None
    assert c.classify(20, 10)[0] is None
    assert c.classify(30, 10)[0] is None
    assert c.classify(40, 10)[0] is True


def test_relative_packet_recovers_only_after_absolute_step():
    c = cursor([mouse(12, motion_flags=1, relative=False), mouse(15)])
    assert c.classify(10, 10)[0] is None
    assert c.classify(20, 10)[0] is True


def test_no_registration_no_focus_and_malformed_events_refuse_or_unknown():
    c = idle.RawCursor(iter([]))
    assert c.classify(10, 10)[0] is None
    with pytest.raises(ValueError):
        classify([event("mystery", 12)])
    with pytest.raises(ValueError):
        classify([mouse(12, relative=False)])
    with pytest.raises(ValueError, match="injected"):
        classify([mouse(12, device=0, dx=1)])
    with pytest.raises(ValueError, match="multiple"):
        classify([key(12), key(15, device=2)])


def test_failed_registration_needs_fresh_snapshot_after_recovery():
    c = cursor([event("raw_input_status", 2, ok=False), event("focus", 3, active=True, held_vk=[]),
                event("raw_input_status", 4, ok=True)])
    assert c.classify(10, 10)[0] is None


def rows(n):
    for i in range(n):
        yield {"i": i, "anchor_ns": i * 10, "run": "r0", "segment": "s0",
               "suitability": "accepted", "regime": "normal", "gap_free": True,
               "held_known": [True, False], "press": [0, 0], "release": [0, 0], "relative_known": True}


@pytest.mark.parametrize("length", [29, 30, 31, 150])
def test_run_threshold_is_fixed_and_whole_run_is_weighted(length):
    ns = array("b", [1]) * length
    lengths, runs = idle.run_lengths(rows(length), ns, [0] * length, 10)
    assert runs == [(0, length)]
    assert list(lengths) == [length] * length
    assert sum(v >= idle.K for v in lengths) == (length if length >= 30 else 0)


@pytest.mark.parametrize("field,value", [
    ("run", "r1"), ("segment", "s1"), ("suitability", "rejected"),
    ("suitability", "unresolved"), ("regime", "no_ability_cooldown"), ("gap_free", False),
])
def test_runs_do_not_cross_table_boundaries(field, value):
    rs = list(rows(40))
    rs[20][field] = value
    lengths, _ = idle.run_lengths(iter(rs), [1] * 40, [0] * 40, 10)
    assert max(lengths) < 30


def test_runs_do_not_cross_focus_generation_or_time_jump_or_unknown():
    lengths, _ = idle.run_lengths(rows(40), [1] * 40, [0] * 20 + [1] * 20, 10)
    assert list(lengths) == [20] * 40
    rs = list(rows(40))
    for r in rs[20:]:
        r["anchor_ns"] += 1
    assert max(idle.run_lengths(iter(rs), [1] * 40, [0] * 40, 10)[0]) == 20
    for value in (0, -1):
        ns = [1] * 40
        ns[20] = value
        assert max(idle.run_lengths(rows(40), ns, [0] * 40, 10)[0]) == 20


def test_row_head_counts_preserve_original_masks_and_pitch_unknown():
    r = next(rows(1))
    h = {"calibration": {"pitch_deg_per_count": None}}
    assert idle.head_counts(r, h) == {"held": 1, "press": 1, "release": 1, "yaw": 1, "pitch": 0}
    r["gap_free"] = False
    assert sum(idle.head_counts(r, h).values()) == 0


def dump(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")


def dump_lines(path, records):
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            idle.write_line(f, r)


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    sid = next(iter(idle.TABLE_HASHES))
    table = tmp_path / f"{sid}.steps.jsonl"
    header = {"session_id": sid, "split": "train", "media_sha256": "a" * 64, "step_ns": 10}
    dump_lines(table, [header, *rows(30)])
    hashes = {**idle.TABLE_HASHES, sid: idle.sha256(table)}
    monkeypatch.setattr(idle, "TABLE_HASHES", hashes)
    reg = tmp_path / "registry.json"
    registrations = [{"session_id": s, "session_group": s, "split": "train",
                      "expected_media_sha256": "a" * 64, "video_path": f"{s}.mkv",
                      "recorded_video_path": f"{s}.mkv"} for s in hashes]
    dump(reg, {"sessions": registrations})
    deny = tmp_path / "deny.json"
    dump(deny, {"sessions": []})
    sidecar = tmp_path / f"{sid}.idle.jsonl"
    producer = dict.fromkeys(idle.SOURCE_PATHS, "b" * 64)
    raw_hashes = dict.fromkeys(idle.RAW_NAMES, "c" * 64)
    sh = {"format": idle.FORMAT, "role": "train", "session_id": sid, "table_sha256": hashes[sid],
          "step_ns": 10, "k": 30, "idle_weight": .1, "raw_sha256": raw_hashes, "producer_sha256": producer}
    proofs = [{"i": i, "anchor_ns": i * 10, "null": True, "idle_run_length": 30, "weight": .1}
              for i in range(30)]
    dump_lines(sidecar, [sh, *proofs])
    entry = {"sidecar": sidecar.name, "sidecar_sha256": idle.sha256(sidecar), "table_sha256": hashes[sid],
             "raw_sha256": raw_hashes, "rows": 30, "step_ns": 10}
    manifest = {"format": idle.MANIFEST_FORMAT, "role": "train", "k": 30, "idle_weight": .1,
                "sessions": {s: entry for s in hashes}, "registry_sha256": idle.sha256(reg),
                "denylist_sha256": idle.sha256(deny), "producer_sha256": producer}
    mp = tmp_path / "manifest.json"
    dump(mp, manifest)
    return dict(table=table, sidecar=sidecar, manifest=manifest, mp=mp, reg=reg, deny=deny,
                sh=sh, proofs=proofs, sid=sid)


def load(b):
    return idle.load_weights(b["table"], b["sidecar"], manifest_path=b["mp"],
                             manifest_sha256=idle.sha256(b["mp"]), registry_path=b["reg"], denylist_path=b["deny"])


def repin(b):
    dump_lines(b["sidecar"], [b["sh"], *b["proofs"]])
    b["manifest"]["sessions"][b["sid"]]["sidecar_sha256"] = idle.sha256(b["sidecar"])
    dump(b["mp"], b["manifest"])


def test_reader_returns_weights_without_opening_raw_sources(bundle):
    result = load(bundle)
    assert result.typecode == "d" and list(result) == [.1] * 30


@pytest.mark.parametrize("field,value", [("i", 4), ("anchor_ns", 0), ("null", "true"),
                                        ("idle_run_length", -1), ("weight", 1), ("null", None)])
def test_reader_rejects_rehashed_structural_mutations(bundle, field, value):
    bundle["proofs"][2][field] = value
    repin(bundle)
    with pytest.raises(ValueError):
        load(bundle)


def test_reader_rejects_raw_provenance_change_even_if_sidecar_rehashed(bundle):
    bundle["sh"]["raw_sha256"] = dict.fromkeys(idle.RAW_NAMES, "d" * 64)
    repin(bundle)
    with pytest.raises(ValueError, match="provenance"):
        load(bundle)


def test_reader_rejects_extra_or_short_sidecar(bundle):
    bundle["proofs"].pop()
    repin(bundle)
    with pytest.raises(ValueError, match="short"):
        load(bundle)


def test_reader_checks_manifest_table_sidecar_and_access_pins(bundle):
    for key in ("sidecar", "table", "reg", "deny"):
        p = bundle[key]
        before = p.read_bytes()  # small synthetic fixtures only
        p.write_bytes(before + b"\n")
        with pytest.raises(ValueError):
            load(bundle)
        p.write_bytes(before)
    with pytest.raises(ValueError, match="manifest hash"):
        idle.load_weights(bundle["table"], bundle["sidecar"], manifest_path=bundle["mp"],
                          manifest_sha256="0" * 64, registry_path=bundle["reg"], denylist_path=bundle["deny"])


@pytest.mark.parametrize("split", ["val", "test", "gate2", "reader_validation"])
def test_preflight_refuses_nontrain_before_creating_output(bundle, tmp_path, split):
    registry = idle.small_json(bundle["reg"])
    registry["sessions"][0]["split"] = split
    dump(bundle["reg"], registry)
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="not independent train"):
        idle.export(logger_root=tmp_path / "must-not-open", table_root=tmp_path / "must-not-open",
                    output=output, registry_path=bundle["reg"], denylist_path=bundle["deny"])
    assert not output.exists()


@pytest.mark.parametrize("match", ["session_id", "media_sha256", "media_path"])
def test_denylist_matches_identity_hash_or_path(bundle, match):
    entry = {"session_id": "other", "media_sha256": "e" * 64, "media_path": "other.mkv"}
    entry[match] = {"session_id": bundle["sid"], "media_sha256": "a" * 64,
                    "media_path": bundle["sid"] + ".mkv"}[match]
    dump(bundle["deny"], {"sessions": [entry]})
    with pytest.raises(ValueError, match="denylisted"):
        idle.authorize(bundle["reg"], bundle["deny"])


def test_frame_continuity_sorts_bframes_and_excludes_gap_and_duplicates(tmp_path):
    path = tmp_path / "frames.csv"
    path.write_text("event_seq,pts,composition_ns,timebase_num,timebase_den\n"
                    "1,0,10,1,100000000\n2,2,30,1,100000000\n3,1,20,1,100000000\n"
                    "4,3,80,1,100000000\n5,4,90,1,100000000\n6,5,90,1,100000000\n"
                    "7,6,110,1,100000000\n", encoding="utf-8")
    frames = idle.FrameContinuity(path, tmp_path / "frames.sqlite",
                                  {"video_packets": 7, "fps_num": 100000000, "fps_den": 1})
    assert frames.valid(10, 30)
    assert not frames.valid(30, 40)
    assert not frames.valid(70, 80)
    assert not frames.valid(80, 90)
    assert frames.valid(100, 110)
    assert not frames.valid(110, 120)


def test_full_synthetic_export_and_readback_are_immutable(tmp_path, monkeypatch):
    sid = next(iter(idle.TABLE_HASHES))
    logger = tmp_path / "logger" / sid
    tables = tmp_path / "tables" / sid
    logger.mkdir(parents=True)
    tables.mkdir(parents=True)
    table = tables / f"{sid}.steps.jsonl"
    header = {"session_id": sid, "split": "train", "media_sha256": "a" * 64, "step_ns": 10,
              "actions": ["a", "b"], "calibration": {"pitch_deg_per_count": 1.0}}
    rs = [{**r, "anchor_ns": r["anchor_ns"] + 10} for r in rows(30)]
    dump_lines(table, [header, *rs])
    monkeypatch.setattr(idle, "TABLE_HASHES", {sid: idle.sha256(table)})
    reg, deny = tmp_path / "registry.json", tmp_path / "deny.json"
    dump(reg, {"sessions": [{"session_id": sid, "session_group": sid, "split": "train",
                            "expected_media_sha256": "a" * 64, "video_path": "s.mkv",
                            "recorded_video_path": "s.mkv"}]})
    dump(deny, {"sessions": []})
    dump_lines(logger / "inputs.jsonl", [{"seq": 0, "t_ns": 0, "type": "raw_input_status", "ok": True},
                                        {"seq": 1, "t_ns": 0, "type": "focus", "active": True, "held_vk": []}])
    with (logger / "frames.csv").open("w", encoding="utf-8") as f:
        f.write("event_seq,pts,composition_ns,timebase_num,timebase_den\n")
        for i in range(81):
            f.write(f"{i+2},{i},{1+i*5},1,200000000\n")
    dump(logger / "metadata.json", {"session_id": sid, "video_path": "s.mkv", "schema_version": 1,
                                    "control_type": "keyboard_mouse", "complete": True, "clean_stop": True,
                                    "status": "complete", "queue_dropped_events": 0, "raw_input_errors": 0,
                                    "frames_without_composition_timestamp": 0, "writer_failed": False,
                                    "start_ns": 0, "end_ns": 410, "input_events": 0, "video_packets": 81,
                                    "events_attempted": 83, "fps_num": 200000000, "fps_den": 1})
    output = tmp_path / "out"
    kwargs = dict(logger_root=logger.parent, table_root=tables.parent, output=output,
                  registry_path=reg, denylist_path=deny)
    manifest = idle.export(**kwargs)
    s = manifest["sessions"][sid]["statistics"]
    assert s["weighted_rows"] == 30
    assert s["row_head_mass"]["held"] == {"U": 30, "C": 30, "E": 3.0}
    assert s["total_effective_row_weight"] == 3.0
    weights = idle.load_weights(table, output / f"{sid}.idle.jsonl", manifest_path=output / "manifest.json",
                                manifest_sha256=idle.sha256(output / "manifest.json"),
                                registry_path=reg, denylist_path=deny)
    assert list(weights) == [.1] * 30
    with pytest.raises(FileExistsError):
        idle.export(**kwargs)
