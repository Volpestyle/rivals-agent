"""Fit the zoom estimator (policy/idm/fov.py) on a Modal H100 from the IDM frame stores (VUH-1353, lean mode):

    modal run --detach -m policy.idm.fov_modal --run zoom-a

Same stores and split as IDM v2 (policy/idm/v2_modal.py); held-out James matches -11/-12 are validated afterwards on
the PC from their 1080p re-encodes. Output: rivals-idm-v2-20260930-out:/<run>/zoom.pt and fit.log.
"""
from pathlib import Path

import modal

from policy.idm.v2_modal import TRAIN, VAL

app = modal.App("rivals-idm-zoom")
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch==2.8.0", "numpy>=2.0")
         .add_local_file(Path(__file__).with_name("fov.py"), "/root/idm_fov.py"))
v_in = modal.Volume.from_name("rivals-idm-expanded-20260928-01-inputs")
v_extra = modal.Volume.from_name("rivals-idm-v2-20260930-inputs")
v_out = modal.Volume.from_name("rivals-idm-v2-20260930-out")


@app.function(image=image, gpu="H100", cpu=8, memory=65536, timeout=2 * 3600,
              volumes={"/inputs": v_in, "/extra": v_extra, "/out": v_out})
def fit(run: str, args: list):
    import idm_fov
    try:
        idm_fov.main(["fit", "--inputs", "/extra", "/inputs", "--out", f"/out/{run}", "--train", *TRAIN,
                      "--val", *VAL, *args])
    finally:
        v_out.commit()
    return run


@app.local_entrypoint()
def main(run: str, steps: int = 20000):
    print(fit.remote(run, ["--steps", str(steps), "--device", "cuda"]))
