"""Per held target on the refind replay: the plate reading of its whole-frame box at each decision (True / False / None, or "nowhole" when
no whole-frame box overlaps it by half). uv run --group perception python docs/evidence/l3/door_plate_release.py OUT.json RUN... (docs/lanes/tracker.md)."""
import json, sys, importlib.util, collections
from pathlib import Path
sys.path.insert(0, ".")
import cv2
spec = importlib.util.spec_from_file_location("rp", "docs/evidence/l4/postfreeze30_replay.py"); rp = importlib.util.module_from_spec(spec); spec.loader.exec_module(rp)
from agent import brain
from perception import outline as O
out = {}
for run in sys.argv[2:]:
    rp.RUN = Path("data/l1/" + run)
    rows = [json.loads(l) for l in open(f"data/l1/{run}/frames.jsonl")]
    files = {r["t"]: r["file"] for r in rows if "file" in r}
    log = []
    def dec(s, m):
        i = brain.decide(s, m); tg = m.target
        acting = type(i).__name__ not in ("Search", "Idle")
        if tg is not None and acting:
            f = cv2.imread(f"data/l1/{run}/{files[s.t]}")
            whole = O.find_enemies(f, scale=2.0)
            def ov(d):
                a, b = d.bbox, tg.bbox
                w = min(a[2], b[2]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[1], b[1])
                return 0 if w <= 0 or h <= 0 else w * h / min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1]))
            best = max(whole, key=ov, default=None)
            plate = best.plate if best is not None and ov(best) >= 0.5 else "nowhole"
            log.append((s.t, tg.track, rp.label(m.target_t, tg.bbox), plate, round(tg.bbox[3] - tg.bbox[1]), [round(v) for v in tg.bbox], files[s.t]))
        return i
    rp.refind("perception/outline.py", "agent/tracker.py", dec)
    out[run] = log
json.dump(out, open(sys.argv[1], "w"))
