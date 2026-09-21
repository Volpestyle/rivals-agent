"""PASS 2 (VUH-1314). Usage: python data\l4\turn_pass2.py <tag>
This file holds NO pad code. It saves timestamped frames and launches the existing scripts/pad.py, unmodified, with the loop's throwaway
move (left stick forward 0.3 s, then back 0.3 s). pad.py opens ITS OWN pad: VX360Gamepad(), 2.0 s, the tokens, 0.5 s, neutral, exit."""
import sys, time, threading, json, subprocess
from pathlib import Path
sys.path.insert(0, "scripts")
import cv2, dxcam
from record import in_range

tag = sys.argv[1]
out = Path("data/l4/turn") / tag
out.mkdir(parents=True, exist_ok=True)
cam = dxcam.create(output_color="BGR")
T0 = time.perf_counter(); WALL0 = time.time()
log = []; stop = threading.Event(); latest = {}

def mark(step):
    t = time.perf_counter() - T0
    log.append({"t": round(t, 3), "wall": time.strftime("%H:%M:%S", time.localtime(WALL0 + t)) + f"{(WALL0 + t) % 1:.3f}"[1:], "step": step})
    print(f"{t:7.3f} {log[-1]['wall']} {step}", flush=True)

def frames():
    n = 0
    while not stop.is_set():
        f = cam.grab()
        if f is None:
            time.sleep(0.002); continue
        t = time.perf_counter() - T0
        latest["f"] = f
        if n % 4 == 0:
            cv2.imwrite(str(out / f"{int(t * 1000):06d}.jpg"), cv2.resize(f, (640, 360), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 85])
        n += 1

th = threading.Thread(target=frames, daemon=True); th.start()
time.sleep(0.5)
f = latest.get("f")
ok = f is not None and bool(in_range(cv2.resize(f, (1280, 720), interpolation=cv2.INTER_AREA)))
mark(f"range HUD on a fresh frame: {ok}")
if not ok:
    stop.set(); th.join(1); (out / "steps.json").write_text(json.dumps(log, indent=1)); sys.exit("not in the range: pad.py not started")
mark("waiting 3 s, no pad"); time.sleep(3.0)
f = latest.get("f")
if not in_range(cv2.resize(f, (1280, 720), interpolation=cv2.INTER_AREA)):
    sys.exit("range HUD gone: pad.py not started")
mark("starting scripts/pad.py \"ls:0,1,0.3 ls:0,-1,0.3\" (it opens its own pad, waits 2.0 s, then the two tokens)")
p = subprocess.run([sys.executable, "scripts/pad.py", "ls:0,1,0.3 ls:0,-1,0.3"], capture_output=True, text=True)
mark(f"pad.py exited {p.returncode} (its pad is gone): {(p.stdout + p.stderr).strip()[:200]}")
time.sleep(3.0)
mark("end")
stop.set(); th.join(1)
(out / "steps.json").write_text(json.dumps(log, indent=1))
