"""Pin the live tree's deployed bytes and runtime identity for galacta-pilot-20260923; issues no live authority.

    uv run --offline --no-project --python 3.11 python -B freeze_deployed.py [--live DIR] [--out DIR]

Refuses (raises, writes nothing further) unless:
- the live tree is clean and at the shared checkout's `main`, a descendant of the predeclared commit;
- nothing under agent/, perception/, policy/ or scripts/ changed since the cohort's identity commit;
- every pinned live file equals its git blob up to CRLF;
- perception (hud+outline+loop) and selector (brain+tracker), hashed as CRLF git blobs, equal the cohort's SourceIdentity;
- the controller's calibration defaults and gates equal the reviewed calibration manifest's.
Every output is opened with mode 'x': a second freeze into the same directory refuses.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LIVE = Path("C:/Users/volpe/repos/rivals-agent-live")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):  # policy.range_policy.digest, without importing policy from either tree
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def refuse(why):
    raise SystemExit(f"REFUSED: {why}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--live", type=Path, default=LIVE)
    ap.add_argument("--out", type=Path, default=HERE)
    a = ap.parse_args(argv)
    cand = json.loads((HERE / "candidate.json").read_text(encoding="utf-8"))
    live, out = a.live.resolve(), a.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    if git(live, "status", "--porcelain").strip():
        refuse(f"{live} has uncommitted changes")
    head = git(live, "rev-parse", "HEAD").decode().strip()
    main_ref = git(ROOT, "rev-parse", "main").decode().strip()
    if head != main_ref:
        refuse(f"live HEAD {head} is not main {main_ref}: fast-forward the live tree first (README step 1)")
    if subprocess.run(["git", "-C", str(live), "merge-base", "--is-ancestor", cand["predeclared_commit"], head]).returncode:
        refuse(f"{head} does not descend from the predeclared {cand['predeclared_commit']}")
    changed = git(live, "diff", "--name-only", cand["identity_commit"], head, "--", *cand["runtime_paths"]).decode().split()
    if changed:
        refuse(f"runtime paths changed since the identity commit {cand['identity_commit']}: {changed}")

    def pin(path):
        raw = (live / path).read_bytes()
        blob = git(live, "show", f"{head}:{path}").replace(b"\r\n", b"\n")
        lf = raw.replace(b"\r\n", b"\n")
        if lf != blob:
            refuse(f"{path}: live bytes differ from {head} beyond line endings")
        return {"sha256": sha(raw), "LF_normalized_sha256": sha(lf), "CRLF_blob_sha256": sha(lf.replace(b"\n", b"\r\n")),
                "live_line_endings": "CRLF" if b"\r\n" in raw else "LF"}

    ident = cand["identity_files"]
    identity = {kind: digest({p: pin(p)["CRLF_blob_sha256"] for p in ident[kind]}) for kind in ("perception", "selector")}
    want = {"perception": cand["source_identity"]["perception_sha256"], "selector": cand["source_identity"]["selector_sha256"]}
    if identity != want:
        refuse(f"runtime identity {identity} differs from the cohort's {want}")

    # Calibration: the reviewed defaults/gates, read from the live controller (import only; no device, capture or input).
    sys.path.insert(0, str(live))
    import agent.controller as controller
    if Path(controller.__file__).resolve().parent.parent != live:
        refuse(f"imported {controller.__file__}, not the live tree")
    base_cal = json.loads((ROOT / cand["baseline_manifests"]["calibration"]).read_text(encoding="utf-8"))
    cal = asdict(controller.Cal())
    now_cal = {k: json.loads(json.dumps(cal[k])) for k in base_cal["Cal_defaults"]}
    now_gates = {k: json.loads(json.dumps(getattr(controller, k))) for k in base_cal["gates"]}
    if now_cal != base_cal["Cal_defaults"] or now_gates != base_cal["gates"]:
        refuse(f"calibration changed: {now_cal} {now_gates}")
    if b"self.next_shot_t = t + 0.34" not in (live / "agent/controller.py").read_bytes():
        refuse("minimum_repeat_spacing_s 0.34 not found in the live controller")

    frozen = datetime.now(timezone.utc).isoformat()
    results = {}

    def write(name, data):
        with (out / name).open("x", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        results[name] = sha((out / name).read_bytes())
        return results[name]

    for kind in ("controller", "perception"):
        path = ROOT / cand["baseline_manifests"][kind]
        data = json.loads(path.read_text(encoding="utf-8"))
        # The diagnostic's own run scope (one 10 s Luna run) and its selector hash are history here, not this pilot's.
        stale = ("D_comparisons", "scope", "planned_mode", "run_limit_s", "run_count", "target_scope",
                 "selector_sha256", "selector_manifest_sha256")
        data["historical_from_baseline_manifest"] = {k: data.pop(k) for k in stale if k in data}
        data.update(status="deployed_bytes_equal_main_git_blobs_up_to_CRLF", checkout=str(live), git_commit=head,
                    frozen_utc=frozen, baseline_manifest={"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes())},
                    files={p: pin(p) for p in data["files"]},
                    planned_mode=("galacta-pilot-20260923: range-skill (checkpoint 698d8831, confidence 0.7, no scripted attack "
                                  "fallback) and scripted agent.brain.decide, both --collect-episode --stop-on-feed; live warmup "
                                  "off; the 180 s keepalive cannot fire in 20 s; end scoreboard on"),
                    run_limit_s=20, startup_limit_s=14, combined_authorization_s=34,
                    budget_limit="proof authorization under existing freshness/watchdog limits; not hard process/physical timing",
                    run_count="one per scheduled allocation, 20 allocations, no replacement", scoreboard=True,
                    target_scope="designated right Galacta by the courtyard stair railing; near and mid; generic continuous selector")
        if kind == "perception":
            data["selector_sha256"] = identity["selector"]
            data["identity"] = {"perception_sha256": identity["perception"], "selector_sha256": identity["selector"],
                                "form": ident["byte_form"], "equals_source_identity": True}
        write(f"{kind}-deployed.json", data)
    write("calibration-current.json", {
        "status": "reviewed_default_calibration_unchanged_since_D_not_a_fresh_measurement",
        "baseline_manifest": {"path": cand["baseline_manifests"]["calibration"],
                              "sha256": sha((ROOT / cand["baseline_manifests"]["calibration"]).read_bytes())},
        "controller_file": pin("agent/controller.py"), "git_commit": head,
        "Cal_defaults": now_cal, "gates": now_gates, "minimum_repeat_spacing_s": base_cal["minimum_repeat_spacing_s"],
        "D_evidence": base_cal["D_evidence"], "D_result": base_cal["D_result"],
        "limits": base_cal["limits"] + " The controller file changed after D (0f71336 body witness); these values did not."})
    write("deployment-check.json", {"commit": head, "main": main_ref, "predeclared_commit": cand["predeclared_commit"],
                                    "identity_commit": cand["identity_commit"], "runtime_paths_unchanged": True,
                                    "identity": identity, "manifest_sha256": dict(results), "frozen_utc": frozen,
                                    "live_authority": False, "remaining": "effective setup, saved settings, binding"})
    print(json.dumps({"commit": head, "identity": identity, "written": results}))


if __name__ == "__main__":
    main()
