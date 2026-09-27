"""CM3 conditional Reader: causal native pixels, immutable caches, blinded precheck.

No automatic jobs, media discovery, label inference, or model integration. Callers
must supply validated Sessions and externally pinned source manifests. All writes
are exclusive. Sampling/scoring is train-only; a cache build also supports the
explicitly pinned frozen dev cohort after the lead's separate R launch gate.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import tempfile

from . import cache, steps

FORMAT = "range-bc-cm3-reader-v1"
ABILITIES = ("swing", "get_over_here", "amazing_combo")
FIELDS = ("webs", "hp", "max_hp", "ult_ready", "ult_charge") + tuple(
    f"{a}.{f}" for a in ABILITIES for f in ("ready", "charges", "cooldown"))
SCALES = (5., 1000., 1000., 1., 1.) + (1., 3., 30.) * 3
DIM = 28
SLOTS = {
    "pad": {"swing": "swing", "get_over_here": "get_over_here", "amazing_combo": "uppercut"},
    "mk": {"swing": "swing", "get_over_here": "uppercut", "amazing_combo": "get_over_here"},
}
HUD_KEYS = {"swing": "swing", "get_over_here": "get_over_here", "amazing_combo": "uppercut"}
TRAIN_PINS = {
    "20260923T051828-422Z-33696-1": "d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb",
    "20260923T200129-346Z-33696-6": "fcc9b0443e720648b899453ea3f04f82c0a6dd1735f30a420a36b3675549ba8e",
    "20260924T232304-170Z-12024-1": "8a6c63d4024b13d5b73ab0154f434782e6cfc853d6eaa8291bd9fa8ca8f3b1b1",
    "20260925T021320-371Z-7804-1": "841fe6953cf473e55c6becfe24143259fa48dca639bb9387bc04615edf6ea537",
    "20260925T025230-605Z-7804-2": "84cef39b81ce8a40637bb5cf9766cdfc6f4054b32cda5d94ac1082329434c288",
}
DEV_PINS = {
    "20260923T171533-187Z-33696-5": "dc28b0c1511f7847c8dde08c3e04addce8b57bc6c32cc2873405962d3235559e",
    "20260923T205528-900Z-45572-3": "941950f16edef6a88b14d6bc536e33a66a0e779867fa145c78e7142164e1fd98",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def write_json(path, obj):
    with Path(path).open("x", encoding="utf-8", newline="\n") as out:
        json.dump(obj, out, sort_keys=True, indent=2, allow_nan=False)
        out.write("\n")


def schema():
    return {"format": FORMAT, "fields": list(FIELDS), "scales": list(SCALES),
            "encoding": "interleaved value,known; unknown=(0,0)", "dtype": "<f4",
            "slots": SLOTS, "hud_semantic_keys": HUD_KEYS,
            "reconciliation": "semantic identities before ability reconciliation",
            "channels": "native RGB uint8 -> contiguous BGR uint8",
            "colour": cache.CONVERT, "ult_charge_tolerance": .05}


def code_pins():
    # Glyph and icon assets are embedded in hud.py; no frame assets are loaded.
    root = Path(__file__).resolve().parents[2]
    return {p: steps.sha256(root / p) for p in (
        "policy/range_bc/cm3_reader.py", "perception/hud.py",
        "policy/range_bc/cache.py", "policy/range_bc/steps.py")}


def freeze(path, *, unavailable, rationale):
    """Write BEFORE sampling. Explicit per-layout field/reason maps, even if empty.

    No field is silently waived: the independent reviewer must approve the
    structural contract. This function inspects code only, never recordings.
    """
    import cv2
    import numpy as np
    require(set(unavailable) == set(SLOTS), "declare availability for both layouts")
    for mapping in unavailable.values():
        require(set(mapping) <= set(FIELDS), "unknown unavailable field")
        require(all(isinstance(v, str) and v.strip() for v in mapping.values()), "missing structural reason")
    require(isinstance(rationale, str) and rationale.strip(), "availability rationale required")
    record = {"schema": schema(), "code": code_pins(), "unavailable": unavailable,
              "rationale": rationale, "numpy": np.__version__, "opencv": cv2.__version__}
    write_json(path, record)
    return steps.sha256(path)


def load_freeze(path, pin):
    import cv2
    import numpy as np
    require(steps.sha256(path) == pin, "reader freeze hash mismatch")
    f = json.loads(Path(path).read_text(encoding="utf-8"))
    require(f["schema"] == schema() and f["code"] == code_pins(), "wrong schema/map/reader code")
    require((f["numpy"], f["opencv"]) == (np.__version__, cv2.__version__), "reader environment changed")
    return f


def valid(field, value):
    if value is None:
        return False
    if field == "ult_ready" or field.endswith(".ready"):
        return type(value) is bool
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return False
    if field == "ult_charge":
        return 0 <= value <= 1
    return value >= 0 and (field.endswith(".cooldown") or float(value).is_integer())


def semantic_layout(layout):
    """Give hud.read semantic keys at recorded positions BEFORE reconciliation.

    hud._read_ability distinguishes multi-charge 'uppercut' from single-cooldown
    'get_over_here' by name. Renaming its reconciled results would be too late.
    The shared Layout and its slot_cx dictionary are never mutated.
    """
    from perception import hud
    require(layout in SLOTS, "unregistered layout")
    base = hud.LAYOUTS[layout]
    positions = {"teamup": base.slot_cx["teamup"]}
    positions.update({HUD_KEYS[ability]: base.slot_cx[physical] for ability, physical in SLOTS[layout].items()})
    return replace(base, slot_cx=positions)


def values_from_hud(reading, layout, unavailable):
    """Encode a Hud already read with semantic_layout, never a physical-key Hud."""
    require(layout in SLOTS, "unregistered layout")
    require(set(unavailable) <= set(FIELDS), "wrong unavailable fields")
    values = {k: getattr(reading, k, None) for k in FIELDS[:5]}
    for ability, slot in HUD_KEYS.items():
        ready, charges = reading.abilities.get(slot, (None, None))
        values.update({f"{ability}.ready": ready, f"{ability}.charges": charges,
                       f"{ability}.cooldown": reading.cooldowns.get(slot)})
    return {f: v if f not in unavailable and valid(f, v) else None for f, v in values.items()}


def encode(values):
    import numpy as np
    require(set(values) == set(FIELDS), "reader fields do not match schema")
    vector = np.zeros(DIM, dtype="<f4")
    for i, (field, scale) in enumerate(zip(FIELDS, SCALES)):
        value = values[field]
        if valid(field, value) and abs(float(value) / scale) <= np.finfo(np.float32).max:
            vector[2*i:2*i+2] = (float(value) / scale, 1.)
    return vector


@dataclass(frozen=True)
class NativeFrame:
    """Decoded identity is supplied by the decoder, independently of the row."""
    rgb: object
    video_path: str
    frame_index: int
    pts: int
    timebase: tuple


def read_native(frame, reference, *, native_size, layout, unavailable):
    import numpy as np
    from perception import hud
    require((frame.video_path, frame.frame_index, frame.pts, tuple(frame.timebase)) ==
            (reference["video_path"], reference["frame_index"], reference["pts"], tuple(reference["timebase"])),
            "current FrameRef mismatch (ordinal/PTS/timebase/source)")
    require(isinstance(frame.rgb, np.ndarray) and frame.rgb.dtype == np.uint8 and
            frame.rgb.shape == (native_size[1], native_size[0], 3), "native RGB frame shape/dtype mismatch")
    require(layout in SLOTS, "unregistered layout")
    reading = hud.read(np.ascontiguousarray(frame.rgb[:, :, ::-1]), semantic_layout(layout))
    return values_from_hud(reading, layout, unavailable)


def check_session(session, role):
    require(role in ("train", "dev"), "forbidden source role")
    pins = TRAIN_PINS if role == "train" else DEV_PINS
    require(pins.get(session.session_id) == session.sha256, "source outside frozen cohort")
    # Frozen dev tables were originally registered train; role is the preregistered ID, not relabeled metadata.
    require(session.split == "train", "validation/test/sealed sources forbidden")
    require(steps.sha256(session.path) == session.sha256, "step table bytes changed")
    require(session.header["hud_layout"] == "mk", "recorded layout differs from cohort")


def verify_source(session, source_dir, source_pin, role):
    check_session(session, role)
    source_dir = Path(source_dir)
    require(steps.sha256(source_dir / "cache.json") == source_pin, "source cache manifest pin mismatch")
    *arrays, row_map, manifest = cache.open_cache(source_dir, session, verify_hashes=True)
    del arrays
    frames, pts, expected_rows = cache.plan(session)
    require(manifest["session_id"] == session.session_id and manifest["hud_layout"] == "mk", "source identity/layout")
    require(row_map == expected_rows and manifest["frames"] == len(frames), "source row order mismatch")
    require(all(manifest[f"{k}_shape"] == list(s) for k, s in
                (("global", cache.GLOBAL), ("crop", cache.CROP), ("hud", cache.HUD))), "source shape mismatch")
    require(manifest["graph"] == cache.GRAPH, "source color/preprocess mismatch")
    return manifest, frames, pts, row_map


def decode_native(path, frames, expected, size, *, ffmpeg="ffmpeg"):
    """One-frame RAM bound. showinfo's ordinal/PTS/timebase is checked before
    yielding any pixels. Stderr goes to a temporary file, never an unbounded pipe.
    Select AFTER showinfo so original decoded ordinals remain independently visible.
    """
    import numpy as np
    with tempfile.TemporaryDirectory(prefix="cm3-reader-decode-") as tmp:
        graph = Path(tmp) / "graph.txt"
        graph.write_text("showinfo," + cache.select_expression([o for _, o in frames]) + "," + cache.CONVERT,
                         encoding="ascii")
        with (Path(tmp) / "stderr").open("w+b") as err:
            proc = subprocess.Popen([ffmpeg, "-v", "info", "-nostdin", "-i", str(path),
                                     "-map", "0:v:0", "-filter_script:v", str(graph), "-fps_mode", "passthrough",
                                     "-an", "-sn", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                                    stdout=subprocess.PIPE, stderr=err)
            try:
                # showinfo precedes stdout; track its complete lines as output arrives.
                offset, pending, seen, tb = 0, b"", {}, set()
                for (video, ordinal), (pts, timebase) in zip(frames, expected):
                    block = proc.stdout.read(size[0] * size[1] * 3)
                    require(len(block) == size[0] * size[1] * 3, "truncated native frame")
                    with (Path(tmp) / "stderr").open("rb") as log:
                        log.seek(offset)
                        chunk = log.read()
                        offset += len(chunk)
                    lines = (pending + chunk).split(b"\n")
                    pending = lines.pop()
                    for line in lines:
                        text = line.decode(errors="replace")
                        for n, p in cache._SHOWINFO.findall(text):
                            seen[int(n)] = int(p)
                        tb.update(tuple(map(int, match)) for match in cache._TIMEBASE.findall(text))
                    require(seen.get(ordinal) == pts and tb == {tuple(timebase)}, "decoded ordinal/PTS/timebase mismatch")
                    # Keep only future showinfo records (ffmpeg can run ahead).
                    seen = {n: p for n, p in seen.items() if n > ordinal}
                    yield NativeFrame(np.frombuffer(block, dtype=np.uint8).reshape(size[1], size[0], 3),
                                      video, ordinal, pts, tuple(timebase))
                require(not proc.stdout.read(1), "extra decoded frame")
                require(proc.wait() == 0, "native ffmpeg decode failed")
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
                proc.stdout.close()


def build_cache(session, source_dir, source_pin, out_dir, freeze_path, freeze_pin, *, role,
                video_root=None, relocation=None, ffmpeg="ffmpeg", ffprobe="ffprobe"):
    """Lead-gated API; does not discover media. No destination until verification.

    Output is unique-frame x 28 little-endian float32 plus the original row map.
    Consumers gather reader[row_frame[row]] exactly as for the scene cache.
    """
    frozen = load_freeze(freeze_path, freeze_pin)
    source, frames, expected, rows = verify_source(session, source_dir, source_pin, role)
    require(len({v for v, _ in frames}) == 1, "one session must name one video")
    video = frames[0][0]
    path = cache.resolve(relocation["transcoded_path"] if relocation else video, video_root)
    media_kind = cache.check_media(path, session, relocation)
    require(cache.probe_size(path, ffprobe) == session.header["video_size"], "native size mismatch")
    colour = cache.probe_colour(path, ffprobe)
    cache.check_colour(colour)
    media_hash = steps.sha256(path)
    require(len(source["videos"]) == 1 and source["videos"][0]["media_sha256"] == media_hash,
            "native media differs from scene cache")
    require(not Path(out_dir).exists(), "reader destination already exists")
    with tempfile.TemporaryDirectory(prefix="cm3-reader-cache-") as tmp:
        blob = Path(tmp) / "reader.f32"
        count = 0
        with blob.open("xb") as stream:
            for f in decode_native(path, frames, expected, session.header["video_size"], ffmpeg=ffmpeg):
                require(count < len(frames), "extra native frame")
                ref = dict(video_path=frames[count][0], frame_index=frames[count][1],
                           pts=expected[count][0], timebase=expected[count][1])
                values = read_native(f, ref, native_size=session.header["video_size"], layout="mk",
                                     unavailable=frozen["unavailable"]["mk"])
                stream.write(encode(values).tobytes())
                count += 1
        require(count == len(frames), "missing native frame")
        require(steps.sha256(path) == media_hash, "media changed during extraction")
        load_freeze(freeze_path, freeze_pin)
        verify_source(session, source_dir, source_pin, role)
        manifest = {"format": FORMAT, "schema": schema(), "freeze_sha256": freeze_pin,
                    "source_cache_sha256": source_pin, "steps_sha256": session.sha256,
                    "session_id": session.session_id, "role": role, "row_frame": rows,
                    "frames": [[v, o, p, list(tb)] for (v, o), (p, tb) in zip(frames, expected)],
                    "shape": [count, DIM], "dtype": "<f4", "reader_sha256": steps.sha256(blob),
                    "media_sha256": media_hash, "media_kind": media_kind, "colour": colour,
                    "ffmpeg": cache.ffmpeg_version(ffmpeg)}
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=False)
        import shutil
        shutil.copyfile(blob, out / "reader.f32")
        write_json(out / "reader.json", manifest)
    return manifest


def open_cache(directory, manifest_pin, session, source_dir, source_pin, freeze_path, freeze_pin, *, role):
    import numpy as np
    load_freeze(freeze_path, freeze_pin)
    _, frames, expected, rows = verify_source(session, source_dir, source_pin, role)
    directory = Path(directory)
    require(steps.sha256(directory / "reader.json") == manifest_pin, "reader manifest pin mismatch")
    m = json.loads((directory / "reader.json").read_text(encoding="utf-8"))
    checks = {"format": FORMAT, "schema": schema(), "freeze_sha256": freeze_pin,
              "source_cache_sha256": source_pin, "steps_sha256": session.sha256,
              "session_id": session.session_id, "role": role, "row_frame": rows,
              "shape": [len(frames), DIM], "dtype": "<f4",
              "frames": [[v, o, p, list(tb)] for (v, o), (p, tb) in zip(frames, expected)]}
    require(all(m.get(k) == v for k, v in checks.items()), "reader schema/map/source/PTS mismatch")
    path = directory / "reader.f32"
    require(path.stat().st_size == len(frames)*DIM*4 and steps.sha256(path) == m["reader_sha256"],
            "reader cache size/hash mismatch")
    return np.memmap(path, dtype="<f4", mode="r", shape=(len(frames), DIM)), rows, m


def sample_plan(sessions, freeze_path, freeze_pin, out_path):
    """Private row key, never a label packet. 200 base + up to 200 reserve.

    Canonical sorted session/row ordering, one Random(20260928) stream: sample
    40/session, then sample 200 remaining rows globally in a pre-drawn order.
    No labels, reader output, targets or logger actions affect selection.
    """
    load_freeze(freeze_path, freeze_pin)  # mandatory existing structural freeze
    require(len(sessions) == 5 and {s.session_id for s in sessions} == set(TRAIN_PINS), "exact five train sessions required")
    rng, base, remaining = random.Random(20260928), [], []
    for session in sorted(sessions, key=lambda s: s.session_id):
        check_session(session, "train")
        eligible = [i for a, b in steps.runs(session) if b-a >= steps.MIN_RUN for i in range(a, b)]
        require(len(eligible) >= 40, "insufficient eligible training rows")
        chosen = rng.sample(eligible, 40)
        selected = set(chosen)
        def item(i):
            return {"session": session.session_id, "row": i, "frame": session.rows[i]["frame"],
                    "native_size": session.header["video_size"], "layout": "mk"}
        base.extend(item(i) for i in chosen)
        remaining.extend(item(i) for i in eligible if i not in selected)
    reserve = rng.sample(remaining, min(200, len(remaining)))
    entries = []
    for phase, items in (("base", base), ("reserve", reserve)):
        for row in items:
            entries.append({**row, "phase": phase, "id": f"blind-{len(entries):04d}"})
    plan = {"format": FORMAT, "freeze_sha256": freeze_pin, "cohort": TRAIN_PINS,
            "seed": 20260928, "entries": entries}
    write_json(out_path, plan)
    return plan


def blind_packet(plan, out_dir, frame_provider, *, plan_pin):
    """Export native RGB PNGs plus EMPTY labels; never execute a reader.

    frame_provider(entry) must return a NativeFrame; lead supplies the authorized
    decoder. All 400 files may be prepared, but labeling reveals reserve entries
    sequentially and stops at coverage. Private plan stays outside this directory.
    """
    import cv2
    import numpy as np
    require(digest(plan) == plan_pin, "private sample plan pin mismatch")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    labels = []
    for entry in plan["entries"]:
        f = frame_provider(entry)
        ref = entry["frame"]
        require((f.video_path, f.frame_index, f.pts, list(f.timebase)) ==
                (ref["video_path"], ref["frame_index"], ref["pts"], ref["timebase"]), "blind frame identity mismatch")
        w, h = entry["native_size"]
        require(f.rgb.dtype == np.uint8 and f.rgb.shape == (h, w, 3), "native RGB required")
        name = entry["id"] + ".png"
        require(cv2.imwrite(str(out / name), np.ascontiguousarray(f.rgb[:, :, ::-1])), "PNG write failed")
        labels.append({"id": entry["id"], "image": name, "image_sha256": steps.sha256(out / name),
                       "phase": entry["phase"], "values": {k: None for k in FIELDS},
                       "strata": [], "complete": False})
    # Separate from the editable labels. Pin the returned digest outside the
    # labeler's packet at export time; never recreate this manifest from labels.
    exported = {"format": "cm3-reader-images-v1", "plan_sha256": plan_pin,
                "freeze_sha256": plan["freeze_sha256"],
                "entries": [{k: e[k] for k in ("id", "image", "image_sha256", "phase")} |
                            {"native_size": p["native_size"]} for e, p in zip(labels, plan["entries"])]}
    write_json(out / "images.json", exported)
    export_pin = steps.sha256(out / "images.json")
    write_json(out / "labels.json", {"plan_sha256": plan_pin, "export_sha256": export_pin, "entries": labels})
    return export_pin


def _hex_digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _load_export(plan, plan_pin, export_path, export_pin, freeze_pin):
    require(_hex_digest(plan_pin) and digest(plan) == plan_pin, "private sample plan pin mismatch")
    require(plan.get("cohort") == TRAIN_PINS and plan.get("freeze_sha256") == freeze_pin,
            "precheck must use frozen training plan")
    require(_hex_digest(export_pin) and steps.sha256(export_path) == export_pin, "export manifest pin mismatch")
    exported = json.loads(Path(export_path).read_text(encoding="utf-8"))
    require(exported.get("format") == "cm3-reader-images-v1" and exported.get("plan_sha256") == plan_pin
            and exported.get("freeze_sha256") == freeze_pin, "export plan/freeze mismatch")
    entries = exported["entries"]
    require(len(entries) == len(plan["entries"]) and len({e["id"] for e in entries}) == len(entries),
            "export entries must match exact plan")
    for e, p in zip(entries, plan["entries"]):
        require(e["id"] == p["id"] and e["image"] == p["id"] + ".png" and e["phase"] == p["phase"]
                and e["native_size"] == p["native_size"], "export entry differs from private plan")
        require(_hex_digest(e.get("image_sha256")), "export image digest missing/malformed")
    return exported


def _check_label_images(labels, exported):
    require(200 <= len(labels) <= len(exported["entries"]), "wrong inspected count")
    for label, image in zip(labels, exported["entries"]):
        require(label["id"] == image["id"], "labels must be inspected prefix")
        require(_hex_digest(label.get("image_sha256")), "label image digest missing/malformed")
        require(label["image_sha256"] == image["image_sha256"], "label image digest differs from export")


def _sealed_packet(plan, labels_path, seal_path, seal_pin, freeze_pin, *, plan_pin, export_path, export_pin):
    exported = _load_export(plan, plan_pin, export_path, export_pin, freeze_pin)
    require(steps.sha256(seal_path) == seal_pin, "label seal pin mismatch")
    seal = json.loads(Path(seal_path).read_text(encoding="utf-8"))
    require(seal.get("plan_sha256") == plan_pin and seal.get("freeze_sha256") == freeze_pin
            and seal.get("export_sha256") == export_pin, "label seal plan/export/freeze mismatch")
    require(steps.sha256(labels_path) == seal["adjudicated_sha256"], "labels changed after seal")
    doc = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    require(doc.get("plan_sha256") == plan_pin and doc.get("export_sha256") == export_pin, "label packet mismatch")
    labels = doc["entries"]
    _check_label_images(labels, exported)
    require(len(labels) == seal["inspected"], "seal inspected prefix mismatch")
    return exported, seal, labels


def predict_blind_packet(plan, packet_dir, labels_path, seal_path, seal_pin, freeze_path, freeze_pin,
                         out_path, *, plan_pin, export_path, export_pin):
    """Read the lossless native labeling PNGs only AFTER labels are sealed.

    Exclusively writes a private prediction artifact bound to the independently
    pinned export, sample plan, label seal, images and reader freeze. Returns its
    file SHA256; the scorer requires this pin, never a raw prediction dictionary.
    """
    import cv2
    import numpy as np
    frozen = load_freeze(freeze_path, freeze_pin)
    exported, seal, labels = _sealed_packet(plan, labels_path, seal_path, seal_pin, freeze_pin,
                                           plan_pin=plan_pin, export_path=export_path, export_pin=export_pin)
    predictions = {}
    for entry, label in zip(plan["entries"], labels):
        require(entry["id"] == label["id"], "inspected prefix changed")
        path = Path(packet_dir) / (entry["id"] + ".png")
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == label["image_sha256"], "blind native image changed")
        bgr = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        require(bgr is not None, "blind image decode failed")
        ref = entry["frame"]
        frame = NativeFrame(np.ascontiguousarray(bgr[:, :, ::-1]), ref["video_path"],
                            ref["frame_index"], ref["pts"], tuple(ref["timebase"]))
        predictions[entry["id"]] = read_native(frame, ref, native_size=entry["native_size"],
                                              layout=entry["layout"],
                                              unavailable=frozen["unavailable"][entry["layout"]])
    # Recheck immutable inputs after extraction, before publishing provenance.
    load_freeze(freeze_path, freeze_pin)
    _sealed_packet(plan, labels_path, seal_path, seal_pin, freeze_pin,
                   plan_pin=plan_pin, export_path=export_path, export_pin=export_pin)
    artifact = {"format": "cm3-reader-predictions-v1", "plan_sha256": plan_pin, "export_sha256": export_pin,
                "freeze_sha256": freeze_pin, "label_seal_sha256": seal_pin,
                "labels_sha256": seal["adjudicated_sha256"],
                "images": exported["entries"][:len(labels)], "values": predictions}
    write_json(out_path, artifact)
    return steps.sha256(out_path)


def coverage(labels, unavailable):
    supported = [f for f in FIELDS if f not in unavailable]
    counts = Counter()
    for label in labels:
        values = label["values"]
        for f in supported:
            v = values[f]
            if v is not None:
                require(valid(f, v), f"invalid human label: {f}")
                counts[f] += 1
                if f == "ult_ready" or f.endswith(".ready"):
                    counts[f + f"={v}"] += 1
        for name, field, maximum in (("low-web", "webs", 2), ("spent-swing", "swing.charges", 2),
                                     ("spent-combo", "amazing_combo.charges", 1)):
            if field in supported and values[field] is not None and values[field] <= maximum:
                counts[name] += 1
        for f in supported:
            if f.endswith(".cooldown") and values[f] is not None and values[f] > 0:
                counts[f + ">0"] += 1
    needed = {f: 20 for f in supported}
    for f in supported:
        if f == "ult_ready" or f.endswith(".ready"):
            needed.update({f + "=True": 5, f + "=False": 5})
        if f.endswith(".cooldown"):
            needed[f + ">0"] = 20
    for name, field in (("low-web", "webs"), ("spent-swing", "swing.charges"), ("spent-combo", "amazing_combo.charges")):
        if field in supported:
            needed[name] = 20
    return {"counts": dict(counts), "required": needed,
            "missing": {k: n-counts[k] for k, n in needed.items() if counts[k] < n}}


def seal_labels(plan, original_path, adjudicated_path, out_path, freeze_path, freeze_pin,
                *, plan_pin, export_path, export_pin):
    """Seal original AND final independent labels before accepting predictions.
    Final entries must be the base 200 plus an inspected reserve prefix. Null
    means explicitly unreadable/absent; complete=True is required on each entry.
    Preserve dispute explanations in adjudicated entries; never rewrite originals.
    """
    frozen = load_freeze(freeze_path, freeze_pin)
    exported = _load_export(plan, plan_pin, export_path, export_pin, freeze_pin)
    originals = json.loads(Path(original_path).read_text(encoding="utf-8"))
    final = json.loads(Path(adjudicated_path).read_text(encoding="utf-8"))
    for doc in (originals, final):
        require(doc["plan_sha256"] == plan_pin and doc.get("export_sha256") == export_pin, "label packet plan/export mismatch")
        _check_label_images(doc["entries"], exported)
        require(200 <= len(doc["entries"]) <= len(plan["entries"]), "wrong inspected count")
        for expected, entry in zip(plan["entries"], doc["entries"]):
            require(entry["id"] == expected["id"] and entry.get("complete") is True, "labels must be inspected prefix")
            require(set(entry["values"]) == set(FIELDS), "missing human field")
            require(all(v is None or valid(f, v) for f, v in entry["values"].items()), "invalid human values")
    require(len(originals["entries"]) == len(final["entries"]), "adjudication changed inspected set")
    for original, adjudicated in zip(originals["entries"], final["entries"]):
        if original["values"] != adjudicated["values"]:
            require(bool(adjudicated.get("adjudication_reason")), "changed labels need dispute explanation")
    unavailable = frozen["unavailable"]["mk"]
    # Stopping is based on the original blinded labels, never reader accuracy.
    for n in range(200, len(originals["entries"])):
        require(coverage(originals["entries"][:n], unavailable)["missing"], "continued past first quota completion")
    if coverage(originals["entries"], unavailable)["missing"]:
        require(len(originals["entries"]) == len(plan["entries"]), "reserve inspection stopped before exhaustion")
    receipt = {"plan_sha256": plan_pin, "export_sha256": export_pin, "freeze_sha256": freeze_pin,
               "original_sha256": steps.sha256(original_path), "adjudicated_sha256": steps.sha256(adjudicated_path),
               "inspected": len(final["entries"]), "coverage": coverage(final["entries"], unavailable)}
    write_json(out_path, receipt)
    return receipt


def score(plan, labels_path, seal_path, seal_pin, predictions_path, freeze_path, freeze_pin,
          *, predictions_pin, plan_pin, export_path, export_pin):
    """Accept only a hash-pinned prediction artifact from predict_blind_packet.
    Returns aggregate and per-session/stratum counters, ult-fill separately.
    A precheck is not P2' parity and this module issues no parity PASS.
    """
    frozen = load_freeze(freeze_path, freeze_pin)
    exported, seal, labels = _sealed_packet(plan, labels_path, seal_path, seal_pin, freeze_pin,
                                           plan_pin=plan_pin, export_path=export_path, export_pin=export_pin)
    require(isinstance(predictions_path, (str, Path)), "unbound prediction dictionary refused")
    require(_hex_digest(predictions_pin) and steps.sha256(predictions_path) == predictions_pin,
            "prediction artifact pin mismatch")
    artifact = json.loads(Path(predictions_path).read_text(encoding="utf-8"))
    bindings = {"format": "cm3-reader-predictions-v1", "plan_sha256": plan_pin, "export_sha256": export_pin,
                "freeze_sha256": freeze_pin, "label_seal_sha256": seal_pin,
                "labels_sha256": seal["adjudicated_sha256"], "images": exported["entries"][:len(labels)]}
    require(all(artifact.get(k) == v for k, v in bindings.items()), "prediction provenance differs from sealed packet")
    predictions = artifact["values"]
    require(set(predictions) == {e["id"] for e in labels}, "predictions must cover exact inspected set")
    by_id = {e["id"]: e for e in plan["entries"]}
    unavailable = frozen["unavailable"]["mk"]
    stats = defaultdict(lambda: defaultdict(Counter))
    for entry in labels:
        truth, pred = entry["values"], predictions[entry["id"]]
        require(set(pred) == set(FIELDS), "prediction schema mismatch")
        require(all(v is None or valid(f, v) for f, v in pred.items()), "invalid prediction domain")
        require(all(pred[f] is None for f in unavailable), "structural unavailable field emitted known")
        strata = set(entry.get("strata", []))
        for name, field, cap in (("low-web", "webs", 2), ("spent-swing", "swing.charges", 2),
                                 ("spent-combo", "amazing_combo.charges", 1)):
            if truth[field] is not None and truth[field] <= cap:
                strata.add(name)
        for f in FIELDS:
            if f.endswith(".cooldown") and truth[f] is not None and truth[f] > 0:
                strata.add(f + ">0")
        session = by_id[entry["id"]]["session"]
        groups = ["all", "session:" + session] + ["stratum:" + s for s in sorted(strata)]
        groups += ["session:" + session + "/stratum:" + s for s in sorted(strata)]
        for f in FIELDS:
            if f in unavailable:
                continue
            t, p = truth[f], pred[f]
            correct = t is not None and p is not None and (abs(t-p) <= .05 + 1e-12 if f == "ult_charge" else t == p)
            for group in groups:
                c = stats[group][f]
                c["total"] += 1
                c["legible"] += t is not None
                c["unknown"] += p is None
                c["unknown_legible"] += t is not None and p is None
                c["correct_known"] += correct
                wrong = t is not None and p is not None and not correct
                c["known_wrong"] += wrong
                c["unsafe_non_abstention"] += t is None and p is not None
                c["false_ready"] += wrong and (f == "ult_ready" or f.endswith(".ready")) and p is True
                c["false_zero"] += wrong and p == 0
                c["low_resource_error"] += wrong and bool(strata & {"low-web", "spent-swing", "spent-combo"})
    cov = coverage(labels, unavailable)
    failed = any(c["known_wrong"] or c["unsafe_non_abstention"] or
                 (c["legible"] and c["correct_known"] * 100 < c["legible"] * 95)
                 for c in stats["all"].values())
    report = {group: {f: {**c, "correct_known_share": c["correct_known"]/c["legible"] if c["legible"] else None,
                              "unknown_legible_share": c["unknown_legible"]/c["legible"] if c["legible"] else None}
                     for f, c in fields.items()} for group, fields in stats.items()}
    return {"status": "FAIL" if failed else "UNDECIDED" if cov["missing"] else "PASS",
            "coverage": cov, "counts": report, "structurally_unavailable": unavailable,
            "ult_fill": {"tolerance": .05, "counts": report["all"].get("ult_charge")},
            "plan_sha256": plan_pin, "export_sha256": export_pin, "label_seal_sha256": seal_pin,
            "freeze_sha256": freeze_pin, "predictions_sha256": predictions_pin, "parity": "NOT RUN"}
