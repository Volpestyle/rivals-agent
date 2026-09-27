"""Aggregate exactly the six preselected exploratory grid/seed results."""
import argparse
import json
from pathlib import Path
from statistics import mean

from .spatial_yaw_cache import sha, write_new


def summarize(results):
    rows = {(r["spec"]["grid"], r["spec"]["seed"]): r for r in results}
    if len(results) != 6 or set(rows) != {(g, s) for g in (4, 8) for s in (1, 2, 3)}:
        raise ValueError("exactly six distinct matched grid/seed results required")
    if len({r["spec"]["dataset_sha256"] for r in results}) != 1:
        raise ValueError("dataset differs between arms")
    paired = []
    for seed in (1, 2, 3):
        four, eight = rows[4, seed], rows[8, seed]
        for key in ("base_sha256", "cutoff_sha256", "epochs", "updates"):
            if four["spec"][key] != eight["spec"][key]:
                raise ValueError("paired recipe differs")
        if four["base"] != eight["base"]:
            raise ValueError("paired frozen-base evaluation differs")
        for result in (four, eight):
            if not (result["retention"]["exact_action_and_pitch_predictions"]
                    and result["retention"]["exact_pitch_logits"] and result["fit"]["frozen_base_exact"]):
                raise ValueError("frozen path retention failed")
        left, right = four["candidate"]["yaw"], eight["candidate"]["yaw"]
        # Missing directional/still support is unknown, never a successful filter.
        valid = all(left[k]["n"] > 0 and right[k]["n"] == left[k]["n"]
                    for k in ("all", "left", "right", "human_yaw_zero", "both_axes_zero"))
        diff = {k: right[k]["mae_deg"]-left[k]["mae_deg"]
                if right[k]["mae_deg"] is not None and left[k]["mae_deg"] is not None else None
                for k in ("all", "left", "right")}
        false = {k: right[k]["false_turn_ge_point6_rate"]-left[k]["false_turn_ge_point6_rate"]
                 if right[k]["n"] and left[k]["n"] else None
                 for k in ("human_yaw_zero", "both_axes_zero")}
        paired.append({"seed": seed, "eight_minus_four_mae_deg": diff,
                       "eight_minus_four_false_turn_rate": false, "supported": valid})
    averages = {}
    for grid in (4, 8):
        selected = [rows[grid, s] for s in (1, 2, 3)]
        averages[str(grid)] = {
            "yaw_mae_deg": mean(r["candidate"]["yaw"]["all"]["mae_deg"] for r in selected),
            "zero_yaw_mae_deg": mean(r["candidate"]["yaw"]["all"]["zero_motion_mae_deg"] for r in selected),
            "press_f1": mean(r["candidate"]["metrics"]["macro_press_f1_tol"] for r in selected),
            "pitch_mae_deg": mean(r["candidate"]["metrics"]["camera"]["pitch"]["mae_deg"] for r in selected)}
    filters = {
        "all_three_seeds_eight_beats_four": all(p["supported"] and p["eight_minus_four_mae_deg"]["all"] < 0 for p in paired),
        "eight_seed_mean_beats_zero": averages["8"]["yaw_mae_deg"] < averages["8"]["zero_yaw_mae_deg"],
        "neither_direction_mean_worse": all(p["supported"] for p in paired) and all(
            mean(p["eight_minus_four_mae_deg"][k] for p in paired) <= 0 for k in ("left", "right")),
        "no_increase_in_mean_false_point6_turns": all(p["supported"] for p in paired) and all(
            mean(p["eight_minus_four_false_turn_rate"][k] for p in paired) <= 0
            for k in ("human_yaw_zero", "both_axes_zero")),
        "exact_action_pitch_retention": True}
    return {"tag": "EXPLORATORY", "paired": paired, "seed_means": averages, "advance_filters": filters,
            "next": "propose fresh-seed confirm" if all(filters.values()) else "report; no new arm authorized",
            "results": results}


def markdown(report):
    lines = ["# EXPLORATORY spatial yaw: 4×4 versus 8×8", "",
             "Offline predictions on the same frozen-dev pixels. Frozen candidate seeds 1/2/3; 26 epochs. "
             "Median camera decode; original CUDA TRAIN press cutoffs. No live-play claim.", "",
             "| Grid | Seed | Yaw MAE | Zero | Left MAE | Right MAE | Still false ≥0.6° | Both axes still false ≥0.6° | Press F1 | Pitch MAE |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    def fmt(value):
        return "unknown" if value is None else f"{value:.6f}"
    for r in sorted(report["results"], key=lambda r: (r["spec"]["grid"], r["spec"]["seed"])):
        y, m = r["candidate"]["yaw"], r["candidate"]["metrics"]
        values = [y["all"]["mae_deg"], y["all"]["zero_motion_mae_deg"], y["left"]["mae_deg"], y["right"]["mae_deg"],
                  y["human_yaw_zero"]["false_turn_ge_point6_rate"], y["both_axes_zero"]["false_turn_ge_point6_rate"],
                  m["macro_press_f1_tol"], m["camera"]["pitch"]["mae_deg"]]
        lines.append(f"| {r['spec']['grid']} | {r['spec']['seed']} | " + " | ".join(map(fmt, values)) + " |")
    lines += ["", "All action channels (including movement) and pitch predictions are exactly retained; "
              "frozen base tensors and pitch logits are checked. Full JSON includes slice counts, missed/opposite turns, "
              "false-left/right rates, per-action press rates and F1, and frozen-base comparisons.", "",
              "Paired differences below are 8×8 minus 4×4 (negative MAE favors 8×8):", ""]
    for p in report["paired"]:
        lines.append(f"- Seed {p['seed']}: {p['eight_minus_four_mae_deg']}; false-turn changes {p['eight_minus_four_false_turn_rate']}.")
    if all("candidate_fixed05" in r for r in report["results"]):
        lines += ["", "| Grid | Seed | TRAIN-cutoff human events/frame | TRAIN rate ratio | Fixed-0.5 F1 | Fixed-0.5 rate ratio | Real yaw NLL | Zero-spatial yaw NLL |",
                  "|---|---|---|---|---|---|---|---|"]
        for r in report["results"]:
            nll = r["spatial_token_ablation"]["yaw_nll"]
            values = [r["candidate"]["press_rates"]["human_events_per_frame"],
                      r["candidate"]["press_rates"]["predicted_human_ratio"],
                      r["candidate_fixed05"]["metrics"]["macro_press_f1_tol"],
                      r["candidate_fixed05"]["press_rates"]["predicted_human_ratio"],
                      nll["real"]["nll"], nll["zero_spatial"]["nll"]]
            lines.append(f"| {r['spec']['grid']} | {r['spec']['seed']} | " + " | ".join(map(fmt, values)) + " |")
        lines += ["", "Zero-spatial NLL is an out-of-distribution inference ablation: the original 4×4 base and recurrent "
                  "memory still see real features. It is not a trained zero-token control."]
    lines += ["", "Historical confirmation reference (MPS evaluation, original CUDA TRAIN cutoffs): candidate random-presser "
              "F1 means for seeds 1/2/3 were 0.027338 / 0.027393 / 0.027929. Human live-action base rate was "
              "0.10009774 events/frame. These are retained reference numbers, not a recomputed chance floor for these "
              "new caches/CUDA evaluations. See docs/evidence/nitrogen-nohistory-confirm-20260927/confirmation-report.md "
              "(SHA-256 a2979dee7901c97f25748e631d5196630d3a56a4685cfbc8179b467471b79b76). "
              "Incumbent H1 press F1 reference: 0.101745815."]
    lines += ["", f"Next: **{report['next']}**.", "", "Pre-stated advancement filters:", ""]
    lines.extend(f"- {k}: {v}" for k, v in report["advance_filters"].items())
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evaluations", nargs=6, required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = summarize([json.loads(p.read_text()) for p in args.evaluations])
    result["source_files"] = [{"path": str(p), "sha256": sha(p)} for p in args.evaluations]
    args.out.mkdir(parents=True, exist_ok=False)
    write_new(args.out / "report.json", result)
    with (args.out / "report.md").open("x", encoding="utf-8") as stream:
        stream.write(markdown(result))


if __name__ == "__main__":
    main()
