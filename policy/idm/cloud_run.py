"""EXPLORATORY Linux/CUDA adapter; never provisions or chooses a cloud budget.

Existing preflight, match-admission and sealed refusals are shared with the Mac
runner. The external bounded worker owns resource limits and hard teardown.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform

import torch

from policy import idm_targets as T
from policy.idm import decode, explore as E, match_targets
from policy.range_bc.explore_mounts import check_mounts, logical_path
from scripts.job_status import write


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("refit", "prepare"))
    for name in ("manifest", "manifest-sha256", "registry", "out", "input-volume-id", "output-volume-id"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args(argv)
    E.require(platform.system() == "Linux" and os.environ.get("MODAL_TASK_ID"), "Modal container required")
    E.require(torch.cuda.is_available() and torch.cuda.get_device_name() == "NVIDIA L40S", "L40S required")
    torch.set_num_threads(8)
    mounts = check_mounts({"/inputs": a.input_volume_id, "/outputs": a.output_volume_id})
    out = logical_path(a.out, mounts)
    E.require(out.is_relative_to("/outputs"), "output mount required")
    for name in ("manifest", "registry"):
        E.require(logical_path(getattr(a, name), mounts).is_relative_to("/inputs"), "input mount required")
    manifest = E.read_pinned(a.manifest, a.manifest_sha256)
    denylist = T.load_denylist()
    receipt = manifest.get("match_admission")
    admission = None
    if receipt:
        E.require(logical_path(receipt["path"], mounts).is_relative_to("/inputs"), "admission mount required")
        admission = match_targets.load(receipt["path"], receipt["sha256"], registry=a.registry, denylist=denylist)
    # Preserve all source/family/header guards before touching native stores.
    for item in manifest["sessions"]:
        for key in ("targets", "store", "video", "steps", "demo"):
            if key in item:
                E.require(logical_path(item[key], mounts).is_relative_to("/inputs"), "input namespace required")
    loaded = E.preflight(manifest, registry=a.registry, denylist=denylist, admission=admission)
    out.mkdir(parents=True, exist_ok=True)
    job = "idm-cloud-" + a.command
    write(job, root=out / "jobs", owner="idm-owner", host="modal", stage="running", evidence=str(out / "report.json"))
    progress = lambda v: write(job, root=out / "jobs", progress=v)
    try:
        E.write_json(out / "run-manifest.json", manifest)
        if a.command == "refit":
            E.require(a.epochs > 0, "positive epochs required")
            result = E.refit(loaded, out=out, seed=a.seed, epochs=a.epochs, device="cuda", progress=progress)
            from policy.idm.press_diagnostic import run
            diagnostic = out / "press-diagnostic"
            diagnostic.mkdir()
            run(loaded, out / "refit.pt", result["checkpoint_sha256"], diagnostic,
                device="cuda", progress=progress, manifest_sha256=a.manifest_sha256)
        else:
            result = {}
            for item, target in loaded:
                if not item.get("prepare", False):
                    continue
                # Reuse the established graph and exact PTS checks. Linux x86
                # is a new decode backend, recorded in its manifest; no bitwise
                # Mac equivalence claim. The generic decode CLI stays Mac-only.
                progress("Decoding " + target.session_id)
                result[target.session_id] = decode.build(
                    item["targets"], item["steps"], item["demo"], out / target.session_id,
                    video_root=Path(item["video"]).parent, any_platform=True, denylist=denylist,
                    threads=8, match_admission=admission)
        E.write_json(out / "report.json", {"scope": "EXPLORATORY", "review": "provisional",
                                         "manifest_sha256": a.manifest_sha256, "device": "cuda:NVIDIA L40S",
                                         "command": a.command, "result": result})
        write(job, root=out / "jobs", stage="done")
    except BaseException:
        write(job, root=out / "jobs", stage="failed")
        raise


if __name__ == "__main__":
    main()
