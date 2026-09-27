"""EXPLORATORY paired IDM preparation/refit and matched short/long edge experiment.

No automatic discovery of recordings. A pinned, independently reviewed run
manifest names every input and role. Actual jobs run only on the released Mac
slot; tests call bounded CPU primitives with synthetic inputs.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from policy import idm_eval, idm_targets as T
from policy.idm import match_targets, temporal, temporal_store, train as TR
from policy.idm.frames import FrameStore
from policy.idm.model import Config as CameraConfig
from policy.range_bc import vocab
from scripts import job_status

FORMAT = "rivals-idm-explore-run-v1"
A4_SHA256 = "90aa4befa489e9a8385d9d40445be2d17efafb32395375aecedb0f488fb7da0a"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_pinned(path, pin):
    import hashlib

    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == pin, f"pin mismatch: {path}")
    return json.loads(raw)


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")


def preflight(manifest, *, registry, denylist, admission=None, edge=False):
    """Registry/header refusal before target row hashing, parsing or store access."""
    from agent import human_intake as hi

    require(manifest.get("format") == FORMAT and manifest.get("scope") == "EXPLORATORY", "run format/scope")
    hi.check_registry(registry, denylist=denylist)
    reg = json.loads(Path(registry).read_text(encoding="utf-8"))
    entries = {r["session_id"]: r for r in reg["sessions"]}
    loaded, groups = [], {"train": set(), "heldout": set()}
    ids = set()
    for item in manifest["sessions"]:
        sid, role = item["session_id"], item["role"]
        require(role in groups and sid not in ids, "invalid role or duplicate session")
        ids.add(sid)
        T.refuse_sealed(sid, None, denylist)
        entry = entries.get(sid)
        require(entry is not None and entry.get("split") in T.TRAIN_SPLITS,
                "explore requires a training source for every role, including heldout")
        require(not entry.get("sealed") and not entry.get("training_pending"), "source sealed or admission pending")
        require(role != "train" or entry["split"] in T.TRAIN_SPLITS, "cannot train on val")
        # Frozen IDs are checked using complete IDs and the unique timestamp prefix.
        frozen = sid.startswith(("20260923T171533-", "20260923T205528-"))
        require(not frozen or (not edge and role == "heldout"), "frozen dev cannot enter this fit/edge experiment")
        if entry["split"] == "idm_train":
            require(admission is not None, "reviewed match admission required")
            admission.check(sid)
        with Path(item["targets"]).open(encoding="utf-8") as f:
            header = json.loads(f.readline())
        require(header["session_id"] == sid and header["split"] == entry["split"], "target registry identity/role mismatch")
        T.refuse_sealed(sid, header["media_sha256"], denylist)
        if entry.get("expected_media_sha256"):
            require(header["media_sha256"] == entry["expected_media_sha256"], "registry media mismatch")
        require(header["session_group"] == entry["session_group"], "registry family mismatch")
        groups[role].add(header["session_group"])
        require(not groups["train"] & groups["heldout"], "same live/replay family in both roles")
        require(T.sha256(item["targets"]) == item["targets_sha256"], "target pin mismatch")
        target = T.load(item["targets"], denylist=denylist, match_admission=admission)
        require(T.sha256(item["targets"]) == item["targets_sha256"], "target changed during load")
        loaded.append((item, target))
    require(groups["train"] and groups["heldout"], "need explicit train and heldout families")
    return loaded


class EdgeExamples:
    def __init__(self, sessions, actions=temporal.DEFAULT_ACTIONS):
        self.actions, self.ticks = tuple(actions), temporal.offsets(actions)
        self.items, self.coverage = [], {}
        for target, store in sessions:
            pairs, counts = temporal.context_rows(target, self.ticks)
            kept = 0
            for row, context in pairs:
                if any(r["frame1"]["frame_index"] not in store.index for r in context):
                    continue
                self.items.append((target, store, row, context))
                kept += 1
            self.coverage[target.session_id] = {**counts, "with_features": kept,
                                               "missing_features": len(pairs) - kept}
        cols = [vocab.INDEX[a] for a in actions]
        self.y = torch.tensor([[float(row["press"][c] > 0) for c in cols] for _, _, row, _ in self.items],
                              dtype=torch.float32).reshape(-1, len(cols))
        self.mask = torch.tensor([[row["held_known"][c] for c in cols] for _, _, row, _ in self.items],
                                 dtype=torch.bool).reshape(-1, len(cols))

    def __len__(self):
        return len(self.items)

    def inputs(self, indices, device):
        features, hud, elapsed = [], [], []
        for i in indices:
            _, store, row, context = self.items[i]
            g, h = store.inputs(context)
            features.append(g)
            hud.append(h)
            zero = row["frame1"]["composition_ns"]
            elapsed.append([(r["frame1"]["composition_ns"] - zero) / 1e9 for r in context])
        return (torch.stack(features).to(device), torch.stack(hud).to(device),
                torch.tensor(elapsed, dtype=torch.float32, device=device))


def edge_fit(examples, *, arm, seed=0, epochs=3, batch=16, device="cpu", config=None,
             min_positives=50, progress=lambda _: None):
    require(len(examples) > 0, "no context-valid edge examples")
    require(all(t.header["split"] in T.TRAIN_SPLITS for t, _, _, _ in examples.items), "edge fit requires train roles")
    require(epochs > 0 and batch > 0, "positive epoch/batch counts required")
    TR.seed_everything(seed)
    model = temporal.PressHead(config or temporal.Config(actions=examples.actions)).to(device)
    positive = (examples.y * examples.mask).sum(0)
    negative = ((1 - examples.y) * examples.mask).sum(0)
    supported = positive >= min_positives
    require(bool(supported[0]), "primary Amazing Combo has insufficient post-context training support")
    mask = examples.mask & supported[None]
    weights = (negative / positive.clamp(min=1)).clamp(1, TR.POS_WEIGHT_MAX).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    history = []
    for epoch in range(epochs):
        order = list(range(len(examples)))
        random.Random(seed * 1000003 + epoch).shuffle(order)
        losses = []
        for start in range(0, len(order), batch):
            idx = order[start:start + batch]
            logits = model(*examples.inputs(idx, device), examples.ticks, arm=arm)
            raw = F.binary_cross_entropy_with_logits(logits, examples.y[idx].to(device),
                                                     pos_weight=weights, reduction="none")
            known = mask[idx].to(device)
            loss = (raw * known).sum() / known.sum().clamp(min=1)
            require(bool(torch.isfinite(loss)), "nonfinite edge loss")
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1)
            opt.step()
            losses.append(float(loss.detach()))
            if start % (batch * 100) == 0 or start + batch >= len(order):
                progress({"n": epoch * len(order) + min(start + batch, len(order)), "total": epochs * len(order)})
        history.append({"epoch": epoch, "loss": sum(losses) / len(losses)})
    return model, {"history": history, "positives": positive.tolist(), "supported": supported.tolist()}


@torch.no_grad()
def probabilities(model, examples, *, arm, device, batch=16, progress=lambda _: None):
    model.eval()
    result = []
    for start in range(0, len(examples), batch):
        idx = list(range(start, min(start + batch, len(examples))))
        result.append(model(*examples.inputs(idx, device), examples.ticks, arm=arm).sigmoid().cpu())
        if start % (batch * 100) == 0:
            progress({"n": min(start + batch, len(examples)), "total": len(examples)})
    return torch.cat(result).numpy() if result else np.empty((0, len(examples.actions)))


def calibrate(examples, scores):
    """Train-only rate-matched thresholds. Ties and achieved rates are reported."""
    require(all(t.header["split"] in T.TRAIN_SPLITS for t, _, _, _ in examples.items), "thresholds require train roles")
    thresholds, rates = [], []
    for c in range(len(examples.actions)):
        known = examples.mask[:, c].numpy()
        values = np.sort(scores[known, c])
        n = int(examples.y[known, c].sum())
        threshold = float(values[-n]) if n else 1.000001
        thresholds.append(threshold)
        rates.append({"target": n / len(values) if len(values) else None,
                      "achieved": float(np.mean(values >= threshold)) if len(values) else None})
    return thresholds, rates


def score_edges(examples, scores, thresholds, supported, progress=lambda _: None):
    result = {}
    for c, action in enumerate(examples.actions):
        if not supported[c]:
            result[action] = {"status": "unsupported"}
            continue
        sessions = {}
        for k, (t, _, row, _) in enumerate(examples.items):
            item = sessions.setdefault(t.session_id, {"header": t.header, "rows": [], "pred": {}})
            item["rows"].append(row)
            item["pred"][row["i"]] = {"press": {action: float(scores[k, c])}}
        observed, chance = {}, []
        for sid, s in sessions.items():
            subset = T.Targets(s["header"], s["rows"])
            observed[sid] = idm_eval.edge_metrics(subset, s["pred"], {action: True}, threshold=thresholds[c])[action]
        for seed in range(20):
            progress(f"{action}: chance comparison {seed + 1}/20")
            rng = random.Random(seed)
            tp = fp = fn = 0
            for sid, s in sessions.items():
                rate = observed[sid]["predicted_onset_rate"] or 0.0
                p = {r["i"]: {"press": {action: float(rng.random() < rate)}} for r in s["rows"]}
                m = idm_eval.edge_metrics(T.Targets(s["header"], s["rows"]), p, {action: True})[action]
                tp, fp, fn = tp + m["tp"], fp + m["fp"], fn + m["fn"]
            chance.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0)
        tp, fp, fn = (sum(m[key] for m in observed.values()) for key in ("tp", "fp", "fn"))
        f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
        result[action] = {"sessions": observed, "f1": f1, "chance_mean": float(np.mean(chance)),
                          "chance_std": float(np.std(chance)), "delta_f1": f1 - float(np.mean(chance)),
                          "decides": all(m["decides"] for m in observed.values())}
    return result


def refit(loaded, *, out, seed, epochs, device, progress, max_examples=None):
    stores, sets, exclusions = {}, {"train": [], "heldout": []}, {}
    for item, target in loaded:
        path = Path(item["store"])
        require(T.sha256(path / "frames.json") == item["frames_sha256"], "frame manifest pin mismatch")
        store = FrameStore(path, verify=True)
        TR.bind(target, store)
        pairs, counts = temporal.context_rows(target, tuple(range(-8, 9)))
        filtered = T.Targets(target.header, [row for row, _ in pairs])
        exclusions[target.session_id] = counts
        sets[item["role"]].append((filtered, store))
        stores[target.session_id] = store
    cohort = T.check_cohort([t for group in sets.values() for t, _ in group], T.load_patch_equivalence())
    config = CameraConfig()
    examples = TR.Examples(sets["train"], config, dict.fromkeys(vocab.NAMES, True), limit=max_examples)
    counts = TR.train_statistics(examples)["positives"]
    supported = {a: counts[a] >= T.MIN_POSITIVES and a not in T.DECLARED_UNSUPPORTED for a in vocab.NAMES}
    examples.supported = supported
    examples.press_mask &= torch.tensor([supported[a] for a in vocab.NAMES])[None]
    stats = TR.train_statistics(examples)
    model, history, seconds = TR.fit(examples, config, stats, seed=seed, epochs=epochs, device=device,
                                     progress=progress)
    prov = TR.provenance(seed=seed, supported=supported, train_press_counts=counts,
                         targets={t.session_id: TR.target_entry(t, i["targets_sha256"]) for i, t in loaded},
                         frame_stores={sid: TR.store_entry(s) for sid, s in stores.items()})
    prov.update(scope="EXPLORATORY", cohort=cohort, camera_beta_nll=TR.CAMERA_BETA_DEFAULT)
    pin = TR.save_checkpoint(out / "refit.pt", model, prov)
    return {"checkpoint_sha256": pin, "history": history, "seconds": seconds, "exclusions": exclusions,
            "gate1_diagnostic": TR.gate1(model, sets["heldout"], device=device),
            "pitch_calibration": TR.PITCH_STD_CALIBRATION, "cohort": cohort}


def run_edges(loaded, manifest, *, out, seed, epochs, device, progress, max_examples=None):
    camera = manifest["camera_checkpoint"]
    require(camera["sha256"] == A4_SHA256, "the first edge experiment fixes A4 weights")
    require(T.sha256(camera["path"]) == camera["sha256"], "fixed camera checkpoint mismatch")
    # No camera deserialization or optimizer: its exact bytes are carried forward.
    sets = {"train": [], "heldout": []}
    asset_identity = None
    for item, target in loaded:
        store = temporal_store.FeatureStore(item["store"], target, item["targets_sha256"],
                                             manifest_sha256=item["features_sha256"])
        current = (store.manifest["assets"], store.manifest["recipe"], store.manifest["decode_graph"])
        require(asset_identity is None or asset_identity == current, "mixed frozen feature assets/recipes")
        asset_identity = current
        sets[item["role"]].append((target, store))
    T.check_cohort([t for group in sets.values() for t, _ in group], T.load_patch_equivalence())
    train, heldout = (EdgeExamples(sets[role]) for role in ("train", "heldout"))
    if max_examples is not None:
        train.items, train.y, train.mask = train.items[:max_examples], train.y[:max_examples], train.mask[:max_examples]
    require(len(heldout) > 0, "no context-valid heldout rows")
    report = {"camera_checkpoint": camera, "pitch_calibration": TR.PITCH_STD_CALIBRATION,
              "window_ticks": temporal.WINDOWS, "ticks": train.ticks,
              "coverage": {"train": train.coverage, "heldout": heldout.coverage}, "arms": {}}
    write_json(out / "heldout-row-ids.json", [[t.session_id, row["i"]] for t, _, row, _ in heldout.items])
    for arm in ("S", "L"):
        progress(f"edge {arm}: training")
        model, stats = edge_fit(train, arm=arm, seed=seed, epochs=epochs, device=device, progress=progress)
        progress(f"edge {arm}: train-only threshold calibration")
        train_p = probabilities(model, train, arm=arm, device=device, progress=progress)
        thresholds, rates = calibrate(train, train_p)
        progress(f"edge {arm}: heldout scoring")
        held_p = probabilities(model, heldout, arm=arm, device=device, progress=progress)
        checkpoint = {"format": "rivals-idm-edge-explore-v1", "scope": "EXPLORATORY", "arm": arm,
                      "config": model.config.as_dict(), "seed": seed, "epochs": epochs,
                      "model": {k: v.detach().cpu() for k, v in model.state_dict().items()},
                      "thresholds": thresholds, "supported": stats["supported"], "camera_checkpoint": camera,
                      "run_manifest": manifest}
        with (out / f"edge-{arm}.pt").open("xb") as f:
            torch.save(checkpoint, f)
        np.save(out / f"heldout-{arm}.npy", held_p)
        report["arms"][arm] = {**stats, "thresholds": thresholds, "calibration_rates": rates,
                               "metrics": score_edges(heldout, held_p, thresholds, stats["supported"], progress),
                               "checkpoint_sha256": T.sha256(out / f"edge-{arm}.pt")}
    require(T.sha256(camera["path"]) == camera["sha256"], "camera checkpoint changed during edge experiment")
    report["verdict"] = "EXPLORATORY single-seed diagnostic; no replicated success claim"
    return report


def with_status(name, evidence, action, *, root=None, host="mac"):
    """Use r3-reader's atomic ~/dev/jobs convention; failure never looks done."""
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with Path(evidence).open("x", encoding="utf-8") as log:
        log.write(json.dumps({"scope": "EXPLORATORY", "started": started}) + "\n")
        log.flush()
        job_status.write(name, root=root, owner="idm-owner", stage="running", host=host,
                         started=started, progress="preflight", eta=None, evidence=str(Path(evidence).resolve()))
        def progress(value):
            log.write(json.dumps({"progress": value, "time": time.time()}) + "\n")
            log.flush()
            job_status.write(name, root=root, progress=value, eta=None)
        try:
            result = action(progress)
        except BaseException:
            import traceback
            traceback.print_exc(file=log)
            log.flush()
            job_status.write(name, root=root, stage="failed", progress="see run log", eta=None)
            raise
        job_status.write(name, root=root, stage="done", progress="process completed; see EXPLORATORY report", eta=None)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pins", "preflight", "build-targets", "prepare", "refit", "edges"))
    parser.add_argument("--manifest")
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--registry", default=str(T.REGISTRY))
    parser.add_argument("--sessions-root", default=str(T.SESSIONS))
    parser.add_argument("--out")
    parser.add_argument("--job-name")
    parser.add_argument("--device", choices=("mps", "cpu"), default="mps")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--max-examples", type=int, help="SMOKE ONLY: deterministic train prefix; not a cohort result")
    parser.add_argument("--walltime-minutes", type=float, default=30,
                        help="cooperative deadline checked at progress boundaries (default: 30)")
    args = parser.parse_args(argv)
    if args.command == "pins":
        print(json.dumps(TR.code_closure(), indent=2, sort_keys=True))
        return 0
    require(args.manifest and args.manifest_sha256, "pinned run manifest required")
    def load_run():
        manifest = read_pinned(args.manifest, args.manifest_sha256)
        closure = TR.code_closure()
        require(manifest.get("code_closure") == closure and manifest.get("independent_review") == "accepted",
                "reviewed exact code closure required before source access")
        deny = T.load_denylist()
        admission = None
        if manifest.get("match_admission"):
            ref = manifest["match_admission"]
            admission = match_targets.load(ref["path"], ref["sha256"], registry=args.registry, denylist=deny)
        return manifest, closure, deny, admission
    if args.command == "preflight":
        manifest, _, deny, admission = load_run()
        loaded = preflight(manifest, registry=args.registry, denylist=deny, admission=admission)
        print(json.dumps({"scope": "EXPLORATORY", "rows": {t.session_id: len(t.rows) for _, t in loaded}}))
        return 0
    require(platform.system() == "Darwin" and platform.machine() == "arm64", "actual jobs require the released Mac slot")
    require(args.out and args.job_name and args.epochs > 0, "out, unique job name and positive epochs required")
    require(args.walltime_minutes > 0 and (args.max_examples is None or args.max_examples > 0), "positive budgets required")
    os.nice(10)
    torch.set_num_threads(2)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)

    def action(update):
        deadline = time.monotonic() + args.walltime_minutes * 60
        def progress(value):
            if time.monotonic() >= deadline:
                raise TimeoutError("explore wall-time budget reached at progress boundary")
            update(value)
        manifest, closure, deny, admission = load_run()
        write_json(out / "run-manifest.json", manifest)
        if args.command == "build-targets":
            require(manifest.get("scope") == "EXPLORATORY", "scope")
            paths = [str(T.build(sid, out_dir=out, sessions=Path(args.sessions_root), registry=args.registry,
                                match_admission=admission)[0])
                     for sid in manifest["build_sessions"]]
            result = {"targets": paths}
        else:
            loaded = preflight(manifest, registry=args.registry, denylist=deny, admission=admission,
                               edge=args.command == "edges")
            if args.command == "refit":
                result = refit(loaded, out=out, seed=args.seed, epochs=args.epochs,
                               device=args.device, progress=progress, max_examples=args.max_examples)
            elif args.command == "edges":
                result = run_edges(loaded, manifest, out=out, seed=args.seed, epochs=args.epochs,
                                   device=args.device, progress=progress, max_examples=args.max_examples)
            else:
                assets = manifest["dino"]
                backbone = temporal_store.cm3_features.FrozenDino(
                    assets["path"], config_sha256=assets["config_sha256"]).to(args.device)
                result = {t.session_id: temporal_store.prepare(
                    t, i["targets_sha256"], video=i["video"], demo=i["demo"], out=out / t.session_id,
                    backbone=backbone, device=args.device, progress=progress) for i, t in loaded}
        require(closure == TR.code_closure(), "code changed during job")
        progress("writing EXPLORATORY report")
        write_json(out / "report.json", {"scope": "EXPLORATORY", "command": args.command,
                                         "manifest_sha256": args.manifest_sha256,
                                         "options": {"seed": args.seed, "epochs": args.epochs, "device": args.device,
                                                     "smoke_max_examples": args.max_examples,
                                                     "walltime_minutes": args.walltime_minutes},
                                         "software": temporal_store.cm3_features.software_receipt(), "result": result})
        return result
    with_status(args.job_name, out / "run.log", action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
