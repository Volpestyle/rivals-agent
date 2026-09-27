"""Synthetic only: all pixels, media, rows and labels are generated in tmp_path."""
import copy
import json
import shutil

import cv2
import numpy as np
import pytest

from perception import hud
from policy.range_bc import cache, cm3_reader as r, fixture, steps


@pytest.fixture
def frozen(tmp_path):
    path = tmp_path / "freeze.json"
    pin = r.freeze(path, unavailable={"mk": {"get_over_here.charges": "Synthetic unavailable contract"},
                                      "pad": {"get_over_here.charges": "Synthetic unavailable contract"}},
                   rationale="Synthetic test; no real structural judgment")
    return path, pin


def reading():
    return hud.Hud(webs=0, hp=250, max_hp=1500, ult_ready=False, ult_charge=.4,
                   abilities={"swing": (False, 0), "get_over_here": (True, 2), "uppercut": (False, 1)},
                   cooldowns={"swing": 40, "get_over_here": 6, "uppercut": 8})


def test_schema_zero_unknown_scales_and_slot_mapping():
    mk = r.values_from_hud(reading(), "mk", {})
    pad = r.values_from_hud(reading(), "pad", {})
    assert mk == pad  # Hud keys are semantic before reconciliation on both layouts.
    assert r.semantic_layout("mk").slot_cx["uppercut"] == hud.MK.slot_cx["get_over_here"]
    assert r.semantic_layout("pad").slot_cx["uppercut"] == hud.PAD.slot_cx["uppercut"]
    vector = r.encode(mk).reshape(14, 2)
    assert vector[0].tolist() == [0, 1] and vector[3].tolist() == [0, 1]
    assert vector[2].tolist() == [1.5, 1] and vector[7, 0] > 1
    unknown = r.values_from_hud(hud.Hud(), "mk", {})
    assert not r.encode(unknown).any()
    with pytest.raises(ValueError, match="layout"):
        r.values_from_hud(reading(), "automatic", {})
    with pytest.raises(ValueError, match="schema"):
        r.encode({})


@pytest.mark.parametrize("field", r.FIELDS)
def test_every_missing_field_and_unavailable_is_unknown(field):
    values = r.values_from_hud(reading(), "mk", {})
    values[field] = None
    assert r.encode(values).reshape(14, 2)[r.FIELDS.index(field)].tolist() == [0, 0]
    suppressed = r.values_from_hud(reading(), "mk", {field: "structural"})
    assert suppressed[field] is None


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), -1, "0", True, 1.5])
def test_invalid_counts_are_unknown(value):
    obj = reading()
    obj.webs = value
    assert r.encode(r.values_from_hud(obj, "pad", {}))[:2].tolist() == [0, 0]


def test_native_current_frame_channel_conversion_and_no_forward_fill(monkeypatch):
    rgb = np.full((90, 160, 3), [10, 20, 30], np.uint8)
    ref = {"video_path": "synthetic", "frame_index": 2, "pts": 17, "timebase": [1, 1000]}
    frame = r.NativeFrame(rgb, "synthetic", 2, 17, (1, 1000))
    def reader(bgr, layout):
        assert layout == r.semantic_layout("mk") and bgr.flags.c_contiguous
        assert bgr[0, 0].tolist() == [30, 20, 10]
        return reading()
    monkeypatch.setattr(hud, "read", reader)
    actual = r.read_native(frame, ref, native_size=[160, 90], layout="mk", unavailable={})
    assert actual == r.values_from_hud(reading(), "mk", {})
    monkeypatch.setattr(hud, "read", lambda *_: hud.Hud())
    assert not r.encode(r.read_native(frame, ref, native_size=[160, 90], layout="mk", unavailable={})).any()
    for key, value in (("frame_index", 3), ("pts", 18), ("timebase", [1, 120]), ("video_path", "future")):
        with pytest.raises(ValueError, match="FrameRef"):
            r.read_native(frame, {**ref, key: value}, native_size=[160, 90], layout="mk", unavailable={})
    with pytest.raises(ValueError, match="shape"):
        r.read_native(frame, ref, native_size=[320, 180], layout="mk", unavailable={})


def test_real_reader_on_synthetic_blank_is_unknown():
    rgb = np.zeros((1440, 2560, 3), np.uint8)
    ref = dict(video_path="blank", frame_index=0, pts=0, timebase=[1, 30])
    actual = r.read_native(r.NativeFrame(rgb, "blank", 0, 0, (1, 30)), ref,
                           native_size=[2560, 1440], layout="mk", unavailable={})
    assert not r.encode(actual).any()


@pytest.mark.parametrize("layout", ["mk", "pad"])
@pytest.mark.parametrize("ability", r.ABILITIES)
@pytest.mark.parametrize("charges", [1, 0, None])
@pytest.mark.parametrize("countdown", [5, 0, None])
@pytest.mark.parametrize("occluded", [False, True])
def test_real_hud_reconciliation_uses_semantics_at_physical_position(
        monkeypatch, layout, ability, charges, countdown, occluded):
    # Actual read_native -> hud.read -> _read_ability; stub only observations.
    # Different observations outside the chosen physical slot detect a missed
    # swap as well as a swap performed too late (the review's reproduction).
    original_slots = dict(hud.LAYOUTS[layout].slot_cx)
    physical_x = original_slots[r.SLOTS[layout][ability]]
    monkeypatch.setattr(hud, "read_hp", lambda *_: (250, 250))
    monkeypatch.setattr(hud, "read_bar_fill", lambda *_: 1.)
    monkeypatch.setattr(hud, "read_damage_segment", lambda *_: 0.)
    monkeypatch.setattr(hud, "read_webs", lambda *_: 2)
    monkeypatch.setattr(hud, "read_ult", lambda *_: (False, .5))
    monkeypatch.setattr(hud, "read_charges", lambda frame, cx, ly: charges if cx == physical_x else 0)
    monkeypatch.setattr(hud, "read_cooldown", lambda frame, name, ly:
                        countdown if ly.slot_cx[name] == physical_x else 9)
    monkeypatch.setattr(hud, "_slot_occluded", lambda frame, cx, limit: occluded if cx == physical_x else False)
    monkeypatch.setattr(hud, "_red_fraction", lambda *_: 0.)  # white ink
    rgb = np.zeros((90, 160, 3), np.uint8)
    ref = dict(video_path="synthetic", frame_index=0, pts=0, timebase=[1, 30])
    frame = r.NativeFrame(rgb, "synthetic", 0, 0, (1, 30))
    actual = r.read_native(frame, ref, native_size=[160, 90], layout=layout, unavailable={})
    if occluded:
        expected = None
    elif charges == 0:
        expected = False
    elif countdown is None:
        expected = True
    elif ability == "get_over_here":
        expected = False if countdown > 0 else None
    else:
        expected = None if charges is None else True
    assert actual[ability + ".ready"] is expected
    assert actual[ability + ".charges"] == charges
    assert actual[ability + ".cooldown"] == countdown
    assert all(actual[a + ".ready"] is False for a in r.ABILITIES if a != ability)
    assert hud.LAYOUTS[layout].slot_cx == original_slots
    suppressed = r.read_native(frame, ref, native_size=[160, 90], layout=layout,
                               unavailable={ability + ".charges": "structural"})
    assert suppressed[ability + ".ready"] is expected and suppressed[ability + ".charges"] is None


@pytest.fixture
def synthetic_cache(tmp_path, monkeypatch):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg required for generated video test")
    video = fixture.write_video(tmp_path / "synthetic.mkv", 5, size=(640, 360))
    tb, pts = fixture.probe_pts(video)
    path = tmp_path / "steps.json"
    header = dict(session_id="synthetic", split="train", hud_layout="mk", video_size=[640, 360],
                  media_sha256=steps.sha256(video))
    rows = [{"frame": dict(video_path=str(video), frame_index=i, pts=pts[i], timebase=list(tb))}
            for i in (0, 2, 2, 4)]
    path.write_text(json.dumps([header, rows]), encoding="utf-8")
    session = steps.Session(str(path), steps.sha256(path), header, rows)
    monkeypatch.setattr(r, "TRAIN_PINS", {"synthetic": session.sha256})
    source = tmp_path / "scene"
    cache.build(session, source, any_platform=True)
    return session, source, steps.sha256(source / "cache.json")


def test_stream_decode_cache_mmap_parity_and_corruption(synthetic_cache, frozen, tmp_path, monkeypatch):
    session, source, pin = synthetic_cache
    freeze, freeze_pin = frozen
    # Deterministic native reader stub proves every current pixel reaches adapter
    # and target/future HUD row values are unused; real blank-reader tested above.
    def pixel_reader(bgr, layout):
        return hud.Hud(hp=int(bgr[0, 0, 2]), webs=0, abilities={"swing": (False, 0)})
    monkeypatch.setattr(hud, "read", pixel_reader)
    session.rows[0]["hud"] = {"webs": 5}
    session.rows[0]["future_target"] = {"hp": 9000}
    out = tmp_path / "reader"
    r.build_cache(session, source, pin, out, freeze, freeze_pin, role="train")
    manifest_pin = steps.sha256(out / "reader.json")
    array, rows, _ = r.open_cache(out, manifest_pin, session, source, pin, freeze, freeze_pin, role="train")
    assert isinstance(array, np.memmap) and rows == [0, 1, 1, 2]
    for index, ordinal in enumerate((0, 2, 4)):
        expected = r.encode(r.values_from_hud(hud.Hud(hp=fixture.frame_colours(ordinal)[0][0], webs=0,
                                                      abilities={"swing": (False, 0)}), "mk", {}))
        np.testing.assert_array_equal(array[index], expected)
    del array
    with (out / "reader.f32").open("r+b") as stream:
        stream.write(b"\xff")
    with pytest.raises(ValueError, match="hash"):
        r.open_cache(out, manifest_pin, session, source, pin, freeze, freeze_pin, role="train")
    with (source / "global.u8").open("r+b") as stream:
        stream.write(b"\xff")
    with pytest.raises(ValueError, match="hash"):
        r.build_cache(session, source, pin, tmp_path / "refused", freeze, freeze_pin, role="train")
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize("mutation", ["pts", "duplicate", "row_map", "schema", "role", "source_pin"])
def test_cache_refuses_mutated_inputs_before_destination(synthetic_cache, frozen, tmp_path, mutation):
    session, source, pin = synthetic_cache
    freeze, freeze_pin = frozen
    if mutation == "pts":
        session.rows[0]["frame"]["pts"] += 1
    elif mutation == "duplicate":
        session.rows[2]["frame"]["pts"] += 1
    elif mutation == "row_map":
        m = json.loads((source / "cache.json").read_text())
        m["row_frame"].reverse()
        (source / "cache.json").write_text(json.dumps(m))
        pin = steps.sha256(source / "cache.json")
    elif mutation == "schema":
        f = json.loads(freeze.read_text())
        f["schema"]["slots"]["mk"]["get_over_here"] = "get_over_here"
        freeze.write_text(json.dumps(f))
        freeze_pin = steps.sha256(freeze)
    elif mutation == "source_pin":
        pin = "0" * 64
    out = tmp_path / "refused"
    with pytest.raises(ValueError):
        r.build_cache(session, source, pin, out, freeze, freeze_pin,
                      role="val" if mutation == "role" else "train")
    assert not out.exists()


@pytest.fixture
def plan(tmp_path, monkeypatch, frozen):
    sessions = []
    for n in range(5):
        header, rows = fixture.session(f"synthetic-{n}", runs=(120,))
        header["video_size"] = [16, 9]  # native dimensions of generated blind PNGs
        # Full synthetic eligible run; no real corpus or registry file loaded.
        for row in rows:
            row["suitability"], row["regime"] = "accepted", "normal"
        path = fixture.write(tmp_path / f"s{n}.jsonl", header, rows)
        sessions.append(steps.Session(str(path), steps.sha256(path), header, rows))
    monkeypatch.setattr(r, "TRAIN_PINS", {s.session_id: s.sha256 for s in sessions})
    freeze, pin = frozen
    result = r.sample_plan(sessions, freeze, pin, tmp_path / "plan.json")
    again = r.sample_plan(list(reversed(sessions)), freeze, pin, tmp_path / "plan2.json")
    assert result == again
    assert len(result["entries"]) == 400
    assert len({(e["session"], e["row"]) for e in result["entries"]}) == 400
    assert all(sum(e["session"] == s.session_id for e in result["entries"][:200]) == 40 for s in sessions)
    sessions[0].header["split"] = "val"
    with pytest.raises(ValueError, match="forbidden"):
        r.sample_plan(sessions, freeze, pin, tmp_path / "bad-plan.json")
    return result


def label_doc(plan, count=200, *, all_ready=False):
    entries = []
    for i, entry in enumerate(plan["entries"][:count]):
        v = {f: (True if all_ready else bool(i % 2)) if f == "ult_ready" or f.endswith(".ready") else
             .5 if f == "ult_charge" else 1 for f in r.FIELDS}
        v["get_over_here.charges"] = None
        entries.append({"id": entry["id"], "values": v, "complete": True, "strata": []})
    return {"plan_sha256": r.digest(plan), "entries": entries}


def exported_fixture(tmp_path, plan, doc=None):
    """Real export route over generated PNGs; never synthesize an export hash."""
    packet = tmp_path / "packet"
    plan_pin = r.digest(plan)
    if not packet.exists():
        def frame_provider(entry):
            w, h = entry["native_size"]
            ref = entry["frame"]
            rgb = np.full((h, w, 3), [entry["row"] % 256, 20, 30], np.uint8)
            return r.NativeFrame(rgb, ref["video_path"], ref["frame_index"], ref["pts"], tuple(ref["timebase"]))
        r.blind_packet(plan, packet, frame_provider, plan_pin=plan_pin)
    export_path = packet / "images.json"
    exported = json.loads(export_path.read_text())
    export_pin = steps.sha256(export_path)
    if doc is not None:
        doc["export_sha256"] = export_pin
        for label, image in zip(doc["entries"], exported["entries"]):
            label["image_sha256"] = image["image_sha256"]
    return dict(plan_pin=plan_pin, export_path=export_path, export_pin=export_pin)


def synthetic_predictions(tmp_path, frozen, plan, doc, labels, seal, bindings, mutate=None):
    """Exercise production extraction/provenance with an explicitly stubbed reader.
    Accuracy fixtures are synthetic values; they are never reader-accuracy evidence.
    """
    predictions = {e["id"]: copy.deepcopy(e["values"]) for e in doc["entries"]}
    if mutate:
        mutate(predictions)
    stream = iter(predictions.values())
    path = tmp_path / "predictions.json"
    with pytest.MonkeyPatch.context() as m:
        m.setattr(r, "read_native", lambda *args, **kwargs: next(stream))
        pin = r.predict_blind_packet(plan, tmp_path / "packet", labels, seal, steps.sha256(seal),
                                     *frozen, path, **bindings)
    return path, pin


def sealed_score(tmp_path, frozen, plan, doc, mutate=None):
    freeze, pin = frozen
    bindings = exported_fixture(tmp_path, plan, doc)
    original, final, seal = (tmp_path / name for name in ("original.json", "final.json", "seal.json"))
    r.write_json(original, doc)
    r.write_json(final, doc)
    r.seal_labels(plan, original, final, seal, freeze, pin, **bindings)
    predictions, predictions_pin = synthetic_predictions(tmp_path, frozen, plan, doc, final, seal, bindings, mutate)
    return r.score(plan, final, seal, steps.sha256(seal), predictions, freeze, pin,
                   predictions_pin=predictions_pin, **bindings)


def test_perfect_precheck_is_not_parity(plan, frozen, tmp_path):
    report = sealed_score(tmp_path, frozen, plan, label_doc(plan))
    assert report["status"] == "PASS" and report["parity"] == "NOT RUN"
    assert report["counts"]["all"]["hp"]["legible"] == 200
    assert report["ult_fill"]["counts"]["correct_known_share"] == 1
    assert any(k.startswith("session:") and "/stratum:" in k for k in report["counts"])


@pytest.mark.parametrize("mutation", ["wrong", "unsafe", "unknown-six-percent", "false-ready", "fill"])
def test_precheck_rejects_errors(plan, frozen, tmp_path, mutation):
    doc = label_doc(plan)
    first = doc["entries"][0]["id"]
    if mutation == "unsafe":
        doc["entries"][0]["values"]["hp"] = None
    def change(p):
        if mutation == "wrong":
            p[first]["webs"] = 0
        elif mutation == "unsafe":
            p[first]["hp"] = 1
        elif mutation == "unknown-six-percent":
            for item in list(p.values())[:12]:
                item["hp"] = None
        elif mutation == "false-ready":
            p[first]["swing.ready"] = True
        else:
            p[first]["ult_charge"] = .5501
    report = sealed_score(tmp_path, frozen, plan, doc, change)
    assert report["status"] == "FAIL"


def test_tolerance_and_five_percent_abstention_boundary(plan, frozen, tmp_path):
    def change(p):
        for item in list(p.values())[:10]:
            item["hp"] = None
        for item in p.values():
            item["ult_charge"] += .05
    assert sealed_score(tmp_path, frozen, plan, label_doc(plan), change)["status"] == "PASS"


def test_vacuous_ready_coverage_undecided(plan, frozen, tmp_path):
    doc = label_doc(plan, count=400, all_ready=True)
    assert sealed_score(tmp_path, frozen, plan, doc)["status"] == "UNDECIDED"


def test_wrong_semantic_map_fails_when_observable(plan, frozen, tmp_path):
    doc = label_doc(plan)
    for entry in doc["entries"]:
        entry["values"]["get_over_here.ready"] = not entry["values"]["amazing_combo.ready"]
    def wrong_map(predictions):
        for p in predictions.values():
            p["get_over_here.ready"], p["amazing_combo.ready"] = p["amazing_combo.ready"], p["get_over_here.ready"]
    assert sealed_score(tmp_path, frozen, plan, doc, wrong_map)["status"] == "FAIL"


def test_reserve_stops_at_first_quota_and_preserves_prefix(plan, frozen, tmp_path):
    doc = label_doc(plan, count=220)
    # First 200 have no spent swing; exactly 20 additional labels fill the quota.
    for entry in doc["entries"][:200]:
        entry["values"]["swing.charges"] = 3
    assert sealed_score(tmp_path, frozen, plan, doc)["status"] == "PASS"


def test_labels_and_predictions_cannot_change_after_seal(plan, frozen, tmp_path):
    doc = label_doc(plan)
    bindings = exported_fixture(tmp_path, plan, doc)
    labels, seal = tmp_path / "labels.json", tmp_path / "seal.json"
    r.write_json(labels, doc)
    r.seal_labels(plan, labels, labels, seal, *frozen, **bindings)
    predictions, pin = synthetic_predictions(tmp_path, frozen, plan, doc, labels, seal, bindings)
    artifact = json.loads(predictions.read_text())
    artifact["values"].pop(next(iter(artifact["values"])))
    predictions.write_text(json.dumps(artifact))
    pin = steps.sha256(predictions)
    with pytest.raises(ValueError, match="exact inspected"):
        r.score(plan, labels, seal, steps.sha256(seal), predictions, *frozen, predictions_pin=pin, **bindings)
    labels.write_bytes(labels.read_bytes() + b" ")
    with pytest.raises(ValueError, match="after seal"):
        r.score(plan, labels, seal, steps.sha256(seal), predictions, *frozen, predictions_pin=pin, **bindings)


def test_prediction_extraction_requires_sealed_native_images(plan, frozen, tmp_path, monkeypatch):
    doc = label_doc(plan)
    bindings = exported_fixture(tmp_path, plan, doc)
    packet = tmp_path / "packet"
    labels, seal = tmp_path / "labels.json", tmp_path / "seal.json"
    r.write_json(labels, doc)
    r.seal_labels(plan, labels, labels, seal, *frozen, **bindings)
    monkeypatch.setattr(hud, "read", lambda *_: reading())
    predictions = tmp_path / "predictions.json"
    r.predict_blind_packet(plan, packet, labels, seal, steps.sha256(seal), *frozen, predictions, **bindings)
    preds = json.loads(predictions.read_text())["values"]
    assert len(preds) == 200
    assert all(p["get_over_here.charges"] is None for p in preds.values())
    first = packet / (plan["entries"][0]["id"] + ".png")
    first.write_bytes(first.read_bytes() + b" ")
    with pytest.raises(ValueError, match="image changed"):
        r.predict_blind_packet(plan, packet, labels, seal, steps.sha256(seal), *frozen,
                               tmp_path / "refused.json", **bindings)


def test_cannot_inspect_past_first_quota_completion(plan, frozen, tmp_path):
    doc = label_doc(plan, count=201)
    bindings = exported_fixture(tmp_path, plan, doc)
    original = tmp_path / "labels.json"
    r.write_json(original, doc)
    with pytest.raises(ValueError, match="first quota"):
        r.seal_labels(plan, original, original, tmp_path / "seal.json", *frozen, **bindings)


@pytest.mark.parametrize("mutation", ["both-missing", "original-missing", "adjudicated-missing",
                                     "null", "short", "nonhex", "integer", "both-changed"])
def test_seal_rejects_unbound_or_replaced_label_images(plan, frozen, tmp_path, mutation):
    original = label_doc(plan)
    bindings = exported_fixture(tmp_path, plan, original)
    final = copy.deepcopy(original)
    if mutation in ("both-missing", "original-missing"):
        original["entries"][0].pop("image_sha256")
    if mutation in ("both-missing", "adjudicated-missing"):
        final["entries"][0].pop("image_sha256")
    bad = {"null": None, "short": "a" * 63, "nonhex": "g" * 64, "integer": 123, "both-changed": "a" * 64}
    if mutation in bad:
        original["entries"][0]["image_sha256"] = final["entries"][0]["image_sha256"] = bad[mutation]
    a, b = tmp_path / "original.json", tmp_path / "adjudicated.json"
    r.write_json(a, original)
    r.write_json(b, final)
    with pytest.raises(ValueError, match="image digest"):
        r.seal_labels(plan, a, b, tmp_path / "refused-seal.json", *frozen, **bindings)
    assert not (tmp_path / "refused-seal.json").exists()


@pytest.mark.parametrize("mutation", ["private-plan", "export-bytes", "other-export", "reordered-labels"])
def test_seal_requires_original_plan_and_export(plan, frozen, tmp_path, mutation):
    doc = label_doc(plan)
    bindings = exported_fixture(tmp_path, plan, doc)
    if mutation == "private-plan":
        plan["entries"][0]["frame"]["pts"] += 1
        doc["plan_sha256"] = r.digest(plan)  # cannot replace the separately pinned plan
    elif mutation == "export-bytes":
        path = bindings["export_path"]
        path.write_bytes(path.read_bytes() + b" ")
    elif mutation == "other-export":
        # Another genuinely exported image packet under the same plan must not
        # substitute for the packet independently labeled/export-pinned earlier.
        def provider(entry):
            ref = entry["frame"]
            w, h = entry["native_size"]
            return r.NativeFrame(np.zeros((h, w, 3), np.uint8), ref["video_path"],
                                  ref["frame_index"], ref["pts"], tuple(ref["timebase"]))
        r.blind_packet(plan, tmp_path / "other-packet", provider, plan_pin=bindings["plan_pin"])
        bindings["export_path"] = tmp_path / "other-packet" / "images.json"
    else:
        doc["entries"][0], doc["entries"][1] = doc["entries"][1], doc["entries"][0]
    labels = tmp_path / "labels.json"
    r.write_json(labels, doc)
    with pytest.raises(ValueError):
        r.seal_labels(plan, labels, labels, tmp_path / "refused-seal.json", *frozen, **bindings)


@pytest.mark.parametrize("mutation", ["dictionary", "bare-json", "artifact-bytes", "plan_sha256", "export_sha256",
                                     "freeze_sha256", "label_seal_sha256", "labels_sha256", "images"])
def test_score_refuses_unbound_predictions_or_foreign_provenance(plan, frozen, tmp_path, mutation):
    doc = label_doc(plan)
    bindings = exported_fixture(tmp_path, plan, doc)
    labels, seal = tmp_path / "labels.json", tmp_path / "seal.json"
    r.write_json(labels, doc)
    r.seal_labels(plan, labels, labels, seal, *frozen, **bindings)
    predictions, pin = synthetic_predictions(tmp_path, frozen, plan, doc, labels, seal, bindings)
    artifact = json.loads(predictions.read_text())
    if mutation == "dictionary":
        predictions = artifact["values"]  # review reproduction's old scoring route
    elif mutation == "artifact-bytes":
        predictions.write_bytes(predictions.read_bytes() + b" ")
    else:
        if mutation == "bare-json":
            artifact = artifact["values"]
        elif mutation == "images":
            artifact["images"][0]["image_sha256"] = "a" * 64
        else:
            artifact[mutation] = "a" * 64
        predictions.write_text(json.dumps(artifact))
        pin = steps.sha256(predictions)  # even a repinned foreign artifact is rejected
    with pytest.raises(ValueError, match="unbound|provenance|artifact pin"):
        r.score(plan, labels, seal, steps.sha256(seal), predictions, *frozen, predictions_pin=pin, **bindings)


def test_review_missing_images_reproduction_refused_without_export(plan, frozen, tmp_path):
    # Exact original failure: perfect-looking labels, no exported images.
    doc = label_doc(plan)
    labels = tmp_path / "labels.json"
    r.write_json(labels, doc)
    with pytest.raises(FileNotFoundError):
        r.seal_labels(plan, labels, labels, tmp_path / "refused.json", *frozen,
                       plan_pin=r.digest(plan), export_path=tmp_path / "no-export.json", export_pin="a" * 64)


def test_blind_export_has_no_predictions_or_source_identity(tmp_path, monkeypatch):
    ref = dict(video_path="secret-native-source", frame_index=0, pts=0, timebase=[1, 30])
    plan = {"freeze_sha256": "0" * 64,
            "entries": [{"id": "blind-0000", "phase": "base", "frame": ref, "native_size": [160, 90]}]}
    rgb = np.full((90, 160, 3), [10, 20, 30], np.uint8)
    monkeypatch.setattr(hud, "read", lambda *_: pytest.fail("blinding ran reader"))
    r.blind_packet(plan, tmp_path / "blind", lambda _: r.NativeFrame(rgb, ref["video_path"], 0, 0, (1, 30)),
                    plan_pin=r.digest(plan))
    text = (tmp_path / "blind" / "labels.json").read_text()
    assert "secret-native-source" not in text and "prediction" not in text
    assert all(v is None for v in json.loads(text)["entries"][0]["values"].values())
    assert cv2.imread(str(tmp_path / "blind" / "blind-0000.png"))[0, 0].tolist() == [30, 20, 10]


def test_freeze_is_exclusive_and_rejects_changes(frozen):
    path, pin = frozen
    with pytest.raises(FileExistsError):
        r.freeze(path, unavailable={"mk": {}, "pad": {}}, rationale="second attempt")
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="freeze hash"):
        r.load_freeze(path, pin)
