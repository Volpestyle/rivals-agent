"""Fit IDM v2 (policy/idm/v2.py) on a Modal H100 (VUH-1353, lean mode). Run from the Mac:

    modal run --detach -m policy.idm.v2_modal --run v2-a --epochs 8

Stores: the retained full03 input volume (13 sessions) plus rivals-idm-v2-20260930-inputs (the -7/-8/-10 stores and
every session's targets, which win over the older volume's). Outputs and fit.log go to rivals-idm-v2-20260930-out
under /<run>/, committed every few minutes. Native timeout; the container stops when the fit ends.
"""
from pathlib import Path

import modal

TRAIN = ["20260923T051828-422Z-33696-1", "20260923T200129-346Z-33696-6", "20260923T205528-900Z-45572-3",
         "20260924T232304-170Z-12024-1", "20260925T021320-371Z-7804-1", "20260925T025230-605Z-7804-2",
         "20260926T045729-166Z-79780-1", "20260926T035932-508Z-63684-14", "20260925T203745-207Z-49728-2",
         "20260927T051206-888Z-150600-4", "20260927T052001-827Z-150600-5", "20260927T053118-260Z-150600-6",
         "20260927T053838-153Z-150600-7", "20260927T055006-068Z-150600-8", "20260927T060021-195Z-150600-10"]
VAL = ["20260923T171533-187Z-33696-5"]          # range dev; the -11/-12 matches are held out whole and scored later

app = modal.App("rivals-idm-v2")
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch==2.8.0", "numpy>=2.0")
         .add_local_file(Path(__file__).with_name("v2.py"), "/root/idm_v2.py"))
v_in = modal.Volume.from_name("rivals-idm-expanded-20260928-01-inputs")
v_extra = modal.Volume.from_name("rivals-idm-v2-20260930-inputs", create_if_missing=True)
v_out = modal.Volume.from_name("rivals-idm-v2-20260930-out", create_if_missing=True)


@app.function(image=image, gpu="H100", cpu=16, memory=196608, timeout=8 * 3600,
              volumes={"/inputs": v_in, "/extra": v_extra, "/out": v_out})
def fit(run: str, args: list):
    import threading
    import time

    import idm_v2
    stop = threading.Event()

    def committer():
        while not stop.wait(300):
            v_out.commit()
    threading.Thread(target=committer, daemon=True).start()
    try:
        idm_v2.main(["fit", "--inputs", "/extra", "/inputs", "--out", f"/out/{run}", "--train", *TRAIN,
                     "--val", *VAL, *args])
    finally:
        stop.set()
        v_out.commit()
    return run


@app.local_entrypoint()
def main(run: str, epochs: int = 8, batch_chunks: int = 8, lr: float = 2e-3, workers: int = 12,
         max_steps: int = 0, window: int = 8, channels: str = "48,96,128,192"):
    print(fit.remote(run, ["--epochs", str(epochs), "--batch-chunks", str(batch_chunks), "--lr", str(lr),
                           "--workers", str(workers), "--max-steps", str(max_steps), "--device", "cuda",
                           "--window", str(window), "--channels", *channels.split(",")]))
