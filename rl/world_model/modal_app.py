"""Train the world model on one Modal GPU. Launch from the Mac, from a directory holding this repo's rl/ package:

  modal run --detach rl/world_model/modal_app.py --run probe-01 --steps 1500
  modal volume get rivals-rl-wm-20260930 probe-01 ./probe-01

Reads the frozen caches15/ and steps15/ (7 train sessions) already on the `rivals-range-bc` volume, sequentially,
once, into RAM and then GPU memory (no random Volume reads). Writes checkpoints, eval.json, the MP4 and GIF to
`rivals-rl-wm-20260930/<run>/`; a restarted container resumes from the last checkpoint.
"""
from __future__ import annotations

from pathlib import Path

import modal

_HERE = Path(__file__).resolve()
ROOT = _HERE.parents[2] if len(_HERE.parents) > 2 else _HERE.parent   # inside the container the file is /root/modal_app.py
app = modal.App("rivals-rl-wm-20260930")
image = (modal.Image.debian_slim(python_version="3.12")
         .apt_install("ffmpeg")
         .pip_install("torch==2.8.0", "numpy<3", "opencv-python-headless", "pillow")
         .add_local_dir(ROOT / "rl", "/root/rl", ignore=["**/__pycache__", "**/out"])
         .add_local_file(ROOT / "data/human/sealed-denylist.v2.json", "/root/sealed-denylist.v2.json"))
data = modal.Volume.from_name("rivals-range-bc")
out = modal.Volume.from_name("rivals-rl-wm-20260930", create_if_missing=True)


@app.function(image=image, gpu="H100", cpu=8, memory=65536, timeout=95 * 60,
              volumes={"/data": data, "/out": out})
def train(run: str, args: list[str]):
    import sys
    sys.path.insert(0, "/root")
    from rl.world_model import train as T
    T.main(["--steps-root", "/data/steps15", "--cache-root", "/data/caches15",
            "--denylist", "/root/sealed-denylist.v2.json", "--out", f"/out/{run}", *args], commit=out.commit)
    out.commit()


@app.local_entrypoint()
def main(run: str, steps: int = 1500, extra: str = ""):
    train.remote(run, ["--steps", str(steps), *extra.split()])
