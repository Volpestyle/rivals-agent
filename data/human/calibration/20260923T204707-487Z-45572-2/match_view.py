import json, sys
import numpy as np, cv2
frames = np.load(sys.argv[1]); meta = json.load(open(sys.argv[1] + ".json"))
ref_i = int(sys.argv[2]); lo, hi = int(sys.argv[3]), int(sys.argv[4])
def band(f):
    g = f[20:170].astype(np.float32).copy()
    g[:55, :240] = 0.0          # the static top-left practice-range overlay
    return g
ref = band(frames[ref_i])
win = cv2.createHanningWindow(ref.shape[::-1], cv2.CV_32F)
res = []
for i in range(lo, hi):
    g = band(frames[i])
    diff = float(np.abs(g - ref).mean())
    (sx, sy), resp = cv2.phaseCorrelate(ref.copy(), g.copy(), win)
    res.append(dict(i=i, t=meta[i]["t"], dcx=meta[i]["cum"][0] - meta[ref_i]["cum"][0],
                    dcy=meta[i]["cum"][1] - meta[ref_i]["cum"][1], sx=sx, sy=sy, resp=resp, diff=diff))
json.dump(res, open(sys.argv[1] + f".match{ref_i}.json", "w"))
for r in res[::int(sys.argv[5])]:
    print("i=%(i)d t=%(t).3f dcx=%(dcx)d dcy=%(dcy)d shift=(%(sx).2f,%(sy).2f) resp=%(resp).3f diff=%(diff).2f" % r)
