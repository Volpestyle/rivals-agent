"""World model v2 on one Modal H100. Launch from the Mac, from a directory holding this repo's rl/ package:

  modal run --detach rl/world_model/modal_v2.py --run v2-probe --steps 600 --minutes 40 --extra "--eval-n 32"
  modal run --detach rl/world_model/modal_v2.py --run v3-expert --steps 38000 --minutes 240       --extra "--expert-root /expert/shards"                      # v3: adds the packed expert shards

Reads the ten cohort sessions from the read-only volume rivals-explore-chunks-20260927 (another lane's: steps/ and
caches/), sequentially, once, into RAM and then GPU memory (no random Volume reads). Writes checkpoints, eval.json and
the visuals to rivals-rl-wm-20260930/<run>/; full-01's model.pt there is the comparison baseline. `--minutes` sets the
function timeout; training stops itself 20 minutes earlier to leave room for evaluation and video.
"""
from __future__ import annotations

from pathlib import Path

import modal

_HERE = Path(__file__).resolve()
ROOT = _HERE.parents[2] if len(_HERE.parents) > 2 else _HERE.parent   # inside the container the file is /root/modal_v2.py
app = modal.App("rivals-rl-wm2-20260930")
image = (modal.Image.debian_slim(python_version="3.12")
         .apt_install("ffmpeg")
         .pip_install("torch==2.8.0", "numpy<3", "opencv-python-headless", "pillow")
         .add_local_dir(ROOT / "rl", "/root/rl", ignore=["**/__pycache__", "**/out"])
         .add_local_file(ROOT / "data/human/sealed-denylist.v2.json", "/root/sealed-denylist.v2.json"))
src = modal.Volume.from_name("rivals-explore-chunks-20260927")
expert = modal.Volume.from_name("rivals-rl-wm-expert-20260930", create_if_missing=True)   # third-party: delete after
out = modal.Volume.from_name("rivals-rl-wm-20260930", create_if_missing=True)


@app.function(image=image, gpu="H100", cpu=16, memory=150000, timeout=60 * 60,
              volumes={"/src": src.read_only(), "/out": out, "/expert": expert.read_only()})
def train(run: str, args: list[str]):
    import sys
    sys.path.insert(0, "/root")
    from rl.world_model import v2
    v2.main(["--steps-root", "/src/steps", "--cache-root", "/src/caches",
             "--labels", "/root/rl/labels/range_rewards_20260930.json", "--denylist", "/root/sealed-denylist.v2.json",
             "--baseline", "/out/full-01/model.pt", "--out", f"/out/{run}", *args], commit=out.commit)
    out.commit()


@app.local_entrypoint()
def main(run: str, steps: int = 600, minutes: int = 60, extra: str = ""):
    fn = train.with_options(timeout=minutes * 60)
    fn.remote(run, ["--steps", str(steps), "--max-minutes", str(minutes - 20), *extra.split()])


@app.function(image=image, gpu="H100", cpu=12, memory=110000, timeout=60 * 60,
              volumes={"/src": src.read_only(), "/out": out})
def imagine(run: str, args: list[str]):
    """Phase C: rl.world_model.imagine_rl on world models already in the output volume."""
    import sys
    sys.path.insert(0, "/root")
    from rl.world_model import imagine_rl
    imagine_rl.main(["--steps-root", "/src/steps", "--cache-root", "/src/caches",
                     "--labels", "/root/rl/labels/range_rewards_20260930.json",
                     "--denylist", "/root/sealed-denylist.v2.json", "--out", f"/out/{run}", *args], commit=out.commit)
    out.commit()


@app.local_entrypoint()
def rl(run: str, minutes: int = 120, extra: str = ""):
    """modal run --detach rl/world_model/modal_v2.py::rl --run irl-01 --extra "--wm /out/v2-main/model.pt ..." """
    imagine.with_options(timeout=minutes * 60).remote(run, extra.split())


@app.function(image=image, gpu="H100", cpu=8, memory=32768, timeout=60 * 60,
              volumes={"/src": src.read_only(), "/out": out})
def sweep(run: str, args: list[str]):
    """rl.world_model.sampler_sweep on a trained model in the output volume."""
    import sys
    sys.path.insert(0, "/root")
    from rl.world_model import sampler_sweep
    sampler_sweep.main(["--steps-root", "/src/steps", "--cache-root", "/src/caches",
                        "--denylist", "/root/sealed-denylist.v2.json", "--out", f"/out/{run}", *args], commit=out.commit)
    out.commit()


@app.local_entrypoint()
def sampler(run: str, wm: str, minutes: int = 45):
    """modal run --detach rl/world_model/modal_v2.py::sampler --run sweep-noroll --wm /out/v2-noroll/model.pt"""
    sweep.with_options(timeout=minutes * 60).remote(run, ["--wm", wm])
