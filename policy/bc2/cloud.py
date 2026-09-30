"""Modal runs for policy.bc2. Launch from the Mac: MODAL_PROFILE=rivals modal run -m policy.bc2.cloud::<entry>.

Inputs are read-only from the existing volume rivals-explore-chunks-20260927 (steps/ and caches/ of the ten cohort
sessions). Outputs and the NitroGen vision assets live in rivals-policy-bc2-20260930:
  /assets/{vision.safetensors, siglip2-large-config.json, incumbent/{epoch-26.pt, evaluation.json}}
  /features/<session>/   (policy.bc2.features)      /runs/<name>/   (policy.bc2.train)
Every function has a native timeout; apps are ephemeral (modal run) and stop when the entry point returns.
"""
from pathlib import Path

import modal

CODE = Path(__file__).resolve().parents[2]
TRAIN = ["20260923T051828-422Z-33696-1", "20260923T200129-346Z-33696-6", "20260924T232304-170Z-12024-1",
         "20260925T021320-371Z-7804-1", "20260925T025230-605Z-7804-2", "20260925T203745-207Z-49728-2",
         "20260926T035932-508Z-63684-14", "20260926T045729-166Z-79780-1"]
DEV = ["20260923T171533-187Z-33696-5", "20260923T205528-900Z-45572-3"]     # the frozen dev pair, for selection
VAL = ["20260925T212646-322Z-49728-6"]                                     # registry val split, never selected on

image = (modal.Image.debian_slim(python_version="3.11")
         .pip_install("torch==2.8.0", "numpy", "transformers==4.57.1", "safetensors")
         .add_local_dir(CODE / "policy", "/repo/policy", ignore=["**/__pycache__", "idm/**"])
         .add_local_dir(CODE / "agent", "/repo/agent", ignore=["**/__pycache__"]))
for relative in ("data/human/sealed-denylist.v2.json", "data/human/patch-equivalence.json"):
    for root in ("/repo/", "/root/"):     # modal run -m executes the package from /root
        image = image.add_local_file(CODE / relative, root + relative)
src = modal.Volume.from_name("rivals-explore-chunks-20260927")
out = modal.Volume.from_name("rivals-policy-bc2-20260930", create_if_missing=True)
app = modal.App("rivals-policy-bc2-20260930")


def _setup():
    import os
    import sys
    sys.path.insert(0, "/repo")
    os.chdir("/repo")


@app.function(image=image, gpu="L40S", cpu=8, memory=32768, timeout=3 * 3600, retries=0,
              volumes={"/src": src.read_only(), "/out": out})
def extract_session(session: str, cache_root: str = "/src/caches", steps_root: str = "/src/steps"):
    _setup()
    import shutil
    from policy.bc2 import features
    local = Path("/tmp/cache") / session
    shutil.copytree(f"{cache_root}/{session}", local, ignore=shutil.ignore_patterns("hud.u8"))
    import json
    frames = json.loads((local / "cache.json").read_text())["frames"]
    with (local / "hud.u8").open("wb") as f:          # unused by bc2; sparse, sized for open_cache's check
        f.truncate(frames * 80 * 200 * 3)
    tower = features.load_tower("/out/assets/vision.safetensors", "/out/assets/siglip2-large-config.json", "cuda")
    dest = Path("/tmp/features") / session
    meta = features.extract(f"{steps_root}/{session}.jsonl", local, dest, tower,
                            log=lambda m: print(m, flush=True))
    final = Path("/out/features") / session
    if final.exists():
        shutil.rmtree(final)
    shutil.copytree(dest, final)
    out.commit()
    return meta


@app.function(image=image, gpu="H100", cpu=8, memory=98304, timeout=4 * 3600, retries=0,
              volumes={"/out": out})
def fit(name: str, seed: int = 0, epochs: int = 12, use_feats: bool = True, use_motion: bool = True,
        eval_sessions: list = None, batch_size: int = 32, lr: float = 3e-4, wd: float = .05,
        feat_dropout: float = .3, hidden: int = 512, use_green: bool = False, use_dt: bool = False,
        chunk: int = 0, onset_weight: float = 1., chunk_weight: float = .5, expert: bool = False,
        expert_epochs: int = None, expert_share: float = None, hires: bool = False, layers: int = 1,
        expert_actions: bool = True, expert_sessions: list = None, expert_label_source: str = None,
        expert_targets: str = None):
    """expert_targets: a volume directory of target-only overlays (<shard>/{targets.npz, meta.json}, from
    expert.relabel) that replace each staged expert shard's targets; the original features are unchanged."""
    _setup()
    import shutil
    from policy.bc2 import model, train
    root = Path("/out/features")
    local = Path("/tmp/features")
    # Modal can reuse a warm container for the next fit call: start from empty scratch every time.
    shutil.rmtree(local, ignore_errors=True)
    shutil.rmtree(Path("/tmp/run"), ignore_errors=True)
    evals = [s for s in (eval_sessions if eval_sessions is not None else VAL) if (root / s).exists()]
    for s in TRAIN + DEV + evals:
        shutil.copytree(root / s, local / s)
    experts = []
    if expert_sessions is not None and not expert:
        raise ValueError("expert_sessions requires expert=True")
    if expert:
        from policy.bc2.cohort import expert_dirs
        base_source = None if expert_targets else expert_label_source
        for d in expert_dirs("/out/expert-features", expert_sessions, base_source):
            shutil.copytree(d, local / d.name)
            experts.append(local / d.name)
        if expert_targets:
            import json
            sources = set()
            for d in experts:
                src = Path(expert_targets) / d.name
                if not (src / "targets.npz").is_file() or not (src / "meta.json").is_file():
                    raise ValueError(f"no target overlay for {d.name} in {expert_targets}")
                meta = json.loads((src / "meta.json").read_text())
                if meta["session"] != d.name:
                    raise ValueError(f"overlay session mismatch: {d.name}")
                sources.add(meta.get("relabel", {}).get("calibration", {}).get("source"))
                shutil.copy(src / "targets.npz", d / "targets.npz")
                shutil.copy(src / "meta.json", d / "meta.json")
            if None in sources or len(sources) != 1 or (expert_label_source and sources != {expert_label_source}):
                raise ValueError(f"overlay label sources {sources} differ from {expert_label_source}")
    run = Path("/tmp/run") / name
    config = model.Config(use_feats=use_feats, use_motion=use_motion, feat_dropout=feat_dropout, hidden=hidden,
                          use_green=use_green, use_dt=use_dt, chunk=chunk, hires=hires, layers=layers)
    report = train.fit([local / s for s in TRAIN], [local / s for s in DEV], [local / s for s in evals], run,
                       config=config, seed=seed, epochs=epochs, batch_size=batch_size, lr=lr, wd=wd,
                       onset_weight=onset_weight, chunk_weight=chunk_weight, expert_dirs=experts,
                       expert_epochs=expert_epochs, expert_share=expert_share, expert_actions=expert_actions,
                       incumbent=train.load_incumbent("/out/assets/incumbent/epoch-26.pt",
                                                      "/out/assets/incumbent/evaluation.json"),
                       log=lambda m: print(m, flush=True))
    final = Path("/out/runs") / name
    if final.exists():
        shutil.rmtree(final)
    shutil.copytree(run, final)
    out.commit()
    return {"name": name, "selected_epoch": report["selected_epoch"]}


@app.function(image=image, cpu=8, memory=16384, timeout=3600, retries=0,
              volumes={"/src": src.read_only(), "/out": out})
def green_session(session: str):
    _setup()
    import torch
    from policy.bc2 import features
    torch.set_num_threads(8)
    cache_root = "/out/val/caches" if session in VAL else "/src/caches"
    n = features.add_green(f"{cache_root}/{session}", f"/out/features/{session}")
    out.commit()
    return session, n


@app.function(image=image, cpu=8, memory=16384, timeout=3600, retries=0,
              volumes={"/src": src.read_only(), "/out": out})
def gray_session(session: str):
    _setup()
    import torch
    from policy.bc2 import features
    torch.set_num_threads(8)
    cache_root = "/out/val/caches" if session in VAL else "/src/caches"
    n = features.add_gray_full(f"{cache_root}/{session}", f"/out/features/{session}")
    out.commit()
    return session, n


@app.local_entrypoint()
def grayhi(sessions: str = ""):
    names = sessions.split(",") if sessions else TRAIN + DEV + VAL
    for result in gray_session.map(names, return_exceptions=True):
        print(result, flush=True)


@app.local_entrypoint()
def green(sessions: str = ""):
    names = sessions.split(",") if sessions else TRAIN + DEV + VAL
    for result in green_session.map(names, return_exceptions=True):
        print(result, flush=True)


@app.local_entrypoint()
def extract(sessions: str = "", val: bool = False):
    if val:
        print(extract_session.remote(VAL[0], cache_root="/out/val/caches", steps_root="/out/val/steps"))
        return
    names = sessions.split(",") if sessions else TRAIN + DEV
    for meta in extract_session.map(names, return_exceptions=True):
        print(meta)


@app.local_entrypoint()
def sweep(prefix: str = "a", epochs: int = 12, seed: int = 0):
    arms = {"full": (True, True), "motion": (False, True), "feats": (True, False)}
    calls = {arm: fit.spawn(f"{prefix}-{arm}-s{seed}", seed, epochs, f, m) for arm, (f, m) in arms.items()}
    for arm, call in calls.items():
        print(arm, call.get())


def _status(name, **fields):
    """Job-board status (docs/compute.md) from the launching host; never fails the run."""
    try:
        from scripts.job_status import write
        write("policy-modal-" + name, **fields)
    except Exception as exc:
        print(f"status write failed for {name}: {exc}", flush=True)


@app.local_entrypoint()
def grid(spec: str, log: str = ""):
    """spec: JSON list of fit kwargs, each with a unique "name". log: this launcher's log path (board evidence)."""
    import json
    specs = json.loads(spec)
    calls = [fit.spawn(**kw) for kw in specs]
    for kw in specs:
        _status(kw["name"], owner="policy (VUH-1346)", stage="running", host="modal",
                evidence=log or "modal volume rivals-policy-bc2-20260930:/runs/" + kw["name"],
                progress="training on a Modal H100; report at /runs/" + kw["name"] + "/report.json")
    for kw, call in zip(specs, calls):
        try:
            result = call.get()
            print(result, flush=True)
            _status(kw["name"], stage="done", progress=f"selected epoch {result.get('selected_epoch')}")
        except Exception as exc:          # one failed run must not stop the others
            print({"name": kw["name"], "failed": str(exc)[:500]}, flush=True)
            _status(kw["name"], stage="failed", progress=str(exc)[:200])
