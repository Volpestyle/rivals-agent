"""Summaries and inspection sheets from measure_hero.py's output (VUH-1355 step 1).

  uv run --offline --no-project --with opencv-python-headless --with numpy \
      python docs/evidence/player-zone-20260923/summarize.py <measure-out-dir> <evidence-dir>

Writes footprint.json (percentiles, occupancy regions, mark counts) and the JPEG sheets into <evidence-dir>.
Sheets are aids for inspection; the native frames are the evidence.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from perception import outline as O  # noqa: E402

W, H = 2560, 1440
CROP = (800, 240, 1760, 1200)
HERO_BOX_CTRL = (0.27, 0.45, 0.47, 1.00)        # agent/controller.py HERO_BOX, for comparison only
RECS = ("take-keyframes", "take-anchors", "galacta-pilot", "plaza30", "tagrun0")
# The near-hero census marks judged NOT enemy by inspection of the native frame (every other mark in it is an enemy
# outline arc, limb, name text or health bar; see README).
JUNK = {("tagrun0", "000422", 0.4299): "effect strokes drawn round his head",     # (recording, frame, box top y)
        ("plaza30", "000184", 0.7007): "lime spawn-door glass seen between his hand and hip"}


def junk_of(r):
    return next((what for (rec, fid, y1), what in JUNK.items()
                 if r["rec"] == rec and r["id"] == fid and abs(r["box"][1] - y1) < 0.002), None)


def to_crop(box):
    """Frame fractions -> aim-crop fractions (may fall outside 0-1)."""
    x1, y1, x2, y2 = box
    cw = CROP[2] - CROP[0]
    return [round((x1 * W - CROP[0]) / cw, 4), round((y1 * H - CROP[1]) / cw, 4),
            round((x2 * W - CROP[0]) / cw, 4), round((y2 * H - CROP[1]) / cw, 4)]


def zone_in_frame(view):
    """The current PLAYER_ZONE (image fractions) expressed in frame fractions for a view."""
    zx1, zy1, zx2, zy2 = O.PLAYER_ZONE
    if view == "wide":
        return (zx1, zy1, zx2, zy2)
    cw = CROP[2] - CROP[0]
    return ((CROP[0] + zx1 * cw) / W, (CROP[1] + zy1 * cw) / H, (CROP[0] + zx2 * cw) / W, (CROP[1] + zy2 * cw) / H)


def pct(vals, qs=(5, 25, 50, 75, 95)):
    return {f"p{q}": round(float(np.percentile(vals, q)), 4) for q in qs} if len(vals) else None


def box_stats(boxes):
    b = np.array(boxes)
    cols = {"x1": b[:, 0], "y1": b[:, 1], "x2": b[:, 2], "y2": b[:, 3], "cx": (b[:, 0] + b[:, 2]) / 2,
            "cy": (b[:, 1] + b[:, 3]) / 2, "w": b[:, 2] - b[:, 0], "h": b[:, 3] - b[:, 1]}
    return {k: pct(v) for k, v in cols.items()}


def region(heat, thr):
    ys, xs = np.nonzero(heat >= thr)
    if not len(xs):
        return None
    hh, hw = heat.shape
    return [round(xs.min() / hw, 4), round(ys.min() / hh, 4), round((xs.max() + 1) / hw, 4), round((ys.max() + 1) / hh, 4)]


def bodies(rows):
    """Group one frame/view's guard-off marks the way find_green merges them; a group whose every member the current
    guard drops is a body the finder loses outright (a dropped arc of a body that still has a kept member is not)."""
    marks = [(round(r["box"][0] * W), round(r["box"][1] * H), round((r["box"][2] - r["box"][0]) * W),
              round((r["box"][3] - r["box"][1]) * H), i) for i, r in enumerate(rows)]
    out = []
    for merged, members in O._merge_groups(marks, O.GREEN_MERGE_GAP * 2.0):
        rs = [rows[m[4]] for m in members]
        out.append({"lost": all(r["dropped_now"] for r in rs), "some_dropped": any(r["dropped_now"] for r in rs),
                    "h_native": merged[3], "flat": merged[2] / max(merged[3], 1) >= O.FLAT_ASPECT,
                    "center_in_hero_box": any(r.get("center_in_hero_box") for r in rs), "members": [m[4] for m in members]})
    return out


def mark_counts(rows):
    c = Counter()
    frames = defaultdict(list)
    for r in rows:
        frames[(r["rec"], r["id"])].append(r)
    for rs in frames.values():
        bs = bodies(rs)
        c["bodies"] += len(bs)
        c["bodies_lost"] += sum(b["lost"] for b in bs)
        c["bodies_lost_not_flat"] += sum(b["lost"] and not b["flat"] for b in bs)
        c["bodies_partly_dropped"] += sum(b["some_dropped"] and not b["lost"] for b in bs)
        c["frames_with_a_body_lost"] += any(b["lost"] for b in bs)
        c["frames_emptied"] += bool(bs) and all(b["lost"] for b in bs)
    for r in rows:
        c["marks"] += 1
        c["zone_now"] += r["zone_now"]
        c["zone_now_small"] += r["zone_now"] and r["small"]
        c["dropped_now"] += r["dropped_now"]
        if "center_in_hero_box" in r:
            c["hero_known"] += 1
            c["center_in_hero_box"] += r["center_in_hero_box"]
            c["center_in_hero_box_small"] += r["center_in_hero_box"] and r["small"]
            c["half_on_silhouette"] += r["on_silhouette"] >= 0.5
            c["dropped_now_center_in_hero_box"] += r["dropped_now"] and r["center_in_hero_box"]
            c["dropped_now_outside_hero_box"] += r["dropped_now"] and not r["center_in_hero_box"]
        else:
            c["dropped_now_hero_unknown"] += r["dropped_now"]
    return dict(c)


def tile(img, box, marks, hero, label, size=(480, 270), zone=None):
    """A downscaled frame with the hero box (yellow), the view's current zone (magenta) and marks (red = dropped)."""
    v = img.copy()
    if zone:
        cv2.rectangle(v, (int(zone[0] * W), int(zone[1] * H)), (int(zone[2] * W), int(zone[3] * H)), (255, 0, 255), 3)
    cv2.rectangle(v, (CROP[0], CROP[1]), (CROP[2], CROP[3]), (255, 255, 0), 2)
    if hero:
        cv2.rectangle(v, (int(hero[0] * W), int(hero[1] * H)), (int(hero[2] * W), int(hero[3] * H)), (0, 255, 255), 5)
    for m in marks:
        b = m["box"]
        cv2.rectangle(v, (int(b[0] * W), int(b[1] * H)), (int(b[2] * W), int(b[3] * H)),
                      (0, 0, 255) if m["dropped_now"] else (0, 255, 0), 5)
    v = cv2.resize(v, size, interpolation=cv2.INTER_AREA)
    cv2.putText(v, label, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3)
    cv2.putText(v, label, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
    return v


def grid(tiles, cols):
    if not tiles:
        return None
    th, tw = tiles[0].shape[:2]
    while len(tiles) % cols:
        tiles.append(np.zeros((th, tw, 3), np.uint8))
    return np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])


def crop_tile(img, m, hero, label, side=300):
    """A native crop round one mark: mark box (red dropped / green kept), hero box yellow. `side` px output."""
    b = m["box"]
    cx, cy = (b[0] + b[2]) / 2 * W, (b[1] + b[3]) / 2 * H
    half = max(160, 1.6 * max((b[2] - b[0]) * W, (b[3] - b[1]) * H))
    x1, y1 = int(max(0, cx - half)), int(max(0, cy - half))
    x2, y2 = int(min(W, cx + half)), int(min(H, cy + half))
    v = img[y1:y2, x1:x2].copy()
    if hero:
        cv2.rectangle(v, (int(hero[0] * W) - x1, int(hero[1] * H) - y1), (int(hero[2] * W) - x1, int(hero[3] * H) - y1),
                      (0, 255, 255), 2)
    cv2.rectangle(v, (int(b[0] * W) - x1, int(b[1] * H) - y1), (int(b[2] * W) - x1, int(b[3] * H) - y1),
                  (0, 0, 255) if m["dropped_now"] else (0, 255, 0), 2)
    s = side / max(v.shape[:2])
    v = cv2.resize(v, (max(1, int(v.shape[1] * s)), max(1, int(v.shape[0] * s))), interpolation=cv2.INTER_AREA)
    pad = np.zeros((side, side, 3), np.uint8)
    pad[:v.shape[0], :v.shape[1]] = v
    cv2.putText(pad, label, (3, side - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 3)
    cv2.putText(pad, label, (3, side - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)
    return pad


def main(measure_dir, evidence_dir):
    md, ed = Path(measure_dir), Path(evidence_dir)
    ed.mkdir(parents=True, exist_ok=True)
    frames = [json.loads(line) for line in open(md / "frames.jsonl")]
    rows = [json.loads(line) for line in open(md / "marks.jsonl")]
    by_frame = defaultdict(list)
    for r in rows:
        by_frame[(r["rec"], r["id"])].append(r)

    summary = {"frames": {}, "hero_box": {}, "hero_box_crop": {}, "occupancy": {}, "marks": {}}
    heats = {}
    for rec in RECS:
        fr = [f for f in frames if f["rec"] == rec and "error" not in f]
        found = [f for f in fr if f["found"]]
        summary["frames"][rec] = {"frames": len(fr), "hero_found": len(found), "reaches_hud_band": sum(f["hud"] for f in found),
                                  "errors": sum(1 for f in frames if f["rec"] == rec and "error" in f)}
        if found:
            summary["hero_box"][rec] = box_stats([f["box"] for f in found])
            summary["hero_box_crop"][rec] = box_stats([to_crop(f["box"]) for f in found])
        p = md / f"heat-{rec}.npy"
        if p.exists():
            heats[rec] = np.load(p)
            summary["occupancy"][rec] = {f">={t}": region(heats[rec], t) for t in (0.05, 0.25, 0.5)}
        for view in ("wide", "aim"):
            summary["marks"][f"{rec}/{view}"] = mark_counts([r for r in rows if r["rec"] == rec and r["view"] == view])
    all_found = [f for f in frames if f.get("found")]
    summary["hero_box"]["all"] = box_stats([f["box"] for f in all_found])
    summary["hero_box_crop"]["all"] = box_stats([to_crop(f["box"]) for f in all_found])
    eq = sum(heats[r] for r in heats) / len(heats)          # each recording weighted equally
    np.save(md / "heat-equal.npy", eq)
    summary["occupancy"]["equal_weight"] = {f">={t}": region(eq, t) for t in (0.05, 0.25, 0.5)}
    summary["occupancy"]["equal_weight_crop"] = {k: to_crop(v) if v else None for k, v in summary["occupancy"]["equal_weight"].items()}
    for view in ("wide", "aim"):
        summary["marks"][f"all/{view}"] = mark_counts([r for r in rows if r["view"] == view])
    summary["zones_in_frame_fractions"] = {"PLAYER_ZONE on the wide frame": zone_in_frame("wide"),
                                           "PLAYER_ZONE on the aim crop": [round(v, 4) for v in zone_in_frame("aim")],
                                           "controller HERO_BOX": HERO_BOX_CTRL, "aim crop": [CROP[0] / W, CROP[1] / H, CROP[2] / W, CROP[3] / H]}

    # occupancy map, equal weight, with the current zones drawn in frame terms
    hm = cv2.resize((np.clip(eq, 0, 1) * 255).astype(np.uint8), (1280, 720), interpolation=cv2.INTER_NEAREST)
    vis = cv2.applyColorMap(hm, cv2.COLORMAP_INFERNO)
    for box, col, name in [(zone_in_frame("wide"), (255, 0, 255), "PLAYER_ZONE, wide"),
                           (zone_in_frame("aim"), (0, 0, 255), "PLAYER_ZONE, on aim crop"),
                           ([CROP[0] / W, CROP[1] / H, CROP[2] / W, CROP[3] / H], (255, 255, 0), "aim crop"),
                           (HERO_BOX_CTRL, (0, 255, 0), "controller HERO_BOX")]:
        cv2.rectangle(vis, (int(box[0] * 1280), int(box[1] * 720)), (int(box[2] * 1280) - 1, int(box[3] * 720) - 1), col, 2)
        cv2.putText(vis, name, (int(box[0] * 1280) + 4, int(box[1] * 720) + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
    for t in (0.05, 0.25, 0.5):
        cnts, _ = cv2.findContours((cv2.resize(eq, (1280, 720)) >= t).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(vis, cnts, -1, (255, 255, 255), 1)
    cv2.drawMarker(vis, (640, 360), (255, 255, 255), cv2.MARKER_CROSS, 20, 1)
    cv2.imwrite(str(ed / "occupancy.png"), vis)

    # segmentation check sheets: 30 evenly spaced frames per recording, plus every frame where no hero was found
    for rec in RECS:
        fr = [f for f in frames if f["rec"] == rec and "error" not in f]
        pick = [fr[i] for i in np.linspace(0, len(fr) - 1, min(30, len(fr))).astype(int)]
        tiles = [tile(cv2.imread(f["path"]), None, [], f.get("box"), f"{rec} {f['id']}" + ("" if f["found"] else " NO HERO"))
                 for f in pick]
        cv2.imwrite(str(ed / f"seg-{rec}.jpg"), grid(tiles, 5), [cv2.IMWRITE_JPEG_QUALITY, 80])
    missing = [f for f in frames if "error" not in f and not f["found"]]
    if missing:
        tiles = [tile(cv2.imread(f["path"]), None, [], None, f"{f['rec']} {f['id']} NO HERO") for f in missing[:60]]
        cv2.imwrite(str(ed / "seg-no-hero.jpg"), grid(tiles, 5), [cv2.IMWRITE_JPEG_QUALITY, 80])

    # how the current zones sit on the measured hero: share of his occupancy mass inside each, and share of each zone
    # where he is drawn in under 5% of frames; how often his box holds the crosshair
    big = cv2.resize(eq, (1280, 720), interpolation=cv2.INTER_NEAREST)
    zstats = {}
    for name, box in [("PLAYER_ZONE, wide", zone_in_frame("wide")), ("PLAYER_ZONE, on aim crop", zone_in_frame("aim")),
                      ("controller HERO_BOX", HERO_BOX_CTRL)]:
        x1, y1, x2, y2 = int(box[0] * 1280), int(box[1] * 720), int(box[2] * 1280), int(box[3] * 720)
        part = big[y1:y2, x1:x2]
        zstats[name] = {"hero_mass_inside": round(float(part.sum() / big.sum()), 3),
                        "zone_share_hero_under_5pct": round(float((part < 0.05).mean()), 3)}
    zstats["frames_hero_box_holds_crosshair"] = f"{sum(f['box'][0] <= 0.5 <= f['box'][2] and f['box'][1] <= 0.5 <= f['box'][3] for f in all_found)}/{len(all_found)}"
    summary["zones_vs_hero"] = zstats
    (ed / "footprint.json").write_text(json.dumps(summary, indent=1))

    # every mark the current guard drops, per view, as a native crop (full pages to <measure-out-dir>, they are many)
    fmap = {(f["rec"], f["id"]): f for f in frames}
    for view in ("wide", "aim"):
        dropped = [r for r in rows if r["view"] == view and r["dropped_now"]]
        tiles, index = [], []
        for i, r in enumerate(dropped):
            f = fmap[(r["rec"], r["id"])]
            where = "hero" if r.get("center_in_hero_box") else ("out" if "center_in_hero_box" in r else "?")
            tiles.append(crop_tile(cv2.imread(f["path"]), r, f.get("box"), f"{i} {r['rec'][:6]} {r['id'][-6:]} h{r['h_native']} {where}"))
            index.append({"i": i, **r})
        for k in range(0, len(tiles), 48):
            g = grid(tiles[k:k + 48], 8)
            if g is not None:
                cv2.imwrite(str(md / f"dropped-{view}-{k // 48:02d}.jpg"), g, [cv2.IMWRITE_JPEG_QUALITY, 82])
        (md / f"dropped-{view}.json").write_text(json.dumps(index, indent=0))
        # a seeded random sample, up to 16 per recording, is what the evidence folder keeps and what was classified
        rng = np.random.default_rng(20260923)
        pick = []
        for rec in RECS:
            idx = [i for i, r in enumerate(dropped) if r["rec"] == rec]
            pick += sorted(rng.choice(idx, size=min(16, len(idx)), replace=False).tolist()) if idx else []
        (ed / f"sample-dropped-{view}.json").write_text(json.dumps([index[i] for i in pick], indent=0))
        cv2.imwrite(str(ed / f"sample-dropped-{view}.jpg"), grid([tiles[i] for i in pick], 8), [cv2.IMWRITE_JPEG_QUALITY, 82])

    # census: every small mark (h < 120 native) whose centre is within 15% of the hero's height of his box, outside the
    # galacta-pilot near pose (one static scene whose bot stands against him; 50+ of its crops were inspected separately),
    # deduplicated across views. Pages go to <measure-out-dir>; each was inspected by eye. JUNK lists the non-enemy ones.
    near, seen = [], set()
    for r in rows:
        f = fmap[(r["rec"], r["id"])]
        if r["rec"] == "galacta-pilot" or not r["small"] or not f.get("found"):
            continue
        hx1, hy1, hx2, hy2 = f["box"]
        m = 0.15 * (hy2 - hy1)
        cx, cy = (r["box"][0] + r["box"][2]) / 2, (r["box"][1] + r["box"][3]) / 2
        key = (r["rec"], r["id"], tuple(round(v, 2) for v in r["box"]))
        if hx1 - m <= cx <= hx2 + m and hy1 - m <= cy <= hy2 + m and key not in seen:
            seen.add(key)
            near.append(r)
    tiles = [crop_tile(cv2.imread(fmap[(r["rec"], r["id"])]["path"]), r, fmap[(r["rec"], r["id"])]["box"],
                       f"{i} {r['view'][0]} {r['rec'][:6]} {r['id'][-6:]} h{r['h_native']}", side=240) for i, r in enumerate(near)]
    for k in range(0, len(tiles), 60):
        cv2.imwrite(str(md / f"near-{k // 60}.jpg"), grid(tiles[k:k + 60], 10), [cv2.IMWRITE_JPEG_QUALITY, 80])
    junk = [r for r in near if junk_of(r)]
    summary["near_hero_census"] = {"marks": len(near), "by_recording": dict(Counter(r["rec"] for r in near)),
                                   "not_enemy": [{**{k: r[k] for k in ("rec", "id", "view", "box", "h_native")},
                                                  "what": junk_of(r)} for r in junk]}
    jt = []
    for r in junk:
        img = cv2.imread(fmap[(r["rec"], r["id"])]["path"])
        b = r["box"]
        x1, y1, x2, y2 = int(b[0] * W), int(b[1] * H), int(b[2] * W), int(b[3] * H)
        X1, Y1 = max(0, x1 - 300), max(0, y1 - 250)
        c = img[Y1:y2 + 350, X1:x2 + 300].copy()
        cv2.rectangle(c, (x1 - X1, y1 - Y1), (x2 - X1, y2 - Y1), (0, 0, 255), 2)
        c = cv2.resize(c, (480, int(480 * c.shape[0] / c.shape[1])), interpolation=cv2.INTER_AREA)
        pad = np.zeros((480, 480, 3), np.uint8)
        pad[:min(480, c.shape[0])] = c[:480]
        cv2.putText(pad, f"{r['rec']} {r['id']} h{r['h_native']}: {junk_of(r)[:40]}", (4, 472),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1)
        jt.append(pad)
    if jt:
        cv2.imwrite(str(ed / "not-enemy.jpg"), np.hstack(jt), [cv2.IMWRITE_JPEG_QUALITY, 88])

    # candidate frame-terms zones, scored on the same marks: small (h < 120 native) with centre inside. An upper bound on
    # drops: the health-strip exemption cannot be recomputed from the log, so marks it would rescue are counted as dropped
    cands = {"current (image fractions)": None, "occupancy>=5%": tuple(summary["occupancy"]["equal_weight"][">=0.05"]),
             "occupancy>=25%": tuple(summary["occupancy"]["equal_weight"][">=0.25"]), "controller HERO_BOX": HERO_BOX_CTRL}
    table = {}
    for name, z in cands.items():
        def drop(r):
            if z is None:
                return r["dropped_now"]
            cx, cy = (r["box"][0] + r["box"][2]) / 2, (r["box"][1] + r["box"][3]) / 2
            return bool(r["small"] and z[0] <= cx <= z[2] and z[1] <= cy <= z[3])
        entry = {"zone": z}
        for view in ("wide", "aim"):
            for rec in RECS + ("all",):
                rs = [dict(r, dropped_now=drop(r)) for r in rows if r["view"] == view and rec in ("all", r["rec"])]
                per = defaultdict(list)
                for r in rs:
                    per[(r["rec"], r["id"])].append(r)
                bs = [b for v in per.values() for b in bodies(v)]
                entry[f"{rec}/{view}"] = {"marks_dropped": sum(r["dropped_now"] for r in rs), "marks": len(rs),
                                          "bodies_lost": sum(b["lost"] for b in bs), "bodies": len(bs)}
            entry[f"not_enemy_dropped/{view}"] = [f"{r['rec']} {r['id']}" for r in rows
                                                  if r["view"] == view and junk_of(r) and drop(r)]
        table[name] = entry
    summary["candidate_zones"] = table
    (ed / "footprint.json").write_text(json.dumps(summary, indent=1))

    # marks at least half on his own silhouette: where hero junk would have to be
    on = [r for r in rows if r.get("on_silhouette", 0) >= 0.5]
    tiles = [crop_tile(cv2.imread(fmap[(r["rec"], r["id"])]["path"]), r, fmap[(r["rec"], r["id"])].get("box"),
                       f"{r['view']} {r['rec'][:6]} {r['id'][-6:]} h{r['h_native']} s{r['on_silhouette']}") for r in on]
    if tiles:
        cv2.imwrite(str(ed / "on-silhouette.jpg"), grid(tiles, 7), [cv2.IMWRITE_JPEG_QUALITY, 85])
        (ed / "on-silhouette.json").write_text(json.dumps(on, indent=0))
    print(json.dumps(summary["frames"], indent=1))
    print(json.dumps({k: v for k, v in summary["marks"].items()}, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
