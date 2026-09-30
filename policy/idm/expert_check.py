"""Validate IDM labels on the expert footage itself (VUH-1353, lean mode, local, $0).

Camera: a loop closure is a stretch where the view comes back to the same landmark after one full turn, so the true
yaw change is 360 degrees (the native-turn calibration's method, docs/evidence/camera-native-turn-20260929). The
search is label-guided but the closure frame is chosen by image similarity alone, then every accepted closure is
confirmed by eye on a contact sheet. Reported: the IDM's integrated yaw over the closure against 360, and its
integrated pitch against 0 (the view returns level).

    python -m policy.idm.expert_check candidates WORK_DIR SPANS.jsonl OUT.json      # label-only prefilter
    python -m policy.idm.expert_check closures OUT.json CANDIDATES.json SHEET_DIR    # decode, match, sheets

Third-party frames: sheets stay under D:/rivals-agent-local; nothing here goes to git or Linear.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path, PureWindowsPath

import numpy as np

LO, HI = 250.0, 470.0          # predicted yaw range searched for a full turn (+-30 %)
MAX_S = 5.0                    # a closure must complete within this many seconds


def creator(span):
    return PureWindowsPath(span.get("source_path", span["local_path"])).parent.name


def load(npz):
    with np.load(npz) as z:
        return {k: z[k] for k in ("t", "cam", "yaw_ans", "pitch_ans")}


def candidates(work, spans_path, out, *, model="v2-cd", per_creator=12):
    """Spans whose integrated predicted yaw sweeps LO..HI within MAX_S, ranked by sweep, a few per creator."""
    rows = [json.loads(x) for x in Path(spans_path).read_text(encoding="utf-8").splitlines() if x.strip()]
    found = {}
    for s in rows:
        f = Path(work) / model / (s["span_id"].replace(":", "_") + ".npz")
        if not f.exists():
            continue
        z = load(f)
        t, yaw = z["t"], np.nan_to_num(z["cam"][:, 0])
        c = np.concatenate([[0.0], np.cumsum(yaw)])[1:]
        best = None
        for i in range(0, len(t), 6):
            j = np.searchsorted(t, t[i] + MAX_S)
            d = np.abs(c[i:j] - c[i])
            hit = np.nonzero((d >= LO) & (d <= HI))[0]
            if len(hit):
                best = (i, int(i + hit[0]))
                break
        if best:
            found.setdefault(creator(s), []).append({"span": s["span_id"], "i": best[0], "t_i": float(t[best[0]]),
                                                     "npz": str(f), "video": s["local_path"],
                                                     "rects": [o["rect"] for o in s.get("overlays", [])]})
    picked = {c: v[:per_creator] for c, v in found.items()}
    Path(out).write_text(json.dumps(picked, indent=1), encoding="utf-8")
    return {c: len(v) for c, v in found.items()}


def small(grey, rects=()):
    """Frames for similarity: world only. HUD bands, the hero's screen region and overlays masked; 112x63."""
    g = grey.astype(np.float32).reshape(len(grey), 63, 4, 112, 4).mean((2, 4))
    m = np.ones((63, 112), bool)
    m[:9], m[-12:] = False, False                                   # top HUD / bottom HUD
    m[30:63, 36:76] = False                                         # hero (centre-bottom)
    for x0, y0, x1, y1 in rects:
        m[int(y0 * 63):int(np.ceil(y1 * 63)), int(x0 * 112):int(np.ceil(x1 * 112))] = False
    v = g[:, m]
    v = v - v.mean(1, keepdims=True)
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-6)


def closures(out, cand_path, sheet_dir, *, fast=True):
    from policy.idm import vod
    cands = json.loads(Path(cand_path).read_text(encoding="utf-8"))
    Path(sheet_dir).mkdir(parents=True, exist_ok=True)
    results = []
    for who, items in cands.items():
        for c in items:
            z = load(c["npz"])
            t, yaw, pitch = z["t"], z["cam"][:, 0], z["cam"][:, 1]
            cy = np.cumsum(np.nan_to_num(yaw))
            i0 = c["i"]
            j_end = int(np.searchsorted(t, t[i0] + MAX_S))
            try:
                grey, _, pts = vod.decode_span(c["video"], float(t[max(0, i0 - 1)]) - 0.02, float(t[min(len(t) - 1,
                                               j_end)]) + 0.02, fast=fast)
            except Exception as e:
                results.append({"creator": who, "span": c["span"], "error": str(e)[:200]})
                continue
            idx = {round(float(p), 3): k for k, p in enumerate(pts)}
            frames = [idx.get(round(float(x), 3)) for x in t]
            best = None
            for i in range(i0, min(i0 + 180, j_end), 3):             # starts over the first 3 s of the sweep
                if frames[i] is None:
                    continue
                d = np.abs(cy[i:j_end] - cy[i])
                js = [i + k for k in np.nonzero((d >= LO) & (d <= HI))[0] if frames[i + k] is not None]
                ctrl = [i + k for k in np.nonzero((d >= 150) & (d <= 210))[0] if frames[i + k] is not None]
                if not js or not ctrl:
                    continue
                v = small(grey[[frames[i]] + [frames[j] for j in js] + [frames[j] for j in ctrl]], c["rects"])
                sims = v[1:] @ v[0]
                k = int(np.argmax(sims[:len(js)]))
                cand = {"i": i, "j": js[k], "sim": float(sims[k]), "ctrl_sim": float(sims[len(js):].max())}
                if best is None or cand["sim"] - cand["ctrl_sim"] > best["sim"] - best["ctrl_sim"]:
                    best = cand
            if best is None:
                continue
            i, j = best["i"], best["j"]
            seg = slice(i + 1, j + 1)                                  # intervals ending after frame i up to frame j
            rate = abs(float(np.nansum(yaw[seg]))) / max(float(t[j] - t[i]), 1e-3)
            rec = {"creator": who, "span": c["span"], "t_i": float(t[i]), "t_j": float(t[j]),
                   "pred_yaw": float(np.nansum(yaw[seg])), "pred_pitch": float(np.nansum(pitch[seg])),
                   "abstain_frac": float(np.mean(np.isnan(z["yaw_ans"][seg]))),
                   "sim": round(best["sim"], 4), "ctrl_sim": round(best["ctrl_sim"], 4),
                   "frame_bound_deg": round(rate / 60 / 2, 2)}               # +- half a 60 Hz interval of turning
            name = f"{who}_{c['span'].replace(':', '_')}"
            sheet(grey, frames, cy, i, j, Path(sheet_dir) / f"{name}.png", rec)
            rec["sheet"] = str(Path(sheet_dir) / f"{name}.png")
            results.append(rec)
            print(json.dumps(rec), flush=True)
    Path(out).write_text(json.dumps(results, indent=1), encoding="utf-8")
    return results


def sheet(grey, frames, cy, i, j, path, rec):
    """Frame i, the frames at predicted +90/180/270, and frame j, in a row (grey, 448x252 each)."""
    import cv2
    picks = [i]
    for q in (90, 180, 270):
        k = i + int(np.argmin(np.abs(np.abs(cy[i:j + 1] - cy[i]) - q)))
        picks.append(k)
    picks.append(j)
    tiles = []
    for n, k in enumerate(picks):
        im = cv2.cvtColor(grey[frames[k]], cv2.COLOR_GRAY2BGR) if frames[k] is not None else np.zeros((252, 448, 3),
                                                                                                          np.uint8)
        lab = ["start", "pred 90", "pred 180", "pred 270", "match"][n]
        cv2.putText(im, f"{lab} {abs(cy[k] - cy[i]):.0f}deg", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        tiles.append(im)
    row = np.concatenate(tiles, 1)
    top = np.zeros((30, row.shape[1], 3), np.uint8)
    cv2.putText(top, f"{rec['creator']} {rec['span']}  pred yaw {rec['pred_yaw']:.1f}  sim {rec['sim']:.2f} "
                f"ctrl {rec['ctrl_sim']:.2f}", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    cv2.imwrite(str(path), np.concatenate([top, row], 0))


def world_mask(rects=()):
    """uint8 mask of world pixels in a 448x252 frame: no HUD bands, hero box or overlays."""
    m = np.full((252, 448), 255, np.uint8)
    m[:36], m[-48:] = 0, 0
    m[120:, 150:300] = 0
    for x0, y0, x1, y1 in rects:
        m[int(y0 * 252):int(np.ceil(y1 * 252)), int(x0 * 448):int(np.ceil(x1 * 448))] = 0
    return m


def closures_sift(out, cand_path, sheet_dir, *, lo=180.0, hi=540.0, max_s=7.0, fast=True):
    """Like `closures`, but the return frame is the one sharing the most RANSAC-homography SIFT inliers with the start
    frame (tolerant of the player's travel), searched over predicted turns lo..hi so a large IDM error cannot hide.
    Control: the best inlier count at a predicted 90-150 degrees."""
    import cv2
    from policy.idm import vod
    sift = cv2.SIFT_create(nfeatures=600)
    matcher = cv2.BFMatcher()
    cands = json.loads(Path(cand_path).read_text(encoding="utf-8"))
    Path(sheet_dir).mkdir(parents=True, exist_ok=True)
    results = []

    def inliers(fa, fb):
        if fa[1] is None or fb[1] is None or len(fa[0]) < 8 or len(fb[0]) < 8:
            return 0
        good = [m for m, n in (p for p in matcher.knnMatch(fa[1], fb[1], k=2) if len(p) == 2) if m.distance < 0.75 * n.distance]
        if len(good) < 8:
            return 0
        a = np.float32([fa[0][m.queryIdx].pt for m in good])
        b = np.float32([fb[0][m.trainIdx].pt for m in good])
        _, mask = cv2.findHomography(a, b, cv2.RANSAC, 4.0)
        return int(mask.sum()) if mask is not None else 0

    for who, items in cands.items():
        for c in items:
            z = load(c["npz"])
            t, yaw, pitch = z["t"], z["cam"][:, 0], z["cam"][:, 1]
            cy = np.cumsum(np.nan_to_num(yaw))
            i0 = c["i"]
            j_end = int(min(len(t) - 1, np.searchsorted(t, t[i0] + max_s)))
            try:
                grey, _, pts = vod.decode_span(c["video"], float(t[max(0, i0 - 1)]) - 0.02, float(t[j_end]) + 0.02,
                                               fast=fast)
            except Exception as e:
                results.append({"creator": who, "span": c["span"], "error": str(e)[:200]})
                continue
            idx = {round(float(p), 3): k for k, p in enumerate(pts)}
            frames = [idx.get(round(float(x), 3)) for x in t]
            mask = world_mask(c["rects"])
            feats = {}

            def feat(k):
                if k not in feats:
                    kp, des = sift.detectAndCompute(grey[frames[k]], mask)
                    feats[k] = (kp, des)
                return feats[k]
            best = None
            for i in range(i0, min(i0 + 120, j_end), 10):
                if frames[i] is None:
                    continue
                d = np.abs(cy[i:j_end + 1] - cy[i])
                js = [i + k for k in np.nonzero((d >= lo) & (d <= hi))[0][::2] if frames[i + k] is not None]
                ctrl = [i + k for k in np.nonzero((d >= 90) & (d <= 150))[0][::4] if frames[i + k] is not None]
                if not js or not ctrl:
                    continue
                fi = feat(i)
                inl = [inliers(fi, feat(j)) for j in js]
                k = int(np.argmax(inl))
                cand = {"i": i, "j": js[k], "inl": inl[k], "ctrl": max(inliers(fi, feat(j)) for j in ctrl)}
                if best is None or cand["inl"] - cand["ctrl"] > best["inl"] - best["ctrl"]:
                    best = cand
            if best is None:
                continue
            i, j = best["i"], best["j"]
            for jj in range(max(i + 1, j - 2), min(j_end, j + 2) + 1):    # refine to the single best frame
                if frames[jj] is not None:
                    n = inliers(feat(i), feat(jj))
                    if n > best["inl"]:
                        best["inl"], j = n, jj
            seg = slice(i + 1, j + 1)
            rate = abs(float(np.nansum(yaw[seg]))) / max(float(t[j] - t[i]), 1e-3)
            rec = {"creator": who, "span": c["span"], "t_i": float(t[i]), "t_j": float(t[j]),
                   "pred_yaw": float(np.nansum(yaw[seg])), "pred_pitch": float(np.nansum(pitch[seg])),
                   "abstain_frac": float(np.mean(np.isnan(z["yaw_ans"][seg]))), "inliers": best["inl"],
                   "ctrl_inliers": best["ctrl"], "frame_bound_deg": round(rate / 60 / 2, 2), "sim": best["inl"],
                   "ctrl_sim": best["ctrl"]}
            name = f"{who}_{c['span'].replace(':', '_')}"
            sheet(grey, frames, cy, i, j, Path(sheet_dir) / f"{name}.png", rec)
            rec["sheet"] = str(Path(sheet_dir) / f"{name}.png")
            results.append(rec)
            print(json.dumps(rec), flush=True)
    Path(out).write_text(json.dumps(results, indent=1), encoding="utf-8")
    return results


ACTIONS_CHECKED = ("web_cluster", "amazing_combo", "jump", "web_swing", "get_over_here")


def press_sheets(work, spans_path, ckpt, out_dir, *, per_action=4, seed=0, model="v2-cd"):
    """Sample predicted press onsets (peak of an above-threshold run) per checked action, spread over creators, and
    render each as a sheet: 10 frames from -0.25 s to +0.5 s (world, grey) over the native colour HUD crops, the
    onset frame marked. The eye decides whether the action happened within +-2 intervals."""
    import cv2
    from policy.idm import vod
    _, _, thr = vod.load_any(ckpt, "cpu")
    rows = [json.loads(x) for x in Path(spans_path).read_text(encoding="utf-8").splitlines() if x.strip()]
    rng = np.random.default_rng(seed)
    by_creator = {}
    for s in rows:
        f = Path(work) / model / (s["span_id"].replace(":", "_") + ".npz")
        if f.exists():
            by_creator.setdefault(creator(s), []).append((s, f))
    creators = sorted(by_creator)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    picked = []
    for a_i, action in enumerate(ACTIONS_CHECKED):
        n, tries = 0, 0
        while n < per_action and tries < 400:
            tries += 1
            who = creators[(a_i + n + tries) % len(creators)]
            s, f = by_creator[who][rng.integers(len(by_creator[who]))]
            with np.load(f) as z:
                prob, t = z["prob"], z["t"]
                meta = json.loads(str(z["meta"]))
            c = meta["actions"].index(action)
            ons = vod.onsets(prob[:, c], thr[action])
            ons = [k for k in ons if t[k] - 0.4 > s["start_s"] and t[k] + 0.6 < s["end_s"]]
            if not ons:
                continue
            k = ons[rng.integers(len(ons))]
            grey, hud, pts = vod.decode_span(s["local_path"], float(t[k]) - 0.3, float(t[k]) + 0.55, fast=True)
            k0 = int(np.argmin(np.abs(pts - t[k])))
            picks = [min(len(pts) - 1, max(0, k0 + d)) for d in range(-15, 31, 5)]
            tiles = []
            for q in picks:
                w = cv2.resize(cv2.cvtColor(grey[q], cv2.COLOR_GRAY2BGR), (224, 126))
                h = cv2.resize(hud[q][:, :, ::-1], (224, 90), interpolation=cv2.INTER_NEAREST)
                col = np.concatenate([w, h], 0)
                if q == k0:
                    cv2.rectangle(col, (0, 0), (223, 215), (0, 0, 255), 3)
                cv2.putText(col, f"{(pts[q] - t[k]) * 1000:+.0f}ms", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                            (0, 255, 255), 1)
                tiles.append(col)
            img = np.concatenate(tiles, 1)
            top = np.zeros((24, img.shape[1], 3), np.uint8)
            cv2.putText(top, f"{action} p={prob[k, c]:.2f} thr={thr[action]:.2f} {who} {s['span_id']} t={t[k]:.3f}",
                        (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            name = f"{action}_{n}_{who}.png"
            cv2.imwrite(str(Path(out_dir) / name), np.concatenate([top, img], 0))
            picked.append({"action": action, "creator": who, "span": s["span_id"], "t": float(t[k]),
                           "p": float(prob[k, c]), "sheet": name})
            n += 1
    Path(out_dir, "picked.json").write_text(json.dumps(picked, indent=1), encoding="utf-8")
    return picked


# ---- geometric yaw: an IDM-independent reference from the far-background image shift --------------------------------
# Band y in [40, 126) of the 448x252 grey frame (below the top HUD / kill feed, above the hero), x in [16, 432).
BAND = (40, 126, 16, 432)


def band(grey, rects, rng):
    """The background band as float32, with overlays and the crosshair filled with fresh noise so that static
    screen-space pixels cannot pull the correlation peak to zero shift."""
    y0, y1, x0, x1 = BAND
    b = grey[y0:y1, x0:x1].astype(np.float32)
    h, w = b.shape
    boxes = [(0.47, 0.47, 0.53, 0.53)] + list(rects)                 # crosshair (full-frame coords) + overlays
    for bx0, by0, bx1, by1 in boxes:
        ya, yb = int(by0 * 252) - y0, int(np.ceil(by1 * 252)) - y0
        xa, xb = int(bx0 * 448) - x0, int(np.ceil(bx1 * 448)) - x0
        ya, yb, xa, xb = max(0, ya), min(h, yb), max(0, xa), min(w, xb)
        if ya < yb and xa < xb:
            b[ya:yb, xa:xb] = rng.uniform(0, 255, (yb - ya, xb - xa))
    return b


def shifts(grey, pairs, rects=(), seed=0):
    """[(dx, dy, response)] of phase correlation between frame pairs (k0, k1) of grey [N, 252, 448] uint8."""
    import cv2
    rng = np.random.default_rng(seed)
    win = cv2.createHanningWindow((BAND[3] - BAND[2], BAND[1] - BAND[0]), cv2.CV_32F)
    out = []
    for k0, k1 in pairs:
        (dx, dy), resp = cv2.phaseCorrelate(band(grey[k0], rects, rng), band(grey[k1], rects, rng), win)
        out.append((dx, dy, resp))
    return np.array(out, np.float64).reshape(-1, 3)


def geo_rows(video, rows_t, windows, rects=(), fast=True):
    """For rows given as (t0, t1) seconds (the interval's start and end frame times), the image shift between the
    decoded frames nearest those times, decoding only the listed windows. Returns {row index: (dx, dy, resp)}."""
    from policy.idm import vod
    out = {}
    for a, b in windows:
        idx = [k for k, (t0, t1) in enumerate(rows_t) if a <= t0 and t1 <= b]
        if not idx:
            continue
        grey, _, pts = vod.decode_span(video, a, b, fast=fast)
        pairs, keep = [], []
        for k in idx:
            t0, t1 = rows_t[k]
            k0, k1 = int(np.argmin(np.abs(pts - t0))), int(np.argmin(np.abs(pts - t1)))
            if abs(pts[k0] - t0) < 0.009 and abs(pts[k1] - t1) < 0.009 and k1 > k0:
                pairs.append((k0, k1))
                keep.append(k)
        for k, s in zip(keep, shifts(grey, pairs, rects)):
            out[k] = tuple(s)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("candidates")
    c.add_argument("work")
    c.add_argument("spans")
    c.add_argument("out")
    c.add_argument("--per-creator", type=int, default=12)
    k = sub.add_parser("closures")
    k.add_argument("out")
    k.add_argument("candidates")
    k.add_argument("sheets")
    k.add_argument("--sift", action="store_true", help="SIFT/RANSAC inliers, predicted 180-540 degrees")
    q = sub.add_parser("presses")
    q.add_argument("work")
    q.add_argument("spans")
    q.add_argument("ckpt")
    q.add_argument("out")
    q.add_argument("--per-action", type=int, default=4)
    a = ap.parse_args(argv)
    if a.cmd == "presses":
        print(json.dumps(press_sheets(a.work, a.spans, a.ckpt, a.out, per_action=a.per_action), indent=1))
    elif a.cmd == "candidates":
        print(json.dumps(candidates(a.work, a.spans, a.out, per_creator=a.per_creator)))
    else:
        (closures_sift if a.sift else closures)(a.out, a.candidates, a.sheets)
    return 0


if __name__ == "__main__":
    sys.exit(main())
