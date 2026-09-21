"""PASS 1, NEUTRAL ONLY (VUH-1314). Usage: python data\l4\turn_pass1.py <tag>
Logs a wall-clock timestamp at each step and saves timestamped 640x360 frames throughout. The only pad calls are the constructor,
reset() + update() (explicit neutral) and deletion. No stick, trigger or button value appears anywhere in this file."""
import sys, time, threading, json
from pathlib import Path
sys.path.insert(0, "scripts")
import cv2, dxcam
from record import in_range

tag = sys.argv[1]
out = Path("data/l4/turn") / tag
out.mkdir(parents=True, exist_ok=True)
cam = dxcam.create(output_color="BGR")
T0 = time.perf_counter()
WALL0 = time.time()
log = []
stop = threading.Event()
latest = {}

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
        if n % 4 == 0:                      # the game runs ~240 fps: keep about every fourth delivered frame
            cv2.imwrite(str(out / f"{int(t * 1000):06d}.jpg"), cv2.resize(f, (640, 360), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 85])
        n += 1

th = threading.Thread(target=frames, daemon=True); th.start()
time.sleep(0.5)
f = latest.get("f")
ok = f is not None and bool(in_range(cv2.resize(f, (1280, 720), interpolation=cv2.INTER_AREA)))
mark(f"range HUD on a fresh frame: {ok}")
if not ok:
    stop.set(); th.join(1); (out / "steps.json").write_text(json.dumps(log, indent=1)); sys.exit("not in the range: nothing created, nothing sent")

mark("waiting 3 s, no pad"); time.sleep(3.0)
import vgamepad as vg
mark("VX360Gamepad() called")
pad = vg.VX360Gamepad()
mark("VX360Gamepad() returned (its constructor sends one default report); nothing for 3 s"); time.sleep(3.0)
pad.reset(); pad.update()
mark("explicit neutral 1 sent (reset + update); 3 s"); time.sleep(3.0)
pad.reset(); pad.update()
mark("explicit neutral 2 sent (reset + update); 3 s"); time.sleep(3.0)
mark("deleting the pad (disconnect)")
del pad
mark("pad deleted; 3 s"); time.sleep(3.0)
mark("end")
stop.set(); th.join(1)
(out / "steps.json").write_text(json.dumps(log, indent=1))
