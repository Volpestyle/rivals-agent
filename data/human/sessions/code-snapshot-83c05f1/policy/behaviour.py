"""Accepted expert future-behaviour exports -> offline forecasts. Never sends input.

Default: validate admission and report support without opening embedding payloads.
--smoke-fit: fixed H2 recipe, whole-session folds, descriptive comparisons only.
The normalized export contract is documented in docs/lanes/policy.md.
"""
import argparse
from decimal import Decimal
import json
import math
import os
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np

from agent.demos import producer_rule
from .b0 import ALLOWED, CONFIG, digest, write_json
from .encode import DEFAULT, SIDECAR_VERSION
from .frames import NORM, SIZE, rects
from .train import Head, MATCH_S, step_row

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path("data/embeddings/vit_small_patch16_224-dino-n1-10hz")
TASK = "expert-next-behaviour-v1"
NAMES = ("approaching_visible_enemy", "attacking", "moving_away", "traversing_without_visible_enemy")
STATES = ("present", "absent", "unknown")
ORIGINS = dict(zip(ALLOWED, (1.616, 0.0)))
CACHE_ORIGINS = dict(zip(ALLOWED, (0.027, 0.0)))
CODE = ("policy/behaviour.py", "policy/train.py", "policy/encode.py", "policy/frames.py",
        "policy/b0.py", "agent/demos.py", "perception/events.py", "perception/hud.py",
        "perception/scoreboard.py")
RECIPE = {k: CONFIG[k] for k in ("seed", "epochs", "batch", "lr", "hidden")}
GATES = dict(positive=20, negative=20, balanced_accuracy=.75, each_recall=.70,
             improvement=.10, paired_cluster_interval_lower_bound=0, purge_margin_s=5)


def code_versions():
    return {p: digest(Path(__file__).resolve().parent.parent / p) for p in CODE}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    require(type(value) in (int, float) and math.isfinite(value), "finite numeric timestamp required")
    return value


def grid_time(t, step=50, offset=0):
    """Declared decimal 10 Hz grid; convert once, after adding the clock offset."""
    return float(Decimal(str(t))-5+Decimal(step)/10+Decimal(str(offset)))


def validate_cache_times(times, sid):
    require(times.ndim == 1 and len(times) > 0 and np.isfinite(times).all()
            and (np.diff(times) > 0).all(), "malformed cache timestamps")
    require(times[0] == CACHE_ORIGINS[sid] and times[-1] <= grid_time(900, offset=CACHE_ORIGINS[sid]),
            "cache timestamps outside source")


def context_index(times, row, step):
    origin = CACHE_ORIGINS[row["source"]]
    cutoff = grid_time(row["t"], step, origin)
    lower = grid_time(row["evidence_from"], offset=origin)
    j = int(np.searchsorted(times, cutoff, side="right"))-1
    if j >= 0 and lower <= float(times[j]) <= cutoff and cutoff-float(times[j]) <= MATCH_S:
        # The observation mask describes this exact inspected grid frame, not its predecessor.
        if float(times[j]) == cutoff:
            return j
    return None


def fields(obj, names):
    require(isinstance(obj, dict) and set(obj) == set(names.split()), "unexpected or missing export fields")


def read_json(path):
    return json.loads(Path(path).read_text())


def bindings(export, cache_dir):
    """Check the complete fixed source scope without opening artifact contents."""
    require(Path(cache_dir).absolute() == ROOT / CACHE, "noncanonical cache root")
    require(set(export["sources"]) == set(ALLOWED), "exact promoted source IDs required")
    for sid, src in export["sources"].items():
        fields(src, "group pts_offset manifest events cache_sidecar_sha256 cache_sha256")
        require(src["group"] == ALLOWED[sid] and number(src["pts_offset"]) == ORIGINS[sid], "source group/clock mismatch")
        for kind, relative in (("manifest", f"data/demos/vods/{sid}.manifest.jsonl"),
                               ("events", f"data/demos/events/sections/{sid}.jsonl")):
            fields(src[kind], "path sha256")
            require(src[kind]["path"] == relative, f"noncanonical {kind} path")
        for fingerprint in (src["manifest"]["sha256"], src["events"]["sha256"],
                            src["cache_sidecar_sha256"], src["cache_sha256"]):
            require(isinstance(fingerprint, str) and len(fingerprint) == 64
                    and all(x in "0123456789abcdef" for x in fingerprint), "invalid fingerprint")
        paths = [ROOT / src[k]["path"] for k in ("manifest", "events")]
        paths += [ROOT / f"data/demos/vods/{sid}.mp4", ROOT / CACHE / f"{sid}.json", ROOT / CACHE / f"{sid}.npz"]
        for path in paths:
            require(not any(p.is_symlink() for p in (path, *path.parents)), "symlink artifact binding")


def checked_file(record):
    path = ROOT / record["path"]  # bindings() has already checked every artifact.
    require(digest(path) == record["sha256"], f"stale evidence: {path}")
    return path


def evidence(value, row, cutoff):
    """Bounds retain every used point/span; known_at is availability, not coverage."""
    fields(value, "from to known_at")
    lo, hi, known = (number(value[k]) for k in ("from", "to", "known_at"))
    require(row["evidence_from"] <= lo <= hi <= known <= min(cutoff, row["evidence_to"]),
            "evidence outside reservation/availability")
    return lo, hi


def channel_evidence(c, r):
    t = r["t"]
    for state, key in (("accepted_state", "accepted_evidence"), ("onset", "onset_evidence"),
                       ("continuation", "continuation_evidence"), ("context_state", "context_evidence")):
        if c[state] == "unknown":
            require(c[key] is None, "unknown assertion must have null evidence")
            continue
        lo, hi = evidence(c[key], r, t if state == "context_state" else r["label_known_at"])
        if state == "context_state":
            require(lo <= t == hi, "context evidence must cover decision")
        elif c[state] == "absent":
            require(lo <= t and hi >= t+2, "negative needs its own complete future coverage")
        else:
            require(lo <= t+2 and hi > t, "positive needs future evidence")
        if state in ("onset", "continuation"):
            context = "absent" if state == "onset" else "present"
            require(c["context_state"] == context, "conditional assertion has wrong/unknown context")
            require(c["accepted_state"] == c[state], "conditional assertion contradicts occurrence")
            if state == "onset" and c[state] == "present":
                require(lo <= c["onset_bounds"][0] < c["onset_bounds"][1] <= hi,
                        "onset bounds exceed own evidence")
            if state == "continuation" and c[state] == "present":
                require(lo <= t < hi, "continuation evidence must cross decision")


def admit(path, cache_dir):
    """Validate the ENTIRE export before any cache sidecar or payload access.

    The lead supplies this normalized, explicitly authorized export, not seat files.
    Hashes establish freshness, not semantic truth or authorization authenticity.
    """
    path, cache_dir = Path(path), Path(cache_dir)
    export = read_json(path)
    require(isinstance(export, dict), "export must be an object")
    require(export.get("training_authorized") is True, "training_authorized must be true before payload access")
    fields(export, "task training_authorized clock history_s horizon_s frame_hz sources code_sha256 rows")
    require(export["task"] == TASK and export["clock"] == "source_seconds", "unrecognized task/clock")
    require([number(export[k]) for k in ("history_s", "horizon_s", "frame_hz")] == [5, 2, 10],
            "unrecognized history/horizon/grid")
    require(isinstance(export["sources"], dict) and set(export["sources"]) == set(ALLOWED), "exact promoted source IDs required")
    require(isinstance(export["rows"], list) and bool(export["rows"]), "absent labels/support")
    require(all(isinstance(r, dict) and r.get("source") in ALLOWED for r in export["rows"]), "unapproved row source")
    require(export["code_sha256"] == code_versions(), "stale code evidence")
    seen = set()
    for r in export["rows"]:
        fields(r, "id source t eligible training_authorized evidence_from evidence_to label_known_at context channels recent_attack")
        require(isinstance(r["id"], str) and r["id"], "row id required")
        require(r["training_authorized"] is True, "row training_authorized must be true")
        require(type(r["eligible"]) is bool, "eligible must be boolean")
        t = number(r["t"])
        require(5 <= t <= 895, "decision outside retained source")
        require(0 <= number(r["evidence_from"]) <= t-5 and t+5 <= number(r["evidence_to"]) <= 900,
                "full evidence reservation must include [t-5,t+5]")
        require(t <= number(r["label_known_at"]) <= r["evidence_to"], "label lookahead exceeds reservation")
        key = (r["source"], t)
        require(key not in seen and r["id"] not in seen, "duplicate context/id")
        seen.update((key, r["id"]))
        require(isinstance(r["context"], list) and len(r["context"]) == 51, "51 observation masks required")
        for i, frame in enumerate(r["context"]):
            fields(frame, "scene_masked evidence")
            require(type(frame["scene_masked"]) is bool, "observation mask must be boolean")
            step = grid_time(t, i)
            lo, hi = evidence(frame["evidence"], r, step)
            require(lo <= step == hi, "observation evidence must cover step")
        fields(r["channels"], " ".join(NAMES))
        for c in r["channels"].values():
            fields(c, "accepted_state imitation_mask onset onset_bounds continuation context_state accepted_evidence onset_evidence continuation_evidence context_evidence")
            require(all(c[k] in STATES for k in ("accepted_state", "onset", "continuation", "context_state")),
                    "invalid channel state")
            require(type(c["imitation_mask"]) is bool, "label mask must be boolean")
            require(c["imitation_mask"] == (r["eligible"] and c["accepted_state"] != "unknown"),
                    "label mask disagrees with eligibility/support")
            if c["onset"] == "present":
                require(isinstance(c["onset_bounds"], list) and len(c["onset_bounds"]) == 2, "onset bounds required")
                lo, hi = map(number, c["onset_bounds"])
                require(t <= lo < hi <= t+2 and hi <= r["label_known_at"], "onset outside future horizon/evidence")
            else:
                require(c["onset_bounds"] is None, "unsupported onset bounds")
            channel_evidence(c, r)
        require(isinstance(r["recent_attack"], list) and len(r["recent_attack"]) == 2, "1s/5s attack controls required")
        for seconds, v in zip((1, 5), r["recent_attack"]):
            fields(v, "present evidence")
            require(v["present"] is None or type(v["present"]) is bool, "invalid baseline mask")
            if v["present"] is None:
                require(v["evidence"] is None, "unknown baseline must have null evidence")
            else:
                lo, hi = evidence(v["evidence"], r, t)
                require(lo <= t-seconds and hi == t, "baseline evidence must cover lookback")
        require(not (r["channels"][NAMES[0]]["accepted_state"] == "present"
                     and r["channels"][NAMES[3]]["accepted_state"] == "present"), "incompatible approach/traversal labels")
    require({r["source"] for r in export["rows"]} == set(ALLOWED), "both whole-session folds required")
    require(any(c["imitation_mask"] for r in export["rows"] for c in r["channels"].values()), "absent supported labels")

    # Metadata freshness and identity are checked for BOTH sources before opening either npz.
    bindings(export, cache_dir)
    patches = set()
    for sid, src in export["sources"].items():
        manifest = checked_file(src["manifest"])
        with manifest.open() as f:
            header = json.loads(f.readline())
        require(header.get("type") == "clip" and header.get("id") == sid and header.get("group") == ALLOWED[sid]
                and header.get("split") == "train" and header.get("splittable") is True
                and header.get("cooldowns") == "normal" and header.get("patch") not in (None, "", "unknown"),
                "source is not promoted normal-patch training footage")
        patches.add(header["patch"])
        events = ROOT / src["events"]["path"]
        require(isinstance(header.get("events"), str)
                and Path(os.path.abspath(manifest.parent / header["events"])) == events, "manifest/event evidence mismatch")
        media = ROOT / f"data/demos/vods/{sid}.mp4"
        video = header.get("media")
        require(isinstance(video, dict) and video.get("kind") == "video"
                and isinstance(video.get("path"), str)
                and Path(os.path.abspath(manifest.parent / video["path"])) == media, "manifest media identity mismatch")
        checked_file(src["events"])
        with events.open() as f:
            meta = json.loads(f.readline())
        require(meta.get("type") == "meta" and meta.get("format") == 5
                and meta.get("writer") == producer_rule()["writer"] == "21a390f547eb"
                and number(meta.get("pts_origin_s")) == ORIGINS[sid], "stale writer or source clock")
        side = cache_dir / f"{sid}.json"
        require(digest(side) == src["cache_sidecar_sha256"], "stale cache sidecar")
        m = read_json(side)
        cache_origin = CACHE_ORIGINS[sid]
        require(Decimal(str(number(meta.get("pts_origin_s"))))
                - Decimal(str(number(meta.get("container_start_s")))) == Decimal(str(cache_origin))
                and number(m.get("t_origin")) == number(m.get("t_first")) == cache_origin,
                "cache/writer/container clock mismatch")
        creator = "daymr" if sid.startswith("day") else "reqmr"
        require(m.get("id") == sid and m.get("group") == ALLOWED[sid] and m.get("splittable") is True
                and m.get("cooldowns") == "normal" and m.get("patch") == header["patch"]
                and m.get("encoder") == DEFAULT and m.get("norm") == NORM and m.get("size") == SIZE
                and m.get("dim") == 384 and m.get("hz") == 10 and m.get("clock") == "media_pts"
                and m.get("sidecar_version") == SIDECAR_VERSION
                and number(m.get("t_origin")) == cache_origin
                and m.get("masks") == [list(x) for x in rects(creator)], "cache provenance/clock mismatch")
        require(isinstance(m.get("media"), str) and Path(os.path.abspath(ROOT / m["media"])) == media,
                "cache/manifest media identity mismatch")
    require(len(patches) == 1, "mixed patches")
    return export


def targets(rows):
    cells = [[r["channels"][c] for c in NAMES] for r in rows]
    y = np.array([[c["accepted_state"] == "present" for c in row] for row in cells], np.float32)
    mask = np.array([[c["imitation_mask"] for c in row] for row in cells], bool)
    return y, mask


def histories(export, cache_dir):
    """Only call with admit's result. Exact paths; no directory-wide cache scan."""
    bindings(export, cache_dir)
    cached = {}
    for sid, src in export["sources"].items():
        path = Path(cache_dir) / f"{sid}.npz"
        require(digest(path) == src["cache_sha256"], "stale embedding payload")
        with np.load(path, allow_pickle=False) as z:
            t, emb = z["t"], z["emb"]
        validate_cache_times(t, sid)
        require(emb.shape == (len(t), 384) and np.isfinite(emb).all(), "malformed cache arrays")
        cached[sid] = (t, emb)
    blocks = []
    for r in export["rows"]:
        times, emb = cached[r["source"]]
        block = []
        for i, frame in enumerate(r["context"]):
            t = grid_time(r["t"], i)
            j = context_index(times, r, i)
            vec = emb[j] if j is not None else None
            if frame["scene_masked"]:
                row = np.zeros(386, np.float32)
                row[-1] = 1
            else:
                require(vec is not None, "unmasked cache miss")
                row = step_row(384, vec, None, None, None, t)[0][:386]
            block.append(row)
        require(any(row[-2] for row in block), "entirely hidden visual history")
        blocks.append(block)
    return np.asarray(blocks, np.float32)


def clusters(rows):
    """Full-footprint connected clusters within one session, including endpoint contact."""
    end, groups = -math.inf, []
    for r in sorted(rows, key=lambda r: r["evidence_from"]):
        if r["evidence_from"] > end:
            groups.append([])
        groups[-1].append(r)
        end = max(end, r["evidence_to"])
    return groups


def independent_count(rows):
    return len(clusters(rows))


def support(rows):
    result = {}
    for sid in ALLOWED:
        local = [r for r in rows if r["source"] == sid]
        groups = clusters(local)
        channels = {}
        for name in NAMES:
            known = [r for r in local if r["channels"][name]["imitation_mask"]]
            pos = [r for r in known if r["channels"][name]["accepted_state"] == "present"]
            neg = [r for r in known if r["channels"][name]["accepted_state"] == "absent"]
            group_states = [{r["channels"][name]["accepted_state"] for r in group
                             if r["channels"][name]["imitation_mask"]} for group in groups]
            channels[name] = dict(positive=len(pos), negative=len(neg),
                                  eligible_unknown=sum(r["eligible"] and r not in known for r in local),
                                  ineligible=sum(not r["eligible"] for r in local),
                                  independent_positive=group_states.count({"present"}),
                                  independent_negative=group_states.count({"absent"}),
                                  mixed_clusters=sum(len(s) > 1 for s in group_states),
                                  onset={s: sum(r["channels"][name]["onset"] == s for r in known) for s in STATES},
                                  continuation={s: sum(r["channels"][name]["continuation"] == s for r in known) for s in STATES})
        result[sid] = channels
    return result


def split(rows, held):
    require(held in ALLOWED, "unapproved held source")
    te = np.array([ALLOWED[r["source"]] == ALLOWED[held] for r in rows])
    tr = ~te
    # Whole-session folds have no shared group. Retain full-footprint + 5 s purge
    # explicitly so a future caller cannot silently replace them with random rows.
    for i, r in enumerate(rows):
        if tr[i] and any(ALLOWED[r["source"]] == ALLOWED[s["source"]]
                         and r["evidence_from"] <= s["evidence_to"]+5
                         and r["evidence_to"] >= s["evidence_from"]-5 for s, take in zip(rows, te) if take):
            tr[i] = False
    require(tr.any() and te.any(), "empty whole-session fold")
    return tr, te


def statistics(y, mask):
    pos, neg = (y*mask).sum(0), ((1-y)*mask).sum(0)
    supported = (pos > 0) & (neg > 0)
    prior = np.divide(pos, pos+neg, out=np.zeros(4, np.float32), where=pos+neg > 0)
    weights = np.stack([(pos+neg)/(2*np.maximum(neg, 1)), (pos+neg)/(2*np.maximum(pos, 1))], 1)
    return supported, prior, weights


def normalization(x):
    observed = x[..., :384][x[..., 384] == 1]
    require(len(observed) > 0, "no observed fitting frames")
    return observed.mean(0), np.maximum(observed.std(0), 1e-6)


def normalize(x, mean, scale):
    out = x.copy()
    out[..., :384] = np.where(x[..., 384:385] == 1, (x[..., :384]-mean)/scale, 0)
    return out


def masked_loss(model, x, y, mask, weights):
    logits = model(x)
    bce = mx.maximum(logits, 0)-logits*y+mx.log1p(mx.exp(-mx.abs(logits)))
    balanced = weights[:, 0]*(1-y)+weights[:, 1]*y
    return (bce*balanced*mask).sum()/mx.maximum(mask.sum(), 1)


def fit_head(x, y, mask, weights):
    mx.random.seed(RECIPE["seed"])
    model = Head(x.shape[-1], 4, d=RECIPE["hidden"])
    opt = optim.Adam(learning_rate=RECIPE["lr"])
    step = nn.value_and_grad(model, masked_loss)
    for epoch in range(RECIPE["epochs"]):
        order = np.random.default_rng(RECIPE["seed"]+epoch).permutation(len(x))
        for start in range(0, len(order), RECIPE["batch"]):
            idx = order[start:start+RECIPE["batch"]]
            loss, grads = step(model, mx.array(x[idx]), mx.array(y[idx]), mx.array(mask[idx]), mx.array(weights))
            opt.update(model, grads)
            mx.eval(model.parameters(), opt.state, loss)
            require(math.isfinite(float(loss)), "nonfinite fit loss")
    model.eval()
    return model


def predict(model, x):
    return np.concatenate([np.asarray(mx.sigmoid(model(mx.array(x[i:i+128])))) for i in range(0, len(x), 128)])


def scores(y, mask, p):
    result = {}
    for c, name in enumerate(NAMES):
        truth, guess = y[mask[:, c], c], p[mask[:, c], c] >= .5
        tp, tn = int(((truth == 1) & guess).sum()), int(((truth == 0) & ~guess).sum())
        fp, fn = int(((truth == 0) & guess).sum()), int(((truth == 1) & ~guess).sum())
        pos, neg = tp+fn, tn+fp
        result[name] = dict(tp=tp, tn=tn, fp=fp, fn=fn, positive=pos, negative=neg,
                            positive_recall=tp/pos if pos else None, negative_recall=tn/neg if neg else None,
                            balanced_accuracy=(tp/pos+tn/neg)/2 if pos and neg else None)
    return result


def stratified_scores(rows, y, mask, p):
    result = {"occurrence": scores(y, mask, p)}
    for label in ("onset", "continuation"):
        states = [[r["channels"][c][label] for c in NAMES] for r in rows]
        known = np.array([[s != "unknown" for s in row] for row in states]) & mask
        # Evaluate starting only where context is absent, persistence only where
        # it is present. Ongoing attacks are not false-positive onset decisions.
        context = "absent" if label == "onset" else "present"
        known &= np.array([[r["channels"][c]["context_state"] == context for c in NAMES] for r in rows])
        truth = np.array([[s == "present" for s in row] for row in states], np.float32)
        result[label] = scores(truth, known, p)
    return result


def reload_predictions(folder, x):
    folder = Path(folder)
    spec = read_json(folder / "checkpoint.json")
    require(spec["task"] == TASK and spec["code_sha256"] == code_versions(), "stale checkpoint code/task")
    with np.load(folder / "normalization.npz", allow_pickle=False) as z:
        x = normalize(x, z["mean"], z["scale"])
    model = Head(386, 4, d=spec["recipe"]["hidden"])
    model.load_weights(str(folder / "model.safetensors"))
    model.eval()
    return predict(model, x)


def smoke_fold(x, export, held, folder):
    require(export["code_sha256"] == code_versions(), "code changed since admission")
    rows = export["rows"]
    y, mask = targets(rows)
    tr, te = split(rows, held)
    supported, prior, weights = statistics(y[tr], mask[tr])
    require(supported.any(), "no channel has both fitting classes")
    train_mask = mask & supported
    useful = tr & train_mask.any(1)
    mean, scale = normalization(x[useful])
    xn = normalize(x, mean, scale)
    model = fit_head(xn[useful], y[useful], train_mask[useful], weights)
    p = predict(model, xn[te])
    held_rows = [r for r, take in zip(rows, te) if take]
    baseline = {"always_negative": np.zeros_like(p), "always_positive": np.ones_like(p),
                "fit_majority": np.tile(prior >= .5, (len(p), 1)).astype(float)}
    context = np.array([[r["channels"][c]["context_state"] for c in NAMES] for r in held_rows])
    baseline["context_persistence"] = np.where(context == "unknown", prior >= .5, context == "present").astype(float)
    last = fit_head(xn[useful, -1:], y[useful], train_mask[useful], weights)
    baseline["decision_frame"] = predict(last, xn[te, -1:])
    # Fit-only ridge over source time and observation-mask fraction; no world features.
    nuisance = np.array([[1, r["t"]/900, np.mean([f["scene_masked"] for f in r["context"]])] for r in rows])
    nuisance_p = np.zeros_like(p)
    for c in range(4):
        take = tr & train_mask[:, c]
        a = nuisance[take]
        w = np.linalg.solve(a.T @ a + np.eye(3), a.T @ y[take, c])
        nuisance_p[:, c] = np.clip(nuisance[te] @ w, 0, 1)
    baseline["nuisance_only"] = nuisance_p
    for k in range(2):
        b = np.tile(prior >= .5, (len(p), 1)).astype(float)
        b[:, 1] = [r["recent_attack"][k]["present"] if r["recent_attack"][k]["present"] is not None
                   else prior[1] >= .5 for r in held_rows]
        baseline[f"attack_event_{(1, 5)[k]}s"] = b
    require(export["code_sha256"] == code_versions(), "code changed during fit")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    model.save_weights(str(folder / "model.safetensors"))
    last.save_weights(str(folder / "decision-frame.safetensors"))
    np.savez(folder / "normalization.npz", mean=mean, scale=scale)
    write_json(folder / "checkpoint.json", dict(task=TASK, recipe=RECIPE, code_sha256=export["code_sha256"],
               fit_sources=sorted({r["source"] for r, take in zip(rows, tr) if take}), held=held,
               channels=NAMES, fit_supported=supported.tolist(), threshold=.5, evaluation_batch=128))
    replay = reload_predictions(folder, x[te])
    require(np.array_equal(p, replay), "checkpoint reload predictions differ")
    report = dict(mode="pipeline_smoke_only", performance_claim=False, held=held, recipe=RECIPE,
                  gates=GATES, support=support(rows), fit_supported=supported.tolist(), fit_prior=prior.tolist(),
                  class_weights=weights.tolist(), model=stratified_scores(held_rows, y[te], train_mask[te], p),
                  baselines={k: stratified_scores(held_rows, y[te], train_mask[te], b) for k, b in baseline.items()},
                  persistence_unknown=int((context == "unknown").sum()), reload_exact=True,
                  limitations=["No performance acceptance or confidence-interval claim in smoke mode.",
                               "Onset/continuation scores apply occurrence forecasts, not separate onset heads.",
                               "Context persistence is privileged annotation; event rules apply only to attacking.",
                               "Two sessions confound creator and session; no live adapter."])
    np.savez_compressed(folder / "predictions.npz", probabilities=p, y=y[te], label_mask=train_mask[te], **baseline)
    write_json(folder / "report.json", report)
    return report


def run(export_path, cache_dir, out, smoke_fit=False):
    export = admit(export_path, cache_dir)
    out = Path(out)
    require(not out.exists(), "fresh output directory required; no restarts/overwrite")
    ready = {}
    if smoke_fit:
        y, mask = targets(export["rows"])
        for held in ALLOWED:
            tr, te = split(export["rows"], held)
            supported = statistics(y[tr], mask[tr])[0]
            ready[held] = bool(supported.any() and (mask[te] & supported).any())
        if any(ready.values()):
            x = histories(export, cache_dir)  # Refuse bad payloads before publishing output.
    out.mkdir(parents=True)
    write_json(out / "run-spec.json", dict(task=TASK, recipe=RECIPE, code_sha256=export["code_sha256"],
               export_sha256=digest(export_path), mode="pipeline_smoke_only" if smoke_fit else "support_only",
               performance_claim=False, source_fingerprints=export["sources"], gates=GATES))
    write_json(out / "accepted-export.json", export)
    report = support(export["rows"])
    write_json(out / "support.json", report)
    if smoke_fit:
        write_json(out / "fit-status.json", {sid: "smoke_fit" if ok else "unsupported_no_fit_or_held_classes"
                                            for sid, ok in ready.items()})
        for held, ok in ready.items():
            if ok:
                smoke_fold(x, export, held, out / held)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--smoke-fit", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.export, args.cache, args.out, args.smoke_fit), indent=2))


if __name__ == "__main__":
    main()
