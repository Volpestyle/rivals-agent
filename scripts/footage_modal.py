"""Private ephemeral cloud screening of public VODs; returns metadata, never frames.

Launch from the Mac with MODAL_PROFILE=rivals. Explicit source allowlist and
timeouts; no volume, secrets, game access, or persistent deployment.
"""
from pathlib import Path
import json
import modal

CODE = Path(__file__).resolve().parent.parent
image = modal.Image.debian_slim(python_version="3.11").apt_install("ffmpeg").pip_install(
    "numpy", "opencv-python-headless", "yt-dlp")
for relative in ("scripts/footage_corpus.py", "perception/hud.py", "perception/events.py",
                 "perception/scoreboard.py", "perception/replay_hud.py", "agent/state.py"):
    image = image.add_local_file(CODE / relative, "/repo/" + relative)
app = modal.App("rivals-expert-footage-20260930")


PROFILE_TIMES = {
    "2886339556": 653.133, "2883793845": 1629.25, "2882124665": 1012.346854,
    "2871149954": 19906.875, "2881098402": 1477.6875, "2879354299": 13878.8125,
    "2879380353": 3669.375, "2878467059": 5931.25,
    "2877513906": 14568.125, "2876584982": 4644.375,
    "2887537188": 5572.1875, "2878735020": 9453.75,
}


def _screen_source(sid: str, pilot_seconds: int = 0, source_profile: bool = False, profile_time: float = 0):
    import sys
    import time
    import subprocess
    import tempfile
    from collections import Counter
    import cv2
    import numpy as np
    sys.path.insert(0, "/repo")
    from scripts.footage_corpus import SEALED, verdict, spans_from_reads, jpeg_frames, portrait_crop
    if sid in SEALED or not sid.isdigit():
        raise ValueError("source refused")
    cv2.setNumThreads(1)
    started = time.monotonic()
    url = f"https://www.twitch.tv/videos/{sid}"
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        args = ["yt-dlp", "--no-progress", "--match-filter", "!is_live", "--concurrent-fragments", "8", "-f", "best",
                "--write-info-json", "--fixup", "never", "--hls-use-mpegts",
                "-o", str(base / "source.%(ext)s"), url]
        if pilot_seconds:
            args += ["--download-sections", f"*0-{pilot_seconds}"]
        download = subprocess.run(args, capture_output=True, text=True, timeout=3600)
        if download.returncode and "Initialization fragment found after media fragments" in download.stderr:
            # Twitch discontinuity/initialization changes need FFmpeg's HLS demuxer.
            args += ["--downloader", "ffmpeg", "--force-overwrites"]
            download = subprocess.run(args, capture_output=True, text=True, timeout=3600)
        if download.returncode:
            raise RuntimeError(download.stderr[-2000:])
        if not (base / "source.info.json").exists():
            raise ValueError("source skipped: live or unfinished archive")
        info = json.loads((base / "source.info.json").read_text())
        media = base / ("source." + info["ext"])
        expected = pilot_seconds or info["duration"]
        template, reference = None, None
        if source_profile:
            if (profile_time or sid in PROFILE_TIMES) and not pilot_seconds:
                reference = dict(source_id=sid, t=profile_time or PROFILE_TIMES[sid], basis="human-inspected Spider-Man frame")
                ref_media = media
                ref_time = reference["t"]
            elif info["uploader_id"] == "simii_exe":
                reference = dict(source_id="2879380353", t=3669.375, basis="human-inspected same-channel HUD, cross-video controls checked")
                # Network seeking across Twitch's fragmented HLS can stall.
                # A full temporary reference download uses the proven demux path.
                subprocess.run(["yt-dlp", "--no-progress", "-f", "best", "--fixup", "never", "--hls-use-mpegts",
                                "-o", str(base / "reference.mp4"), "https://www.twitch.tv/videos/2879380353"],
                               check=True, capture_output=True, timeout=600)
                ref_media, ref_time = base / "reference.mp4", reference["t"]
            else:
                raise ValueError("source profile requires a human-inspected positive timestamp")
            raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-threads", "1", "-ss", str(ref_time),
                                  "-i", str(ref_media), "-frames:v", "1", "-threads", "1", "-f", "image2pipe",
                                  "-c:v", "mjpeg", "pipe:1"], capture_output=True, check=True, timeout=90).stdout
            frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("reference frame unavailable")
            template = portrait_crop(frame)
        command = ["ffmpeg", "-v", "error", "-threads", "8", "-i", str(media),
                   "-t", str(expected), "-an", "-vf", "fps=2", "-threads", "2",
                   "-f", "image2pipe", "-c:v", "mjpeg", "-q:v", "3", "pipe:1"]
        reads = []
        with (base / "decode.log").open("w") as log:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=log)
            try:
                for raw in jpeg_frames(process.stdout):
                    frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                    if frame is None:
                        raise ValueError("invalid analysis frame")
                    reads.append(dict(t=len(reads) / 2, **verdict(frame, template)))
                    if len(reads) % 1000 == 0:
                        print(f"{sid}: {len(reads)/2:.0f}/{expected}s; elapsed={time.monotonic()-started:.1f}s", flush=True)
                if process.wait(timeout=30):
                    raise RuntimeError((base / "decode.log").read_text()[-2000:])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=30)
                process.stdout.close()
        if len(reads) < expected * 2 - 8:
            raise ValueError(f"incomplete decode: {len(reads)/2}s of {expected}s")
        spans = spans_from_reads(reads, max_gap=0.6, trim_s=0.5, min_s=4, bridge_unknown=2)
        for span in spans:
            span["confidence"] = "2hz_hud_candidate"
        return dict(source_id=sid, url=url, spans=spans, dense_validated=True,
                    classifier_version="native_portrait_banner_v5" if source_profile else "ability_banner_v5",
                    portrait_reference=reference,
                    reads=reads,
                    gameplay_candidate_s=sum(s["end_s"]-s["start_s"] for s in spans),
                    sample_counts=dict(Counter(r["reason"] for r in reads)),
                    sampled_until_s=reads[-1]["t"], interval=[0, expected],
                    elapsed_s=time.monotonic()-started,
                    info={k: info.get(k) for k in ("id", "uploader_id", "title", "duration", "upload_date", "width", "height", "fps", "tbr")},
                    limitation="Private cloud 2-Hz HUD screening, inward 0.5s trims. Sub-500ms exclusions may escape sampling; human spot-check required.")


@app.function(image=image, cpu=8, memory=4096,
              timeout=7200, max_containers=4, retries=0, scaledown_window=2,
              nonpreemptible=True)
def screen_source(sid: str, pilot_seconds: int = 0, source_profile: bool = False, profile_time: float = 0):
    try:
        return _screen_source(sid, pilot_seconds, source_profile, profile_time)
    except Exception as error:
        # One unavailable public source must not discard other completed results.
        return dict(source_id=sid, error=str(error), spans=[])


@app.local_entrypoint()
def main(ids: str = "2886339556", output: str = "/Users/james/dev/expert-footage-results", pilot_seconds: int = 0,
         source_profile: bool = False, profile_times: str = ""):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    source_ids = ids.split(",")
    times = json.loads(Path(profile_times).read_text()) if profile_times else {}
    for result in screen_source.map(source_ids, [pilot_seconds] * len(source_ids),
                                    [source_profile] * len(source_ids),
                                    [float(times.get(sid, 0)) for sid in source_ids], order_outputs=False):
        path = out / f"{result['source_id']}.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(result, indent=2) + "\n")
        temp.replace(path)
        if "error" in result:
            print(f"FAILED {path}: {result['error']}", flush=True)
        else:
            print(f"RESULT {path} gameplay_hours={result['gameplay_candidate_s']/3600:.3f}", flush=True)
