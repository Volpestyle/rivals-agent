"""Pack IDM-labelled expert shards into small 10 Hz world-model inputs, on the PC, without decoding video again.

  python -m rl.world_model.expert_prep --out D:/rivals-agent-local/rl-wm-expert [shard ...]

Reads policy's views (D:/rivals-policy/expert-views/<shard>/global.npy, uint8 [n,144,256,3] RGB, row k = row k of
D:/rivals-policy/expert-labels/<shard>.steps.jsonl; read-only, chunked plain file IO, no whole-file load, no memmap)
and writes per shard to --out/<shard>/:
  frames.bin + offsets.npy  JPEG (q90) of every kept 10 Hz frame, overlay rects from idm-spans.jsonl blacked out
  actions.npy               [m, 2*ACTION_DIM] float32: the step action (data.ACTION_DIM) then its known mask
  segs.npy                  [m] int32 segment code: kept rows m, m+1 share a code only if they are 100 ms apart
  meta.json
Third-party footage: keep it private, never in git, Linear or visuals; delete it from any volume after the run.

Labels (idm v2-a, REPLAY table): null is unknown, never "no". Only the channels idm validated are used: holds of
move_forward/left/right, web_swing, spider_power; presses of jump, amazing_combo, web_cluster; camera degrees when
camera_conf >= CONF_MIN in all three rows. Everything else is marked unknown.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

from rl.world_model import data as D

VIEWS = Path("D:/rivals-policy/expert-views")
LABELS = Path("D:/rivals-policy/expert-labels")
SPANS = Path("D:/rivals-expert-footage/idm-spans.jsonl")
HELD_OK = ("move_forward", "move_left", "move_right", "web_swing", "spider_power")
PRESS_OK = ("jump", "amazing_combo", "web_cluster")
CONF_MIN = 0.3
H, W = 144, 256
FRAME = H * W * 3
CHUNK = 900            # rows per read: ~100 MB


def below_normal():
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def npy_header(f):
    """(shape, data offset) of an uncompressed C-order uint8 .npy, read with plain file IO."""
    magic = f.read(8)
    if magic[:6] != b"\x93NUMPY":
        raise ValueError("not an .npy file")
    size = int.from_bytes(f.read(2 if magic[6] == 1 else 4), "little")
    header = ast.literal_eval(f.read(size).decode("latin1"))
    if header["descr"] not in ("|u1", "<u1") or header["fortran_order"]:
        raise ValueError(f"unexpected npy layout {header}")
    return tuple(header["shape"]), f.tell()


def step_action(rows, order):
    """ACTION_DIM values and ACTION_DIM known bits for one 10 Hz step (three 30 Hz REPLAY rows)."""
    n = D.N_ACT
    vals, known = [0.0] * D.ACTION_DIM, [0.0] * D.ACTION_DIM
    for c, name in enumerate(D.ACTIONS):
        j = order[name]
        if name in HELD_OK and all(r["held_known"][j] and r["held_end"][j] is not None for r in rows):
            vals[c], known[c] = sum(r["held_end"][j] for r in rows) / len(rows), 1.0
        if name in PRESS_OK and all(r.get("press_known", [False] * n)[j] and r["press"][j] is not None for r in rows):
            vals[n + c], known[n + c] = float(max(r["press"][j] for r in rows)), 1.0
    if all(r.get("yaw_deg") is not None and r.get("pitch_deg") is not None
           and (r.get("camera_conf") or 0) >= CONF_MIN for r in rows):
        vals[-2] = sum(r["yaw_deg"] for r in rows) / D.DEG_SCALE
        vals[-1] = sum(r["pitch_deg"] for r in rows) / D.DEG_SCALE
        known[-2] = known[-1] = 1.0
    return vals + known


def kept_rows(rows):
    """Indices of the first row of each complete 3-row step, runs kept separate and consecutive."""
    keep, k = [], 0
    while k + 2 < len(rows):
        a, b, c = rows[k:k + 3]
        if (a["run"] == b["run"] == c["run"] and b["i"] == a["i"] + 1 and c["i"] == b["i"] + 1
                and all(r.get("suitability") == "accepted" for r in (a, b, c))):
            keep.append(k)
            k += 3
        else:
            k += 1
    return keep


def load_spans(path=SPANS):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            j = json.loads(line)
            rects = [o["rect"] for o in (j.get("overlay_rects") or []) + (j.get("overlays") or [])
                     + (j.get("facecam_rects") or []) if isinstance(o, dict) and o.get("rect")]
            rects += [r for r in (j.get("facecam_rects") or []) if isinstance(r, list)]
            out[j["span_id"]] = rects
    return out


def pack(shard, out_root, spans, views_root=VIEWS, labels_root=LABELS, log=print):
    import cv2
    vdir, lpath = views_root / shard, labels_root / f"{shard}.steps.jsonl"
    vmeta = json.loads((vdir / "views.json").read_text(encoding="utf-8"))
    if vmeta["decoded"] != vmeta["rows"]:
        raise ValueError(f"{shard}: views incomplete ({vmeta['decoded']}/{vmeta['rows']})")
    if sha256(lpath) != vmeta["steps_sha256"]:
        raise ValueError(f"{shard}: labels changed since the views were built")
    with open(lpath, encoding="utf-8") as f:
        header = json.loads(f.readline())
        rows = [json.loads(line) for line in f if line.strip()]
    if len(rows) != vmeta["rows"]:
        raise ValueError(f"{shard}: {len(rows)} label rows vs {vmeta['rows']} views")
    order = {name: header["actions"].index(name) for name in D.ACTIONS}
    keep = kept_rows(rows)
    run_codes, codes, seg = {}, [], -1
    actions = np.zeros((len(keep), 2 * D.ACTION_DIM), np.float32)
    for m, k in enumerate(keep):
        actions[m] = step_action(rows[k:k + 3], order)
        run_codes.setdefault(rows[k]["run"], len(run_codes))
        prev = rows[keep[m - 1]] if m else None
        if not (prev and prev["run"] == rows[k]["run"] and rows[k]["i"] == prev["i"] + 3):
            seg += 1
        codes.append(seg)
    masks = {}
    for run in run_codes:
        rects = spans.get(run, [])
        masks[run] = [(int(x0 * W), int(y0 * H), int(np.ceil(x1 * W)), int(np.ceil(y1 * H))) for x0, y0, x1, y1 in rects]
    dest = Path(out_root) / shard
    dest.mkdir(parents=True, exist_ok=True)
    offsets = [0]
    with open(vdir / "global.npy", "rb") as src, open(dest / "frames.bin.tmp", "wb") as blob:
        shape, base = npy_header(src)
        if shape[1:] != (H, W, 3) or shape[0] != len(rows):
            raise ValueError(f"{shard}: views shape {shape}")
        for a in range(0, len(keep), CHUNK // 3):
            ks = keep[a:a + CHUNK // 3]
            lo, hi = ks[0], ks[-1] + 1
            src.seek(base + lo * FRAME)
            buf = np.frombuffer(src.read((hi - lo) * FRAME), np.uint8).reshape(hi - lo, H, W, 3)
            for k in ks:
                img = buf[k - lo].copy()
                for x0, y0, x1, y1 in masks[rows[k]["run"]]:
                    img[y0:y1, x0:x1] = 0
                ok, jpg = cv2.imencode(".jpg", img[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 90])
                if not ok:
                    raise RuntimeError("jpeg encode failed")
                blob.write(jpg.tobytes())
                offsets.append(offsets[-1] + len(jpg))
            del buf
    os.replace(dest / "frames.bin.tmp", dest / "frames.bin")
    np.save(dest / "offsets.npy", np.asarray(offsets, np.int64))
    np.save(dest / "actions.npy", actions)
    np.save(dest / "segs.npy", np.asarray(codes, np.int32))
    known = actions[:, D.ACTION_DIM:].mean(0)
    meta = {"shard": shard, "player": (header.get("expert_context") or {}).get("player"),
            "video_group": header.get("source_video_group"), "rows": len(rows), "kept": len(keep),
            "runs": len(run_codes), "segments": seg + 1, "masked_runs": sum(bool(v) for v in masks.values()),
            "frames_bytes": offsets[-1], "labels_sha256": vmeta["steps_sha256"],
            "known_share": {"held": dict(zip(D.ACTIONS, known[:D.N_ACT].round(3).tolist())),
                            "press": dict(zip(D.ACTIONS, known[D.N_ACT:2 * D.N_ACT].round(3).tolist())),
                            "camera": float(known[-1])},
            "third_party": True}
    (dest / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    log(json.dumps({k: meta[k] for k in ("shard", "player", "kept", "runs", "segments", "masked_runs", "frames_bytes")}))
    return meta


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("shards", nargs="*", help="default: every shard whose views are complete")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    below_normal()
    shards = a.shards or sorted(d.name for d in VIEWS.iterdir() if (d / "views.json").exists())
    spans = load_spans()
    for shard in shards:
        if (Path(a.out) / shard / "meta.json").exists():
            print(f"{shard}: already packed", flush=True)
            continue
        t = time.time()
        try:
            pack(shard, a.out, spans)
        except ValueError as e:
            print(f"{shard}: skipped: {e}", flush=True)
            continue
        print(f"{shard}: {time.time() - t:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
