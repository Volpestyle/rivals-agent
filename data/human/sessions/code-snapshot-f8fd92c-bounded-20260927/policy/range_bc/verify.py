"""CPU reload reference (Mac) and verifier (Windows) for `rivals-range-bc-v2` checkpoints.

The chain, as for the 09-22 and 09-23 fits: MPS fit -> Mac CPU reload (the reference, written by the fit) -> Windows CPU
reload (this verifier). Nothing here opens a pad, a capture or the live loop.

Mac side, called by the fit for the candidate checkpoint (`model-seed0.pt`, or `model_nohud-seed0.pt` when the HUD
parity failed; the report names it) on each evaluation set:
    `write_reference` reloads the saved checkpoint on the CPU and writes <set>-cpu-reference.json plus
    <set>-cpu-probs.f32: teacher-forced and self-fed decisions (hold/press/release bits, camera classes) as sha256,
    teacher-forced probabilities as float32, and the metrics. The fit also records the MPS-vs-CPU difference.

Windows side:
    python -m policy.range_bc.verify --run <fit out dir> --set val --steps <step tables> --cache-root <dir>
        [--report-sha256 <hex>] [--full-hash] --out <windows-report.json>
    It checks the report (optionally against a hash given out of band), the checkpoint's sha256, the code (the fit's
    code closure: every repo module it imported, compared LF-normalised so a CRLF checkout passes), the sealed denylist
    (intake's, pinned; always loaded), the step tables and frame caches (manifest
    hashes; all bytes with --full-hash), then reloads on the CPU and requires identical teacher-forced and self-fed
    decisions and a maximum probability delta <= TOLERANCE. Exit status 1 and the failing checks on any mismatch.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

TOLERANCE = 1e-4
ROOT = Path(__file__).resolve().parents[2]


def lf_sha256(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _decisions(runs):
    """Bytes of every step's decisions: 36 hold/press/release bits and two camera classes (255 = no value)."""
    from . import vocab
    out = bytearray()
    for run in runs:
        for _, p in run:
            for ch in ("held", "press", "release"):
                out += bytes(int(v >= .5) for v in p[ch])
            for axis in ("yaw", "pitch"):
                out.append(255 if p[axis] is None else vocab.camera_class(p[axis]))
    return bytes(out)


def _probabilities(runs):
    return b"".join(struct.pack(f"<{3 * len(p['held'])}f", *p["held"], *p["press"], *p["release"])
                    for run in runs for _, p in run)


def predictions(checkpoint, arrays, live_mask, *, device="cpu"):
    from .train import load_checkpoint, predict_self, predict_teacher
    model, payload = load_checkpoint(checkpoint, device=device)
    return predict_teacher(model, arrays, device=device), predict_self(model, arrays, live_mask, device=device), payload


def summarise(tf, sf):
    from . import metrics
    tf_all, sf_all = metrics.evaluate(tf, **metrics.TEACHER), metrics.evaluate(sf, **metrics.SELF)
    return {"steps": sum(len(r) for r in tf),
            "tf_decisions_sha256": hashlib.sha256(_decisions(tf)).hexdigest(),
            "sf_decisions_sha256": hashlib.sha256(_decisions(sf)).hexdigest(),
            "tf_macro_press_f1_tol": tf_all["macro_press_f1_tol"], "tf_camera_mae_mean": tf_all["camera_mae_mean"],
            "sf_macro_press_f1_tol": sf_all["macro_press_f1_tol"], "sf_camera_mae_mean": sf_all["camera_mae_mean"]}


def write_reference(out_dir, set_name, arrays, live_mask, *, device_runs=None, checkpoint="model-seed0.pt"):
    """Mac CPU reference for the candidate on one evaluation set. `device_runs` (the fit device's tf predictions of
    the same checkpoint) adds the MPS-vs-CPU comparison. Returns the summary recorded in the fit report."""
    import torch
    out_dir = Path(out_dir)
    ckpt = out_dir / checkpoint
    tf, sf, _ = predictions(ckpt, arrays, live_mask)
    probs = _probabilities(tf)
    probs_path = out_dir / f"{set_name}-cpu-probs.f32"
    with probs_path.open("xb") as stream:
        stream.write(probs)
    for mode, runs in (("tf", tf), ("sf", sf)):
        with (out_dir / f"{set_name}-cpu-{mode}-decisions.bin").open("xb") as stream:
            stream.write(_decisions(runs))
    ref = {"format": "rivals-range-bc-cpu-reference-v1", "set": set_name, "checkpoint": checkpoint,
           "checkpoint_sha256": hashlib.sha256(ckpt.read_bytes()).hexdigest(), "device": "cpu",
           "torch": torch.__version__, "sessions": {a.session.session_id: a.session.sha256 for a in arrays},
           "live_mask": list(live_mask), "probs_file": probs_path.name,
           "probs_sha256": hashlib.sha256(probs).hexdigest(), **summarise(tf, sf)}
    if device_runs is not None:
        dev_probs = _probabilities(device_runs)
        a, b = struct.unpack(f"<{len(probs) // 4}f", probs), struct.unpack(f"<{len(dev_probs) // 4}f", dev_probs)
        ref["device_vs_cpu"] = {"tf_decisions_equal": _decisions(device_runs) == _decisions(tf),
                                "max_probability_delta": max((abs(x - y) for x, y in zip(a, b)), default=0.)}
    path = out_dir / f"{set_name}-cpu-reference.json"
    text = json.dumps(ref, sort_keys=True, indent=1)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text + "\n")
    return {**ref, "reference_sha256": hashlib.sha256((text + "\n").encode()).hexdigest()}


def _first_divergence(a, b, width=38):
    for i in range(0, min(len(a), len(b)), width):
        if a[i:i + width] != b[i:i + width]:
            return i // width
    return None if len(a) == len(b) else min(len(a), len(b)) // width


def verify(run, set_name, step_paths, cache_root, *, denylist, report_sha256, full_hash=True, equivalence=None):
    """All checks; returns (ok, windows report dict). equivalence: the pinned patch-equivalence file, as the fit used
    it to cohort the set (the CLI always passes it)."""
    import torch
    from . import cache, steps
    from .train import SessionArrays
    run = Path(run)
    checks, fail = {}, []

    def check(name, ok, detail=None):
        checks[name] = {"ok": bool(ok), **({"detail": detail} if detail is not None else {})}
        if not ok:
            fail.append(name)
        return ok

    report_bytes = (run / "report.json").read_bytes()
    # L7: the report hash comes out of band (the lead records it on the issue); without it the checks are circular
    check("report_sha256", hashlib.sha256(report_bytes).hexdigest() == report_sha256)
    report = json.loads(report_bytes)
    from . import steps as _steps
    sd = report.get("sealed_denylist", {})
    check("denylist_default", sd.get("default") is True and sd.get("sha256_pin") == _steps.DENYLIST_SHA256, sd)
    ref_path = run / f"{set_name}-cpu-reference.json"
    ref_bytes = ref_path.read_bytes()
    recorded = report["cpu_reference"][set_name]
    check("reference_sha256", hashlib.sha256(ref_bytes).hexdigest() == recorded["reference_sha256"])
    ref = json.loads(ref_bytes)
    candidate = report["candidate_checkpoint"]
    check("candidate", ref["checkpoint"] == candidate, candidate)
    ckpt = run / candidate
    check("checkpoint_sha256", hashlib.sha256(ckpt.read_bytes()).hexdigest() == ref["checkpoint_sha256"]
          == report["checkpoints"][candidate])
    code_diff = {n: {"here_lf": lf_sha256(ROOT / n) if (ROOT / n).exists() else None, "fit": d}
                 for n, d in report["code_closure"].items()
                 if not (ROOT / n).exists() or lf_sha256(ROOT / n) != d}
    check("code_closure", not code_diff, code_diff or None)
    probs = (run / ref["probs_file"]).read_bytes()
    check("probs_sha256", hashlib.sha256(probs).hexdigest() == ref["probs_sha256"])
    split = "val" if set_name == "val" else "train"
    sessions = steps.load_cohort(step_paths, splits=(split,), denylist=denylist, equivalence=equivalence)
    check("sessions", {s.session_id: s.sha256 for s in sessions} == ref["sessions"],
          {s.session_id: s.sha256 for s in sessions})
    arrays = []
    for s in sessions:
        frames = cache.open_cache(Path(cache_root) / s.session_id, s, verify_hashes=full_hash)
        recorded_cache = report["caches"].get(s.session_id, {})
        check(f"cache:{s.session_id}", all(frames[4][k] == recorded_cache.get(k)
                                            for k in ("global_sha256", "crop_sha256", "hud_sha256")))
        lag = report["config"]["lag"]
        arrays.append(SessionArrays(s, frames, lag=lag, regimes=tuple(report["config"]["regimes"])))
    ok = not fail
    out = {"scope": f"CPU reload of {candidate} on the {set_name} set", "checks": checks,
           "torch": torch.__version__, "git": None}
    if ok:
        torch.set_num_threads(4)
        tf, sf, _ = predictions(ckpt, arrays, ref["live_mask"])
        summary = summarise(tf, sf)
        mine = _probabilities(tf)
        a = struct.unpack(f"<{len(mine) // 4}f", mine)
        b = struct.unpack(f"<{len(probs) // 4}f", probs)
        delta = max((abs(x - y) for x, y in zip(a, b)), default=0.) if len(a) == len(b) else float("inf")
        for mode, runs in (("tf", tf), ("sf", sf)):
            same = summary[f"{mode}_decisions_sha256"] == ref[f"{mode}_decisions_sha256"]
            theirs = (run / f"{set_name}-cpu-{mode}-decisions.bin").read_bytes()
            detail = None
            if not same:
                step = _first_divergence(_decisions(runs), theirs)
                flat = [p for r in runs for _, p in r]
                # L7: how close that step's decisions sat to a threshold here (numeric noise vs a real mismatch)
                detail = {"first_divergent_step": step,
                          "margin_here": flat[step].get("margin") if step is not None and step < len(flat) else None}
            check(f"{mode}_decisions", same and hashlib.sha256(theirs).hexdigest() == ref[f"{mode}_decisions_sha256"],
                  detail)
        check("probability_delta", delta <= TOLERANCE, delta)
        check("metrics", all(summary[k] == ref[k] for k in ("tf_macro_press_f1_tol", "sf_macro_press_f1_tol",
                                                            "tf_camera_mae_mean", "sf_camera_mae_mean")))
        out.update(summary=summary, max_probability_delta=delta)
    check("no_live_io", not any(m in sys.modules for m in ("vgamepad", "dxcam", "agent.loop")))
    out["ok"] = not fail
    out["failed"] = fail
    return out["ok"], out


def main(argv=None):
    p = argparse.ArgumentParser(description="Verify a rivals-range-bc-v2 candidate on this machine's CPU")
    p.add_argument("--run", required=True)
    p.add_argument("--set", default="val", choices=("val", "dev"))
    p.add_argument("--steps", nargs="+", required=True)
    p.add_argument("--cache-root", required=True)
    p.add_argument("--report-sha256", required=True, help="recorded out of band (review L7)")
    p.add_argument("--sealed-denylist", default=None, help="default: the fit's pinned data/human/sealed-denylist.v2.json")
    p.add_argument("--sealed-denylist-sha256", default=None)
    p.add_argument("--patch-equivalence", default=None, help="default: the fit's pinned data/human/patch-equivalence.json")
    p.add_argument("--patch-equivalence-sha256", default=None)
    p.add_argument("--manifest-hash-only", action="store_true",
                   help="skip re-hashing cache bytes (full hashing is the default, review L7)")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    from . import steps
    denylist = steps.load_denylist(a.sealed_denylist or steps.DENYLIST,
                                   a.sealed_denylist_sha256 or steps.DENYLIST_SHA256)
    equivalence = steps.load_patch_equivalence(a.patch_equivalence or steps.PATCH_EQUIVALENCE,
                                               a.patch_equivalence_sha256 or steps.PATCH_EQUIVALENCE_SHA256)
    ok, out = verify(a.run, a.set, a.steps, a.cache_root, denylist=denylist, report_sha256=a.report_sha256,
                     full_hash=not a.manifest_hash_only, equivalence=equivalence)
    import subprocess
    out["git"] = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    with open(a.out, "x", encoding="utf-8") as stream:
        json.dump(out, stream, indent=1, sort_keys=True, allow_nan=True)
    print(json.dumps({"ok": ok, "failed": out["failed"]}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
