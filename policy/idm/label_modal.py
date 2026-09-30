"""Label expert span clips on Modal GPUs (VUH-1353, lean mode). Run from the Mac once a video's clips are on the
input volume (policy/idm/labels.py `clips` made them; timestamps are the source's):

    modal run --detach -m policy.idm.label_modal --videos 2874840778

One container per video: it labels /clips/<video>/ with the v2-cd ensemble into rivals-idm-label-out-20260930
(/v2-cd/<span>.npz, the same files `labels.py run` writes on the PC), commits as it goes, and deletes the video's
clips from the input volume when it finishes. Native timeout; the container exits when the function returns.
Third-party frames stay on private volumes and are deleted after use.
"""
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[2]
app = modal.App("rivals-idm-label")
image = (modal.Image.debian_slim(python_version="3.12")
         .apt_install("ffmpeg")
         .pip_install("torch==2.8.0", "numpy>=2.0")
         .add_local_dir(ROOT / "policy", "/root/policy", ignore=["**/__pycache__", "**/*.pyc"])
         .add_local_dir(ROOT / "agent", "/root/agent", ignore=["**/__pycache__", "**/*.pyc"]))
v_clips = modal.Volume.from_name("rivals-idm-label-clips-20260930", create_if_missing=True)
v_out = modal.Volume.from_name("rivals-idm-label-out-20260930", create_if_missing=True)
CKPT = "/clips/ckpt/v2-c-w8-wide.pt+/clips/ckpt/v2-d-w12-wide.pt"


@app.function(image=image, gpu="L4", cpu=8, memory=32768, timeout=3 * 3600,
              volumes={"/clips": v_clips, "/out": v_out})
def label_video(video: str):
    import json
    import os
    import shutil
    import sys
    import threading
    os.environ["IDM_FFMPEG_THREADS"] = "2"
    sys.path.insert(0, "/root")
    from policy.idm import labels

    d = Path("/clips") / video
    rows = [json.loads(x) for x in (d / "spans.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    for r in rows:
        r["local_path"] = str(d / Path(r["local_path"].replace("\\", "/")).name)
    spans = Path("/tmp") / f"{video}.spans.jsonl"
    spans.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    stop = threading.Event()

    def committer():
        while not stop.wait(120):
            v_out.commit()
    threading.Thread(target=committer, daemon=True).start()
    try:
        labels.run(CKPT, str(spans), "/out", model="v2-cd", fast=True, workers=6, device="cuda")
    finally:
        stop.set()
        v_out.commit()
    done = sum((Path("/out/v2-cd") / (r["span_id"].replace(":", "_") + ".npz")).exists() for r in rows)
    shutil.rmtree(d)                                     # the clips were only needed here
    v_clips.commit()
    return {"video": video, "spans": len(rows), "labelled": done}


@app.local_entrypoint()
def main(videos: str):
    for result in label_video.map(videos.split(",")):
        print(result)
