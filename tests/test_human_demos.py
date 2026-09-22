"""Synthetic admission/causality tests; never discover or open the corpus."""
import copy
import csv
from dataclasses import FrozenInstanceError, asdict
from fractions import Fraction
import json
import os
from pathlib import Path

import pytest

from agent import human_demos as hd
from scripts.import_human_demo import main


BASE = 10**17 + 123  # Above IEEE754's exact integer range.
STEP = 10_000_000
OPTIONS = dict(history_ns=2*STEP, frame_step_ns=STEP, bin_ns=STEP, bins=2, stride_ns=STEP)


def key(t, down=True, vk=87, scan=17, flags=None, device=12):
    return dict(type="key", t_ns=BASE+t*STEP, device=device, vk=vk, scan=scan,
                flags=(0 if down else 1) if flags is None else flags, down=down)


def mouse(t, dx=7, relative=True, down=(), up=()):
    flags = sum(1 << (2*b-2) for b in down) | sum(1 << (2*b-1) for b in up)
    return dict(type="mouse", t_ns=BASE+t*STEP, device=22, dx=dx, dy=-3,
                motion_flags=0 if relative else 1, button_flags=flags, wheel_data=0,
                relative=relative, buttons_down=list(down), buttons_up=list(up),
                wheel_vertical=0, wheel_horizontal=0)


def event(kind, t, **fields):
    return dict(type=kind, t_ns=BASE+t*STEP, **fields)


def payload(tmp_path, extra=()):
    video = tmp_path / "original.mkv"
    video.write_bytes(b"synthetic media; probe is explicitly mocked")
    events = [event("raw_input_status", 0, ok=True), event("focus", 0, active=True, held_vk=[]),
              key(3), mouse(4, down=(1,)), key(6, False), mouse(7, up=(1,)), *extra]
    events.sort(key=lambda e: e["t_ns"])
    for i, row in enumerate(events):
        row["seq"] = i
    packets = []
    for i in range(21):
        row = dict.fromkeys(hd.FRAME_COLUMNS, 0)
        row.update(event_seq=len(events)+i, packet_index=i, pts=i*10, dts=i*10,
                   timebase_num=1, timebase_den=1000, composition_ns=BASE+i*STEP)
        packets.append(row)
    meta = dict(schema_version=1, control_type="keyboard_mouse", status="complete", complete=True,
                clean_stop=True, writer_failed=False, queue_dropped_events=0, raw_input_errors=0,
                first_queue_drop_ns=0, last_queue_drop_ns=0, frames_without_composition_timestamp=0,
                events_attempted=len(events)+len(packets), video_packets=len(packets), input_events=4,
                start_ns=BASE, end_ns=BASE+21*STEP, width=640, height=360, fps_num=100, fps_den=1,
                capture_latency_calibrated=False, session_id="s1", video_path=str(video.resolve()),
                target_executable="Marvel-Win64-Shipping.exe")
    meta["input_events"] = sum(e["type"] in ("key", "mouse") for e in events)
    review = dict(schema_version=1, session_id="s1", reviewer="human-reviewer", reviewed_at="2026-09-21",
        device_scope={"kind": "single_keyboard_mouse", "source": "synthetic fixture uses one of each"},
        pts_anchor={"kind": "independent_muxer_offset", "offset_num": 21, "offset_den": 1000,
                    "source": "synthetic fixture constructs file PTS from this exact offset"},
        provenance={"hero": "Spider-Man", **{name: {"value": "explicit-setting", "source": "review note"}
                    for name in ("settings", "bindings", "game_patch", "cooldown_regime")}},
        alignment={"kind": "assumption", "statement": "CTS is the labeling clock; latency unknown", "source": "review note"},
        segments=[dict(segment_id="gameplay-1", start_ns=BASE, end_ns=BASE+21*STEP,
                       reviewed_gameplay=True, evidence="inspected source interval",
                       imitation_suitability="accepted", suitability_reason="synthetic accepted fixture")])
    return dict(metadata=meta, review=review, events=events, packets=packets,
                decoded=dict(timebase_num=1, timebase_den=1000, pts=[21+i*10 for i in range(21)],
                             width=640, height=360))


def build(data):
    meta = data["metadata"]
    return hd._build(data, hd.Placement(meta["session_id"], "group-1", "train", meta["video_path"]), "a"*64)


def write_session(tmp_path, data, split="train"):
    session = tmp_path / "session"
    session.mkdir(exist_ok=True)
    (session / "metadata.json").write_text(json.dumps(data["metadata"]))
    (session / "inputs.jsonl").write_text("".join(json.dumps(e)+"\n" for e in data["events"]))
    with (session / "frames.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=hd.FRAME_COLUMNS)
        writer.writeheader()
        writer.writerows(data["packets"])
    review = tmp_path / "review.json"
    review.write_text(json.dumps(data["review"]))
    registry = tmp_path / "splits.json"
    registry.write_text(json.dumps(dict(schema_version=1, sessions=[dict(session_id=data["metadata"]["session_id"], session_group="group-1",
        split=split, video_path=data["metadata"]["video_path"])])))
    return session, review, registry


def test_immutable_exact_ns_and_separate_future_bins(tmp_path):
    dataset = build(payload(tmp_path))
    sample = next(dataset.samples(**OPTIONS))
    assert sample.anchor_ns == BASE+2*STEP
    assert sample.frames[0].composition_ns == BASE
    assert all(f.composition_ns <= sample.anchor_ns for f in sample.frames)
    assert all(e.t_ns <= sample.anchor_ns for e in sample.past_events)
    assert [e.type for e in sample.future[0].events] == ["key"]
    assert [e.type for e in sample.future[1].events] == ["mouse"]
    assert sample.future[0].held_end.keys == (hd.PhysicalKey(12, 87, 17, 0),)
    assert sample.future[1].held_end.mouse_buttons == (1,)
    assert sample.future[1].mouse_dx == 7
    assert "future" not in sample.observation()
    with pytest.raises(FrozenInstanceError):
        sample.anchor_ns = 0
    sample.future[0].events[0].payload["scan"] = 99
    assert sample.future[0].events[0].payload["scan"] == 17


def test_b_frame_tail_is_callback_suffix_not_pts_suffix():
    # Two discarded callbacks interleave in PTS among retained packets.
    order = [0, 3, 1, 2, 6, 4, 5]
    packets = [dict(packet_index=i, track=0, pts=p, timebase_num=1, timebase_den=120,
                    composition_ns=BASE+p*8_333_333) for i, p in enumerate(order)]
    retained = sorted(order[:5])
    pts = [round(Fraction(p*1000, 120)+21) for p in retained]
    frames, audit = hd.match_frames(packets, dict(pts=pts, timebase_num=1, timebase_den=1000), "movie.mkv",
        pts_anchor=dict(kind="independent_muxer_offset", offset_num=21, offset_den=1000, source="fixture construction"))
    assert [f.packet_index for f in frames] == [0, 2, 3, 1, 4]
    assert audit["unwritten_tail_packets"] == 2
    assert abs(Fraction(audit["muxer_offset_num"], audit["muxer_offset_den"])-Fraction(21, 1000)) < Fraction(1, 1000)


def test_b_frame_interior_loss_rejected(tmp_path):
    data = payload(tmp_path)
    del data["decoded"]["pts"][4]
    with pytest.raises(hd.DemoError, match="interior"):
        build(data)


@pytest.mark.parametrize("mutation,match", [
    (lambda d: d["events"].pop(3), "sequence"),
    (lambda d: d["packets"].pop(3), "sequence"),
    (lambda d: d["metadata"].update(events_attempted=10000), "sequence"),
    (lambda d: d["metadata"].update(queue_dropped_events=1), "loss"),
    (lambda d: d["metadata"].update(input_events=99), "count"),
    (lambda d: d["metadata"].update(video_packets=99), "count"),
    (lambda d: d["metadata"].update(complete=False), "incomplete"),
    (lambda d: d["metadata"].update(clean_stop=False), "incomplete"),
    (lambda d: d["metadata"].update(writer_failed=True), "writer"),
    (lambda d: d["metadata"].update(raw_input_errors=1), "loss"),
    (lambda d: d["packets"][3].update(composition_ns=0), "CTS"),
    (lambda d: d["metadata"].update(frames_without_composition_timestamp=1), "CTS"),
    (lambda d: d["events"][3].pop("relative"), "relative"),
    (lambda d: d["events"][3].update(motion_flags=1), "mode"),
    (lambda d: d["events"][3].update(button_flags=0), "flags"),
    (lambda d: d["events"][2].update(t_ns=float(BASE)), "integer"),
    (lambda d: d["review"]["segments"][0].update(reviewed_gameplay=False), "reviewed"),
    (lambda d: d["review"]["provenance"].pop("bindings"), "provenance"),
])
def test_detectable_loss_and_invalid_contract_refused(tmp_path, mutation, match):
    data = payload(tmp_path)
    mutation(data)
    with pytest.raises(hd.DemoError, match=match):
        build(data)


def test_focus_snapshot_is_not_a_physical_press(tmp_path):
    data = payload(tmp_path)
    data["events"][1]["held_vk"] = [87, 2]
    sample = next(build(data).samples(**OPTIONS))
    assert sample.state.observed
    assert sample.state.keys == ()
    assert sample.state.unknown_physical_vk == (87,)
    assert not sample.state.physical_keys_known
    assert sample.state.mouse_buttons == (2,)
    assert not any(e.type == "key" for e in sample.past_events)
    assert sample.future[0].held_end.physical_keys_known


def test_extended_keys_devices_repeats_and_release(tmp_path):
    data = payload(tmp_path, [key(3, vk=17, scan=29, flags=2), key(4, vk=17, scan=29, flags=2),
        key(5, False, vk=163, scan=29, flags=3)])
    sample = list(build(data).samples(**OPTIONS))[3]  # anchor 5
    assert hd.PhysicalKey(12, 17, 29, 2) not in sample.state.keys
    assert not any(k.scan == 29 for k in sample.state.keys)
    assert len([e for e in sample.past_events if e.type == "key" and e.payload["device"] == 12]) == 4


def test_absolute_mouse_is_unknown_relative_motion_not_neutral(tmp_path):
    data = payload(tmp_path, [mouse(3, dx=64000, relative=False)])
    sample = next(build(data).samples(**OPTIONS))
    assert sample.future[0].mouse_dx is None
    assert sample.future[0].mouse_dy is None
    assert not sample.future[0].relative_motion_known
    assert sample.future[0].events[-1].payload["dx"] == 64000
    assert sample.future[1].relative_motion_known


@pytest.mark.parametrize("boundary", ["focus", "pause"])
def test_no_samples_cross_focus_pause_or_resume(tmp_path, boundary):
    middle = [event("focus", 8, active=False, held_vk=[])] if boundary == "focus" else [
        event("pause", 8, paused=True), event("pause", 10, paused=False)]
    data = payload(tmp_path, [*middle, event("focus", 11, active=True, held_vk=[87])])
    samples = list(build(data).samples(**OPTIONS))
    assert samples
    for sample in samples:
        start, end = sample.frames[0].composition_ns, sample.future[-1].end_ns
        assert end < BASE+8*STEP or start >= BASE+11*STEP
    resumed = next(s for s in samples if s.anchor_ns >= BASE+13*STEP)
    assert resumed.state.unknown_physical_vk == (87,)


def test_gap_rejected_even_with_zero_metadata_count(tmp_path):
    data = payload(tmp_path, [event("gap", 9, reason="device_change")])
    with pytest.raises(hd.DemoError, match="gap"):
        build(data)


def test_observation_prefix_causality_under_future_rewrite(tmp_path):
    data = payload(tmp_path)
    before = next(build(data).samples(**OPTIONS))
    changed = copy.deepcopy(data)
    changed["events"][2].update(vk=65, scan=30)
    changed["events"][3].update(dx=99999)
    after = next(build(changed).samples(**OPTIONS))
    assert before.observation() == after.observation()
    assert before.future != after.future
    prefix = [e for e in build(data).events if e.t_ns <= before.anchor_ns]
    _, states, _ = hd._timeline(prefix, BASE, before.anchor_ns+1)
    assert states[-1] == before.state


def test_frame_sampling_floors_instead_of_using_future_nearest(tmp_path):
    dataset = build(payload(tmp_path))
    options = {**OPTIONS, "history_ns": STEP+STEP//2, "frame_step_ns": STEP}
    sample = next(dataset.samples(**options))
    assert sample.anchor_ns == BASE+STEP+STEP//2
    assert sample.frames[-1].composition_ns == BASE+STEP


def test_alignment_gate_preserves_uncalibrated_metadata(tmp_path):
    data = payload(tmp_path)
    data["review"]["alignment"] = {"kind": "uncalibrated"}
    dataset = build(data)
    with pytest.raises(hd.DemoError, match="alignment"):
        list(dataset.samples(**OPTIONS))
    assert list(dataset.samples(**OPTIONS, for_training=False))
    data["review"]["alignment"] = dict(kind="measured_bound", min_latency_ns=0,
        max_latency_ns=20_000_000, source="external measured end-to-end bound")
    dataset = build(data)
    assert list(dataset.samples(**OPTIONS))
    assert json.loads(dataset.metadata_json)["capture_latency_calibrated"] is False


@pytest.mark.parametrize("change,match", [
    ({"session_id": "s2", "split": "val", "video_path": "other.mkv"}, "group split leakage"),
    ({"session_id": "s1", "split": "train"}, "duplicate session"),
    ({"session_id": "s2", "session_group": "other", "split": "val"}, "media split leakage"),
])
def test_session_split_leakage(tmp_path, change, match):
    data = payload(tmp_path)
    _, _, registry = write_session(tmp_path, data)
    doc = json.loads(registry.read_text())
    doc["sessions"].append({**doc["sessions"][0], **change})
    registry.write_text(json.dumps(doc))
    with pytest.raises(hd.DemoError, match=match):
        hd.read_splits(registry)


def test_sealed_refusal_before_session_or_artifact_payload_access(tmp_path):
    data = payload(tmp_path)
    _, review, registry = write_session(tmp_path, data, split="test")
    with pytest.raises(hd.SealedError):
        hd.import_session(tmp_path / "DOES_NOT_EXIST", review=review, splits=registry, output=tmp_path/"out")
    artifact = tmp_path / "sealed.jsonl"
    artifact.write_text(json.dumps(dict(format=hd.FORMAT, session_id="s1", split="test", sealed=True)) +
                        "\nTHIS PAYLOAD MUST NEVER BE PARSED\n")
    with pytest.raises(hd.SealedError):
        hd.load_dataset(artifact, splits=registry)


def test_roundtrip_import_export_and_cli(tmp_path, monkeypatch, capsys):
    data = payload(tmp_path)
    session, review, registry = write_session(tmp_path, data)
    monkeypatch.setattr(hd, "probe_video", lambda *a, **k: data["decoded"])
    artifact = tmp_path / "imported.jsonl"
    assert main(["import", "--session", str(session), "--review", str(review), "--splits", str(registry),
                 "--output", str(artifact)]) == 0
    dataset = hd.load_dataset(artifact, splits=registry)
    samples_path = tmp_path / "samples.jsonl"
    count = hd.export_dataset(dataset, samples_path, **OPTIONS)
    records = [json.loads(line) for line in samples_path.read_text().splitlines()]
    assert count == len(records)-1 > 0
    assert records[1]["anchor_ns"] == BASE+2*STEP
    assert records[1]["future"][0]["events"][0]["t_ns"] == BASE+3*STEP
    assert records[0]["review"]["alignment"]["kind"] == "assumption"
    assert records[0]["audit"]["capture_latency_calibrated"] is False
    assert hd.load_datasets([artifact], splits=registry) == (dataset,)
    with pytest.raises(hd.DemoError, match="duplicate imported"):
        hd.load_datasets([artifact, artifact], splits=registry)
    assert main(["export", "--dataset", str(artifact), "--splits", str(registry), "--output", str(tmp_path/"cli.jsonl"),
        "--history-ns", str(2*STEP), "--frame-step-ns", str(STEP), "--bin-ns", str(STEP), "--bins", "2",
        "--stride-ns", str(STEP)]) == 0
    assert "samples" in capsys.readouterr().out


def test_partial_jsonl_and_existing_output_refused(tmp_path, monkeypatch):
    data = payload(tmp_path)
    session, review, registry = write_session(tmp_path, data)
    monkeypatch.setattr(hd, "probe_video", lambda *a, **k: data["decoded"])
    output = tmp_path / "out.jsonl"
    output.write_text("keep me")
    with pytest.raises(FileExistsError):
        hd.import_session(session, review=review, splits=registry, output=output)
    assert output.read_text() == "keep me"
    with (session / "inputs.jsonl").open("a") as handle:
        handle.write('{"seq":')
    with pytest.raises(hd.DemoError, match="partial"):
        hd.import_session(session, review=review, splits=registry, output=tmp_path/"new.jsonl")


def test_repeated_cts_retained_and_capture_gap_not_bridged(tmp_path):
    data = payload(tmp_path)
    data["packets"][1]["composition_ns"] = BASE
    dataset = build(data)
    assert len(dataset.frames) == 21
    assert dataset.frames[0].composition_ns == dataset.frames[1].composition_ns
    # Skip three composition slots without dropping output PTS; this is a capture gap.
    for row in data["packets"][8:]:
        row["composition_ns"] += 3*STEP
    data["metadata"]["end_ns"] += 3*STEP
    data["review"]["segments"][0]["end_ns"] += 3*STEP
    for sample in build(data).samples(**OPTIONS):
        assert sample.future[-1].end_ns <= BASE+7*STEP or sample.frames[0].composition_ns >= BASE+11*STEP


def test_decode_command_uses_integer_pts_and_rejects_missing_pts(monkeypatch):
    calls = []
    class Run:
        stderr = ""
        stdout = json.dumps({"streams": [dict(time_base="1/1000", width=640, height=360)],
                             "frames": [dict(pts=21), dict(pts=31)]})
    def run(command, **kwargs):
        calls.append(command)
        return Run()
    monkeypatch.setattr(hd.subprocess, "run", run)
    assert hd.probe_video("movie.mkv")["pts"] == [21, 31]
    assert "stream=time_base,width,height:frame=pts" in calls[0]
    Run.stdout = json.dumps({"streams": [dict(time_base="1/1000", width=640, height=360)], "frames": [{}]})
    with pytest.raises(hd.DemoError, match="PTS"):
        hd.probe_video("movie.mkv")


def test_wheel_and_simultaneous_mouse_edges_are_preserved(tmp_path):
    action = mouse(3, down=(1, 2), up=(3,))
    action.update(button_flags=action["button_flags"] | 0x400, wheel_data=-120, wheel_vertical=-120)
    sample = next(build(payload(tmp_path, [action])).samples(**OPTIONS))
    assert sample.future[0].wheel_vertical == -120
    assert sample.future[0].held_end.mouse_buttons == (1, 2)
    assert sample.future[0].events[-1].payload["buttons_up"] == [3]


def test_event_at_anchor_is_past_and_shared_bin_edge_is_not_duplicated(tmp_path):
    dataset = build(payload(tmp_path, [mouse(2, dx=100)]))
    sample = next(dataset.samples(**OPTIONS))
    assert sample.past_events[-1].t_ns == sample.anchor_ns
    assert sample.past_events[-1].payload["dx"] == 100
    assert sample.future[0].mouse_dx == 0
    seqs = [e.seq for b in sample.future for e in b.events]
    assert len(seqs) == len(set(seqs))


def test_callback_queue_order_does_not_replace_timestamp_order(tmp_path):
    data = payload(tmp_path)
    # A later queued packet can carry an earlier receipt timestamp.
    data["events"][2]["t_ns"], data["events"][3]["t_ns"] = data["events"][3]["t_ns"], data["events"][2]["t_ns"]
    sample = next(build(data).samples(**OPTIONS))
    assert sample.future[0].events[0].type == "mouse"
    assert sample.future[1].events[0].type == "key"


def test_stale_split_registry_and_changed_media_refused(tmp_path, monkeypatch):
    data = payload(tmp_path)
    session, review, registry = write_session(tmp_path, data)
    monkeypatch.setattr(hd, "probe_video", lambda *a, **k: data["decoded"])
    artifact = tmp_path / "out.jsonl"
    hd.import_session(session, review=review, splits=registry, output=artifact)
    doc = json.loads(registry.read_text())
    doc["sessions"][0]["split"] = "val"
    registry.write_text(json.dumps(doc))
    with pytest.raises(hd.DemoError, match="mismatch: split"):
        hd.load_dataset(artifact, splits=registry)
    doc["sessions"][0]["split"] = "train"
    registry.write_text(json.dumps(doc))
    Path(data["metadata"]["video_path"]).write_bytes(b"changed or remuxed video")
    with pytest.raises(hd.DemoError, match="fingerprint"):
        hd.load_dataset(artifact, splits=registry)


def test_test_unseal_is_explicit_and_still_not_for_training(tmp_path, monkeypatch):
    data = payload(tmp_path)
    session, review, registry = write_session(tmp_path, data, split="test")
    monkeypatch.setattr(hd, "probe_video", lambda *a, **k: data["decoded"])
    artifact = tmp_path / "out.jsonl"
    hd.import_session(session, review=review, splits=registry, output=artifact, unseal=True)
    with pytest.raises(hd.SealedError):
        hd.load_dataset(artifact, splits=registry)
    dataset = hd.load_dataset(artifact, splits=registry, unseal=True)
    with pytest.raises(hd.DemoError, match="evaluation-only"):
        list(dataset.samples(**OPTIONS))
    assert list(dataset.samples(**OPTIONS, for_training=False))


def test_no_review_no_samples_and_failed_export_creates_nothing(tmp_path):
    data = payload(tmp_path)
    data["review"]["segments"] = []
    with pytest.raises(hd.DemoError, match="reviewed gameplay"):
        build(data)
    data = payload(tmp_path)
    data["review"]["alignment"] = {"kind": "uncalibrated"}
    with pytest.raises(hd.DemoError, match="alignment"):
        hd.export_dataset(build(data), tmp_path/"out.jsonl", **OPTIONS)
    assert not (tmp_path/"out.jsonl").exists()


@pytest.mark.parametrize("mixed_patch", [False, True])
def test_combined_loader_rejects_copied_media_leakage_and_mixed_patch(tmp_path, monkeypatch, mixed_patch):
    first_dir, second_dir = tmp_path/"one", tmp_path/"two"
    first_dir.mkdir()
    second_dir.mkdir()
    first, second = payload(first_dir), payload(second_dir)
    second["metadata"]["session_id"] = second["review"]["session_id"] = "s2"
    if mixed_patch:
        Path(second["metadata"]["video_path"]).write_bytes(b"different original media")
        second["review"]["provenance"]["game_patch"]["value"] = "another-patch"
    a_session, a_review, registry = write_session(first_dir, first)
    b_session, b_review, _ = write_session(second_dir, second)
    doc = json.loads(registry.read_text())
    doc["sessions"].append(dict(session_id="s2", session_group="group-2", split="val",
                                video_path=second["metadata"]["video_path"]))
    registry.write_text(json.dumps(doc))
    monkeypatch.setattr(hd, "probe_video", lambda *a, **k: first["decoded"])
    a_artifact, b_artifact = first_dir/"out.jsonl", second_dir/"out.jsonl"
    hd.import_session(a_session, review=a_review, splits=registry, output=a_artifact)
    hd.import_session(b_session, review=b_review, splits=registry, output=b_artifact)
    match = "mixed patch" if mixed_patch else "identical media"
    with pytest.raises(hd.DemoError, match=match):
        hd.load_datasets([a_artifact, b_artifact], splits=registry)


def test_artifact_body_checksum_rejects_tampering(tmp_path, monkeypatch):
    data = payload(tmp_path)
    session, review, registry = write_session(tmp_path, data)
    monkeypatch.setattr(hd, "probe_video", lambda *a, **k: data["decoded"])
    artifact = tmp_path/"out.jsonl"
    hd.import_session(session, review=review, splits=registry, output=artifact)
    text = artifact.read_text().replace('"dx":7', '"dx":8')
    artifact.write_text(text)
    with pytest.raises(hd.DemoError, match="checksum"):
        hd.load_dataset(artifact, splits=registry)


def test_invalid_late_focus_and_inputs_during_pause_rejected(tmp_path):
    data = payload(tmp_path, [event("pause", 2, paused=True)])
    with pytest.raises(hd.DemoError, match="outside focused"):
        build(data)
    data = payload(tmp_path, [event("pause", 2, paused=True), event("focus", 2, active=True, held_vk=[])])
    with pytest.raises(hd.DemoError, match="during pause"):
        build(data)


def test_review_boundaries_and_short_history_never_padded(tmp_path):
    data = payload(tmp_path)
    data["review"]["segments"] = [
        dict(segment_id="a", start_ns=BASE, end_ns=BASE+7*STEP, reviewed_gameplay=True, evidence="review",
             imitation_suitability="accepted", suitability_reason="clear action evidence"),
        dict(segment_id="b", start_ns=BASE+10*STEP, end_ns=BASE+20*STEP, reviewed_gameplay=True, evidence="review",
             imitation_suitability="accepted", suitability_reason="clear action evidence")]
    samples = list(build(data).samples(**OPTIONS))
    assert {s.segment_id for s in samples} == {"a", "b"}
    for sample in samples:
        assert sample.future[-1].end_ns < BASE+7*STEP or sample.frames[0].composition_ns >= BASE+10*STEP
    assert not list(build(data).samples(**{**OPTIONS, "history_ns": 100*STEP}))


@pytest.mark.skipif(not os.environ.get("RIVALS_HUMAN_TIMING_FIXTURE"), reason="explicit blank OBS timing fixture only")
def test_authorized_blank_obs_timing_fixture():
    folder = Path(os.environ["RIVALS_HUMAN_TIMING_FIXTURE"])
    meta = json.loads((folder/"metadata.json").read_text())
    assert meta["input_events"] == 0  # Timing evidence only; no training admission.
    assert meta["target_executable"] == "NonexistentCaptureTest.exe"
    with (folder/"frames.csv").open(newline="") as handle:
        packets = [{k: int(v) for k, v in row.items()} for row in csv.DictReader(handle)]
    frames, audit = hd.match_frames(packets, hd.probe_video(meta["video_path"]), meta["video_path"], inspection_only=True)
    assert len(packets) == 714
    assert len(frames) == 711
    assert audit["unwritten_tail_packets"] == 3
    assert Fraction(audit["muxer_offset_num"], audit["muxer_offset_den"]) == Fraction(21, 1000)
    assert Fraction(audit["max_residual_num"], audit["max_residual_den"]) == Fraction(1, 3000)
    assert audit["pts_alignment_verified"] is False


def test_missing_first_file_frame_requires_independent_offset(tmp_path):
    data = payload(tmp_path)
    data["decoded"]["pts"] = data["decoded"]["pts"][1:]
    with pytest.raises(hd.DemoError, match="leading frame loss"):
        build(data)
    # A freely fitted offset would falsely explain this as 31 ms plus one tail.
    _, audit = hd.match_frames(data["packets"], data["decoded"], "movie.mkv", inspection_only=True)
    assert Fraction(audit["muxer_offset_num"], audit["muxer_offset_den"]) == Fraction(31, 1000)
    assert audit["pts_alignment_verified"] is False
    with pytest.raises(hd.DemoError, match="anchor required"):
        hd.match_frames(data["packets"], data["decoded"], "movie.mkv")


def test_unanchored_review_cannot_admit_even_with_latency_assumption(tmp_path):
    data = payload(tmp_path)
    del data["review"]["pts_anchor"]
    with pytest.raises(hd.DemoError, match="anchor required"):
        build(data)


@pytest.mark.parametrize("held,remaining", [([16, 160], ()), ([16, 160, 161], (161,)), ([16], (161,))])
def test_generic_and_sided_shift_snapshots_preserve_opposite_uncertainty(tmp_path, held, remaining):
    data = payload(tmp_path, [key(3, vk=16, scan=42), key(4, False, vk=16, scan=42)])
    data["events"][1]["held_vk"] = held
    sample = next(build(data).samples(**OPTIONS))
    assert sample.future[-1].held_end.unknown_physical_vk == remaining
    assert not any(k.scan == 42 for k in sample.future[-1].held_end.keys)


@pytest.mark.parametrize("generic,left,right,scan", [(17, 162, 163, 29), (18, 164, 165, 56)])
def test_control_alt_snapshot_aliases_resolve_only_observed_side(tmp_path, generic, left, right, scan):
    data = payload(tmp_path, [key(3, vk=generic, scan=scan, flags=2),
                              key(4, False, vk=right, scan=scan, flags=3)])
    data["events"][1]["held_vk"] = [generic, left, right]
    sample = next(build(data).samples(**OPTIONS))
    assert sample.future[-1].held_end.unknown_physical_vk == (left,)
    assert not any(k.scan == scan for k in sample.future[-1].held_end.keys)


@pytest.mark.parametrize("kind", ["key", "mouse"])
def test_multiple_devices_are_rejected_before_aggregate_holds(tmp_path, kind):
    if kind == "mouse":
        extra = [mouse(3, down=(1,)), {**mouse(4, down=(1,)), "device": 23}, mouse(5, up=(1,))]
    else:
        extra = [key(3), key(4, device=13), key(5, False)]
    with pytest.raises(hd.DemoError, match=f"multiple {kind} devices"):
        build(payload(tmp_path, extra))


def test_keys_without_scan_codes_keep_distinct_vk_identity(tmp_path):
    data = payload(tmp_path, [key(3, vk=175, scan=0), key(4, vk=174, scan=0),
                              key(5, False, vk=175, scan=0)])
    dataset = build(data)
    key_states = [state for event, state in zip(dataset.events, dataset.states)
                  if event.type == "key" and event.payload["scan"] == 0]
    assert {k.vk for k in key_states[-2].keys if k.scan == 0} == {174, 175}
    assert {k.vk for k in key_states[-1].keys if k.scan == 0} == {174}


def test_single_device_review_attestation_required(tmp_path):
    data = payload(tmp_path)
    del data["review"]["device_scope"]
    with pytest.raises(hd.DemoError, match="single-device"):
        build(data)


def test_zero_effect_mouse_packets_do_not_create_second_control_device(tmp_path):
    data = payload(tmp_path)
    ancillary = mouse(3, dx=0, relative=True)
    ancillary["dy"] = 0
    ancillary["device"] = 999
    data["events"].append(ancillary)
    data["events"].sort(key=lambda row: row["t_ns"])
    for index, row in enumerate(data["events"]):
        row["seq"] = index
    for index, row in enumerate(data["packets"], start=len(data["events"])):
        row["event_seq"] = index
    data["metadata"]["events_attempted"] = len(data["events"]) + len(data["packets"])
    data["metadata"]["input_events"] = sum(e["type"] in ("key", "mouse") for e in data["events"])
    dataset = build(data)
    assert any(e.type == "mouse" and e.payload["device"] == 999 for e in dataset.events)
    assert not any(e.type == "mouse" and e.payload["device"] == 999 and hd._control_affecting(e)
                   for e in dataset.events)


def test_control_affecting_second_mouse_device_is_rejected(tmp_path):
    data = payload(tmp_path, [mouse(3, dx=2, relative=True)])
    data["events"][-1]["device"] = 999
    with pytest.raises(hd.DemoError, match="multiple mouse devices"):
        build(data)


@pytest.mark.parametrize("suitability,training", [("accepted", True), ("rejected", False), ("unresolved", False)])
def test_imitation_suitability_gates_training_but_preserves_inspection(tmp_path, suitability, training):
    data = payload(tmp_path)
    segment = data["review"]["segments"][0]
    segment["imitation_suitability"] = suitability
    segment["suitability_reason"] = f"explicit {suitability} reason"
    dataset = build(data)
    assert bool(list(dataset.samples(**OPTIONS))) is training
    assert list(dataset.samples(**OPTIONS, for_training=False))


def test_imitation_suitability_missing_or_reasonless_is_rejected(tmp_path):
    data = payload(tmp_path)
    data["review"]["segments"][0].pop("imitation_suitability")
    with pytest.raises(hd.DemoError, match="imitation_suitability"):
        build(data)
    data = payload(tmp_path)
    data["review"]["segments"][0]["suitability_reason"] = ""
    with pytest.raises(hd.DemoError, match="suitability reason"):
        build(data)
