"""Pre-registered NitroGen no-history confirmation; stdlib-only judging and chance floor."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

from . import metrics, vocab

SEEDS = (1, 2, 3)
CONDITIONS = tuple(f"{t}/{d}" for t in ("fixed_0.5", "train_chosen")
                   for d in ("median", "mode", "expectation"))
PRIMARY = "train_chosen/median"
SECONDARY = "fixed_0.5/median"
ZERO = 1.2246451263967797
INCUMBENT_F = .10174581457659797
VISION_SHA = "2fceee7b828e737e459b39aa5d11e01362ce38210033f6f885b9974d7a0d6e79"
INPUT_SHA = "aec08c08e247e3743ddeb1eec49dd880e1c0f62039c375932cab31dfccb91e22d"
RANDOM_DRAWS = 256
RANDOM_SEED = 20260927
CONFIG = {"channels": [16, 32, 32], "reduce": 8, "embed": 256, "hud_embed": 128,
          "history_embed": 64, "hidden": 512, "global_hw": [144, 256], "crop_hw": [128, 128],
          "hud_hw": [80, 200], "frames": True, "hud": False, "regime_bit": False}
FRAMES = {"20260923T051828-422Z-33696-1": 12550, "20260923T200129-346Z-33696-6": 47910,
          "20260924T232304-170Z-12024-1": 15777, "20260925T021320-371Z-7804-1": 62126,
          "20260925T025230-605Z-7804-2": 6594, "20260925T203745-207Z-49728-2": 82756,
          "20260926T035932-508Z-63684-14": 54270, "20260926T045729-166Z-79780-1": 18465,
          "20260923T171533-187Z-33696-5": 4630, "20260923T205528-900Z-45572-3": 19926}


def require(value, message):
    if not value:
        raise ValueError(message)


def source_sha(path):
    """Source pins use canonical LF bytes; artifact pins use unmodified bytes."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def random_press_floor(runs, live_mask, *, draws=RANDOM_DRAWS, seed=RANDOM_SEED):
    """Randomize press positions, preserving counts for every action in every run.

    Only valid, press-known positions are eligible. Runs never share a matching
    window. This is an event-prediction chance floor, not an executable pad policy.
    """
    require(draws > 0, "positive random draw count required")
    blocks = {name: [] for name in vocab.EDGE_ACTIONS}
    valid = human_live = human_edge = any_press = observable = 0
    for run in runs:
        for rec, _ in run:
            if not rec["valid"]:
                continue
            valid += 1
            target = rec["target"]
            known = target.get("press_known", target["known"])
            live = [i for i, enabled in enumerate(live_mask) if enabled]
            human_live += sum(bool(target["press"][i]) for i in live if known[i])
            if all(known[i] for i in live):
                observable += 1
                any_press += any(target["press"][i] for i in live)
        for name in vocab.EDGE_ACTIONS:
            c = vocab.INDEX[name]
            eligible, truth, count = [], [], 0
            for pos, (rec, pred) in enumerate(run):
                if not rec["valid"]:
                    continue
                target = rec["target"]
                if target.get("press_known", target["known"])[c]:
                    eligible.append(pos)
                    if target["press"][c]:
                        truth.append(pos)
                    count += pred["press"][c] >= metrics.THRESHOLD
            blocks[name].append((eligible, truth, count))
            human_edge += len(truth)
    require(valid > 0, "nonempty eligible evaluation required")
    scores = []
    for draw in range(draws):
        rng = random.Random(seed + draw)
        actions = []
        for name in vocab.EDGE_ACTIONS:
            tp = predicted = actual = 0
            for eligible, truth, count in blocks[name]:
                positions = sorted(rng.sample(eligible, count))
                tp += metrics.match_window(truth, positions, early=1, late=1)
                predicted += count
                actual += len(truth)
            actions.append(metrics.f1(tp, predicted - tp, actual - tp) or 0.)
        scores.append(statistics.mean(actions))
    ordered = sorted(scores)
    return {"method": "uniform without replacement per action and eligible run; exact predicted count",
            "draws": draws, "seed": seed, "window": {"early": 1, "late": 1},
            "actions": list(vocab.EDGE_ACTIONS), "macro_f1_mean": statistics.mean(scores),
            "macro_f1_p05": ordered[math.floor(.05 * (draws - 1))],
            "macro_f1_p95": ordered[math.ceil(.95 * (draws - 1))],
            "valid_steps": valid, "human_live_presses": human_live,
            "human_edge_presses": human_edge, "human_live_events_per_frame": human_live / valid,
            "human_edge_events_per_frame": human_edge / valid,
            "human_any_press_observable_frames": observable, "human_any_press_frames": any_press,
            "human_any_press_frame_rate": any_press / observable if observable else None,
            "matched_predicted_counts": {n: [count for _, _, count in b] for n, b in blocks.items()}}


def validate_run(ev, arm, seed):
    require(arm in ("candidate", "control") and seed in SEEDS, "unknown arm or confirmation seed")
    recipe = ev["recipe"]
    require(ev["tag"] == recipe["tag"] == "CONFIRM", "confirmation track required")
    require(recipe["seed"] == seed and ev["epoch"] == 26, "wrong seed or endpoint")
    for key, value in {"horizon": 1, "epochs": 26, "batch": 8, "lr": .0003,
                       "weight_decay": .0001, "warmup": 500, "device": "cuda", "prev_dropout": .2,
                       "lag": 0, "cohort": "full", "windows": 4697, "total_steps": 15288}.items():
        require(recipe[key] == value, f"recipe differs: {key}")
    require(recipe["run_identity"].startswith(INPUT_SHA), "input manifest differs")
    config = recipe["config"]
    require(config["history"] is (arm == "control") and config["frames"] and not config["hud"],
            "wrong history or visual input mode")
    require({k: v for k, v in config.items() if k != "history"} == CONFIG, "architecture differs")
    require(recipe["pos_weight"] == [[20.] * vocab.N] * 2, "loss weights differ")
    extra = recipe["encoder_explore"]
    prereg = extra["prereg_sha256"]
    require(len(prereg) == 64 and all(c in "0123456789abcdef" for c in prereg), "invalid prereg pin")
    require(extra["history_input"] == ("enabled" if arm == "control" else "disabled"), "history receipt differs")
    require(extra["arm"] == "nitrogen" and extra["assets"]["vision_sha256"] == VISION_SHA,
            "wrong frozen encoder")
    require({k: v["frames"] for k, v in extra["extraction"].items()} == FRAMES, "cohort frames differ")
    require(ev["threshold_calibration"]["source"] == "TRAIN teacher-forced predictions only",
            "calibration source differs")
    require(set(ev["decode"]) == set(CONDITIONS) and not ev.get("skipped_decodes")
            and not ev.get("stop_reason"), "incomplete/stopped evaluation; no confirm verdict")
    refs = ev["references"]["frozen_dev"]
    require(abs(refs["zero_motion"]["camera_mae_mean"] - ZERO) < 1e-12, "zero baseline differs")
    require(refs["zero_motion"]["camera"]["yaw"]["steps"] == 24556, "frozen-dev denominator differs")
    for name in CONDITIONS:
        value = ev["decode"][name]
        require(math.isfinite(value["F"]) and 0 <= value["F"] <= 1, "invalid F1")
        require(math.isfinite(value["S3_camera_mae"]) and value["S3_camera_mae"] >= 0, "invalid MAE")
        checks = value["S1_S2_S4"]
        require(checks["steps"] == 24556 and checks["true_presses"] == 2458, "press denominator differs")
        require(math.isfinite(checks["press_ratio"]) and checks["press_ratio"] >= 0, "invalid press ratio")
    for name in (PRIMARY, SECONDARY):
        floor = ev["decode"][name]["chance_floor"]
        require(floor["draws"] == RANDOM_DRAWS and floor["seed"] == RANDOM_SEED,
                "chance floor recipe differs")
        require(floor["human_live_presses"] == 2458 and floor["human_edge_presses"] == 1437,
                "chance floor population differs")
        require(floor["valid_steps"] == 24556 and floor["window"] == {"early": 1, "late": 1}
                and floor["actions"] == list(vocab.EDGE_ACTIONS), "chance floor metric differs")
        require(math.isfinite(floor["macro_f1_mean"]) and 0 <= floor["macro_f1_mean"] <= 1,
                "invalid chance floor")
    return {k: v for k, v in config.items() if k != "history"}


def judge(rows):
    """All six runs are mandatory. No seed/threshold/epoch is chosen from results."""
    indexed, configs, identities = {}, [], []
    for arm, seed, ev in rows:
        require((arm, seed) not in indexed, "duplicate arm/seed")
        configs.append(validate_run(ev, arm, seed))
        r = ev["recipe"]
        x = r["encoder_explore"]
        identities.append((x["prereg_sha256"], r["pos_weight"], x["assets"],
                           {k: v["frames"] for k, v in x["extraction"].items()}))
        indexed[arm, seed] = ev
    require(set(indexed) == {(a, s) for a in ("candidate", "control") for s in SEEDS},
            "need exactly candidate/control seeds 1, 2, 3")
    require(all(c == configs[0] for c in configs) and all(i == identities[0] for i in identities),
            "paired architecture, assets, cohort or loss weights differ")
    values = {}
    for arm in ("candidate", "control"):
        values[arm] = [{"seed": seed,
                        "press_f1": indexed[arm, seed]["decode"][PRIMARY]["F"],
                        "camera_mae": indexed[arm, seed]["decode"][PRIMARY]["S3_camera_mae"],
                        "press_ratio": indexed[arm, seed]["decode"][PRIMARY]["S1_S2_S4"]["press_ratio"],
                        "chance_f1": indexed[arm, seed]["decode"][PRIMARY]["chance_floor"]["macro_f1_mean"],
                        "fixed_f1": indexed[arm, seed]["decode"][SECONDARY]["F"],
                        "fixed_press_ratio": indexed[arm, seed]["decode"][SECONDARY]["S1_S2_S4"]["press_ratio"],
                        "fixed_chance_f1": indexed[arm, seed]["decode"][SECONDARY]["chance_floor"]["macro_f1_mean"]}
                       for seed in SEEDS]
    candidate, control = values["candidate"], values["control"]
    means = {a: {k: statistics.mean(r[k] for r in rows) for k in rows[0] if k != "seed"}
             for a, rows in values.items()}
    press = (means["candidate"]["press_f1"] > max(means["control"]["press_f1"], INCUMBENT_F)
             and all(c["press_f1"] > h["press_f1"] for c, h in zip(candidate, control)))
    camera = (means["candidate"]["camera_mae"] < min(means["control"]["camera_mae"], ZERO)
              and all(c["camera_mae"] < min(h["camera_mae"], ZERO) for c, h in zip(candidate, control)))
    return {"tag": "CONFIRM", "decision": "CONFIRMED" if press and camera else "NOT_CONFIRMED",
            "press_primary_pass": press, "camera_primary_pass": camera,
            "primary_condition": PRIMARY, "zero_motion_mae": ZERO,
            "incumbent_h1_f1_context": INCUMBENT_F, "per_seed": values, "means": means,
            "human_live_press_events_per_frame": 2458 / 24556,
            "human_edge_press_events_per_frame": 1437 / 24556,
            "scope": "offline frozen-dev confirmation only; no live deployment clearance"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    spec = json.loads(args.runs.read_text())
    require(spec["judge_sha256"] == source_sha(__file__), "judge pin mismatch")
    for module in (metrics, vocab):
        require(spec["dependency_sha256"][module.__name__] == source_sha(module.__file__),
                "judge dependency pin mismatch")
    require(source_sha(spec["preregistration"]) == spec["prereg_sha256"], "prereg pin mismatch")
    rows = []
    for item in spec["runs"]:
        raw = Path(item["evaluation"]).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == item["evaluation_sha256"], "evaluation hash mismatch")
        final_raw = Path(item["final"]).read_bytes()
        require(hashlib.sha256(final_raw).hexdigest() == item["final_sha256"], "final receipt hash mismatch")
        final = json.loads(final_raw)
        require(final["exit"] == 0 and final["teardown"]["terminal"], "run not successful and terminal")
        require(final["collection"]["evaluation.json"]["sha256"] == item["evaluation_sha256"],
                "collector did not authenticate evaluation")
        ev = json.loads(raw)
        require(ev["recipe"]["encoder_explore"]["prereg_sha256"] == spec["prereg_sha256"],
                "result prereg pin mismatch")
        rows.append((item["arm"], item["seed"], ev))
    result = judge(rows)
    result["source_manifest"] = spec
    with args.out.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write("\n")


if __name__ == "__main__":
    main()
