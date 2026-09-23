"""Build tests/fixtures/placement/frames.json from held frames (operator tool, run on the PC; not a test).

Inputs: the pilot-2 frames and first-pilot scouts named below, plus `labelled.json` (argv[1]): the mined candidate
pairs, labelled by eye from contact sheets (see docs/lanes/placement.md section 5). Runs the loop's own readers on each
image and records its size, range proof, finder boxes, SHA-256 and the operator label. No video decode.
"""
import hashlib, json, sys
from pathlib import Path
import cv2
R = Path(r"C:\Users\volpe\repos\rivals-agent"); sys.path.insert(0, str(R))
from agent.loop import default_perception
from agent.placement import classify
p = default_perception()
P2 = {  # pilot 2 frames the design names, operator labels from the inspected frames
 "p0923-scene-01.png": ("PAIR", "James's park, ~15 m on the lane"),
 "p0923-scene-03.png": ("LOST", "on the lane at the 25 m marks, but the finder boxed only the right bot on this frame"),
 "p0923-e2-pos2-a.jpg": ("PAIR", "lane, 25 m end"), "p0923-e2-pos2-b.jpg": ("PAIR", "lane, ~15 m"),
 "p0923-e2-pos3-a.jpg": ("PAIR", "lane, mid"), "galacta-0923-ready-e2.png": ("PAIR", "slot 3 readiness, mid"),
 "p0923-e2-cd-d.jpg": ("PAIR", "lane, mid, after the cooldown check"), "p0923-pos-01-a.jpg": ("PAIR", "slot 1 approach"),
 "p0923-pos-02-a.jpg": ("NEAR_ONE", "slot 1 approach, point blank"), "p0923-cdcheck-d.jpg": ("NEAR_ONE", "slot 1 readiness, near"),
 "p0923-pre04-look.png": ("NEAR_ONE", "after slot 3's KO, point blank, respawned bot"),
 "p0923-ka-131606-a.jpg": ("NEAR_ONE", "beside the bot on the lane, side view"),
 "p0923-restart-look.png": ("LOST", "the nook under the terrace, bots only as through-wall icons"),
 "p0923-pl-up-a.jpg": ("LOST", "under the terrace wall"), "p0923-pl-stair3-c.jpg": ("LOST", "lower plaza"),
 "p0923-pos04-a.jpg": ("LOST", "below the lane's side after the back-walk: one bot seen from below"),
 "p0923-e2-pos1-a.jpg": ("LOST", "the other (moving-bot) lane"), "p0923-nav-19-p5.jpg": ("LOST", "plaza, no bots"),
}
SCOUTS = sorted(R.glob("data/benchmarks/galacta-setup-20260922*/*.png"))
mined = json.load(open(sys.argv[1]))   # tests/fixtures/placement/labelled.json
items = [(Path(r"C:\desk\out") / k, v[0], v[1], "pilot2") for k, v in P2.items()]
SL = {"galacta-setup-20260922/mid.png": ("LOST", "on the lane, mid; the left bot hidden behind Spider-Man, one box"),
      "galacta-setup-20260922/near-02.png": ("PAIR", "lane, near: left bot cut by the frame edge"),
      "galacta-setup-20260922/near-03.png": ("NEAR_ONE", "lane, near; slot-1 scout of the first pilot"),
      "galacta-setup-20260922/near-candidate.png": ("PAIR", "lane, near-mid"),
      "galacta-setup-20260922-entry2/mid-ready.png": ("PAIR", "lane, mid"),
      "galacta-setup-20260922-entry2/mid.png": ("LOST", "on the lane, mid, both bots visible but the finder returned no box"),
      "galacta-setup-20260922-entry3/slot04-mid.png": ("PAIR", "lane, mid; slot-4 scout of the first pilot")}
items += [(s, *SL["/".join(s.parts[-2:])], "pilot1-scout") for s in SCOUTS]
items += [(Path(m["path"]), "PAIR" if m["label"] == "pos" else "NOT_PAIR", m["why"], "mined") for m in mined]
out, seen = [], set()
for path, label, note, src in items:
    if label not in ("PAIR", "NOT_PAIR", "LOST", "NEAR_ONE"):
        raise SystemExit(f"unlabelled frame {path}: every row needs an operator label")
    raw = path.read_bytes(); sha = hashlib.sha256(raw).hexdigest()
    if sha in seen: continue
    seen.add(sha)
    f = cv2.imread(str(path)); size = [f.shape[1], f.shape[0]]
    ir = bool(p.in_range(f)); boxes = [[round(v, 1) for v in d.bbox] for d in p.wide(f)]
    rel = str(path.relative_to(R)).replace("\\", "/") if str(path).startswith(str(R)) else str(path).replace("\\", "/")
    got = classify(tuple(size), boxes, ir).kind
    out.append({"path": rel, "sha256": sha, "size": size, "in_range": ir, "boxes": boxes, "label": label,
                "label_source": "operator, from the inspected frame", "note": note, "set": src, "classified": got})
fx = R / "tests/fixtures/placement"; fx.mkdir(parents=True, exist_ok=True)
for o in out:
    ok = o["classified"] == o["label"] or (o["label"] == "NOT_PAIR" and o["classified"] != "PAIR")
    if not ok: print("DISAGREE", o["path"][-60:], o["label"], o["classified"], o["note"])
json.dump([{k: v for k, v in o.items() if k != "classified"} for o in out], open(fx / "frames.json", "w", newline="\n"), indent=1)
print(len(out), "frames;", sum(o["set"] == "mined" for o in out), "mined;", {s: sum(o["set"] == s for o in out) for s in ("pilot2", "pilot1-scout")})
for o in out:
    if o["set"] == "pilot1-scout": print("scout", o["path"], o["classified"], o["boxes"])
