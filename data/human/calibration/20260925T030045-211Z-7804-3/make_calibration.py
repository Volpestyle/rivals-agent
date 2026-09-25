"""Write data/human/calibration/20260925T030045-211Z-7804-3/calibration.json from the folder's own outputs.

Every number comes from analysis.json, pitch-runs.json, strokes json and recorder-and-anchor.json in that folder.
"""
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path("C:/Users/volpe/repos/rivals-agent")
SID = "20260925T030045-211Z-7804-3"
D = ROOT / "data/human/calibration" / SID
PRIOR = ROOT / "data/human/calibration/20260923T204707-487Z-45572-2/calibration.json"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


a = json.loads((D / "analysis.json").read_text(encoding="utf-8"))
pr = json.loads((D / "pitch-runs.json").read_text(encoding="utf-8"))
st = json.loads((D / f"strokes-{SID}.json").read_text(encoding="utf-8"))
rec = json.loads((D / "recorder-and-anchor.json").read_text(encoding="utf-8"))
prior = json.loads(PRIOR.read_text(encoding="utf-8"))
prior_counts = prior["yaw"]["counts_per_360"]
turns = a["turns"]
cp = [t["counts_per_360"] for t in turns]
gains = [t["deg_per_count"] for t in turns]
strokes = {i: s for i, s in enumerate(st["yaw"])}
per_class = []
for i, t in enumerate(turns):
    s = strokes[i]
    per_class.append(dict(
        speed_class=t["speed_class"], stroke_logger_s=[s["start_s"], s["end_s"]], moving_s=s["moving_s"],
        mean_counts_per_s=s["mean_counts_per_s"], median_bin_counts_per_s=s["median_bin_counts_per_s"],
        peak_counts_per_s_100ms=s["peak_counts_per_s_100ms"],
        still_frames_logger_s=[t["pre_s"], t["post_s"]], dx_counts_between_still_frames=t["dx_counts"],
        dy_counts_between_still_frames=t["dy_counts"], excess_yaw_deg=round(t["yaw_deg"], 4),
        excess_pitch_deg=round(t["pitch_deg"], 4), still_pair_inliers=t["inliers"], turn_deg=round(t["turn_deg"], 4),
        counts_per_360=round(t["counts_per_360"], 2), yaw_deg_per_count=round(t["deg_per_count"], 8)))
free_ratio = a["pitch"]["free_sum_ratio_deg_per_count"]
long_runs = [r for r in pr["runs"] if abs(r["dy_counts"]) >= 3000]
doc = dict(
    format="rivals-calibration-v1", session=SID,
    media={"path": "C:/Users/volpe/Videos/2026-09-24 22-00-45.mkv", "sha256": rec["media_sha256"]}, codec="hevc",
    recorder=rec["report"], anchor_applies=rec["callback_pred_first16_video_ms"][:11] == [21, 46, 29, 38, 71, 54, 63, 96, 79, 88, 121],
    game_build="1.1.3892207/build25501035 (kit-equivalent to 1.1.3870120/build25364676, data/human/patch-equivalence.json)",
    settings=dict(source="unchanged since the 2026-09-23 settings look (James, relayed by the lead 2026-09-24): DPI 800, "
                         "sensitivity 1.89/1.89, mouse acceleration on at factor 1.00, smoothing on",
                  settings_look=f"{PRIOR.relative_to(ROOT).as_posix()} ({sha(PRIOR)[:16]})"),
    take=dict(description="four rightward yaw turns at rising speed, each ended on a still view, then 12 pitch sweeps; "
                          "James: 'turns not exact'", strokes=f"strokes-{SID}.json (inputs.jsonl alone)"),
    yaw=dict(
        method="per turn: the camera rotation between the still frame before the turn and the still frame after it "
               "(the snapshot Estimator's rotation fit on the two frames' ORB features) is the turn's excess over "
               "one revolution; degrees = 360 + excess; gain = degrees / the mouse x counts between the two still "
               "frames. Still frames on both ends: display latency does not enter.",
        per_speed_class=per_class,
        controls=[dict(still_frames_logger_s=[c["pre_s"], c["post_s"]], yaw_deg=round(c["yaw_deg"], 5),
                       pitch_deg=round(c["pitch_deg"], 5), inliers=c["inliers"], dx_counts=c["dx_counts"])
                  for c in a["controls"]],
        counts_per_360=dict(mean=round(statistics.mean(cp), 2), sd=round(statistics.stdev(cp), 2),
                            min=round(min(cp), 2), max=round(max(cp), 2),
                            range_pct=round(100 * (max(cp) - min(cp)) / statistics.mean(cp), 3)),
        yaw_deg_per_count=dict(mean=round(statistics.mean(gains), 8), sd=round(statistics.stdev(gains), 8)),
        vs_2026_09_23=dict(counts_per_360=prior_counts, yaw_deg_per_count=prior["yaw"]["yaw_deg_per_count"],
                           mean_difference_pct=round(100 * (statistics.mean(cp) - prior_counts) / prior_counts, 3)),
        result="speed-independent: four speed classes from 1.8k to 12.1k counts/s mean (peaks to 27k) give "
               f"{min(cp):.1f}-{max(cp):.1f} counts per 360 degrees, a {100 * (max(cp) - min(cp)) / statistics.mean(cp):.2f} % "
               "range with no trend in speed, and a mean within "
               f"{abs(100 * (statistics.mean(cp) - prior_counts) / prior_counts):.2f} % of the 2026-09-23 slow closure; "
               "mouse acceleration (on, factor 1.00) has no measurable effect",
        uncertainty=dict(
            excess="controls between adjacent still frames read at most 0.009 deg; the excess scales with the "
                   "estimator's focal, whose error for this footage is about 3 % (below), so +-0.03-0.11 deg on "
                   "excesses of 1.2-3.6 deg",
            slow_turn="its still pair differs by 8.3 deg of pitch (197 y counts) and fits on 116 inliers; its "
                      "excess is the least certain (+-0.3 deg, 0.08 %)",
            per_class_gain="+-0.02-0.08 %"),
        latency="none: every measurement is still frame to still frame"),
    estimator_scale=dict(
        note="for the inverse-dynamics lane (VUH-1353): the per-pair estimator (focal 465 px at 1280 wide) summed "
             "over each turn against the still-to-still truth",
        per_turn=a["per_turn_estimator_sum"],
        finding="the per-pair yaw sums read 2.4 % (slow), 3.2 % (medium) and 3.7 % (fast) above the true turn, "
                "consistent with a focal about 3 % short for this footage; the fastest turn fits only 226 of 288 "
                "pairs (the fitted sum is 9.8 % below the turn). A focal refit on this take is the IDM lane's call.",
        per_rate_band=a["bands"],
        lag=a["lag"],
        lag_note="the yaw-vs-counts correlation is flat within +-30 ms (0.90-0.93); these data do not pin the lag"),
    pitch=dict(
        pitch_deg_per_count=None, kind="derived_equal_sensitivity (unchanged; lead decision 2026-09-23)",
        why_null="the orbiting third-person camera moves as well as rotates on pitch: still-to-still rotation fails "
                 "across a 64 deg sweep (0 inliers), and the estimator's pitch sign flips near the limits",
        observations=dict(
            free_pair_ratio_deg_per_count=round(free_ratio, 6) if free_ratio else None,
            free_pair_note="per-pair estimator pitch / -dy over moving pairs not at a limit; carries the estimator's "
                           "~3 % scale error, so it is consistent with pitch = yaw, not a measurement",
            limit_to_limit_runs=[dict(start_s=r["start_s"], direction=r["direction"], dy_counts=r["dy_counts"],
                                      mean_counts_per_s=r["mean_counts_per_s"]) for r in long_runs],
            limit_to_limit_note="counts from leaving one pitch limit to reaching the other (by estimator motion): "
                                "3,225-3,601 for nine sweeps from 1.6k to 13.8k counts/s, no speed trend; one 21k "
                                "sweep 3,844 with a confounded start. Below the 2026-09-23 4,624 by definition "
                                "(motion onset at the limits blurs)"),
        conclusion="no evidence that pitch gain depends on speed or differs from yaw; not established by this take"),
    header_calibration=prior["header_calibration"],
    header_note="unchanged: the step header keeps the 2026-09-23 calibration (v2). This take shows its yaw gain holds "
                "from 1.8k to 12.1k counts/s mean; relabelling the gain kind would re-step the admitted tables, so it "
                "is left to the lead",
    applies_to="every session with DPI 800 and sensitivity 1.89/1.89 (all campaign sessions so far)",
    version=1, accel_on=True)
out = D / "calibration.json"
out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
print(out.name, sha(out))
print(doc["yaw"]["counts_per_360"], doc["yaw"]["yaw_deg_per_count"], doc["yaw"]["vs_2026_09_23"]["mean_difference_pct"])
print(doc["yaw"]["result"])
