"""Synthetic-only execution tests. Never open the demonstration corpus."""
import csv
from dataclasses import asdict, replace
import json
from pathlib import Path
import shutil
import subprocess

import pytest

torch = pytest.importorskip("torch")

from agent import human_demos as hd
from policy import execution as ex


KEY = hd.PhysicalKey(12, 87, 17, 0)
IDLE = hd.HeldState(observed=True)
HELD = hd.HeldState(keys=(KEY,), observed=True)


def event(t, down, vk=87, scan=17, device=12):
    row = dict(t_ns=t, seq=t, type="key", device=device, vk=vk, scan=scan,
               flags=0 if down else 1, down=down)
    return hd.InputEvent(t, t, "key", json.dumps(row))


def sample(split="train", future=None, state=IDLE):
    future = future or (hd.ActionBin(20, 40, (event(25, True), event(30, False)),
                                      IDLE, IDLE, 7, -3, 120, 0),)
    return hd.Sample("s1" if split == "train" else "s2", "g1" if split == "train" else "g2",
        split, "segment", 20, (hd.FrameRef("synthetic", 0, 0, 1, 50, 0, 0),), (), state, future)


def test_taps_repeats_multi_edges_and_physical_device_normalization():
    s = sample()
    spec = ex.fit_spec([s], 1, 20)
    assert spec.controls[0] == "key:17:0"
    y, mask, motion, mm, unseen, unsupported = ex.targets(s.future, spec)
    assert y[0, 0].tolist() == [0, 1, 1]
    assert mask[0, 0].tolist() == [1, 1, 1]
    assert motion[0].tolist() == [7, -3, 120, 0]
    assert not unseen and not unsupported
    new_device = replace(s.future[0], events=(event(25, True, device=99), event(30, False, device=99)))
    assert torch.equal(ex.targets((new_device,), spec)[0], y)
    repeated = replace(s.future[0], events=(event(24, True), event(25, True), event(30, False)))
    assert torch.equal(ex.targets((repeated,), spec)[0], y)
    multi = replace(s.future[0], events=(event(24, True), event(25, False), event(30, True), event(31, False)))
    output = ex.targets((multi,), spec)
    assert output[1][0, 0].tolist() == [1, 0, 0]
    assert output[5] == [(0, "key:17:0")]


def test_snapshot_unknown_absolute_motion_and_modifier_alias_masks():
    s = sample()
    spec = ex.fit_spec([s], 1, 20)
    unknown = hd.HeldState(unknown_physical_vk=(87,), observed=True)
    action = replace(s.future[0], held_start=unknown, held_end=unknown, mouse_dx=None, mouse_dy=None)
    y, mask, _, mm, *_ = ex.targets((action,), spec)
    assert mask[0, 0].tolist() == [0, 0, 0]
    assert mm[0].tolist() == [0, 0, 1, 1]
    assert ex.observation_input(replace(s, state=unknown).observation(), spec)[len(spec.controls)] == 0
    shift = replace(s.future[0], events=(event(25, True, vk=16, scan=42), event(30, False, vk=160, scan=42)))
    shift_spec = ex.fit_spec([replace(s, future=(shift,))], 1, 20)
    assert ex.targets((shift,), shift_spec)[0][0, 0].tolist() == [0, 1, 1]
    shift_unknown = hd.HeldState(unknown_physical_vk=(160,), observed=True)
    assert ex.encode_state(shift_unknown, shift_spec)[1][0] == 0


def test_future_rewrite_cannot_change_inputs_or_training_vocabulary():
    s = sample()
    spec = ex.fit_spec([s], 1, 20)
    altered = replace(s, future=(replace(s.future[0], mouse_dx=9999,
        events=(event(25, True, vk=65, scan=30), event(30, False, vk=65, scan=30))),))
    assert ex.observation_input(s.observation(), spec) == ex.observation_input(altered.observation(), spec)
    assert ex.targets(altered.future, spec)[4] == {"key:30:0"}
    assert "key:30:0" not in spec.controls
    with pytest.raises(hd.DemoError, match="future labels"):
        ex.observation_input(s.to_dict(), spec)
    with pytest.raises(hd.DemoError, match="train"):
        ex.fit_spec([replace(s, split="val")], 1, 20)


def test_masked_targets_have_zero_gradient():
    spec = ex.fit_spec([sample()], 1, 20)
    unknown = hd.HeldState(unknown_physical_vk=(87,), observed=True)
    action = replace(sample().future[0], held_start=unknown, held_end=unknown, mouse_dx=None, mouse_dy=None)
    labels = tuple(t[None] for t in ex.targets((action,), spec)[:4])
    logits = torch.zeros_like(labels[0], requires_grad=True)
    motion = torch.zeros_like(labels[2], requires_grad=True)
    stats = dict(motion_mean=torch.zeros(4), motion_scale=torch.ones(4))
    loss = ex.masked_loss(logits, motion, labels, stats)
    loss.backward()
    assert logits.grad[0, 0, 0].abs().sum() == 0
    assert motion.grad[0, 0, :2].abs().sum() == 0
    assert logits.grad[0, 0, 1:].abs().sum() > 0


def test_tiny_cpu_fit_exact_reload_and_train_only_statistics(tmp_path):
    torch.set_num_threads(1)
    torch.manual_seed(0)
    s = sample()
    spec = ex.fit_spec([s], 1, 20)
    frames = {("synthetic", 0): torch.full((3, 16, 16), 120, dtype=torch.uint8)}
    train = ex.Examples([s] * 4, spec, frames)
    val = ex.Examples([replace(s, split="val", session_id="s2")], spec, frames)
    stats = ex.fit_statistics(train)
    with pytest.raises(hd.DemoError, match="train only"):
        ex.fit_statistics(val)
    model = ex.make_model(spec, hidden=8)
    losses = ex.train_model(model, train, stats, epochs=12, batch_size=4, lr=.02, device="cpu")
    assert losses[-1] < losses[0]
    config = dict(encoder="small", hidden=8)
    checkpoint = tmp_path / "checkpoint.pt"
    model.eval()
    rgb, prev, _ = val.batch([0])
    before = model(rgb, prev)
    ex.save_checkpoint(checkpoint, model, spec, stats, config, {})
    restored, restored_spec, payload = ex.load_checkpoint(checkpoint)
    assert restored_spec == spec
    assert all(torch.equal(a, b) for a, b in zip(before, restored(rgb, prev)))
    assert ex.evaluate(model, val, stats) == ex.evaluate(restored, val, payload["statistics"])
    with pytest.raises(hd.DemoError, match="pad"):
        ex.load_checkpoint(tmp_path / "absent.pt", domain="gamepad")
    with pytest.raises(hd.DemoError, match="never test"):
        ex.evaluate(model, ex.Examples([replace(s, split="test")], spec, frames), stats)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg unavailable")
def test_decode_exact_nonconsecutive_ordinals(tmp_path):
    raw = tmp_path / "frames.rgb"
    raw.write_bytes(b"".join(bytes([i * 40, 10, 20]) * (16 * 16) for i in range(5)))
    video = tmp_path / "frames.mkv"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "rawvideo", "-pixel_format", "rgb24",
        "-video_size", "16x16", "-framerate", "50", "-i", str(raw), "-c:v", "ffv1", str(video)], check=True)
    frames = ex.decode_frames([dict(video_path=str(video), frame_index=i) for i in (4, 1, 4)], image_size=16)
    assert set(frames) == {(str(video), 1), (str(video), 4)}
    assert frames[str(video), 1][:, 0, 0].tolist() == [40, 10, 20]
    assert frames[str(video), 4][:, 0, 0].tolist() == [160, 10, 20]
    with pytest.raises(hd.DemoError, match="ordinal count"):
        ex.decode_frames([dict(video_path=str(video), frame_index=20)], image_size=16)


def synthetic_sessions(tmp_path):
    """Real generated media, raw recorder files, reviewed importer artifacts."""
    base, step, count = 10**9, 20_000_000, 20
    records, raw_sessions = [], []
    for sid, split, color, device in (("train", "train", "red", 12), ("val", "val", "blue", 999)):
        folder = tmp_path / sid
        folder.mkdir()
        video = folder / "original.mkv"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c={color}:s=16x16:r=50",
            "-frames:v", str(count), "-c:v", "ffv1", str(video)], check=True)
        decoded = hd.probe_video(video)
        events = [dict(type="raw_input_status", t_ns=base, ok=True),
            dict(type="focus", t_ns=base, active=True, held_vk=[])]
        for t, down in ((4, True), (8, False)):
            row = event(base+t*step, down, device=device).payload
            events.append(row)
        for seq, row in enumerate(events):
            row["seq"] = seq
        packets = []
        for i, pts in enumerate(decoded["pts"]):
            row = dict.fromkeys(hd.FRAME_COLUMNS, 0)
            row.update(event_seq=len(events)+i, packet_index=i, pts=pts, dts=pts,
                timebase_num=decoded["timebase_num"], timebase_den=decoded["timebase_den"],
                composition_ns=base+i*step)
            packets.append(row)
        meta = dict(schema_version=1, control_type="keyboard_mouse", status="complete", complete=True,
            clean_stop=True, writer_failed=False, queue_dropped_events=0, raw_input_errors=0,
            first_queue_drop_ns=0, last_queue_drop_ns=0, frames_without_composition_timestamp=0,
            events_attempted=len(events)+count, video_packets=count, input_events=2,
            start_ns=base, end_ns=base+count*step, width=16, height=16, fps_num=50, fps_den=1,
            capture_latency_calibrated=False, session_id=sid, video_path=str(video.resolve()),
            target_executable="Marvel-Win64-Shipping.exe")
        review = dict(schema_version=1, session_id=sid, reviewer="synthetic-test", reviewed_at="2026-09-21",
            device_scope=dict(kind="single_keyboard_mouse", source="generated one keyboard and no mouse"),
            pts_anchor=dict(kind="independent_muxer_offset", offset_num=0, offset_den=1,
                            source="generated packet PTS equal file PTS by construction"),
            provenance={"hero": "Spider-Man", **{k: dict(value="synthetic", source="fixture") for k in
                ("settings", "bindings", "game_patch", "cooldown_regime")}},
            alignment=dict(kind="assumption", statement="synthetic clocks coincide", source="fixture"),
            segments=[dict(segment_id="segment", start_ns=base, end_ns=base+count*step,
                           reviewed_gameplay=True, evidence="synthetic fixture, no gameplay claim",
                           imitation_suitability="accepted", suitability_reason="synthetic pipeline test")])
        (folder / "metadata.json").write_text(json.dumps(meta))
        (folder / "inputs.jsonl").write_text("".join(json.dumps(e)+"\n" for e in events))
        with (folder / "frames.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=hd.FRAME_COLUMNS)
            writer.writeheader()
            writer.writerows(packets)
        review_path = folder / "review.json"
        review_path.write_text(json.dumps(review))
        records.append(dict(session_id=sid, session_group=sid, split=split, video_path=str(video)))
        raw_sessions.append((folder, review_path, folder / "imported.json"))
    registry = tmp_path / "splits.json"
    registry.write_text(json.dumps(dict(schema_version=1, sessions=records)))
    for folder, review, output in raw_sessions:
        hd.import_session(folder, review=review, splits=registry, output=output)
    return registry, [row[2] for row in raw_sessions]


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg/ffprobe unavailable")
def test_real_import_to_fit_evaluate_cli_and_registry_sealing(tmp_path):
    registry, (train, val) = synthetic_sessions(tmp_path)
    checkpoint, report = tmp_path / "model.pt", tmp_path / "fit.json"
    ex.cli(["fit", "--train", str(train), "--val", str(val), "--splits", str(registry),
        "--checkpoint", str(checkpoint), "--report", str(report), "--device", "cpu",
        "--epochs", "2", "--hidden", "8", "--image-size", "16", "--history-ms", "40",
        "--frame-step-ms", "20", "--bin-ms", "20", "--bins", "2", "--stride-ms", "20",
        "--max-samples-per-session", "8", "--threads", "1"])
    fitted = json.loads(report.read_text())
    assert fitted["validation"]["samples"] == 8
    assert fitted["validation"]["unseen_controls"] == []
    assert fitted["action_spec"]["controls"][0] == "key:17:0"
    again = tmp_path / "evaluate.json"
    ex.cli(["evaluate", "--val", str(val), "--splits", str(registry), "--checkpoint", str(checkpoint),
            "--report", str(again), "--threads", "1"])
    assert json.loads(again.read_text())["validation"] == fitted["validation"]
    registry_doc = json.loads(registry.read_text())
    registry_doc["sessions"][1]["session_group"] = "train"
    broken = tmp_path / "leaky.json"
    broken.write_text(json.dumps(registry_doc))
    with pytest.raises(hd.DemoError, match="leakage"):
        ex.load_cohort([train, val], broken)
    sealed = tmp_path / "sealed.json"
    sealed.write_text(json.dumps(dict(format=hd.FORMAT, sealed=True, split="test"))+"\nPOISON PAYLOAD")
    with pytest.raises(hd.SealedError):
        ex.load_cohort([sealed], registry)
    changed = json.loads(val.read_text().splitlines()[1])
    changed["review"]["provenance"]["settings"]["value"] = "different sensitivity"
    header = json.loads(val.read_text().splitlines()[0])
    body = ex.canonical(changed)
    import hashlib
    header["payload_sha256"] = hashlib.sha256(body.encode()).hexdigest()
    mismatch = tmp_path / "different-settings.json"
    mismatch.write_text(ex.canonical(header)+"\n"+body+"\n")
    with pytest.raises(hd.DemoError, match="settings"):
        ex.load_cohort([train, mismatch], registry)
