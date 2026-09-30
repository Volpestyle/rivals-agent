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
    image = image.add_local_file(CODE / relative, "/repo/" + relative)
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
    (local / "hud.u8").symlink_to(f"{cache_root}/{session}/hud.u8")
    tower = features.load_tower("/out/assets/vision.safetensors", "/out/assets/siglip2-large-config.json", "cuda")
    dest = Path("/tmp/features") / session
    meta = features.extract(f"{steps_root}/{session}.steps.jsonl", local, dest, tower,
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
        eval_sessions: list = None):
    _setup()
    import shutil
    from policy.bc2 import model, train
    root = Path("/out/features")
    local = Path("/tmp/features")
    evals = [s for s in (eval_sessions if eval_sessions is not None else VAL) if (root / s).exists()]
    for s in TRAIN + DEV + evals:
        shutil.copytree(root / s, local / s)
    run = Path("/tmp/run") / name
    config = model.Config(use_feats=use_feats, use_motion=use_motion)
    report = train.fit([local / s for s in TRAIN], [local / s for s in DEV], [local / s for s in evals], run,
                       config=config, seed=seed, epochs=epochs,
                       incumbent=train.load_incumbent("/out/assets/incumbent/epoch-26.pt",
                                                      "/out/assets/incumbent/evaluation.json"),
                       log=lambda m: print(m, flush=True))
    final = Path("/out/runs") / name
    if final.exists():
        shutil.rmtree(final)
    final.mkdir(parents=True)
    keep = {f"epoch-{report['selected_epoch']}.pt", f"epoch-{epochs}.pt", "report.json"}
    for f in run.iterdir():
        if f.name in keep:
            shutil.copy(f, final / f.name)
    out.commit()
    return {k: report[k] for k in ("selected_epoch", "history")}


@app.local_entrypoint()
def extract(sessions: str = ""):
    names = sessions.split(",") if sessions else TRAIN + DEV
    for meta in extract_session.map(names, return_exceptions=True):
        print(meta)


@app.local_entrypoint()
def sweep(prefix: str = "a", epochs: int = 12, seed: int = 0):
    arms = {"full": (True, True), "motion": (False, True), "feats": (True, False)}
    calls = {arm: fit.spawn(f"{prefix}-{arm}-s{seed}", seed, epochs, f, m) for arm, (f, m) in arms.items()}
    for arm, call in calls.items():
        print(arm, call.get())
