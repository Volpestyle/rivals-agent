"""Synthetic-only expert behaviour admission, causal histories and tiny smoke fits."""
import copy
import json

import pytest

pytest.importorskip("mlx.core")
np = pytest.importorskip("numpy")
from policy import behaviour as b


@pytest.fixture(autouse=True)
def synthetic_root(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "ROOT", tmp_path.resolve())


def bounds(lo, hi=None, known=None):
    hi = lo if hi is None else hi
    return {"from": lo, "to": hi, "known_at": hi if known is None else known}


def label_evidence(c, t):
    # Only fixture construction: production normalization must retain audited bounds.
    for state, key in (("accepted_state", "accepted_evidence"), ("onset", "onset_evidence"),
                       ("continuation", "continuation_evidence"), ("context_state", "context_evidence")):
        c[key] = None if c[state] == "unknown" else bounds(t, t if state == "context_state" else t+2)


def fixture_export(tmp_path):
    """All payloads below tmp_path are generated noise, never corpus artifacts."""
    cache = tmp_path / b.CACHE
    cache.mkdir(parents=True)
    export = dict(task=b.TASK, training_authorized=True, clock="source_seconds", history_s=5,
                  horizon_s=2, frame_hz=10, sources={}, code_sha256=b.code_versions(), rows=[])
    for n, (sid, group) in enumerate(b.ALLOWED.items()):
        events = tmp_path / f"data/demos/events/sections/{sid}.jsonl"
        manifest = tmp_path / f"data/demos/vods/{sid}.manifest.jsonl"
        events.parent.mkdir(parents=True, exist_ok=True)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        events.write_text(json.dumps(dict(type="meta", format=5, writer="21a390f547eb", pts_origin_s=b.ORIGINS[sid],
                                               container_start_s=1.589 if n == 0 else 0.0))+"\n")
        manifest.write_text(json.dumps(dict(type="clip", id=sid, group=group, split="train", splittable=True,
                                           cooldowns="normal", patch="synthetic", events=f"../events/sections/{sid}.jsonl",
                                           media=dict(kind="video", path=f"{sid}.mp4")))+"\n")
        times = np.array([b.grid_time(0, i+50, b.CACHE_ORIGINS[sid]) for i in range(601)], np.float64)
        emb = np.random.default_rng(n).normal(n*30, 1, (len(times), 384)).astype(np.float32)
        np.savez(cache / f"{sid}.npz", t=times, emb=emb)
        creator = "daymr" if n == 0 else "reqmr"
        side = cache / f"{sid}.json"
        side.write_text(json.dumps(dict(id=sid, group=group, splittable=True, cooldowns="normal", patch="synthetic",
                                        encoder=b.DEFAULT, norm=b.NORM, size=b.SIZE, dim=384, hz=10,
                                        clock="media_pts", t_origin=b.CACHE_ORIGINS[sid], t_first=b.CACHE_ORIGINS[sid], masks=b.rects(creator),
                                        sidecar_version=b.SIDECAR_VERSION, media=f"data/demos/vods/{sid}.mp4")))
        export["sources"][sid] = dict(group=group, pts_offset=b.ORIGINS[sid],
                                     manifest=dict(path=str(manifest.relative_to(tmp_path)), sha256=b.digest(manifest)),
                                     events=dict(path=str(events.relative_to(tmp_path)), sha256=b.digest(events)),
                                     cache_sidecar_sha256=b.digest(side), cache_sha256=b.digest(cache / f"{sid}.npz"))
        for j, t in enumerate((6., 20., 34., 48.)):
            positive = j % 2 == 1
            channels = {}
            for c in b.NAMES:
                channels[c] = dict(accepted_state="present" if positive else "absent", imitation_mask=True,
                                   onset="present" if j == 1 else "absent", onset_bounds=[t+.1, t+.3] if j == 1 else None,
                                   continuation="present" if j == 3 else "absent",
                                   context_state="present" if j == 3 else "absent")
            channels["traversing_without_visible_enemy"].update(
                accepted_state="absent" if positive else "present", onset="absent", onset_bounds=None,
                continuation="absent" if positive else "present", context_state="absent" if positive else "present")
            # Away is entirely unknown: it must not acquire negative supervision.
            channels["moving_away"].update(accepted_state="unknown", imitation_mask=False, onset="unknown",
                                           onset_bounds=None, continuation="unknown", context_state="unknown")
            for c in channels.values():
                if c["context_state"] != "absent":
                    c.update(onset="unknown", onset_bounds=None)
                if c["context_state"] != "present":
                    c["continuation"] = "unknown"
                label_evidence(c, t)
            export["rows"].append(dict(id=f"synthetic-{n}-{j}", source=sid, t=t, eligible=True,
                                       training_authorized=True, evidence_from=t-5, evidence_to=t+5, label_known_at=t+2,
                                       context=[dict(scene_masked=False, evidence=bounds(b.grid_time(t, i))) for i in range(51)],
                                       channels=channels, recent_attack=[dict(present=None, evidence=None)]*2))
    path = tmp_path / "export.json"
    path.write_text(json.dumps(export))
    return path, cache, export


@pytest.mark.parametrize("mutation", ["unauthorized", "missing_auth", "source", "row_source", "task", "horizon",
                                     "clock", "nan_time", "bool_time", "mask", "future_mask", "future_baseline",
                                     "label_future", "onset_future", "label_mask", "no_support", "code", "extra_input"])
def test_refusal_before_payload(tmp_path, monkeypatch, mutation):
    path, cache, e = fixture_export(tmp_path)
    r = e["rows"][0]
    if mutation == "unauthorized": e["training_authorized"] = False
    elif mutation == "missing_auth": del e["training_authorized"]
    elif mutation == "source": e["sources"]["sealed"] = e["sources"].pop(next(iter(b.ALLOWED)))
    elif mutation == "row_source": r["source"] = "unapproved"
    elif mutation == "task": e["task"] = "old-task"
    elif mutation == "horizon": e["horizon_s"] = 1
    elif mutation == "clock": e["clock"] = "native"
    elif mutation == "nan_time": r["t"] = float("nan")
    elif mutation == "bool_time": r["t"] = True
    elif mutation == "mask": r["context"][0]["scene_masked"] = 1
    elif mutation == "future_mask": r["context"][0]["evidence"]["known_at"] = r["t"]+1
    elif mutation == "future_baseline": r["recent_attack"][0] = dict(present=True, evidence=bounds(r["t"]-1, r["t"], r["t"]+1))
    elif mutation == "label_future": r["label_known_at"] = r["evidence_to"]+1
    elif mutation == "onset_future": e["rows"][1]["channels"]["attacking"]["onset_bounds"][1] = 24
    elif mutation == "label_mask": r["channels"]["moving_away"]["imitation_mask"] = True
    elif mutation == "no_support": e["rows"] = []
    elif mutation == "code": e["code_sha256"]["policy/train.py"] = "0"*64
    elif mutation == "extra_input": r["outcome_embedding"] = [1]*384
    path.write_text(json.dumps(e))
    monkeypatch.setattr(np, "load", lambda *a, **kw: pytest.fail("payload opened before admission"))
    monkeypatch.setattr(b, "checked_file", lambda *a: pytest.fail("source evidence opened before structural admission"))
    with pytest.raises(ValueError):
        b.run(path, cache, tmp_path / "out", smoke_fit=True)
    assert not (tmp_path / "out").exists()


def test_source_freshness_and_canary_refusal(tmp_path, monkeypatch):
    path, cache, e = fixture_export(tmp_path)
    monkeypatch.setattr(np, "load", lambda *a, **kw: pytest.fail("payload opened"))
    sid = next(iter(b.ALLOWED))
    e["sources"][sid]["manifest"]["sha256"] = "0"*64
    path.write_text(json.dumps(e))
    with pytest.raises(ValueError, match="stale evidence"):
        b.run(path, cache, tmp_path / "out")
    path.write_text(json.dumps(dict(training_authorized=False, rows=[dict(training_authorized=False)])))
    with pytest.raises(ValueError, match="training_authorized"):
        b.run(path, cache, tmp_path / "out", True)


def test_causal_clock_future_append_and_label_invariance(tmp_path):
    path, cache, e = fixture_export(tmp_path)
    admitted = b.admit(path, cache)
    before = b.histories(admitted, cache)
    for sid in b.ALLOWED:
        payload = cache / f"{sid}.npz"
        with np.load(payload) as z:
            t, emb = z["t"], z["emb"]
        # All appended frames are later than every decision; their values must not matter.
        np.savez(payload, t=np.append(t, b.grid_time(70, offset=b.CACHE_ORIGINS[sid])), emb=np.vstack((emb, np.full((1, 384), 1e6))))
        e["sources"][sid]["cache_sha256"] = b.digest(payload)
    e["rows"][0]["channels"]["attacking"]["accepted_state"] = "present"
    e["rows"][0]["channels"]["attacking"]["onset"] = "unknown"
    e["rows"][0]["label_known_at"] += 1
    label_evidence(e["rows"][0]["channels"]["attacking"], e["rows"][0]["t"])
    path.write_text(json.dumps(e))
    after = b.histories(b.admit(path, cache), cache)
    np.testing.assert_array_equal(before, after)
    for i, r in enumerate(e["rows"]):
        with np.load(cache / f'{r["source"]}.npz') as z:
            times = z["t"]
            idx = np.searchsorted(times, b.grid_time(r["t"], offset=b.CACHE_ORIGINS[r["source"]]), side="right")-1
            np.testing.assert_array_equal(after[i, -1, :384], z["emb"][idx])
        assert (after[i, :, 384:] == [1, 0]).all()


def test_masks_missing_fit_classes_and_onset_reports(tmp_path):
    _, _, e = fixture_export(tmp_path)
    rows = e["rows"]
    rows[0]["eligible"] = False
    for c in rows[0]["channels"].values(): c["imitation_mask"] = False
    y, mask = b.targets(rows)
    assert not mask[0].any() and not mask[:, 2].any()
    supported, _, weights = b.statistics(y, mask)
    assert supported.tolist() == [True, True, False, True]
    mx = b.mx
    class Constant:
        def __call__(self, x): return x
    logits = mx.zeros((len(rows), 4))
    original = b.masked_loss(Constant(), logits, mx.array(y), mx.array(mask), mx.array(weights))
    changed = y.copy()
    changed[~mask] = 1-changed[~mask]
    actual = b.masked_loss(Constant(), logits, mx.array(changed), mx.array(mask), mx.array(weights))
    assert float(original) == float(actual)
    grads = mx.grad(lambda v: b.masked_loss(Constant(), v, mx.array(y), mx.array(mask), mx.array(weights)))(logits)
    assert (np.asarray(grads)[~mask] == 0).all()
    report = b.stratified_scores(rows, y, mask, np.ones_like(y))
    assert report["occurrence"]["attacking"]["positive"] == 4
    assert report["onset"]["attacking"]["positive"] == 2
    assert report["onset"]["attacking"]["negative"] == 3  # one ineligible control; continuations excluded
    assert report["continuation"]["attacking"]["positive"] == 2
    assert report["continuation"]["attacking"]["negative"] == 0
    assert report["occurrence"]["moving_away"]["balanced_accuracy"] is None


def test_fold_local_normalization_and_full_reservations(tmp_path):
    path, cache, e = fixture_export(tmp_path)
    x = b.histories(b.admit(path, cache), cache)
    tr, te = b.split(e["rows"], next(iter(b.ALLOWED)))
    mean, scale = b.normalization(x[tr])
    changed = x.copy()
    changed[te, :, :384] += 1e6
    mean2, scale2 = b.normalization(changed[tr])
    np.testing.assert_array_equal(mean, mean2)
    np.testing.assert_array_equal(scale, scale2)
    normalized = b.normalize(x[tr], mean, scale)
    np.testing.assert_allclose(normalized[..., :384].mean((0, 1)), 0, atol=3e-5)
    np.testing.assert_array_equal(normalized[..., 384:], x[tr, :, 384:])
    rows = copy.deepcopy(e["rows"][:2])
    rows[1]["evidence_from"] = rows[0]["evidence_to"]
    assert b.independent_count(rows) == 1  # touching full evidence footprints merge
    rows.append(copy.deepcopy(rows[1]))
    rows[-1]["evidence_from"] = rows[1]["evidence_to"]
    rows[-1]["evidence_to"] += 10
    assert b.independent_count(rows) == 1  # transitive overlap, not just pairwise dedupe
    assert b.support(rows)[next(iter(b.ALLOWED))]["attacking"]["independent_positive"] == 0
    assert b.support(rows)[next(iter(b.ALLOWED))]["attacking"]["mixed_clusters"] == 1
    assert b.support(e["rows"])[next(iter(b.ALLOWED))]["attacking"]["independent_positive"] == 2


def test_synthetic_smoke_reload_and_no_performance_claim(tmp_path, monkeypatch):
    path, cache, e = fixture_export(tmp_path)
    # Synthetic optimization only; the actual CLI has no epoch/seed tuning flags.
    monkeypatch.setattr(b, "RECIPE", dict(b.RECIPE, epochs=1, hidden=8))
    out = tmp_path / "smoke"
    b.run(path, cache, out, smoke_fit=True)
    x = b.histories(b.admit(path, cache), cache)
    for sid in b.ALLOWED:
        folder = out / sid
        report = b.read_json(folder / "report.json")
        assert report["mode"] == "pipeline_smoke_only" and report["performance_claim"] is False
        assert report["fit_supported"][2] is False and report["reload_exact"] is True
        _, te = b.split(e["rows"], sid)
        with np.load(folder / "predictions.npz") as z:
            np.testing.assert_array_equal(b.reload_predictions(folder, x[te]), z["probabilities"])
            assert not z["label_mask"][:, 2].any()
        assert {"context_persistence", "decision_frame", "nuisance_only", "attack_event_1s"} <= set(report["baselines"])
    with pytest.raises(ValueError, match="fresh output"):
        b.run(path, cache, out, True)


@pytest.mark.parametrize("mutation", ["origin", "sidecar", "payload", "cache_nan", "negative_coverage", "incompatible"])
def test_provenance_and_evidence_fail_closed(tmp_path, mutation):
    path, cache, e = fixture_export(tmp_path)
    sid = next(iter(b.ALLOWED))
    if mutation == "origin": e["sources"][sid]["pts_offset"] = 0
    elif mutation == "sidecar": (cache / f"{sid}.json").write_text("{}")
    elif mutation == "payload": e["sources"][sid]["cache_sha256"] = "0"*64
    elif mutation == "cache_nan":
        payload = cache / f"{sid}.npz"
        with np.load(payload) as z: t, emb = z["t"], z["emb"]
        t[-1] = np.nan
        np.savez(payload, t=t, emb=emb)
        e["sources"][sid]["cache_sha256"] = b.digest(payload)
    elif mutation == "negative_coverage": e["rows"][0]["label_known_at"] = e["rows"][0]["t"]+.5
    elif mutation == "incompatible": e["rows"][0]["channels"][b.NAMES[0]]["accepted_state"] = "present"
    path.write_text(json.dumps(e))
    with pytest.raises(ValueError):
        b.histories(b.admit(path, cache), cache)


def test_unsupported_smoke_opens_no_embeddings(tmp_path, monkeypatch):
    path, cache, e = fixture_export(tmp_path)
    for r in e["rows"]:
        for c in r["channels"].values():
            c.update(accepted_state="absent", imitation_mask=True, onset="absent", onset_bounds=None,
                     continuation="unknown", context_state="absent")
            label_evidence(c, r["t"])
    path.write_text(json.dumps(e))
    monkeypatch.setattr(np, "load", lambda *a, **kw: pytest.fail("no supported fold: payload must stay closed"))
    out = tmp_path / "unsupported"
    b.run(path, cache, out, True)
    assert set(b.read_json(out / "fit-status.json").values()) == {"unsupported_no_fit_or_held_classes"}


@pytest.mark.parametrize("mutation", ["manifest_path", "events_path", "manifest_link", "events_link", "media_link",
                                     "sidecar_link", "payload_link", "ancestor_link", "cache_root_link", "cache_argument"])
def test_complete_binding_before_any_artifact_read(tmp_path, monkeypatch, mutation):
    path, cache, e = fixture_export(tmp_path)
    admitted = b.admit(path, cache)  # Canonical tree is the valid control.
    sid = list(b.ALLOWED)[-1]  # Even the first source must stay unopened on second-source refusal.
    src = e["sources"][sid]
    sentinel = tmp_path / "unapproved"
    sentinel.write_text("synthetic forbidden content")
    if mutation.endswith("_path"):
        kind = mutation.removesuffix("_path")
        src[kind]["path"] = str(sentinel)
        if kind == "events":
            manifest = tmp_path / src["manifest"]["path"]
            header = b.read_json(manifest)
            header["events"] = str(sentinel)  # Agreement with the header is not authority.
            manifest.write_text(json.dumps(header))
            src["manifest"]["sha256"] = b.digest(manifest)
    elif mutation == "cache_argument":
        cache = tmp_path / "other-cache"
    elif mutation in ("ancestor_link", "cache_root_link"):
        target = tmp_path / "data/demos" if mutation == "ancestor_link" else cache
        moved = tmp_path / "moved"
        target.rename(moved)
        target.symlink_to(moved, target_is_directory=True)
    else:
        target = {"manifest_link": tmp_path / src["manifest"]["path"],
                  "events_link": tmp_path / src["events"]["path"],
                  "media_link": tmp_path / f"data/demos/vods/{sid}.mp4",
                  "sidecar_link": cache / f"{sid}.json", "payload_link": cache / f"{sid}.npz"}[mutation]
        target.unlink(missing_ok=True)
        target.symlink_to(sentinel)
    path.write_text(json.dumps(e))
    original_digest = b.digest
    def guard(p):
        assert not p.is_relative_to(tmp_path), f"artifact hashed before binding: {p}"
        return original_digest(p)
    monkeypatch.setattr(b, "digest", guard)
    monkeypatch.setattr(np, "load", lambda *a, **k: pytest.fail("array opened before binding"))
    with pytest.raises(ValueError, match="canonical|symlink"):
        b.admit(path, cache)
    # Binding is checked again at the actual payload boundary, including metadata paths.
    admitted["sources"] = e["sources"]
    with pytest.raises(ValueError, match="canonical|symlink"):
        b.histories(admitted, cache)


@pytest.mark.parametrize("sid", list(b.ALLOWED))
def test_native_cutoff_nextafter_and_maximum_age(tmp_path, sid):
    path, cache, e = fixture_export(tmp_path)
    before = b.histories(b.admit(path, cache), cache)
    row = next(i for i, r in enumerate(e["rows"]) if r["source"] == sid)
    payload = cache / f"{sid}.npz"
    with np.load(payload) as z:
        times, emb = z["t"], z["emb"]
    cutoff = b.grid_time(4.0, offset=b.CACHE_ORIGINS[sid])
    exact = np.flatnonzero(times == cutoff)[0]
    np.testing.assert_array_equal(before[row, 30, :384], emb[exact])
    future = np.nextafter(cutoff, np.inf)
    assert future > cutoff
    times = np.append(times, future)
    emb = np.vstack((emb, np.full((1, 384), 777, np.float32)))
    order = np.argsort(times)
    np.savez(payload, t=times[order], emb=emb[order])
    e["sources"][sid]["cache_sha256"] = b.digest(payload)
    path.write_text(json.dumps(e))
    after = b.histories(b.admit(path, cache), cache)
    np.testing.assert_array_equal(before[row, 30], after[row, 30])
    keep = (times < cutoff-.2) | (times > cutoff)
    np.savez(payload, t=times[keep][np.argsort(times[keep])], emb=emb[keep][np.argsort(times[keep])])
    e["sources"][sid]["cache_sha256"] = b.digest(payload)
    path.write_text(json.dumps(e))
    with pytest.raises(ValueError, match="unmasked cache miss"):
        b.histories(b.admit(path, cache), cache)


@pytest.mark.parametrize("mutation", ["observation_start", "context_point", "context_start", "baseline_point",
                                     "baseline_start", "baseline_short", "label_start", "label_late", "unknown_evidence"])
def test_evidence_envelope_and_lookback(tmp_path, mutation):
    path, cache, e = fixture_export(tmp_path)
    r = e["rows"][0]
    t = r["t"]
    r["recent_attack"] = [dict(present=True, evidence=bounds(t-1, t)),
                          dict(present=False, evidence=bounds(t-5, t))]
    path.write_text(json.dumps(e))
    b.admit(path, cache)  # Concrete positive/negative baselines preserve the full lookback.
    c = r["channels"]["attacking"]
    if mutation == "observation_start": r["context"][0]["evidence"]["from"] = 0
    elif mutation == "context_point": c["context_evidence"] = bounds(0)
    elif mutation == "context_start": c["context_evidence"]["from"] = 0
    elif mutation == "baseline_point": r["recent_attack"][0]["evidence"] = bounds(0)
    elif mutation == "baseline_start": r["recent_attack"][1]["evidence"]["from"] = 0
    elif mutation == "baseline_short": r["recent_attack"][1]["evidence"]["from"] = t-4
    elif mutation == "label_start": c["accepted_evidence"]["from"] = 0
    elif mutation == "label_late": c["accepted_evidence"]["known_at"] = r["evidence_to"]+1
    elif mutation == "unknown_evidence": r["channels"]["moving_away"]["context_evidence"] = bounds(t)
    path.write_text(json.dumps(e))
    with pytest.raises(ValueError, match="evidence|lookback"):
        b.admit(path, cache)


@pytest.mark.parametrize("mutation", ["onset_contradiction", "continuation_contradiction", "occurrence_short",
                                     "onset_short", "continuation_short"])
def test_conditional_assertions_need_their_own_coverage(tmp_path, mutation):
    path, cache, e = fixture_export(tmp_path)
    r = e["rows"][0]
    t, c = r["t"], r["channels"]["attacking"]
    if mutation.startswith("continuation"):
        c.update(context_state="present", onset="unknown", continuation="absent")
        label_evidence(c, t)
    path.write_text(json.dumps(e))
    b.admit(path, cache)  # Full-horizon absence is a valid conditional negative.
    y, mask = b.targets([r])
    label = "continuation" if mutation.startswith("continuation") else "onset"
    report = b.stratified_scores([r], y, mask, np.zeros((1, 4)))
    assert report[label]["attacking"]["tn"] == 1
    if mutation.endswith("contradiction"):
        c["accepted_state"] = "present"  # All bounds stay valid: semantic contradiction alone must fail.
        r["channels"][b.NAMES[3]]["accepted_state"] = "unknown"
        r["channels"][b.NAMES[3]]["imitation_mask"] = False
        r["channels"][b.NAMES[3]]["continuation"] = "unknown"
        label_evidence(r["channels"][b.NAMES[3]], t)
    else:
        key = "accepted_evidence" if mutation == "occurrence_short" else f"{label}_evidence"
        c[key] = bounds(t, t+.5)
        # Row and other channels still have full-horizon evidence; they cannot certify this cell.
        assert r["label_known_at"] == t+2
    path.write_text(json.dumps(e))
    with pytest.raises(ValueError, match="contradicts|own complete"):
        b.admit(path, cache)


def test_positive_onset_and_unknown_are_not_negative_controls(tmp_path):
    path, cache, e = fixture_export(tmp_path)
    r = e["rows"][1]
    c, t = r["channels"]["attacking"], r["t"]
    c["accepted_evidence"] = bounds(t+.1, t+.3, t+.5)
    c["onset_evidence"] = bounds(t+.1, t+.3, t+.5)
    path.write_text(json.dumps(e))
    b.admit(path, cache)
    y, mask = b.targets([r])
    assert b.stratified_scores([r], y, mask, np.ones((1, 4)))["onset"]["attacking"]["tp"] == 1
    c.update(onset="unknown", onset_bounds=None, onset_evidence=None)
    path.write_text(json.dumps(e))
    b.admit(path, cache)
    metric = b.stratified_scores([r], y, mask, np.zeros((1, 4)))["onset"]["attacking"]
    assert metric["positive"] == metric["negative"] == 0


def test_payload_refusal_preserves_outputs(tmp_path):
    path, cache, e = fixture_export(tmp_path)
    e["sources"][next(iter(b.ALLOWED))]["cache_sha256"] = "0"*64
    path.write_text(json.dumps(e))
    out = tmp_path / "output"
    with pytest.raises(ValueError, match="stale embedding"):
        b.run(path, cache, out, True)
    assert not out.exists()
    out.mkdir()
    sentinel = out / "keep"
    sentinel.write_text("unchanged")
    with pytest.raises(ValueError, match="fresh output"):
        b.run(path, cache, out, True)
    assert list(out.iterdir()) == [sentinel] and sentinel.read_text() == "unchanged"


def test_actual_sidecar_producer_and_rehashed_bad_masks(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from policy import encode
    path, cache, e = fixture_export(tmp_path)
    monkeypatch.setattr(encode, "ROOT", b.ROOT)
    for n, (sid, group) in enumerate(b.ALLOWED.items()):
        source = SimpleNamespace(id=sid, kind="vod", creator="daymr" if n == 0 else "reqmr", group=group,
                                 cooldowns="normal", cooldowns_evidence="synthetic", patch="synthetic",
                                 patch_evidence="synthetic", recorder=None,
                                 path=b.ROOT / f"data/demos/vods/{sid}.mp4", fps=60, upload_date="20260901",
                                 edited=False, splittable=True, is_video=True)
        with np.load(cache / f"{sid}.npz") as z:
            side = encode.sidecar(source, b.DEFAULT, 384, 10, z["emb"], z["t"])
        file = cache / f"{sid}.json"
        file.write_text(json.dumps(side))
        e["sources"][sid]["cache_sidecar_sha256"] = b.digest(file)
    path.write_text(json.dumps(e))
    b.admit(path, cache)
    side["masks"] = []
    file.write_text(json.dumps(side))
    e["sources"][sid]["cache_sidecar_sha256"] = b.digest(file)
    path.write_text(json.dumps(e))
    monkeypatch.setattr(np, "load", lambda *a, **k: pytest.fail("bad sidecar opened arrays"))
    with pytest.raises(ValueError, match="cache provenance"):
        b.admit(path, cache)


@pytest.mark.parametrize("mutation", ["string", "missing_kind", "wrong_kind", "missing_path", "null_path",
                                     "number_path", "redirect"])
def test_manifest_video_header_shape_and_identity(tmp_path, monkeypatch, mutation):
    path, cache, e = fixture_export(tmp_path)
    b.admit(path, cache)  # The loader's actual {kind: video, path: ...} shape is accepted.
    sid = next(iter(b.ALLOWED))
    manifest = tmp_path / e["sources"][sid]["manifest"]["path"]
    header = b.read_json(manifest)
    media = header["media"]
    if mutation == "string": header["media"] = media["path"]
    elif mutation == "missing_kind": del media["kind"]
    elif mutation == "wrong_kind": media["kind"] = "frames"
    elif mutation == "missing_path": del media["path"]
    elif mutation == "null_path": media["path"] = None
    elif mutation == "number_path": media["path"] = 12
    elif mutation == "redirect": media["path"] = "unapproved.mp4"
    manifest.write_text(json.dumps(header)+"\n")
    e["sources"][sid]["manifest"]["sha256"] = b.digest(manifest)
    path.write_text(json.dumps(e))
    original_digest = b.digest
    def guard(p):
        assert p == manifest or not p.is_relative_to(tmp_path), "content read after malformed media header"
        return original_digest(p)
    monkeypatch.setattr(b, "digest", guard)
    monkeypatch.setattr(np, "load", lambda *a, **k: pytest.fail("bad media header opened arrays"))
    with pytest.raises(ValueError, match="manifest media identity mismatch"):
        b.admit(path, cache)


@pytest.mark.parametrize("mutation", ["missing_container", "unknown_container", "wrong_container", "side_origin", "side_first", "array_first"])
def test_rebased_clock_contract(tmp_path, mutation):
    path, cache, e = fixture_export(tmp_path)
    b.admit(path, cache)
    sid = next(iter(b.ALLOWED))
    if mutation in ("missing_container", "unknown_container", "wrong_container"):
        file = tmp_path / e["sources"][sid]["events"]["path"]
        meta = b.read_json(file)
        if mutation == "missing_container": del meta["container_start_s"]
        else: meta["container_start_s"] = None if mutation == "unknown_container" else 0.0
        file.write_text(json.dumps(meta)+"\n")
        e["sources"][sid]["events"]["sha256"] = b.digest(file)
    elif mutation in ("side_origin", "side_first"):
        file = cache / f"{sid}.json"
        side = b.read_json(file)
        side["t_origin" if mutation == "side_origin" else "t_first"] = b.ORIGINS[sid]
        file.write_text(json.dumps(side))
        e["sources"][sid]["cache_sidecar_sha256"] = b.digest(file)
    else:
        file = cache / f"{sid}.npz"
        with np.load(file) as z: times, emb = z["t"], z["emb"]
        times[0] = np.nextafter(times[0], np.inf)
        np.savez(file, t=times, emb=emb)
        e["sources"][sid]["cache_sha256"] = b.digest(file)
    path.write_text(json.dumps(e))
    with pytest.raises(ValueError, match="timestamp|clock"):
        b.histories(b.admit(path, cache), cache)


@pytest.mark.parametrize("decision,previous_bug", [(135.2, True), (177.7, True), (208.3, False)])
def test_declared_grid_first_frame_and_no_substitution(decision, previous_bug):
    sid = next(iter(b.ALLOWED))
    row = dict(source=sid, t=decision, evidence_from=decision-5)
    origin = b.CACHE_ORIGINS[sid]
    times = np.array([b.grid_time(decision, i, origin) for i in (-1, 0, 1)])
    old = int(np.searchsorted(times, decision-5+origin, side="right"))-1
    assert (old == 0) == previous_bug  # pt2-02/04 failures and pt2-05 valid control.
    assert b.context_index(times, row, 0) == 1
    assert b.context_index(times, row, 1) == 2
    assert b.context_index(times[:2], row, 1) is None  # In-reservation predecessor is uninspected for this step.
    assert b.grid_time(decision, 0) == float(str(decision-5))
