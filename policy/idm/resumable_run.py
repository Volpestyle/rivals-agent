"""v2 consumer: admitted inputs, verified local stores, complete-epoch recovery."""
from pathlib import Path
import json

from policy.idm import cloud_run, refit_stages as R
from policy.idm.telemetry import emit


def relocate(loaded, local_data_root, source_root="/inputs"):
    """Keep source-relative paths; FrameStore still verifies every native hash."""
    source = Path(source_root).resolve(strict=True)
    local = Path(local_data_root).resolve(strict=True)
    R.E.require(not local.is_relative_to(source) and not local.is_relative_to("/outputs"),
                "resumable store must be on local disk")
    result = []
    for item, target in loaded:
        original = Path(item["store"]).resolve(strict=True)
        R.E.require(original.is_relative_to(source), "store outside admitted input root")
        path = local / original.relative_to(source)
        R.E.require(not path.is_symlink() and path.resolve(strict=True).is_relative_to(local),
                    "local store escapes staged root")
        result.append(({**item, "store": str(path)}, target))
    return result


def run(root, *, phase, manifest, manifest_sha256, registry, input_volume_id, output_volume_id,
        scientific_identity, commit=None, resume_state=None, local_data_root=None):
    root = Path(root)
    R.E.require(root.name == phase and phase in R.ARTIFACTS, "resumable stage differs")
    bound = json.loads((root / "started.json").read_bytes())["identity"]
    keys = ("inputs_sha256", "recipe_sha256", "code_sha256")
    R.E.require(set(scientific_identity) == set(keys)
                and all(scientific_identity[k] == bound[k] for k in keys)
                and scientific_identity["inputs_sha256"] == manifest_sha256,
                "scientific identity differs from stage")
    _, loaded, _, _ = cloud_run.load_inputs(
        manifest=manifest, manifest_sha256=manifest_sha256, registry=registry, out=str(root),
        input_volume_id=input_volume_id, output_volume_id=output_volume_id)
    R.D.require_disjoint_roles(loaded)
    R.E.require_decode_platform(loaded)
    if phase not in ("zero", "report"):
        R.E.require(local_data_root is not None, "verified local staging required")
        loaded = relocate(loaded, local_data_root)
    if phase == "fit":
        R.E.require(callable(commit), "epoch checkpoints require durable volume commit")
    else:
        R.E.require(resume_state is None, "epoch resume only applies to fit")

    def progress(value):
        # Reporting must not discard healthy compute or a completed epoch.
        emit(R.write, "idm-epoch-" + phase, root=root / "jobs", owner="idm-owner", host="modal",
             stage="running", evidence=str(root / "completed.json"), progress=json.dumps(value))

    return R.compute(root, phase, loaded, device="cuda", manifest_sha256=manifest_sha256,
                     progress=progress, commit=commit, resume_state=resume_state,
                     scientific_identity=scientific_identity)
