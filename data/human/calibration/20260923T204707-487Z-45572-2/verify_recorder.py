import json, subprocess, sys, hashlib, csv
from pathlib import Path
sys.path.insert(0, "C:/Users/volpe/obs-input-logger")
import check_session
BELOW = subprocess.BELOW_NORMAL_PRIORITY_CLASS
S = Path("C:/Users/volpe/Videos/RivalsInput/20260923T204707-487Z-45572-2")
V = "C:/Users/volpe/Videos/2026-09-23 15-47-07.mkv"
real = check_session.subprocess.run
def limited(cmd, **kw):
    cmd = [cmd[0], "-threads", "4", *cmd[1:]]; kw.setdefault("creationflags", BELOW); return real(cmd, **kw)
check_session.subprocess.run = limited
rep = check_session.check(S, verify_video=True)
run = lambda c: subprocess.run(c, capture_output=True, text=True, check=True, creationflags=BELOW).stdout
pk = run(["ffprobe","-v","error","-show_entries","packet=stream_index,pts_time,dts_time,flags","-read_intervals","%+#24","-of","csv=p=0",V]).split()
streams = json.loads(run(["ffprobe","-v","error","-show_entries","stream=index,codec_name,profile,time_base,avg_frame_rate,has_b_frames,sample_rate,bit_rate:format=bit_rate,duration,size:format_tags=encoder","-of","json",V]))
rows = list(csv.DictReader(open(S/"frames.csv")))
pred = [round(int(r["pts"])*1000/120)+21 for r in rows[:16]]
meta = json.loads((S/"metadata.json").read_text())
print(json.dumps(dict(report={k: rep.get(k) for k in ("integrity_ok","errors","warnings","decoded_video_frames","matched_video_frames","unwritten_muxer_tail_packets","muxer_pts_offset_seconds","max_video_pts_residual_seconds","composition_duration_seconds","counts")},
    first_packets=pk, callback_pred_first16_video_ms=pred, callback_pts_first16=[int(r["pts"]) for r in rows[:16]], callback_dts_first16=[int(r["dts"]) for r in rows[:16]],
    streams=streams, media_sha256=hashlib.sha256(open(V,"rb").read()).hexdigest(), meta={k: meta[k] for k in ("obs_version","video_packets","input_events","status","clean_stop","queue_dropped_events","raw_input_errors")}), indent=1))
