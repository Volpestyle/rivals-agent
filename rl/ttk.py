"""Time to kill (TTK) and KO/hit rates from pixel reward events (VUH-1321). CPU only, no game.

  python -m rl.ttk OUT_DIR [--sitting DIR ...] [--scripted FRAME_DIR]

TTK is per engagement: hits closer than GAP_S to the previous one belong to one engagement, which starts on its first
hit. A KO no more than GAP_S after the engagement's last hit ends it, and its TTK is KO time minus first hit. The
readers have no target identity, so "same target" is this time rule; two bots killed back to back without a 3 s pause
count as one engagement for the first KO, then a new one. A KO without a hit in the GAP_S before it gets no TTK.

Sources: James's range takes (rl/labels/range_rewards_20260930.json, read at 10 fps by the 6 px hit rule;
HIT_RUN 10 px kept precision 1.00 on the labels and recall 0.98 -> 0.97), the scripted brain's baseline1 run (its
retained native frames, ~9 Hz), and online-RL sittings (every retained frame of each episode's policy phase, split by
arm, rl/aim/exclusions.json applied). Writes ttk.json and ttk.png (KOs/min and median TTK per source).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

GAP_S = 3.0
LABELS = Path("rl/labels/range_rewards_20260930.json")
EXCLUSIONS = Path("rl/aim/exclusions.json")


def engagements(hits, kos, gap=GAP_S):
    """[{start, last, hits, ko_t, ttk}] from hit and KO times (seconds, any order)."""
    events = sorted([(t, 0) for t in hits] + [(t, 1) for t in kos])
    out, cur = [], None
    for t, kind in events:
        if kind == 0:
            if cur is None or t - cur["last"] > gap:
                if cur is not None:
                    out.append(cur)
                cur = {"start": t, "last": t, "hits": 0, "ko_t": None, "ttk": None}
            cur["last"] = t
            cur["hits"] += 1
        elif cur is not None and t - cur["last"] <= gap:
            cur["ko_t"], cur["ttk"] = t, round(t - cur["start"], 2)
            out.append(cur)
            cur = None                       # the bot is down: the next hit is a new engagement
    if cur is not None:
        out.append(cur)
    return out


def summary(hits, kos, seconds, gap=GAP_S):
    eng = engagements(hits, kos, gap)
    ttk = [e["ttk"] for e in eng if e["ttk"] is not None]
    return {"seconds": round(seconds, 1), "hits": len(hits), "kos": len(kos),
            "hits_per_min": round(len(hits) / max(seconds, 1e-6) * 60, 2),
            "kos_per_min": round(len(kos) / max(seconds, 1e-6) * 60, 2),
            "engagements": len(eng), "kos_with_ttk": len(ttk),
            "ttk_median_s": round(float(np.median(ttk)), 2) if ttk else None,
            "ttk_p25_p75_s": [round(float(v), 2) for v in np.percentile(ttk, [25, 75])] if ttk else None,
            "ttk_s": ttk}


def frame_events(frames_and_times):
    """Hit and KO rising-edge times from (frame, t) in time order, via RewardTracker."""
    from rl.rewards import RewardTracker, hit_marker, ko_marker, own_hp
    tracker, hits, kos = RewardTracker(), [], []
    for frame, t in frames_and_times:
        hp, max_hp = own_hp(frame)
        s = tracker.update(t, hit_marker(frame), ko_marker(frame), hp, max_hp)
        if s.hit:
            hits.append(t)
        if s.ko:
            kos.append(t)
    return hits, kos


def _stream(base, rows):
    import cv2
    for r in rows:
        frame = cv2.imread(str(Path(base) / r["file"]))
        if frame is not None:
            yield frame, float(r["t"])


def james():
    d = json.loads(LABELS.read_text())
    per, hits, kos, secs, off = {}, [], [], 0., 0.
    for name, s in d["sessions"].items():
        per[name] = summary(s["hit"], s["ko"], s["seconds"])
        hits += [t + off for t in s["hit"]]          # sessions laid end to end, a gap apart, so engagements never join
        kos += [t + off for t in s["ko"]]
        secs += s["seconds"]
        off += s["seconds"] + 10 * GAP_S
    out = summary(hits, kos, secs)
    out["sessions"] = {k: {kk: v[kk] for kk in ("seconds", "kos_per_min", "ttk_median_s")} for k, v in per.items()}
    return out


def scripted(frame_dir):
    rows = [json.loads(line) for line in open(Path(frame_dir) / "frames.jsonl", encoding="utf-8") if line.strip()]
    rows = [r for r in rows if r.get("file")]
    hits, kos = frame_events(_stream(frame_dir, rows))
    return summary(hits, kos, rows[-1]["t"] - rows[0]["t"])


def sitting(sitting_dir, excluded=()):
    """Per arm: events from each episode's retained policy-phase frames, episodes laid end to end."""
    from rl.online.data import decisions
    arms = {}
    for ep in sorted(Path(sitting_dir).glob("ep-*")):
        if not ep.is_dir() or any(ep.as_posix().endswith(x) for x in excluded):
            continue
        arm = ep.name.rsplit("-", 1)[-1]
        rows, saved, _ = decisions(ep)
        if not rows:
            continue
        hits, kos = frame_events(_stream(ep, saved))
        a = arms.setdefault(arm, {"hits": [], "kos": [], "seconds": 0., "episodes": 0})
        off = a["seconds"] + a["episodes"] * 10 * GAP_S
        t0 = float(rows[0]["t"])
        a["hits"] += [t - t0 + off for t in hits]
        a["kos"] += [t - t0 + off for t in kos]
        a["seconds"] += float(rows[-1]["t"]) - t0
        a["episodes"] += 1
    return {arm: {**summary(a["hits"], a["kos"], a["seconds"]), "episodes": a["episodes"]} for arm, a in arms.items()}


def plot(rows, path):
    """Three panels: KOs/min, hits/min and median TTK (red bar: IQR) per source."""
    import cv2
    w, h, pad, left, gap = 1180, 560, 50, 230, 40
    img = np.full((h, w, 3), 255, np.uint8)
    rh = (h - 2 * pad) // max(len(rows), 1)
    pw = (w - left - pad - 2 * gap) // 3
    panels = [("KOs / min", "kos_per_min"), ("hits / min", "hits_per_min"), ("median TTK, s (red: IQR)", "ttk_median_s")]
    for p, (title, key) in enumerate(panels):
        x0 = left + p * (pw + gap)
        x1 = x0 + pw - 50
        vals = [r[key] for _, r in rows if r.get(key) is not None]
        if key == "ttk_median_s":
            vals += [r["ttk_p25_p75_s"][1] for _, r in rows if r.get("ttk_p25_p75_s")]
        top = max(vals + [1e-6])
        cv2.putText(img, title, (x0, pad - 14), 0, .55, (0, 0, 0), 1)
        cv2.line(img, (x0, pad - 4), (x0, h - pad), (150, 150, 150), 1)
        for k, (label, r) in enumerate(rows):
            y = pad + k * rh + rh // 2
            colour = (60, 60, 60) if label.startswith(("James", "scripted")) else (180, 119, 31)
            v = r.get(key)
            if v is None:
                cv2.putText(img, "no KO", (x0 + 6, y + 5), 0, .45, (120, 120, 120), 1)
                continue
            xe = int(x0 + (x1 - x0) * v / top)
            cv2.rectangle(img, (x0, y - rh // 3), (max(xe, x0 + 2), y + rh // 3), colour, -1)
            right = xe
            if key == "ttk_median_s" and r.get("ttk_p25_p75_s"):
                a, b = (int(x0 + (x1 - x0) * q / top) for q in r["ttk_p25_p75_s"])
                cv2.line(img, (a, y), (b, y), (0, 0, 200), 2)
                right = max(right, b)
            cv2.putText(img, f"{v:g}", (right + 6, y + 5), 0, .45, (0, 0, 0), 1)
    for k, (label, _) in enumerate(rows):
        cv2.putText(img, label, (8, pad + k * rh + rh // 2 + 5), 0, .45, (0, 0, 0), 1)
    cv2.putText(img, "pixel readers; TTK = first hit -> KO within an engagement (hits under 3 s apart); "
                "grey = baselines, blue = model arms", (8, h - 14), 0, .45, (90, 90, 90), 1)
    cv2.imwrite(str(path), img)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--sitting", action="append", default=[])
    ap.add_argument("--scripted")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    excluded = set(json.loads(EXCLUSIONS.read_text())["episodes"]) if EXCLUSIONS.exists() else set()
    result = {"gap_s": GAP_S, "james": james()}
    rows = [("James (range takes)", result["james"])]
    if a.scripted:
        result["scripted"] = scripted(a.scripted)
        rows.append(("scripted (baseline1)", result["scripted"]))
    for s in a.sitting:
        name = Path(s).name
        result[name] = sitting(s, excluded)
        for arm in ("bc", "rl"):
            if arm in result[name]:
                rows.append((f"{name.removeprefix('rl-sitting-')} {arm.upper()}", result[name][arm]))
    (out / "ttk.json").write_text(json.dumps(result, indent=1) + "\n")
    plot(rows, out / "ttk.png")
    for label, r in rows:
        print(f"{label:28s} KOs/min {r['kos_per_min']:5.2f}  hits/min {r['hits_per_min']:6.2f}  "
              f"TTK median {r['ttk_median_s']}  ({r['kos_with_ttk']}/{r['kos']} KOs)")
    return result


if __name__ == "__main__":
    main()
