"""The 126 rises of the 2026-09-23 take whose web recipient body is established, under any player-zone rule (VUH-1355).

  uv run --offline --no-project --with opencv-python-headless --with numpy \
      python docs/evidence/player-zone-20260923/rises.py decode <old-code> <new-code> <work-dir>
  uv run ... rises.py score <old-code> <new-code> <work-dir> [recipients.json]

<old-code> is `git archive 0f71336 perception agent policy scripts` (the packet's pinned bytes, checked here); <new-code>
is the same with this change's perception/outline.py.

decode: for every rise n, the five causal ticks n-4..n (tick k is the frame at PTS 100k+21 ms, as measure_grid.py defines
it) and one impact frame (the latest time in the producer's note within 1.5 s after the anchor, else tick n+2) are
decoded from the original with CPU ffmpeg at below-normal priority. Per tick and view (aim crop with origin/frame as
agent.loop passes it, and the whole frame) the new finder is run twice with its merge step recorded: guard off
(PLAYER_ZONE_MIN_H 0) gives every accepted component in find_green's own order; everything guarded (zone = whole frame)
gives the components the health-strip evidence keeps. A zone rule only chooses among these, so any rule's output is
rebuilt exactly from them (score checks that). Writes marks.jsonl and anchor/impact thumbnails.

score: rebuilds the finder's output for each rule, checks the HEAD rule against the packet's grid cache (the pinned
finder's recorded boxes) at every tick, replays the selector as replay_windows.py does (fresh Tracker/Memory over
n-4..n, aim first, whole frame only when the aim crop is empty, grid HUD reading; tracer tags are left unread because
brain.gate never reads them), and with recipients.json (per rise, the component ids on the recipient body, from
inspecting the tiles) says per rule whether a component on the recipient survives at the anchor.
"""
import ctypes
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import textwrap
from dataclasses import asdict, replace
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
PACKET = ROOT / "data/human/skill-event-candidates/051828-request-timing-v2"
VIDEO = "C:/Users/volpe/Videos/2026-09-23 00-18-28.mkv"
W, H = 2560, 1440
AIM = (800, 240, 1760, 1200)
S = W / 1280.0
PINS = {
    "perception/hud.py": "aa2dc58575e9f9c405ad3e430d9ed0d046f0f9b2f3fcba3884e7fb204e3c1969",
    "perception/outline.py": "1589f8dcc892cb545b1a63442d6092167a47da2e0fce4379f25d732f70e631de",
    "agent/loop.py": "be16e045d9ef06a8a1fbb38ca7beb979a8927a9bdd6be0540592721ec08417da",
    "agent/brain.py": "0deaafb77cae4fa4a15fc8c8abe6d49c09821de7a1ab5810b096788117b30c00",
    "agent/tracker.py": "0f181117f434a8a0168f1222f5a183f9e9061367838354a6bd5be4e0e540d093",
    "agent/state.py": "83983c59f0ea39772686b9ce8e002aab86d312c5e75937bc2b9e6a21eddb8f5a",
}
# Rules scored: ("image", zone) is the pre-change rule (zone in the passed image's own fractions); ("frame", zone) tests
# the mark's centre in whole-frame fractions for both views.
RULES = {
    "HEAD": ("image", (0.28, 0.33, 0.64, 1.00)),
    "this change (.27,.39,.47,.90)": ("frame", (0.27, 0.39, 0.47, 0.90)),
    "first approval (.18,.39,.47,.90)": ("frame", (0.18, 0.39, 0.47, 0.90)),
    "(.27,.39,.50,.90)": ("frame", (0.27, 0.39, 0.50, 0.90)),
    "(.27,.39,.55,.90)": ("frame", (0.27, 0.39, 0.55, 0.90)),
    "no guard": ("frame", (2.0, 2.0, 2.0, 2.0)),
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def established(notes):
    """build.py's selector_stats rule: the recipient is a body unless the note says none / not_seen / not established."""
    def body(x):
        r = x["recipient"]
        return not (r.startswith("none") or r == "not_seen" or "not established" in r)
    return {int(k): x for k, x in notes["requests"].items() if body(x)}


def impact_pts(n, note):
    """PTS (ms) of the frame at the latest time the note gives within 1.5 s after the anchor, else tick n+2."""
    times = [float(t) for t in re.findall(r"(?<![\d.])(\d{1,3}\.\d{2,3})(?![\d.])", note.get("why") or "")]
    later = [t for t in times if n / 10 <= t <= n / 10 + 1.5]
    t = max(later) if later else (n + 2) / 10
    return round(round(t * 120) * 1000 / 120) + 21, t


def decode(pts_list, sink):
    """Decode exactly these PTS (ms) frames, one ffmpeg per cluster, and call sink(pts, bgr) for each."""
    pts_list = sorted(set(pts_list))
    clusters, cur = [], [pts_list[0]]
    for p in pts_list[1:]:
        if p - cur[-1] <= 3000 and len(cur) < 24:        # 24 raw frames is ~265 MB of pipe output
            cur.append(p)
        else:
            clusters.append(cur)
            cur = [p]
    clusters.append(cur)
    for c in clusters:
        ss = max(0.0, (c[0] - 21) / 1000 - 2.2)          # lands on the keyframe before (every 2.08 s); frames are identified by PTS
        sel = "+".join(f"eq(pts\\,{p})" for p in c)
        cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "info", "-copyts", "-threads", "2", "-ss", f"{ss:.3f}",
               "-t", f"{(c[-1] - 21) / 1000 - ss + 0.2:.3f}", "-i", VIDEO, "-an", "-sn", "-dn", "-filter_threads", "1",
               "-vf", f"select='{sel}',showinfo", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
        proc = subprocess.run(cmd, capture_output=True, creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
        got = [int(m) for m in re.findall(r"showinfo.*?\bpts:\s*(\d+)", proc.stderr.decode("utf-8", "replace"))]
        size = W * H * 3
        assert proc.returncode == 0 and got == c and len(proc.stdout) == size * len(c), (c, got, proc.returncode)
        for i, p in enumerate(c):
            sink(p, np.frombuffer(proc.stdout[i * size:(i + 1) * size], np.uint8).reshape(H, W, 3))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def setup(old_code, new_code):
    old_code, new_code = Path(old_code), Path(new_code)
    assert {p: sha(old_code / p) for p in PINS} == PINS
    assert all(sha(new_code / p) == h for p, h in PINS.items() if p != "perception/outline.py")
    assert sha(new_code / "perception/outline.py") == sha(ROOT / "perception/outline.py"), "new snapshot is not this change"
    sys.path.insert(0, str(old_code))
    notes = json.loads((PACKET / "visual-inspection-notes.json").read_text())
    rises = established(notes)
    assert len(rises) == 126, len(rises)
    grid = {}
    for line in (PACKET / "grid-cache.jsonl").read_text().splitlines():
        r = json.loads(line)
        grid[r["k"]] = r
    return load("outline_new", new_code / "perception/outline.py"), rises, grid


def components(o, img, origin, frame):
    """(accepted components in find_green's order, those the strip evidence keeps), both before merging."""
    real, seen = o._merge, []
    saved = o.PLAYER_ZONE, o.PLAYER_ZONE_MIN_H

    def record(marks, gap):
        seen.append(list(marks))
        return real(marks, gap)
    o._merge = record
    try:
        o.PLAYER_ZONE_MIN_H = 0
        o.find_green(img, S, o.GREEN, origin, frame)
        o.PLAYER_ZONE, o.PLAYER_ZONE_MIN_H = (-1.0, -1.0, 2.0, 2.0), 1e9
        o.find_green(img, S, o.GREEN, origin, frame)
    finally:
        o._merge = real
        o.PLAYER_ZONE, o.PLAYER_ZONE_MIN_H = saved
    return [list(m) for m in seen[0]], [list(m) for m in seen[1]]


def cmd_decode(old_code, new_code, work):
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    cv2.setNumThreads(1)
    new_o, rises, grid = setup(old_code, new_code)
    work = Path(work)
    (work / "thumbs").mkdir(parents=True, exist_ok=True)
    need, impacts = {}, {}
    for n, note in rises.items():
        for k in range(n - 4, n + 1):
            need[100 * k + 21] = k
        impacts[n] = impact_pts(n, note)
    keep = {100 * n + 21 for n in rises} | {p for p, _ in impacts.values()}
    out = open(work / "marks.jsonl", "w")

    def sink(p, f):
        if p in need:
            x0, y0, x1, y1 = AIM
            a_all, a_sup = components(new_o, f[y0:y1, x0:x1], (x0, y0), (W, H))
            w_all, w_sup = components(new_o, f, (0, 0), None)
            x0, y0 = AIM[:2]                            # and what the shipped finder itself returns, as agent.loop calls it
            direct_aim = [box(replace(d, bbox=(d.bbox[0] + x0, d.bbox[1] + y0, d.bbox[2] + x0, d.bbox[3] + y0)))
                          for d in new_o.find_enemies(f[AIM[1]:AIM[3], AIM[0]:AIM[2]], S, new_o.GREEN, (x0, y0), (W, H))]
            direct_wide = [box(d) for d in new_o.find_enemies(f, S)]
            out.write(json.dumps(dict(k=need[p], aim=a_all, aim_supported=a_sup, wide=w_all, wide_supported=w_sup,
                                      direct_aim=direct_aim, direct_wide=direct_wide)) + "\n")
        if p in keep:
            cv2.imwrite(str(work / "thumbs" / f"{p}.jpg"), cv2.resize(f, (1280, 720), interpolation=cv2.INTER_AREA),
                        [cv2.IMWRITE_JPEG_QUALITY, 90])

    decode(list(need) + list(keep), sink)
    out.close()
    (work / "impacts.json").write_text(json.dumps({n: v for n, v in impacts.items()}))


def rebuild(o, marks, supported, rule, origin, size):
    """find_green's output under `rule`, from its accepted components: a small mark centred in the zone is dropped unless
    the strip evidence keeps it; then find_green's own merge and order."""
    kind, (zx1, zy1, zx2, zy2) = rule
    sup = {tuple(m) for m in supported}
    iw, ih = size
    keep = []
    for m in marks:
        x, y, w, h, _ = m
        if kind == "image":
            cx, cy = (x + w / 2) / iw, (y + h / 2) / ih
        else:
            cx, cy = (origin[0] + x + w / 2) / W, (origin[1] + y + h / 2) / H
        guarded = zx1 <= cx <= zx2 and zy1 <= cy <= zy2 and h < o.PLAYER_ZONE_MIN_H * S
        if not guarded or tuple(m) in sup:
            keep.append(tuple(m))
    return sorted(o._merge(keep, o.GREEN_MERGE_GAP * S), key=lambda b: -b[2] * b[3])


def enemies(o, green, size):
    """find_enemies on a precomputed find_green output (it reads the image only for its shape)."""
    real = o.find_green
    o.find_green = lambda *a, **k: green
    try:
        return o.find_enemies(np.zeros((size[1], size[0], 3), np.uint8), S)
    finally:
        o.find_green = real


def box(d):
    return {**asdict(d), "bbox": list(d.bbox)}


def cmd_score(old_code, new_code, work, recipients_path=None):
    new_o, rises, grid = setup(old_code, new_code)
    from agent import brain
    from agent.loop import aim_window
    from agent.state import Ability, Detection, State
    from agent.tracker import Tracker
    work = Path(work)
    ticks = {}
    for line in (work / "marks.jsonl").read_text().splitlines():
        r = json.loads(line)
        ticks[r["k"]] = r

    def views(k, rule):
        t = ticks[k]
        x0, y0 = AIM[:2]
        aim = [replace(d, bbox=(d.bbox[0] + x0, d.bbox[1] + y0, d.bbox[2] + x0, d.bbox[3] + y0))
               for d in enemies(new_o, rebuild(new_o, t["aim"], t["aim_supported"], rule, (x0, y0), (960, 960)), (960, 960))]
        wide = enemies(new_o, rebuild(new_o, t["wide"], t["wide_supported"], rule, (0, 0), (W, H)), (W, H))
        return [box(d) for d in aim], [box(d) for d in wide]

    # exactness: the HEAD rule rebuilt from the new finder's components must equal the pinned finder's recorded boxes, and
    # this change's rule must equal what the shipped finder returned on the same frame
    shipped = next(n for n in RULES if n.startswith("this change"))
    assert RULES[shipped] == ("frame", new_o.PLAYER_ZONE), "RULES does not name the shipped zone"
    for k in ticks:
        a, w = views(k, RULES["HEAD"])
        assert a == grid[k]["aim"] and w == grid[k]["wide"], f"tick {k}: rebuilt HEAD rule != grid cache"
        a, w = views(k, RULES[shipped])
        assert a == ticks[k]["direct_aim"] and w == ticks[k]["direct_wide"], f"tick {k}: rebuilt change != shipped finder"

    def det(d):
        return Detection(**{**d, "bbox": tuple(d["bbox"]), "tagged": None})

    def replay(n, rule):
        tracker, memory = Tracker(), brain.Memory()
        for k in range(n - 4, n + 1):
            g, t = grid[k], grid[k]["composition_t"]
            aim_raw, wide_raw = views(k, rule)
            aim = tracker.update([det(d) for d in aim_raw], t, (W, H), clip=aim_window((W, H)))
            dets = aim or tracker.update([det(d) for d in wide_raw], t, (W, H))
            h = dict(g["hud"])
            h["abilities"] = {a: Ability(**v) for a, v in h.get("abilities", {}).items()}
            early, target = brain.gate(State(t=t, frame=(W, H), detections=dets, coasting=tuple(tracker.coasting), **h), memory)
        return dict(target=box(target)["bbox"] if target else None, aim=aim_raw, wide=wide_raw)

    inspected = {}
    for line in (PACKET / "inspected-windows.jsonl").read_text().splitlines():
        r = json.loads(line)
        inspected[r["n"]] = r["history"][-1]["target"]
    recipients = json.loads(Path(recipients_path).read_text()) if recipients_path else {}
    rows = []
    for n in sorted(rises):
        res = {name: replay(n, rule) for name, rule in RULES.items()}
        assert res["HEAD"]["target"] == ((inspected.get(n) or {}).get("bbox")), f"n{n}: HEAD replay != packet window"
        t = ticks[n]
        row = dict(n=n, recipient=rises[n]["recipient"], selector_before=rises[n]["selector"],
                   target={name: r["target"] for name, r in res.items()})
        rec = recipients.get(str(n))
        if rec:
            row["recipient_components"] = rec
            row["recipient_found"] = {}
            for name, rule in RULES.items():
                found = []
                for view, origin, size in (("aim", AIM[:2], (960, 960)), ("wide", (0, 0), (W, H))):
                    ids = rec.get(view, [])
                    found.append(any(_survives(new_o, t[view][i], t[view + "_supported"], rule, origin, size) for i in ids))
                row["recipient_found"][name] = dict(aim=found[0], wide=found[1])
            row["target_on_recipient"] = {name: _on(new_o, res[name]["target"], t, rec, RULES[name]) for name in RULES}
        rows.append(row)
    with open(work / "scored.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(len(rows), "rises scored; on", len(ticks), "ticks HEAD rebuilt = grid cache and the change rebuilt = shipped finder;",
          "HEAD replays = packet windows")


def _survives(o, m, supported, rule, origin, size):
    kind, (zx1, zy1, zx2, zy2) = rule
    x, y, w, h, _ = m
    if kind == "image":
        cx, cy = (x + w / 2) / size[0], (y + h / 2) / size[1]
    else:
        cx, cy = (origin[0] + x + w / 2) / W, (origin[1] + y + h / 2) / H
    guarded = zx1 <= cx <= zx2 and zy1 <= cy <= zy2 and h < o.PLAYER_ZONE_MIN_H * S
    return not guarded or tuple(m) in {tuple(s) for s in supported}


def _on(o, target, t, rec, rule):
    """Is the selected target built from the recipient? Each rebuilt merged mark keeps its member components
    (_merge_groups); the target is the detection made from one merged mark (its outline box, or the body projected under
    a bar), so it is on the recipient when that mark has a recipient member. None when there is no target; a target that
    matches no anchor detection (a tracker-coasted box) falls back to containing a recipient component's centre."""
    if target is None:
        return None
    for view, origin, size in (("aim", AIM[:2], (960, 960)), ("wide", (0, 0), (W, H))):
        ids = set(rec.get(view, []))
        marks = t[view]
        kept = [tuple(m) for m in marks if _survives(o, m, t[view + "_supported"], rule, origin, size)]
        groups = o._merge_groups(kept, o.GREEN_MERGE_GAP * S)
        for merged, members in groups:
            for d in enemies(o, [merged], size):
                box = [d.bbox[0] + origin[0], d.bbox[1] + origin[1], d.bbox[2] + origin[0], d.bbox[3] + origin[1]]
                if all(abs(a - b) < 0.6 for a, b in zip(box, target)):
                    return any(list(m) in [marks[i] for i in ids] for m in members)
    x1, y1, x2, y2 = target
    for view, (ox, oy) in (("aim", AIM[:2]), ("wide", (0, 0))):
        for i in rec.get(view, []):
            x, y, w, h, _ = t[view][i]
            if x1 <= ox + x + w / 2 <= x2 and y1 <= oy + y + h / 2 <= y2:
                return True
    return False


def tiles(work):
    """Inspection sheets, four rises each: the anchor (aim-crop components numbered a0, a1 ... in the crop's order, green;
    whole-frame components whose centre is outside the crop w0 ..., magenta; the crop outlined cyan) beside the impact
    frame, with the producer's note."""
    work = Path(work)
    notes = established(json.loads((PACKET / "visual-inspection-notes.json").read_text()))
    ticks = {json.loads(l)["k"]: json.loads(l) for l in (work / "marks.jsonl").read_text().splitlines()}
    impacts = {int(k): v for k, v in json.loads((work / "impacts.json").read_text()).items()}
    (work / "sheets").mkdir(exist_ok=True)
    X0, Y0, X1, Y1 = 160, 40, 1120, 680                   # the panel, in the 1280x720 thumbnail
    panels = []
    for n in sorted(notes):
        note = notes[n]
        a = cv2.imread(str(work / "thumbs" / f"{100 * n + 21}.jpg"))
        b = cv2.imread(str(work / "thumbs" / f"{impacts[n][0]}.jpg"))
        cv2.rectangle(a, (400, 120), (880, 600), (255, 255, 0), 1)
        t = ticks[n]
        for view, (ox, oy), col in (("wide", (0, 0), (255, 0, 255)), ("aim", AIM[:2], (0, 255, 0))):
            for i, (x, y, w, h, _) in enumerate(t[view]):
                cx, cy = ox + x + w / 2, oy + y + h / 2
                if view == "wide" and AIM[0] <= cx <= AIM[2] and AIM[1] <= cy <= AIM[3]:
                    continue
                p1, p2 = (int((ox + x) / 2), int((oy + y) / 2)), (int((ox + x + w) / 2), int((oy + y + h) / 2))
                cv2.rectangle(a, p1, p2, col, 1)
                lab, org = f"{view[0]}{i}", (p1[0], max(12, p1[1] - 3))
                cv2.putText(a, lab, org, cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4)
                cv2.putText(a, lab, org, cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 1)
        left = cv2.resize(a[Y0:Y1, X0:X1], (840, 560), interpolation=cv2.INTER_AREA)
        right = cv2.resize(b[Y0:Y1, X0:X1], (360, 240), interpolation=cv2.INTER_AREA)
        col = np.zeros((560, 360, 3), np.uint8)
        col[:240] = right
        lines = [f"n{n}  {note['selector']}", f"impact {impacts[n][1]:.2f}s"] + textwrap.wrap(f"R: {note['recipient']}", 34)             + textwrap.wrap(f"why: {note.get('why')}", 34)
        for i, s in enumerate(lines[:13]):
            cv2.putText(col, s, (6, 262 + 23 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        panel = np.hstack([left, col])
        cv2.rectangle(panel, (0, 0), (panel.shape[1] - 1, panel.shape[0] - 1), (90, 90, 90), 2)
        panels.append(panel)
    while len(panels) % 4:
        panels.append(np.zeros_like(panels[0]))
    for k in range(0, len(panels), 4):
        sheet = np.vstack([np.hstack(panels[k:k + 2]), np.hstack(panels[k + 2:k + 4])])
        cv2.imwrite(str(work / "sheets" / f"rises-{k // 4:02d}.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:]
    {"decode": cmd_decode, "score": cmd_score, "tiles": tiles}[cmd](*rest)
