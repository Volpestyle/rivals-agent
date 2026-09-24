"""M1 and M2 from rows2.json / corr2_*.npz (measure2.py). Reads only.

Review F6: no spectral comparison against range play (player, content and parallax all differ). Instead:
- replay windows, player-independent replication signatures:
  * kinks: autocorrelation of |change in angular velocity| at lags 1-12 frames; a replication rate R Hz shows as a
    peak at lag 120/R;
  * pitch lattice: Rayleigh test of cumulative pitch modulo 360/256 = 1.40625 deg (Unreal's stock byte-compressed
    replicated view pitch -- a hypothesis to test, not a Rivals fact). The estimator resolves ~0.12 deg per pixel.
- live windows: validate the per-pair abstain rule against known mouse counts (fast pairs with zero flow should be
  withheld; still pairs kept), and the mouse-to-yaw lag and gain (estimator gain, not ground truth: the 360 take is).
M2: perception.camera_motion.replay_focal on the masked correspondences (live gate first); the viewer-FOV re-record
(review F5) is the decisive test and supersedes this if it disagrees.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, r"C:\Users\volpe\repos\rivals-agent")
from perception import camera_motion as cm  # noqa: E402

LATTICE = 360 / 256
res = json.loads((HERE / "rows2.json").read_text())
out = {"stopped": res.pop("stopped", None), "windows": {}}


def ac(v, lags=12):
    v = v - v.mean()
    d = (v * v).sum() or 1.0
    return [round(float((v[:-k] * v[k:]).sum() / d), 2) for k in range(1, lags + 1)]


def arr(rows, key):
    return np.array([np.nan if r[key] is None else r[key] for r in rows], float)


for name, w in res.items():
    rows, verdict = w["rows"], w["verdict"]
    diff = arr(rows, "diff")
    yaw, pitch = arr(rows, "yaw"), arr(rows, "pitch")
    rec = {"verdict": verdict, "fresh_frac": round(float((diff >= 0.25).mean()), 3),
           "pair_abstain": sum(1 for r in rows if r["abstain"] and r["abstain"] != "window invalid"),
           "fitted": int(np.isfinite(yaw).sum())}
    if verdict["valid"] and np.isfinite(yaw).sum() > 60:
        rate = np.hypot(np.nan_to_num(yaw), np.nan_to_num(pitch)) * 120
        rec["rate_dps_p50_p95"] = [round(float(np.percentile(rate, q)), 1) for q in (50, 95)]
        if w["replay"]:
            rec["ac_kinks"] = ac(np.abs(np.diff(np.nan_to_num(yaw))))
            cum = np.nancumsum(pitch)
            phase = 2 * np.pi * (cum % LATTICE) / LATTICE
            n = len(phase)
            r = abs(np.exp(1j * phase).mean())
            ctrl = np.random.default_rng(0).uniform(0.8, 2.2, 200)
            rc = np.array([abs(np.exp(2j * np.pi * (cum % q) / q).mean()) for q in ctrl])
            rec["pitch_lattice"] = {"rayleigh_R": round(float(r), 3), "naive_p": float(np.exp(-n * r * r)),
                                    "percentile_among_200_random_periods": round(float(100 * (rc < r).mean())),
                                    "pitch_span_deg": round(float(np.nanmax(cum) - np.nanmin(cum)), 2)}
        else:
            dx = np.array(w["mouse_dx"][:len(yaw)])
            y = np.nan_to_num(yaw)
            lag = max(range(0, 13), key=lambda k: np.corrcoef(dx[:len(dx) - k], y[k:])[0, 1]
                      if dx[:len(dx) - k].std() and y[k:].std() else -1)
            rec.update(mouse_lag_frames=lag, mouse_corr=round(float(np.corrcoef(dx[:len(dx) - lag], y[lag:])[0, 1]), 3))
            # the per-pair rule against truth, at the fitted lag: moved = >= 20 counts (x and y), still = 0 counts
            dy = np.array(w["mouse_dy"][:len(yaw)])
            mag = np.hypot(dx, dy)[:len(dx) - lag]
            moved, still = mag >= 20, mag == 0
            flow = arr(rows, "flow")[lag:]
            zero = flow <= cm.ZERO_FLOW_PX
            reasons = [r["abstain"] for r in rows][lag:]
            rep = np.isfinite(yaw)[lag:]
            def why(mask):
                got = {}
                for m, r in zip(mask, reasons):
                    if m and r:
                        got[r] = got.get(r, 0) + 1
                return got
            # B3 validation: centre-sourced yaw against the mouse-derived yaw (window gain fitted on main-source
            # moving pairs; an estimator-side gain, not the 360 take)
            src = np.array([r.get("source") for r in rows])[lag:]
            main_mov = (src == "main") & np.isfinite(yaw[lag:]) & (np.abs(dx[:len(dx) - lag]) >= 20)
            cen = (src == "centre") & np.isfinite(yaw[lag:])
            b3 = {"centre_pairs": int(cen.sum())}
            if main_mov.sum() >= 20 and cen.sum():
                gain = float(np.polyfit(dx[:len(dx) - lag][main_mov], yaw[lag:][main_mov], 1)[0])
                pred = gain * dx[:len(dx) - lag][cen]
                got = yaw[lag:][cen]
                b3.update(gain_deg_per_count=round(gain, 5),
                          median_abs_err_deg=round(float(np.median(np.abs(got - pred))), 3),
                          sign_agree=round(float(np.mean(np.sign(got) == np.sign(pred))), 3),
                          median_abs_pred_deg=round(float(np.median(np.abs(pred))), 3),
                          corr=round(float(np.corrcoef(got, pred)[0, 1]), 3) if cen.sum() > 2 else None)
            rec["b3_on_live"] = b3
            rec["rule_on_live"] = {
                "moved_pairs": int(moved.sum()), "moved_zero_flow": int((moved & zero).sum()),
                "moved_zero_flow_withheld": int((moved & zero & ~rep).sum()),
                "still_pairs": int(still.sum()), "still_reported": int((still & rep).sum()),
                "still_withheld": int((still & ~rep).sum()), "still_withheld_reasons": why(still & ~rep),
                "still_zero_flow_kept": int((still & zero & rep).sum())}
    out["windows"][name] = rec


def pairs(prefix):
    got = []
    for p in sorted(HERE.glob(f"corr2_{prefix}_*.npz")):
        z = np.load(p)
        for k in sorted({n.rsplit("_", 1)[0] for n in z.files}, key=int):
            got.append((z[f"{k}_a"], z[f"{k}_b"]))
    return got


live, rep = pairs("live"), pairs("replay")
out["m2"] = {"live_pairs": len(live), "replay_pairs": len(rep)}
if live:
    out["m2"].update(cm.replay_focal(live, rep, (720, 1280)))
(HERE / "m1m2-2.json").write_text(json.dumps(out, indent=1, default=float))
print(json.dumps(out, indent=1, default=float))
