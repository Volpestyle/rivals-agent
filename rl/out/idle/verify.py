"""CPU-only checks on the saved replay and named admitted label tables."""
from pathlib import Path
import json
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main():
    import numpy as np
    import torch
    torch.set_num_threads(2)
    from policy.bc2.train import decode
    from policy.live_policy import LivePolicy
    from policy.range_bc import steps, vocab
    from rl.out.idle.diagnose import log_stats
    out = ROOT / "rl/out/idle"
    r = json.loads((out / "results.json").read_text())
    bundle = json.loads(Path("D:/rivals-policy/bundles/bc2-mix399-s0/bundle.json").read_text())
    levels = [bundle["thresholds"][n] for n in vocab.NAMES]
    mask = [bundle["live"][n] for n in vocab.NAMES]
    checks = {}
    # Real LivePolicy.step decode, substituting saved raw predictions. This object
    # does not load a model, tower, capture, pad, or GPU.
    with np.load(out / "comparison.npz") as z:
        for name in ("live_A", "James_10Hz", "BC07_ep000"):
            a, c = z[name + "_actions"], z[name + "_cameras"]
            policy = object.__new__(LivePolicy)
            policy.predict, policy.graph, policy.kind = None, None, "bc2"
            policy.names, policy.levels, policy.mask = vocab.NAMES, levels, mask
            policy.camera_decode = "mean"
            policy.reset()
            live_h, live_p, yaw = [], [], []
            for acts, cams in zip(a, c):
                policy._bc2_predict = lambda frame, t=None: (acts.tolist(), cams.tolist())
                step = policy.step(np.zeros((1, 1, 3), np.uint8))
                live_h.append([step.held[n] for n in vocab.NAMES])
                live_p.append([step.press[n] for n in vocab.NAMES])
                yaw.append(step.yaw_deg)
            starts = np.zeros(len(a), bool)
            starts[0] = True
            offline_h, offline_p = decode(torch.from_numpy(a), SimpleNamespace(t={"run_start": starts}), levels, mask)
            mismatch = int((np.array(live_h) != offline_h.numpy()).sum() +
                           (np.array(live_p) != offline_p.numpy()).sum())
            assert mismatch == 0, (name, mismatch)
            expected_yaw = (c[:, 0] * np.array([vocab.class_degrees(k) for k in range(vocab.CAMERA_CLASSES)])).sum(-1)
            assert np.max(abs(expected_yaw - yaw)) < 1e-12
            for kind in ("single_step", "graph"):
                for head in ("action", "camera"):
                    key = f"{kind}_{head}_max_abs_difference"
                    if key in r["parity"][name]:
                        assert r["parity"][name][key] == 0
            checks[name] = {"hold_press_decode_bit_mismatches": mismatch, "mean_camera_decode_max_difference":
                            float(np.max(abs(expected_yaw - yaw)))}
    for record in r["human_activity"]:
        sid = record["session"]
        session = steps.load(ROOT / f"data/human/sessions/{sid}/{sid}.steps.jsonl", denylist=steps.load_denylist())
        base = Path("D:/rivals-policy/dev-features" if session.split == "train" else "D:/rivals-policy/local-features") / sid
        meta = json.loads((base / "meta.json").read_text())
        assert meta["steps_sha256"] == session.sha256, sid
        with np.load(base / "targets.npz") as z:
            t = {k: z[k] for k in z.files}
        ok = t["valid"] & t["cam_known"].all(-1) & t["act_known"][:, :2].all((1, 2))
        exact = (t["yaw"] == 0) & (t["pitch"] == 0) & ~t["act"][:, :2].any((1, 2)) & ok
        longest = current = 0
        for bit, boundary in zip(exact, t["run_start"]):
            current = (1 if boundary else current + 1) if bit else 0
            longest = max(longest, current)
        record["exact_neutral_share"] = float(exact[ok].mean())
        record["longest_exact_neutral_steps"] = longest
        record["step_table_identity_verified"] = True
    # Refresh CPU log summaries after the timing-field addition; does not rerun inference.
    r["logs"] = [log_stats(ROOT / log["source"])[0] for log in r["logs"]]
    (out / "logs.json").write_text(json.dumps(r["logs"], indent=2) + "\n")
    (out / "results.json").write_text(json.dumps(r, indent=2) + "\n")
    (out / "checks.json").write_text(json.dumps(checks, indent=2) + "\n")
    print(json.dumps({"checks": checks, "human_exact_neutral": [{"session": h["session"],
        "share": h["exact_neutral_share"], "longest_steps": h["longest_exact_neutral_steps"]}
        for h in r["human_activity"]]}, indent=2))


if __name__ == "__main__":
    main()
