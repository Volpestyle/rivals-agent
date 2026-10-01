"""Summarise an online-RL sitting (rl/online/sitting.py output), CPU only. No game, no GPU.

  python -m rl.online.analyze <sitting dir> <out dir>

Per episode: arm, stop result, runner decisions and how many were actually sent (disposition 'ready') versus dropped,
exploration options started and what they held, sampled-vs-deterministic disagreements, pixel reward events (hit, KO,
fall) and the update's loss/KL. Per arm: hits/min, KOs/min and time to kill (rl.ttk, from the retained frames) next to
James's and the scripted baselines (rl/out/ttk/ttk.json). Writes summary.json and summary.png (KOs/min, hits/min and
executed-decision share by episode, frozen BC vs RL).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def episode_stats(ep_dir):
    rows = [json.loads(line) for line in open(ep_dir / "frames.jsonl", encoding="utf-8") if line.strip()] \
        if (ep_dir / "frames.jsonl").exists() else []
    dec = [r for r in rows if r.get("event") == "decision"]
    disp = Counter(r.get("disposition") for r in dec)
    sends = sum(r.get("event") == "send" for r in rows)
    active = Counter(n for r in dec if r.get("disposition") == "ready" for n in r.get("active", []))
    stop = next((r.get("clause") for r in rows if r.get("event") == "stop"), None)
    out = {"decisions": len(dec), "ready": disp.get("ready", 0), "stale": disp.get("stale_after_inference", 0),
           "sends": sends, "stop": stop, "active_counts": dict(active.most_common())}
    explore = Path(str(ep_dir) + ".explore.jsonl")
    if explore.exists():
        steps = [json.loads(line) for line in open(explore, encoding="utf-8") if '"step"' in line]
        opts = [s["option"] for s in steps if s.get("option")]
        starts = [b for a, b in zip([None] + opts, opts) if a != b]
        differ = sum(set(s["exec"]["held"]) != set(s["det"]["held"]) for s in steps)
        out.update(explore_steps=len(steps), option_steps=len(opts), option_starts=dict(Counter(starts)),
                   sampled_differs=differ)
    return out


def main(argv=None):
    argv = argv or sys.argv[1:]
    sitting, out = Path(argv[0]), Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    curve = [json.loads(line) for line in open(sitting / "curve.jsonl", encoding="utf-8") if line.strip()] \
        if (sitting / "curve.jsonl").exists() else []
    meta = json.loads((sitting / "sitting.json").read_text()) if (sitting / "sitting.json").exists() else {}
    episodes = []
    for c in curve:
        ep = sitting / f"ep-{c['episode']:03d}-{c['arm']}"
        episodes.append({**{k: v for k, v in c.items() if k != "update"}, **episode_stats(ep),
                         "update": {k: c["update"].get(k) for k in ("first", "last", "return_mean", "episodes")}
                         if c.get("update") else None})
    summary = {"sitting": str(sitting), "meta": meta, "episodes": episodes}
    for arm in ("bc", "rl"):
        rows = [e for e in episodes if e["arm"] == arm and "kos_per_min" in e]
        secs = sum(e.get("seconds", 0) for e in rows)
        summary[arm] = {"episodes": len(rows), "seconds": round(secs, 1), "kos": sum(e.get("ko", 0) for e in rows),
                        "hits": sum(e.get("hit", 0) for e in rows), "falls": sum(e.get("death", 0) for e in rows),
                        "kos_per_min": round(sum(e.get("ko", 0) for e in rows) / max(secs, 1e-6) * 60, 2),
                        "hits_per_min": round(sum(e.get("hit", 0) for e in rows) / max(secs, 1e-6) * 60, 2),
                        "ready_share": round(sum(e["ready"] for e in rows) / max(1, sum(e["decisions"] for e in rows)), 3)}
    from rl import ttk
    excluded = set(json.loads(ttk.EXCLUSIONS.read_text())["episodes"]) if ttk.EXCLUSIONS.exists() else set()
    for arm, r in ttk.sitting(sitting, excluded).items():
        if arm in summary:
            summary[arm]["ttk"] = {k: r[k] for k in ("kos_with_ttk", "ttk_median_s", "ttk_p25_p75_s", "ttk_s")}
    base = Path("rl/out/ttk/ttk.json")
    if base.exists():
        b = json.loads(base.read_text())
        summary["baselines"] = {k: {kk: b[k][kk] for kk in ("hits_per_min", "kos_per_min", "ttk_median_s")}
                                for k in ("james", "scripted") if k in b}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    plot(episodes, out / "summary.png")
    print(json.dumps({k: summary[k] for k in ("bc", "rl", "baselines") if k in summary}, indent=1))
    return summary


def plot(episodes, path):
    import cv2
    import numpy as np
    w, h, pad = 900, 560, 60
    img = np.full((h, w, 3), 255, np.uint8)
    panels = [("KOs/min", "kos_per_min"), ("hits/min", "hits_per_min"), ("sent share", None)]
    n = max([e["episode"] for e in episodes] + [1])
    ph = (h - 2 * pad) // 3
    for k, (label, key) in enumerate(panels):
        y0 = pad + k * ph
        vals = [(e["episode"], e["arm"], (e.get(key, 0) if key else e["ready"] / max(1, e["decisions"])))
                for e in episodes]
        top = max([v for _, _, v in vals] + [1e-6])
        cv2.rectangle(img, (pad, y0), (w - pad, y0 + ph - 12), (215, 215, 215), 1)
        cv2.putText(img, f"{label} (max {top:.2f})", (pad + 4, y0 + 16), 0, .5, (0, 0, 0), 1)
        for arm, colour in (("bc", (136, 136, 136)), ("rl", (180, 119, 31))):
            pts = [(int(pad + (w - 2 * pad) * x / n), int(y0 + ph - 14 - (ph - 34) * v / top))
                   for x, a, v in vals if a == arm]
            for a, b in zip(pts, pts[1:]):
                cv2.line(img, a, b, colour, 2)
            for p in pts:
                cv2.circle(img, p, 4, colour, -1)
    cv2.putText(img, "online-RL sitting: grey frozen BC, blue RL (updated after each RL episode); x = episode",
                (pad, 30), 0, .55, (0, 0, 0), 1)
    cv2.imwrite(str(path), img)


if __name__ == "__main__":
    main()
