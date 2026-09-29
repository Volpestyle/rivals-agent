"""The sole real-data entry point for round 3; library primitives are synthetic seams.

The --receipt-sha256 argument is the externally communicated LEAD pin, not a
self-signature. No command creates an approval. See handoff/round3/impl/FIT-RECEIPT-a3.md.
"""
import argparse
import difflib
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import multiprocessing
import platform
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

import torch

from agent import human_intake
from . import cm3_accounting as accounting
from . import baselines, cm3, cm3_features as features, cm3_proof as proof
from . import cm3_train as training, idle_sidecar, metrics, steps, train
from .model import Config as LegacyConfig

ROOT = Path(__file__).resolve().parents[2]
STAGES = ("inputs", "proof128", "smoke", "extract", "fit")
SUBSETS = {"inputs": "train-inputs-assets-pairing", "proof128": "128-unique-train-frames-both-views",
           "smoke": "first-complete-96-per-train-session-32-full-schedule-updates",
           "extract": "all-cached-frames-seven-frozen-sessions", "fit": "one-registered-fit"}
LOCKS = ("uv.lock", "policy/range_bc/cm3-requirements.txt", "policy/range_bc/cm3-environment.in",
         "policy/range_bc/cm3-execution-constraints.txt", "policy/range_bc/cm3-macos-arm64.lock",
         "policy/range_bc/cm3-linux-x86_64.lock")
require = training.require
MOUNT_ROOTS = ("/inputs", "/outputs")
MODAL_VOLUMES = Path("/__modal/volumes")
RUNTIME_DIAGNOSTIC_PREFIX = "CM3_RUNTIME_MISMATCH "
RUNTIME_DIAGNOSTIC_MAX_BYTES = 16384


def require_runtime_match(kind, expected, actual, message):
    """Fail closed with bounded metadata on stderr; never open an output path."""
    if expected == actual:
        return
    diagnostic = {"format": "cm3-runtime-mismatch-v1", "kind": kind,
        "expected_sha256": cm3.digest(expected), "actual_sha256": cm3.digest(actual),
        "differing_top_level_keys": [], "value_differences": [],
        "mapping_differences": {"packages": [], "locks": []},
        "torch_build_unified_diff": [], "truncated": False}

    def encode():
        return RUNTIME_DIAGNOSTIC_PREFIX + json.dumps(diagnostic, sort_keys=True, separators=(",", ":")) + "\n"

    def append(items, value):
        items.append(value)
        # ensure_ascii=True makes the string length its UTF-8 byte length, even
        # when package metadata contains non-ASCII text or embedded newlines.
        if len(encode()) > RUNTIME_DIAGNOSTIC_MAX_BYTES:
            items.pop()
            diagnostic["truncated"] = True

    def difference(key, left, right):
        return {"key": key, "expected_present": key in left, "actual_present": key in right,
                "expected": left.get(key), "actual": right.get(key)}

    keys = [key for key in sorted(set(expected) | set(actual))
            if key not in expected or key not in actual or expected[key] != actual[key]]
    for key in keys:
        append(diagnostic["differing_top_level_keys"], key)
    for key in keys:
        if key in ("packages", "locks") and isinstance(expected.get(key), dict) and isinstance(actual.get(key), dict):
            left, right = expected[key], actual[key]
            for name in sorted(set(left) | set(right)):
                if name not in left or name not in right or left[name] != right[name]:
                    append(diagnostic["mapping_differences"][key], difference(name, left, right))
        elif key == "torch_build" and isinstance(expected.get(key), str) and isinstance(actual.get(key), str):
            for line in difflib.unified_diff(expected[key].splitlines(), actual[key].splitlines(),
                    fromfile="expected.torch_build", tofile="actual.torch_build", lineterm=""):
                append(diagnostic["torch_build_unified_diff"], line)
        else:
            append(diagnostic["value_differences"], difference(key, expected, actual))
    print(encode(), end="", file=sys.stderr, flush=True)
    require(False, message)


def logical_path(path, *, resolve_local=True):
    """Keep approved Modal aliases in references; retain local-path behavior elsewhere."""
    path = Path(path)
    for root in map(Path, MOUNT_ROOTS):
        if path.is_relative_to(root):
            require(".." not in path.parts, "mount path traversal")
            child = root
            for part in path.relative_to(root).parts:
                child /= part
                require(not child.is_symlink(), "child symlink in mount namespace")
            return path
    return path.resolve() if resolve_local else path


def check_namespace(receipt, ref):
    """After receipt hash authentication, bind logical aliases to exact volume IDs."""
    def paths(value, key=None):
        if isinstance(value, dict):
            for name, child in value.items():
                yield from paths(child, name)
        elif isinstance(value, list):
            for child in value:
                yield from paths(child)
        elif isinstance(value, str) and (Path(value).is_absolute() or key in ("path", "output", "cache", "directory")):
            yield Path(value)
    named = list(paths(receipt)) + [Path(ref["path"])]
    mounts = receipt.get("context", {}).get("mounts", receipt.get("mounts"))
    if mounts is None:
        require(not any(p.is_relative_to(root) for p in named for root in (*MOUNT_ROOTS, MODAL_VOLUMES)),
                "Modal volume pins required")
        return
    require(isinstance(mounts, dict) and set(mounts) == set(MOUNT_ROOTS), "both Modal volume pins required")
    targets = {}
    for alias, volume in mounts.items():
        require(isinstance(volume, str) and re.fullmatch(r"vo-[a-zA-Z0-9]+", volume), "invalid volume ID")
        root, expected = Path(alias), MODAL_VOLUMES / volume
        require(root.is_symlink() and root.readlink() == expected and root.resolve(strict=True) == expected
                and expected.is_dir() and not expected.is_symlink(), "mount differs from pinned volume")
        targets[root] = expected
    require(len(set(mounts.values())) == 2, "input and output volumes must differ")
    for path in named:
        root = next((r for r in targets if path.is_relative_to(r)), None)
        require(root is not None, "path outside logical mount namespace")
        path = logical_path(path)
        require(path.resolve(strict=False) == targets[root] / path.relative_to(root), "mount path escaped pinned volume")


def sha(path):
    return steps.sha256(Path(path))


def read_json(path):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            require(k not in result, "duplicate JSON key")
            result[k] = v
        return result
    def invalid(value):
        raise ValueError("nonfinite JSON value: " + value)
    path = Path(path)
    require(path.stat().st_size <= 32 * 1024 * 1024, "oversize receipt")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=invalid)


def pinned(ref):
    require(isinstance(ref, dict) and set(ref) == {"path", "sha256"}, "pinned file reference required")
    require(Path(ref["path"]).is_absolute(), "absolute pinned path required")
    require(re.fullmatch("[0-9a-f]{64}", ref["sha256"]) is not None, "invalid receipt digest")
    path = logical_path(ref["path"], resolve_local=False)
    require(sha(path) == ref["sha256"], "receipt/file hash mismatch")
    return path


def document(ref):
    return read_json(pinned(ref))


def reference(path):
    path = logical_path(path)
    return {"path": str(path), "sha256": sha(path)}


def write_json(path, value):
    path = logical_path(path, resolve_local=False)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    return reference(path)


def code_hashes():
    # Includes the reviewed sidecar, registry, denylist and all imported legacy code.
    return {p: sha(ROOT / p) for p in train.code_closure()}


def software_snapshot(device, *, observation=None):
    name = "cm3-macos-arm64.lock" if device == "mps" else "cm3-linux-x86_64.lock"
    packages = dict(re.findall(r"^([a-zA-Z0-9_.-]+)==([^\s;\\]+)",
                              (ROOT / "policy/range_bc" / name).read_text(), re.M))
    for package, version in packages.items():
        require(importlib.metadata.version(package) == version, "installed package differs: " + package)
    raw_os, build = platform.platform(), torch.__config__.show()
    result = {"python": platform.python_version(), "os": raw_os, "machine": platform.machine(),
              "packages": packages, "torch_build": build, "locks": {p: sha(ROOT / p) for p in LOCKS}}
    if observation is not None:
        observation.update(format="cm3-runtime-observation-v1", platform=raw_os)
    if device == "cuda":
        kernel = platform.release()
        require(platform.system() == "Linux" and result["machine"] == "x86_64" and kernel
                and re.fullmatch(r"Linux-" + re.escape(kernel) + r"-x86_64-with-glibc[0-9]+(?:\.[0-9]+)+", raw_os),
                "unrecognized CUDA platform layout")
        lines = build.splitlines(keepends=True)
        capability = [line for line in lines if "CPU capability usage" in line]
        require(len(capability) == 1 and re.fullmatch(
            r"  - CPU capability usage: (DEFAULT|AVX2|AVX512)\n", capability[0]),
            "unrecognized CPU capability layout")
        result.update(format="cm3-software-v2", os="Linux-" + raw_os[len("Linux-" + kernel + "-"):],
                      torch_build="".join(line for line in lines if line != capability[0]))
        if observation is not None:
            observation.update(kernel=kernel, torch_cpu_capability_line=capability[0])
    return result


def hardware_snapshot(device, *, observation=None):
    if device == "cuda":
        require(platform.system() == "Linux" and platform.machine() == "x86_64", "CUDA host refused")
        description = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], text=True).strip()
        require("\n" not in description, "exactly one visible GPU required")
        name, driver = [v.strip() for v in description.split(",")]
        name = name.removeprefix("NVIDIA ")
        match = re.fullmatch(r"([1-9][0-9]*)\.[0-9]+(?:\.[0-9]+)?", driver)
        require(match, "unrecognized NVIDIA driver layout")
        if observation is not None:
            observation.update(format="cm3-runtime-observation-v1", driver=driver)
        driver = match[1]
    else:
        require(device == "mps" and platform.system() == "Darwin" and platform.machine() == "arm64",
                "MPS host refused")
        name = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
        driver = platform.mac_ver()[0]
    return {"class": device + ":" + name, "driver": driver,
            "cuda_runtime": torch.version.cuda, "cudnn": torch.backends.cudnn.version()}


def runtime_snapshot(device):
    """Capture required identity and raw host observations together, before freezing."""
    observation = {}
    software = software_snapshot(device, observation=observation)
    hardware = hardware_snapshot(device, observation=observation)
    return {"software": software, "hardware": hardware, "runtime_observation": observation}


def check_sources(context, stage):
    """Metadata only. Complete allowlist/registry/denylist refusal precedes tables/caches."""
    sources = context["sources"]
    expected = {**cm3.TRAIN_TABLES, **cm3.DEV_SESSIONS}
    require(set(sources) == set(expected), "frozen seven-source allowlist required")
    denylist = human_intake.load_denylist(pinned(context["denylist"]), sha256_pin=steps.DENYLIST_SHA256)
    registrations = human_intake.check_registry(pinned(context["registry"]), denylist=denylist)
    for sid, spec in sources.items():
        require(set(spec) == {"role", "table", "cache", "cache_manifest_sha256", "sidecar"}, "source schema/bypass")
        role = "train" if sid in cm3.TRAIN_TABLES else "dev"
        require(spec["role"] == role, "dev session cannot be train")
        require(sid in registrations, "unregistered session")
        p = registrations[sid]
        require(p.split == "train" and p.session_group == sid, "registry split/group refused")
        require(spec["table"]["sha256"] == expected[sid], "table outside frozen allowlist")
        require(Path(spec["table"]["path"]).name in (sid + ".steps.jsonl", sid + ".jsonl"), "wrong table path")
        require((role == "train") == (spec["sidecar"] is not None), "sidecar bypass or dev sidecar")
        require(not human_intake.sealed_matches(
            {"session_id": sid, "media_sha256": p.expected_media_sha256, "video_path": p.video_path},
            denylist, Path(context["registry"]["path"]).parent), "sealed source")
    allowed = list(cm3.TRAIN_TABLES) if stage in ("inputs", "proof128", "smoke") else list(expected)
    return allowed, denylist, registrations


def authenticate(stage, ref, *, runtime=True, runtime_observation=None):
    """No payload reads/output/model construction here. Re-run in the bounded worker."""
    receipt = document(ref)
    require(receipt["format"] == "cm3-stage-approval-v1" and receipt["approved_by"] == "herdr-lead",
            "lead stage approval required")
    require(receipt["stage"] == stage and stage in STAGES, "wrong stage")
    check_namespace(receipt, ref)
    context = receipt["context"]
    fields = {"amendment", "device", "hardware", "software", "code", "implementation_review", "judge", "judge_tests",
              "registry", "denylist", "patch_equivalence", "sidecar_manifest", "sidecar_reader_sha256",
              "assets", "dev_workload", "sources"}
    require(set(context) == fields | ({"mps_A"} if context.get("device") == "mps" else set())
            | ({"mounts"} if "mounts" in context else set()),
            "incomplete context or caller-supplied weights/statistics")
    require(Path(receipt["output"]).is_absolute(), "absolute immutable output required")
    identity = cm3.digest(context)
    require(receipt["context_sha256"] == identity and context["amendment"] in (2, 3), "context identity")
    require(receipt["subset"] == SUBSETS[stage], "unregistered subset")
    require(context["device"] in ("mps", "cuda"), "device not chosen")
    require(set(context["hardware"]) == {"class", "driver", "cuda_runtime", "cudnn"}
            and context["hardware"]["class"].startswith(context["device"] + ":")
            and context["hardware"]["driver"], "hardware class/driver required; no host UUID pin")
    require(context["sidecar_manifest"]["sha256"] ==
            "03bbf9836dc06824d2380bcaa9c096ea2b6f8cea46758c18316bb70b7eb016ba", "reviewed sidecar manifest required")
    require(set(context["assets"]) == {"directory", "config_sha256", "receipt"}
            and context["assets"]["receipt"]["weights_sha256"] == features.WEIGHTS_SHA256, "asset receipt incomplete")
    workload = context["dev_workload"]
    require(set(workload) == {"run_lengths", "window_count"} and workload["run_lengths"]
            and all(type(n) is int and n > 0 for n in workload["run_lengths"])
            and type(workload["window_count"]) is int and workload["window_count"] > 0, "timing dimensions required")
    if context["device"] == "mps":
        require(set(context["mps_A"]) == {"0", "1", "2"}, "historical A pins required")
    require(context["code"] == code_hashes(), "code closure changed")
    require(set(context["software"]["locks"]) == set(LOCKS), "incomplete software lock")
    require(context["software"]["locks"] == {p: sha(ROOT / p) for p in LOCKS}, "software hashes changed")
    require(context["sidecar_reader_sha256"] == sha(idle_sidecar.__file__), "unreviewed sidecar reader")
    pinned(context["judge"])
    pinned(context["judge_tests"])
    review = document(context["implementation_review"])
    require(review["status"] == "PASS" and review["code"] == context["code"], "implementation review missing")
    require(review["reviewer"] != "r3-impl", "independent review required")
    predecessors = receipt["predecessors"]
    index = STAGES.index(stage)
    require(set(predecessors) == set(STAGES[:index]), "missing/wrong predecessor order")
    previous_elapsed, previous_refs = 0., {}
    previous_results = {}
    for name in STAGES[:index]:
        result = document(predecessors[name])
        require(result["format"] == "cm3-stage-result-v1" and result["stage"] == name
                and result["status"] == "PASS" and result["context_sha256"] == identity,
                "predecessor stage/status/context mismatch")
        approval = document(result["approval"])
        require(approval["approved_by"] == "herdr-lead" and approval["stage"] == name
                and approval["context"] == context and approval["predecessors"] == previous_refs,
                "broken approval chain")
        authenticate(name, result["approval"], runtime=False)
        require(result["elapsed_total_seconds"] >= previous_elapsed, "budget ledger moved backwards")
        previous_elapsed = result["elapsed_total_seconds"]
        previous_refs[name] = predecessors[name]
        previous_results[name] = result
    if stage != "inputs":
        require(receipt["pairing"] == previous_results["inputs"]["artifacts"]["pairing"],
                "pre-proof pairing manifest not bound")
        pinned(receipt["pairing"])
    budget = receipt["budget"]
    require(0 < budget["cap_seconds"] <= 69120 and budget["spent_seconds"] >= previous_elapsed
            and 0 < budget["stage_seconds"] <= budget["cap_seconds"] - budget["spent_seconds"], "budget exhausted")
    require(budget["approved_by"] == "herdr-lead", "budget not approved")
    if "accounting" in budget:
        require(budget["cloud_instance"] == context["hardware"]["class"], "budget class mismatch")
        accounting.allocation(budget, document, required_results=predecessors.values())
    if context["device"] == "cuda" and "accounting" not in budget:
        require(budget["cloud_instance"] and 0 < budget["hourly_usd"] and
                budget["hourly_usd"] * budget["cap_seconds"] / 3600 <= budget["cloud_cap_usd"], "cloud budget missing")
    if stage in ("extract", "fit"):
        require(0 < budget["forecast_total_seconds"] <= budget["cap_seconds"], "full budget approval missing")
    if stage == "fit":
        require(receipt["freeze"] == previous_results["extract"]["artifacts"], "pre-freeze fit or changed freeze")
        require(receipt["arm"] in ("A", *cm3.ARMS) and type(receipt["seed"]) is int
                and receipt["seed"] in range(3), "unregistered arm/seed")
        require(receipt["purpose"] == "registered" or
                (receipt["purpose"] == "repeat" and receipt["arm"] == "H" and receipt["seed"] == 0),
                "unregistered repeat")
        require(isinstance(receipt["attempt_id"], str) and re.fullmatch(r"[a-zA-Z0-9_.-]+", receipt["attempt_id"]),
                "unique attempt identity required")
        require(set(receipt["fit_predecessors"]) == required_fit_predecessors(receipt), "fit predecessor gate missing")
    allowed, denylist, registrations = check_sources(context, stage)
    require(receipt["allowed_sources"] == allowed, "wrong allowed sources")
    if runtime:
        observed = {} if runtime_observation is None else {"observation": runtime_observation}
        require_runtime_match("software", context["software"], software_snapshot(context["device"], **observed), "software runtime differs")
        require_runtime_match("hardware", context["hardware"], hardware_snapshot(context["device"], **observed), "wrong device/model/driver")
        if stage == "fit":
            require_fit_peak_supported(context["device"], context)
    if stage == "fit":
        check_fit_predecessors(receipt)
    return receipt, denylist, registrations, previous_results


class Inputs:
    """Only constructed by the guarded loader. No caller-supplied stats or vectors."""
    def __init__(self, arrays, caches, identities, weights, stats, binding):
        self.arrays, self.caches, self.identities = arrays, caches, identities
        self.weights, self.stats, self.binding = weights, stats, binding

    def check(self):
        require(self.binding["weight_vectors"] == {sid: proof.f32_digest(v) for sid, v in self.weights.items()},
                "sidecar vector replaced or swapped")
        expected = steps.train_statistics([self.arrays[s].session for s in cm3.TRAIN_TABLES], regimes=("normal",))
        require(self.stats == expected and cm3.digest(expected) == self.binding["statistics_sha256"],
                "statistics replaced/dev-derived")
        for sid, arr in self.arrays.items():
            require(arr.session.sha256 == self.identities[sid]["steps_sha256"], "source replaced")


def load_inputs(receipt, denylist, registrations):
    context = receipt["context"]
    # Authenticate table bytes only after every requested ID was checked as metadata.
    paths = [pinned(context["sources"][sid]["table"]) for sid in receipt["allowed_sources"]]
    eq_path = pinned(context["patch_equivalence"])
    equivalence = steps.load_patch_equivalence(eq_path, hashlib.sha256(eq_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest())
    sessions = steps.load_cohort(paths, splits=("train",), denylist=denylist, equivalence=equivalence)
    require([s.session_id for s in sessions] == receipt["allowed_sources"], "table/header order mismatch")
    manifest = context["sidecar_manifest"]
    pinned(manifest)
    arrays, caches, identities, weights = {}, {}, {}, {}
    sidecars = {}
    for session in sessions:
        sid = session.session_id
        spec = context["sources"][sid]
        require(session.header["media_sha256"] == registrations[sid].expected_media_sha256, "registry media mismatch")
        # ALL paths, including I, use the same rehashed RGB cache identity.
        cache, identity = features.source_identity(session, spec["cache"],
            manifest_sha256=spec["cache_manifest_sha256"], role=spec["role"])
        caches[sid], identities[sid] = cache, identity
        arrays[sid] = train.SessionArrays(session, cache, lag=0, regimes=("normal",))
        if spec["role"] == "train":
            sidecar = pinned(spec["sidecar"])
            values = idle_sidecar.load_weights(session.path, sidecar,
                manifest_path=manifest["path"], manifest_sha256=manifest["sha256"],
                registry_path=context["registry"]["path"], denylist_path=context["denylist"]["path"])
            weights[sid] = torch.tensor(list(values), dtype=torch.float32)
            training.validate_weights(weights[sid], len(arrays[sid].valid))
            sidecars[sid] = spec["sidecar"]
    stats = steps.train_statistics([arrays[s].session for s in cm3.TRAIN_TABLES], regimes=("normal",))
    binding = {"sources": identities, "sidecar_manifest": manifest, "sidecars": sidecars,
               "reader_sha256": context["sidecar_reader_sha256"],
               "weight_vectors": {sid: proof.f32_digest(v) for sid, v in weights.items()},
               "statistics_sha256": cm3.digest(stats), "statistics_sources": list(cm3.TRAIN_TABLES)}
    obj = Inputs(arrays, caches, identities, weights, stats, binding)
    obj.check()
    return obj


def batches(inputs, feature_arrays=None, *, dev=False):
    inputs.check()
    ids = list(cm3.DEV_SESSIONS if dev else cm3.TRAIN_TABLES)
    weights = None if dev else [inputs.weights[s] for s in ids]
    arms = ("I",) if feature_arrays is None else cm3.ARMS
    result = {arm: training.Batches([inputs.arrays[s] if arm == "I" else feature_arrays[s] for s in ids],
                                   arm=arm, weights=weights, training=not dev) for arm in arms}
    if len(result) == 3:
        for seed in range(3):
            for epoch in range(13):
                hashes = [cm3.window_order(b, seed, epoch)[1] for b in result.values()]
                require(all(h == hashes[0] for h in hashes), "independent H/I/W window pairing failed")
    return result


def input_pairing(inputs, expected=None):
    # Metadata-only feature adapters: constructing windows never dereferences scene tensors.
    mapped = {sid: training.FeatureArrays(inputs.arrays[sid],
        (None, None, sorted(set(inputs.arrays[sid].row_frame.tolist())), {"source": inputs.identities[sid]}))
        for sid in cm3.TRAIN_TABLES}
    paired = batches(inputs, mapped)
    manifest = proof.paired_receipt(paired["H"])
    if expected is not None:
        require(manifest == document(expected), "pre-proof pairing changed")
    return manifest


def evaluation(model, arrays, stats, device):
    tf = train.predict_teacher(model, arrays, device=device)
    sf = train.predict_self(model, arrays, stats["live_mask"], device=device)
    teacher = metrics.stratified(tf, **metrics.TEACHER)
    executed = metrics.evaluate(train.executed_runs(tf, stats["live_mask"]), **metrics.EXECUTED_TEACHER)
    self_fed = metrics.stratified(sf, **metrics.SELF)
    zero = metrics.evaluate(metrics.predict_runs(train.baseline_runs(arrays), baselines.zero_motion),
                            **metrics.TEACHER)["camera_mae_mean"]
    checks = metrics.selffed_checks(sf, stats["live_mask"])
    # Match the original evaluate_set's stored check blocks as well as its math.
    checks.update(camera_mae=self_fed["all"]["camera_mae_mean"], zero_motion_camera_mae=zero,
        held_change_f1={name: {n: a["held_change_f1"] for n, a in block["actions"].items()}
            for name, block in (("teacher_forced", teacher["all"]), ("executed_teacher_forced", executed),
                                ("self_fed", self_fed["all"]))})
    return {"teacher_forced": teacher, "executed_teacher_forced": executed, "self_fed": self_fed,
            "self_fed_checks": checks, "sanity": metrics.sanity(sf), "zero_motion_camera_mae": zero,
            "executed_decisions_sha256": cm3.digest([[p for _, p in run] for run in sf])}


def _worker(stage, ref, output, started):
    observation = {}
    receipt, denylist, registrations, predecessors = authenticate(stage, ref, runtime_observation=observation)
    context, device = receipt["context"], receipt["context"]["device"]
    backend = proof.configure_backend(device)
    backend["hardware"] = context["hardware"]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    input_start = time.monotonic()
    inputs = load_inputs(receipt, denylist, registrations)
    input_seconds = time.monotonic() - input_start
    artifacts = {"inputs": write_json(output / "inputs.json", inputs.binding)}
    raw_batches = batches(inputs)["I"]
    audit = training.effective_weight_audit(raw_batches, raw_batches.weights)
    artifacts["audit"] = write_json(output / "effective-weight.json", audit)
    pairing = input_pairing(inputs, receipt.get("pairing"))
    artifacts["pairing"] = write_json(output / "pairing.json", pairing)
    if stage != "inputs":
        original = document(predecessors["inputs"]["artifacts"]["inputs"])
        current = dict(inputs.binding, sources={s: inputs.identities[s] for s in cm3.TRAIN_TABLES})
        require(original == current, "train inputs changed since pre-proof manifest")
    if stage == "fit":
        result = fit_one(receipt, inputs, predecessors["extract"]["artifacts"], backend, output)
    else:
        backbone = features.FrozenDino(context["assets"]["directory"], config_sha256=context["assets"]["config_sha256"]).to(device)
        require(backbone.asset_receipt == context["assets"]["receipt"], "asset/implementation identity changed")
        if stage == "inputs":
            result = {"backend": backend, "assets": backbone.asset_receipt}
        elif stage == "proof128":
            values, result = proof.numerical_features(backbone, list(inputs.arrays.values()),
                proof.sample_frames(list(inputs.arrays.values())), device=device)
            model = cm3.Policy(cm3.Config("H", 0))
            g, c = values["global"][None], values["crop"][None]
            prev = torch.zeros(1, 128, steps.PREV_DIM)
            result["policy"] = proof.policy_comparison(model, g, c, prev, device=device,
                live_mask=inputs.stats["live_mask"], pitch_known=True)
            result["normalization"] = proof.normalization_diagnostics(model, g, c, prev)
            artifacts["probe_global"] = save_tensor(output / "global.pt", g)
            artifacts["probe_crop"] = save_tensor(output / "crop.pt", c)
        else:
            selections = {}
            if stage == "smoke":
                for wi in training.smoke_windows(raw_batches):
                    si, start, n, _ = raw_batches.windows[wi]
                    arr = raw_batches.arrays[si]
                    selections[arr.session.session_id] = sorted(set(arr.row_frame[start:start + n].tolist()))
            else:
                selections = {s: list(range(len(cache[0]))) for s, cache in inputs.caches.items()}
            mapped, feature_refs = {}, {}
            extraction_start = time.monotonic()
            for sid, ids in selections.items():
                dest = output / "features" / sid
                features.write_cache(dest, backbone, inputs.caches[sid], inputs.identities[sid],
                    asset_receipt=backbone.asset_receipt, backend_receipt=backend, selected_frames=ids)
                feature_refs[sid] = reference(dest / "manifest.json")
                opened = features.open_features(dest, manifest_sha256=feature_refs[sid]["sha256"],
                    identity=inputs.identities[sid], assets=backbone.asset_receipt, backend=backend)
                mapped[sid] = training.FeatureArrays(inputs.arrays[sid], opened)
            artifacts["features"] = feature_refs
            extraction_seconds = time.monotonic() - extraction_start
            paired = batches(inputs, mapped)
            require(pairing == proof.paired_receipt(paired["H"]), "extracted window pairing changed")
            if stage == "extract":
                result = {"cache_freeze": feature_refs, "backend": backend, "assets": backbone.asset_receipt}
            else:
                result = smoke_queue(receipt, inputs, paired, predecessors["proof128"], output)
            result["extraction_and_rehash"] = {"seconds": extraction_seconds,
                "views": 2 * sum(map(len, selections.values())),
                "views_per_second": 2 * sum(map(len, selections.values())) / extraction_seconds}
    result["source_verification_seconds"] = input_seconds
    artifacts["details"] = write_json(output / "details.json", result)
    elapsed = time.monotonic() - started
    require(elapsed < receipt["budget"]["stage_seconds"], "INCOMPLETE: stage time limit")
    result_receipt = {"format": "cm3-stage-result-v1", "stage": stage, "status": "PASS",
        "approval": ref, "context_sha256": receipt["context_sha256"], "artifacts": artifacts,
        "runtime_observation": observation,
        "elapsed_stage_seconds": elapsed, "elapsed_total_seconds": receipt["budget"]["spent_seconds"] + elapsed}
    if stage == "fit":
        result_receipt.update({k: receipt[k] for k in ("arm", "seed", "purpose", "attempt_id")})
        result_receipt.update(hardware=context["hardware"], code_sha256=cm3.digest(context["code"]),
                              software_sha256=cm3.digest(context["software"]))
    # Parent alone promotes completion after confirming the child finished within its allocation.
    write_json(output / "completed.json", result_receipt)


def save_tensor(path, value):
    with Path(path).open("xb") as stream:
        torch.save(value, stream)
    return reference(path)


def legacy_smoke(inputs, device):
    """Legacy A initialization/augmentation/optimizer, first 32 of full 13-epoch schedule."""
    raw = train.Batches([inputs.arrays[s] for s in cm3.TRAIN_TABLES])
    chosen = training.smoke_windows(raw)
    train.seed_everything(0)
    model = train.Policy(LegacyConfig(hud=False)).to(device).train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=.0003, weight_decay=.0001)
    total = 13 * math.ceil(len(raw.windows) / 8)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, train.schedule(total, min(500, total)))
    generator = torch.Generator().manual_seed(0)
    pw = train.pos_weights(inputs.stats).to(device)
    torch.cuda.synchronize()
    started = time.monotonic()
    losses = []
    for update in range(32):
        ids = [chosen[(update * 8 + j) % 5] for j in range(8)]
        batch = train.to_device(raw.batch(ids, generator, jitter=.1, prev_dropout=.2), device)
        loss = train.total_loss(train.loss_terms(*train.forward(model, batch)[:2], batch, pw))
        require(bool(torch.isfinite(loss)), "nonfinite A smoke")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
        optimizer.step()
        scheduler.step()
        losses.append(float(loss.detach()))
    torch.cuda.synchronize()
    elapsed = time.monotonic() - started
    return model, {"updates": 32, "full_schedule_updates": total, "seconds_per_update": elapsed / 32,
                   "losses": losses, "discarded": True, "dev_opened": False}


def smoke_queue(receipt, inputs, paired, probe, output):
    device = receipt["context"]["device"]
    workload = receipt["context"]["dev_workload"]  # dimensions only, no dev payloads
    g = torch.load(pinned(probe["artifacts"]["probe_global"]), weights_only=True)
    c = torch.load(pinned(probe["artifacts"]["probe_crop"]), weights_only=True)
    result, first = {}, None
    for arm in ("H", "H-repeat", "I", "W"):
        key = arm.split("-")[0]
        model, smoke = training.smoke(paired[key], inputs.stats, arm=key, device=device,
                                     approved_stage="lead-approved-post-numerical-proof")
        if arm == "H":
            comparison = proof.policy_comparison(model, g, c, torch.zeros(1, 128, steps.PREV_DIM),
                device=device, live_mask=inputs.stats["live_mask"], pitch_known=True)
            first = (model.cpu(), smoke)
            result["trained_H_comparison"] = comparison
            model.to(device)
        elif arm == "H-repeat":
            result["repeat"] = proof.verify_smoke_repeat(*first, model, smoke)
            first = None
        timing = proof.time_evaluation(model, workload["run_lengths"], device=device, path=key,
                                       window_count=workload["window_count"])
        result[arm] = {"smoke": smoke, "timing": timing}
        model.cpu()
        del model
    if device == "cuda":
        model, smoke = legacy_smoke(inputs, device)
        result["A"] = {"smoke": smoke, "timing": proof.time_evaluation(model, workload["run_lengths"],
            device=device, path="A", window_count=workload["window_count"])}
    return result


def judge_module(context):
    spec = importlib.util.spec_from_file_location("_cm3_frozen_judge", pinned(context["judge"]))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def control_checks(report, judge):
    checks = dict(report["self_fed_checks"])
    require(checks["any_hold_observable_steps"] == judge.OBSERVABLE and checks["any_hold_excluded_steps"] == 0
            and checks["human_any_hold_share"] == judge.HUMAN, "changed dev denominator/baseline")
    checks["camera_mae"] = report["self_fed"]["all"]["camera_mae_mean"]
    require(report["zero_motion_camera_mae"] == judge.ZERO, "changed zero-motion baseline")
    checks["zero_motion_camera_mae"] = report["zero_motion_camera_mae"]
    return judge.seed_checks(checks)


def required_fit_predecessors(receipt):
    if receipt.get("context", {}).get("amendment") == 3:
        return set() if receipt["arm"] == "A" or (receipt["arm"], receipt["seed"]) == ("H", 0) else {"phase1_gate"}
    if receipt["arm"] == "A":
        return set()
    keys = {"A_control_gate"}
    if receipt["purpose"] == "repeat":
        keys.add("H0")
    elif (receipt["arm"], receipt["seed"]) != ("H", 0):
        keys.add("H0_repeat")
    return keys


def fit_result(ref, context, *, arm, seed, purpose="registered"):
    result = document(ref)
    require(result["format"] == "cm3-stage-result-v1" and result["status"] == "PASS" and result["stage"] == "fit",
            "incomplete per-fit predecessor")
    require((result["arm"], result["seed"], result["purpose"]) == (arm, seed, purpose), "wrong predecessor arm/seed")
    require(result["context_sha256"] == cm3.digest(context) and result["hardware"] == context["hardware"]
            and result["code_sha256"] == cm3.digest(context["code"])
            and result["software_sha256"] == cm3.digest(context["software"]), "mixed hardware/code/software")
    approval, _, _, _ = authenticate("fit", result["approval"], runtime=False)
    require((approval["arm"], approval["seed"], approval["purpose"]) == (arm, seed, purpose)
            and approval["context"] == context and approval["attempt_id"] == result["attempt_id"], "per-fit approval mismatch")
    require(0 <= result["elapsed_stage_seconds"] <= approval["budget"]["stage_seconds"]
            and result["elapsed_total_seconds"] >= approval["budget"]["spent_seconds"] + result["elapsed_stage_seconds"],
            "per-fit elapsed budget mismatch")
    require(logical_path(ref["path"]) == logical_path(approval["output"]) / "result.json", "wrong attempt output")
    require(not (Path(approval["output"]) / "INCOMPLETE.json").exists(), "interrupted attempt")
    details = document(result["artifacts"]["details"])
    if arm != "A" or context["device"] == "cuda":
        require([row["epoch"] for row in details["logs"]["epochs"]] == list(range(13)), "partial fit epochs")
    pinned(details["checkpoint_file"])
    require(details["checkpoint_sha256"] == details["checkpoint_file"]["sha256"], "checkpoint identity mismatch")
    stable = stable_fit_content(details["checkpoint_sha256"], details["logs"], details["evaluation"], details.get("context", {}))
    require(details["stable_sha256"] == cm3.digest(stable), "changed non-timing fit content")
    if purpose == "repeat" and context["amendment"] == 2:
        require(details["repeat_identical"] is True and details["repeats"] == approval["fit_predecessors"]["H0"],
                "repeat predecessor changed")
        _, original = fit_result(details["repeats"], context, arm="H", seed=0)
        require(original["stable_sha256"] == details["stable_sha256"], "H0 repeat content changed")
    return result, details


def check_fit_predecessors(receipt):
    deps, context = receipt["fit_predecessors"], receipt["context"]
    if context["amendment"] == 3:
        if deps:
            check_phase1_gate(deps["phase1_gate"], context)
        return
    if receipt["arm"] == "A":
        return
    gate = document(deps["A_control_gate"])
    require(gate["format"] == "cm3-control-gate-v1" and gate["approved_by"] == "herdr-lead"
            and gate["status"] == "PASS" and gate["context_sha256"] == cm3.digest(context), "A gate missing")
    require(set(gate["controls"]) == {"0", "1", "2"}, "three A controls required")
    judge = judge_module(context)
    passes = 0
    for seed in range(3):
        _, details = fit_result(gate["controls"][str(seed)], context, arm="A", seed=seed)
        passes += control_checks(details["evaluation"], judge)["pass"]
    require(passes < 2, "CONTROL_REGIME_STOP: A passes S")
    if "H0" in deps:
        fit_result(deps["H0"], context, arm="H", seed=0)
    if "H0_repeat" in deps:
        _, details = fit_result(deps["H0_repeat"], context, arm="H", seed=0, purpose="repeat")
        require(details["repeat_identical"] is True, "H0 repeat gate failed")
        _, original = fit_result(details["repeats"], context, arm="H", seed=0)
        require(original["stable_sha256"] == details["stable_sha256"], "H0 repeat content changed")


def check_phase1_gate(ref, context):
    gate = document(ref)
    require(gate["format"] == "cm3-phase1-gate-v1" and gate["approved_by"] == "herdr-lead"
            and gate["status"] == "PASS" and gate["context_sha256"] == cm3.digest(context), "phase 1 gate missing")
    refs = gate["outputs"]
    require(set(refs) == {"A0", "A1", "A2", "H0", "H0_repeat"}, "complete phase 1 required")
    judge = judge_module(context)
    controls = [fit_result(refs[f"A{s}"], context, arm="A", seed=s)[1] for s in range(3)]
    require(sum(control_checks(d["evaluation"], judge)["pass"] for d in controls) < 2, "CONTROL_REGIME_STOP: A passes S")
    original = fit_result(refs["H0"], context, arm="H", seed=0)[1]
    repeat = fit_result(refs["H0_repeat"], context, arm="H", seed=0, purpose="repeat")[1]
    require(original["stable_sha256"] == repeat["stable_sha256"], "phase 1 H0 repeat differs")
    identity = lambda d: {"checkpoint_sha256": d["checkpoint_sha256"], "content_sha256": d["stable_sha256"]}
    require(gate["A_control_gate"] == {"status": "PASS", "controls": {str(s): identity(d) for s, d in enumerate(controls)}},
            "judge/runner A gate identities differ")
    require(gate["H0_repeat"] == {"status": "PASS", "repeat_identical": True,
                                 "H0": identity(original), "repeat": identity(repeat)}, "judge/runner repeat identities differ")
    require(isinstance(gate["completed"], str) and gate["completed"]
            and re.fullmatch("[0-9a-f]{64}", gate["launch_pins_sha256"]), "judge phase 1 gate metadata missing")
    return refs


MPS_MEMORY_POLL_SECONDS = .01


def require_fit_peak_supported(device, context=None):
    if device == "cuda":
        return
    require(device == "mps" and context is not None and context["amendment"] == 3,
            "MPS fit blocked: requires pinned A3 judge accepting unmeasurable_mps")
    judge = judge_module(context)  # exact externally pinned source, no filename/source-text guesses
    require(getattr(judge, "MPS_PEAK_STATUS", None) == "unmeasurable_mps"
            and getattr(judge, "MPS_MEMORY_SAMPLE_INTERVAL_MS", None) == 1000 * MPS_MEMORY_POLL_SECONDS,
            "MPS fit blocked: pinned judge has no explicit unmeasurable_mps acceptance")


class FitMeasurement:
    def __init__(self, device, context=None):
        require_fit_peak_supported(device, context)
        self.device, self.stop, self.thread = device, threading.Event(), None
        self.high_water, self.samples, self.error = 0, 0, None
        self.started = time.monotonic()
        if device == "cuda":
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
        else:
            torch.mps.synchronize()
            self.sample()
            self.thread = threading.Thread(target=self.poll, name="cm3-mps-memory", daemon=True)
            self.thread.start()

    def sample(self):
        value = torch.mps.driver_allocated_memory()
        require(type(value) is int and value >= 0, "invalid MPS driver-memory sample")
        self.high_water = max(self.high_water, value)
        self.samples += 1

    def poll(self):
        try:
            while not self.stop.wait(MPS_MEMORY_POLL_SECONDS):
                self.sample()
        except Exception as exc:
            self.error = exc

    def close(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join()
            self.thread = None

    def fields(self):
        if self.device == "cuda":
            torch.cuda.synchronize()
            peak = torch.cuda.max_memory_allocated()
            require(type(peak) is int and peak > 0, "missing CUDA allocated-memory peak")
            return {"peak_memory_bytes": peak, "peak_memory_source": "torch.cuda.max_memory_allocated",
                    "peak_memory_reset": True}
        torch.mps.synchronize()
        self.close()
        if self.error is not None:
            raise ValueError("MPS memory polling failed") from self.error
        self.sample()
        return {"peak_memory_bytes": None, "peak_memory_status": "unmeasurable_mps",
                "sampled_driver_high_water_bytes": self.high_water,
                "memory_sample_interval_ms": 10, "memory_sample_count": self.samples,
                "memory_sample_source": "torch.mps.driver_allocated_memory",
                "peak_memory_source": "torch.mps.driver_allocated_memory; sampled lower bound, not allocator peak"}


def begin_fit_measurement(device, context=None):
    return FitMeasurement(device, context)


@torch.no_grad()
def unweighted_train_diagnostics(model, batches, stats, device):
    """Final model, fixed first full window/session, original masks/weights, no augmentation or RNG."""
    chosen = training.smoke_windows(batches)
    # The original loader assembles identical targets without idle weights/history dropout.
    base = train.Batches(batches.arrays, frames=batches.arm == "I", stride=training.STRIDE)
    require(base.windows == batches.windows, "diagnostic window schedule mismatch")
    batch = base.batch(chosen, generator=None)
    if batches.arm != "I":
        g = torch.zeros(len(chosen), base.window, cm3.FEATURE_DIM)
        c = torch.zeros_like(g)
        for j, wi in enumerate(chosen):
            si, start, n, _ = base.windows[wi]
            gv, cv, _ = base.arrays[si].frames(torch.arange(start, start + n))
            g[j, :n], c[j, :n] = gv, cv
        batch["global"], batch["crop"] = g, c
    batch = train.to_device(batch, device)
    was_training = model.training
    model.eval()
    try:
        terms = train.loss_terms(*train.forward(model, batch)[:2], batch, train.pos_weights(stats).to(device))
        loss = train.total_loss(terms)
        require(bool(torch.isfinite(loss)) and float(loss) >= 0, "invalid unweighted diagnostic loss")
        diagnostics = proof.normalization_diagnostics(model, batch["global"], batch["crop"], batch["prev"])
        require(all(math.isfinite(v) for value in diagnostics.values()
                    for v in (value if isinstance(value, list) else [value])), "nonfinite feature/gate diagnostics")
    finally:
        model.train(was_training)
    subset = [[base.arrays[si].session.session_id, start, n, run_start]
              for si, start, n, run_start in (base.windows[i] for i in chosen)]
    return {"unweighted_train_loss": float(loss),
        "normalized_feature_diagnostics": {k: diagnostics[k] for k in ("pre_range", "post_range")},
        "gate_diagnostics": {k: diagnostics[k] for k in
            ("gate_preactivation_range", "sigmoid_saturated_share", "tanh_saturated_share")},
        "train_diagnostic_subset": {"rule": "first complete 96-step window per train session", "windows": subset,
            "sha256": cm3.digest(subset), "dropout": False, "augmentation": False, "idle_weighting": False,
            "pos_weight_source": "original unweighted train", "loss": "original masked loss, camera multiplier 0.5"}}


def measured_fit_context(model, batches, stats, report, *, arm, device, measurement):
    diagnostics = {} if arm == "A" else unweighted_train_diagnostics(model, batches, stats, device)
    memory = measurement.fields()
    return {"wall_seconds": time.monotonic() - measurement.started, **memory,
        "measurement_scope": "per-fit verification, model construction, full fit, dev evaluation, checkpoint serialization and train diagnostics",
        "held_change_f1": report["self_fed_checks"]["held_change_f1"],
        "raw_teacher_forced": report["teacher_forced"],
        "executed_counts": {"teacher_forced": {a: {k: v[k] for k in ("true_presses", "pred_presses")}
                            for a, v in report["executed_teacher_forced"]["actions"].items()},
                            "self_fed": report["self_fed_checks"]}, **diagnostics}


def stable_fit_content(checkpoint_sha256, logs, report, context):
    result = {"checkpoint": checkpoint_sha256, "logs": {k: v for k, v in logs.items()
              if k != "launch_manifest_sha256"}, "evaluation": report}
    diagnostics = {k: context[k] for k in ("unweighted_train_loss", "normalized_feature_diagnostics",
                   "gate_diagnostics", "train_diagnostic_subset") if k in context}
    if diagnostics:
        result["diagnostics"] = diagnostics
    return result


def fit_one(receipt, inputs, freeze, backend, output):
    measurement = begin_fit_measurement(receipt["context"]["device"], receipt["context"])
    try:
        return _fit_one(receipt, inputs, freeze, backend, output, measurement)
    finally:
        measurement.close()


def _fit_one(receipt, inputs, freeze, backend, output, measurement):
    context, device = receipt["context"], receipt["context"]["device"]
    # Bind the pre-fit report/statistics/vectors to the full extraction freeze.
    require(document(freeze["inputs"]) == inputs.binding, "frozen inputs/sidecar/statistics changed")
    details = document(freeze["details"])
    require(details["backend"] == backend and details["assets"] == context["assets"]["receipt"], "changed feature backend/assets")
    mapped = {}
    require(set(freeze["features"]) == set(inputs.arrays), "incomplete feature freeze")
    for sid, ref in freeze["features"].items():
        path = pinned(ref)
        opened = features.open_features(path.parent, manifest_sha256=ref["sha256"],
            identity=inputs.identities[sid], assets=details["assets"], backend=backend)
        require(opened[2] == list(range(len(inputs.caches[sid][0]))), "partial feature freeze")
        mapped[sid] = training.FeatureArrays(inputs.arrays[sid], opened)
    bt, bd = batches(inputs, mapped), batches(inputs, mapped, dev=True)
    require(document(freeze["pairing"]) == proof.paired_receipt(bt["H"]), "paired streams changed after freeze")
    audit = training.effective_weight_audit(bt["H"], bt["H"].weights)
    require(document(freeze["audit"]) == audit, "pre-fit audit changed")
    arm, seed = receipt["arm"], receipt["seed"]
    train_raw = [inputs.arrays[s] for s in cm3.TRAIN_TABLES]
    dev_raw = [inputs.arrays[s] for s in cm3.DEV_SESSIONS]
    inputs.check()
    seconds = None
    if arm == "A":
        if device == "cuda":
            model, logs, seconds = train.fit(train.Batches(train_raw), LegacyConfig(hud=False), inputs.stats,
                seed=seed, epochs=13, device=device, dev=train.Batches(dev_raw))
            checkpoint = train.checkpoint_bytes(model, {"arm": "A", "seed": seed})
            logs = {"epochs": [{k: v for k, v in row.items() if k != "seconds"} for row in logs]}
        else:
            control = context["mps_A"][str(seed)]
            checkpoint_path = pinned(control["checkpoint"])
            model, _ = train.load_checkpoint(checkpoint_path, device=device)
            logs, checkpoint = {"historical_reread": True}, checkpoint_path.read_bytes()
        report = evaluation(model, dev_raw, inputs.stats, device)
        if device == "mps":
            expected = document(control["evaluation"])
            require(set(expected) == {"teacher_forced", "executed_teacher_forced", "self_fed", "self_fed_checks", "sanity"},
                    "complete historical MPS A metric blocks required")
            require({k: report[k] for k in expected} == expected, "historical MPS A blocks changed")
        control_checks(report, judge_module(context))
    else:
        model, logs = training.fit_registered(bt[arm], bd[arm], inputs.stats, seed=seed, device=device,
            audit=training.effective_weight_audit(bt[arm], bt[arm].weights), launch_manifest_sha256=cm3.digest(receipt))
        report = evaluation(model, bd[arm].arrays, inputs.stats, device)
        checkpoint = training.checkpoint_bytes(model, purpose="fit", meta={"arm": arm, "seed": seed})
    measured = measured_fit_context(model, bt.get(arm), inputs.stats, report, arm=arm, device=device, measurement=measurement)
    stable = stable_fit_content(hashlib.sha256(checkpoint).hexdigest(), logs, report, measured)
    result = {"checkpoint_sha256": stable["checkpoint"], "logs": logs, "evaluation": report,
              "stable_sha256": cm3.digest(stable), "seconds": seconds,
              "context": measured}
    if receipt["purpose"] == "repeat" and context.get("amendment", 2) == 2:
        original_ref = receipt["fit_predecessors"]["H0"]
        _, original = fit_result(original_ref, context, arm="H", seed=0)
        require(result["stable_sha256"] == original["stable_sha256"], "full H0 checkpoint/loss/metrics/decisions repeat differs")
        result.update(repeat_identical=True, repeats=original_ref)
    path = output / "checkpoint.pt"
    with path.open("xb") as stream:
        stream.write(checkpoint)
    result["checkpoint_file"] = reference(path)
    return result


def run(stage, receipt_path, receipt_sha256, *, arm=None, seed=None):
    """Budget supervisor owns only its child. A killed/failed stage never emits PASS."""
    started = time.monotonic()
    ref = {"path": str(logical_path(receipt_path)), "sha256": receipt_sha256}
    if stage == "fit":
        header = document(ref)
        require((arm, seed) == (header["arm"], header["seed"]), "CLI arm/seed differs from receipt")
    else:
        require(arm is None and seed is None, "arm/seed only for fit")
    receipt, _, _, _ = authenticate(stage, ref)
    output = Path(receipt["output"])
    require(not output.exists(), "immutable output already exists")
    limit = receipt["budget"]["stage_seconds"]
    require(time.monotonic() - started < limit, "INCOMPLETE: approval verification exhausted allocation")
    worker = multiprocessing.get_context("spawn").Process(target=_worker, args=(stage, ref, str(output), started))
    worker.start()
    worker.join(max(0, limit - (time.monotonic() - started)))
    if worker.is_alive():
        worker.terminate()
        worker.join()
        if output.exists():
            write_json(output / "INCOMPLETE.json", {"status": "INCOMPLETE", "reason": "stage budget exceeded", "approval": ref})
        raise ValueError("INCOMPLETE: stage budget exceeded")
    if worker.exitcode != 0 or time.monotonic() - started >= limit:
        if output.exists():
            write_json(output / "INCOMPLETE.json", {"status": "INCOMPLETE", "reason": "worker failure/time limit", "approval": ref})
        raise ValueError("INCOMPLETE: stage worker failed; artifacts retained")
    result = read_json(output / "completed.json")
    return write_json(output / "result.json", result)


def verify_matrix(receipt_path, receipt_sha256):
    """Mandatory pre-judge check; no model load, fitting or policy selection."""
    started = time.monotonic()
    ref = {"path": str(logical_path(receipt_path)), "sha256": receipt_sha256}
    receipt = document(ref)
    require(receipt["format"] == "cm3-verify-approval-v1" and receipt["approved_by"] == "herdr-lead", "verification approval")
    check_namespace(receipt, ref)
    require(Path(receipt["output"]).is_absolute() and not Path(receipt["output"]).exists(), "new absolute verification output required")
    budget = receipt["budget"]
    require(budget["approved_by"] == "herdr-lead" and 0 < budget["cap_seconds"] <= 69120
            and 0 < budget["stage_seconds"] <= budget["cap_seconds"] - budget["spent_seconds"], "verification budget exhausted")
    if "accounting" in budget:
        accounting.allocation(budget, document, required_results=receipt["outputs"])
    require(len(receipt["outputs"]) == 13, "complete 13-output matrix required")
    expected = {(a, s, "registered") for a in ("A", *cm3.ARMS) for s in range(3)} | {("H", 0, "repeat")}
    found, class_pins, elapsed_fits, elapsed_preflight = {}, None, 0., 0.
    approvals = {}
    for ref in receipt["outputs"]:
        result = document(ref)
        key = (result["arm"], result["seed"], result["purpose"])
        require(key in expected and key not in found, "duplicate/unknown matrix fit")
        approval = document(result["approval"])
        context = approval["context"]
        require(context.get("mounts") == receipt.get("mounts"), "matrix mount binding differs")
        require(result["context_sha256"] == receipt["context_sha256"], "mixed matrix context")
        fit_result(ref, context, arm=key[0], seed=key[1], purpose=key[2])
        pins = (result["hardware"], result["code_sha256"], result["software_sha256"])
        require(class_pins is None or pins == class_pins, "mixed matrix hardware/code/software")
        class_pins = pins
        found[key], approvals[key] = ref, approval
        elapsed_fits += result["elapsed_stage_seconds"]
        elapsed_preflight = max(elapsed_preflight,
            document(approval["predecessors"]["extract"])["elapsed_total_seconds"])
        require(time.monotonic() - started < budget["stage_seconds"], "INCOMPLETE: verification time allocation")
    require(set(found) == expected, "incomplete matrix")
    for key, approval in approvals.items():
        deps = approval["fit_predecessors"]
        if approval["context"]["amendment"] == 3:
            if deps:
                phase1 = check_phase1_gate(deps["phase1_gate"], approval["context"])
                expected_phase1 = {**{f"A{s}": found[("A", s, "registered")] for s in range(3)},
                                   "H0": found[("H", 0, "registered")], "H0_repeat": found[("H", 0, "repeat")]}
                require(phase1 == expected_phase1, "substituted phase 1 attempt")
            continue
        if key[0] != "A":
            controls = document(deps["A_control_gate"])["controls"]
            require(all(controls[str(s)] == found[("A", s, "registered")] for s in range(3)), "substituted control attempt")
        for name, required in (("H0", ("H", 0, "registered")), ("H0_repeat", ("H", 0, "repeat"))):
            if name in deps:
                require(deps[name] == found[required], "substituted H0/repeat attempt")
    require(budget["spent_seconds"] >= elapsed_fits + elapsed_preflight, "matrix compute missing from budget ledger")
    return write_json(receipt["output"], {"format": "cm3-matrix-verification-v1", "status": "PASS",
        "context_sha256": receipt["context_sha256"], "outputs": receipt["outputs"], "approval": reference(receipt_path),
        "hardware": class_pins[0], "code_sha256": class_pins[1], "software_sha256": class_pins[2],
        "elapsed_total_seconds": budget["spent_seconds"] + time.monotonic() - started})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=(*STAGES, "verify"))
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--receipt-sha256", required=True, help="SHA256 communicated by the lead outside the receipt")
    parser.add_argument("--arm", choices=("A", *cm3.ARMS))
    parser.add_argument("--seed", type=int, choices=(0, 1, 2))
    args = parser.parse_args()
    if args.stage == "verify":
        require(args.arm is None and args.seed is None, "verify does not take arm/seed")
        result = verify_matrix(args.receipt, args.receipt_sha256)
    else:
        result = run(args.stage, args.receipt, args.receipt_sha256, arm=args.arm, seed=args.seed)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
