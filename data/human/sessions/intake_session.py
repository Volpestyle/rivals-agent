"""Whole-session intake of one logged session, step by step (VUH-1359). Offline; never sends game input.

    python intake_session.py STEP SESSION_ID --scratch DIR [--snapshot code-snapshot-XXXXXXX]

Steps, in order (each writes into ./<SESSION_ID>/ and refuses to overwrite its own output):
  provenance  media sha256, recorder metadata, first-16-packet anchor applicability, OBS log recording block,
              Steam build evidence, saved-settings receipt, ffprobe/ffmpeg versions      -> provenance.json
  verify      obs-input-logger check_session (ffprobe 4 threads, below normal)           -> recorder-verification.json
  profile     devices (R6), focus, UI keys, AFK gaps, raw-input gaps                       -> input-profile.json
  vote        the source's own HUD slot mapping from its first 60 s (reused scan, unchanged)  -> slot-mapping.json
  scan        reused regime scan over the whole original at 5 fps                          -> hud-scan-samples.jsonl
  regime      5 s regime timeline from the scan                                          -> regime-timeline.json
  motor       motor settings and binding table with per-session sources (review R2, fit R7)  -> motor-settings.json
  propose     candidate segments (first pass) with the native-frame brackets to decode      -> candidates-pass1.json
  evidence    decode each bracket, refine edges on native frames, re-propose; decode and hash the review frames
              for every segment (both edges plus stratified interior frames)             -> segments-evidence.json

Code runs from the archived snapshot (agent.human_intake, agent.human_demos, perception.hud, the reused
scan.py), never the live worktree. Decodes are CPU, four threads, below-normal priority. The sealed denylist
is checked before the registry or any session file is read.
"""
import argparse
import csv
import ctypes
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


class Refused(RuntimeError):
    pass


def need(condition, message):
    """An explicit guard that survives `python -O` (review I3); asserts are not used for refusals here."""
    if not condition:
        raise Refused(message)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RAW = Path("C:/Users/volpe/Videos/RivalsInput")
DENYLIST = ROOT / "data/human/sealed-denylist.json"
DENYLIST_SHA256 = "57cfe01f29f6e1a55293f968ec697aa293c268bd87d7cf247ef648279e2fba7c"   # pinned (review I3)
REGISTRY = ROOT / "data/human/session-splits.corpus.json"
SCAN_REL = "data/human/inspection/20260922T033319-205Z-24328-2/regime-scan/scan.py"
OBS_LOGS = Path("C:/Users/volpe/AppData/Roaming/obs-studio/logs")
STEAM = Path("C:/Program Files (x86)/Steam")
SETTINGS = Path("C:/Users/volpe/AppData/Local/Marvel/Saved/Saved/Config/1295996384/MarvelUserSetting.json")
SETTINGS_0922 = ROOT / "data/human/inspection/20260922T033319-205Z-24328-2/local-provenance.json"
CHECKER = "C:/Users/volpe/obs-input-logger"
BELOW = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
W, H = 2560, 1440
ANCHOR_VIDEO_MS = [21, 46, 29, 38, 71, 54, 63, 96, 79, 88, 121]
ANCHOR_AUDIO_MS = [0, 21, 42, 64, 85]
REVIEW_INTERIOR_EVERY_NS = 10_000_000_000   # one interior review frame per 10 s of segment, at least one
REVIEW_THUMB = (1280, 720)


def below_normal():
    if sys.platform == "win32":
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def write_once(path, doc):
    need(not path.exists(), f"{path.name} already written")
    path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(path.name, sha(path))


class Ctx:
    def __init__(self, args):
        self.sid = args.session
        self.snapshot = HERE / args.snapshot
        self.earlier_snapshot = getattr(args, "earlier_snapshot", None)
        sys.path.insert(0, str(self.snapshot))
        from agent import human_intake as hi
        from agent import human_demos as hd
        self.hi, self.hd = hi, hd
        self.denylist = hi.load_denylist(DENYLIST, sha256_pin=DENYLIST_SHA256)
        registry = hi.check_registry(REGISTRY, denylist=self.denylist)   # denylist first, then registry
        need(self.sid in registry, "session not registered")
        self.place = registry[self.sid]
        need(self.place.split != "test", "sealed sessions are never taken in")
        self.raw = RAW / self.sid
        self.meta = json.loads((self.raw / "metadata.json").read_text())
        self.video = self.meta["video_path"]
        self.out = HERE / self.sid
        self.out.mkdir(exist_ok=True)
        self.scratch = Path(args.scratch) / self.sid
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.media_sha = self.place.expected_media_sha256
        hi.assert_not_sealed(self.sid, self.media_sha, self.denylist)

    def events(self):
        return [json.loads(line) for line in (self.raw / "inputs.jsonl").read_text().splitlines()]

    def packets(self):
        with open(self.raw / "frames.csv", newline="") as f:
            return [{k: int(v) for k, v in r.items()} for r in csv.DictReader(f)]

    def scan_module(self):
        spec = importlib.util.spec_from_file_location("reused_scan", self.snapshot / SCAN_REL)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def mapping(self):
        return json.loads((self.out / "slot-mapping.json").read_text())["mapping"]


def step_provenance(c):
    got = sha(c.video)
    need(got == c.media_sha, "original media differs from the registry")
    run = lambda cmd: subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=BELOW).stdout
    packets = run(["ffprobe", "-v", "error", "-show_entries", "packet=stream_index,pts_time", "-read_intervals", "%+#16",
                   "-of", "csv=p=0", c.video]).split()
    video = [round(float(p.split(",")[1]) * 1000) for p in packets if p.startswith("0,")]
    audio = [round(float(p.split(",")[1]) * 1000) for p in packets if p.startswith("1,")]
    streams = run(["ffprobe", "-v", "error", "-show_entries", "stream=index,codec_name,sample_rate,time_base,width,height,"
                   "avg_frame_rate:format_tags=encoder", "-of", "json", c.video])
    # the OBS log block that wrote this file
    log_hit = None
    for log in sorted(OBS_LOGS.glob("*.txt")):
        lines = log.read_text(errors="replace").splitlines()
        for i, line in enumerate(lines):
            if f"Writing file '{c.video}'" in line:
                start = max(j for j in range(i) if "obs-nvenc" in lines[j] and "settings:" in lines[j])
                stop = next(j for j in range(i, len(lines)) if "==== Recording Stop" in lines[j])
                log_hit = dict(log=log.name, log_sha256=sha(log), lines=[start + 1, stop + 1],
                               block=[l[13:] if len(l) > 13 and l[2] == ":" else l for l in lines[start:stop + 1]])
    content_log = STEAM / "logs/content_log.txt"
    app_lines = [l for l in content_log.read_text(errors="replace").splitlines() if "2767030" in l]
    manifest = (STEAM / "steamapps/appmanifest_2767030.acf").read_text(errors="replace")
    buildid = re.findall(r'"(buildid|TargetBuildID)"\s+"(\d+)"', manifest)
    remote = json.loads(SETTINGS.read_text(errors="replace"))["RemoteUserSetting"]
    controls = remote["UserControl"]
    controls = json.loads(controls) if isinstance(controls, str) else controls
    chosen = {}
    for hero in ("0", "1036"):   # the extraction of the 2026-09-22 receipt, unchanged
        value = controls[hero]
        value = json.loads(value) if isinstance(value, str) else value
        chosen[hero] = {k: v for k, v in value.items() if not k.startswith("Gamepad")}
        chosen[hero]["AbilityUserSettingList"] = [v for v in value.get("AbilityUserSettingList", []) if not v.get("bIsGamepad")]
    prior = json.loads(SETTINGS_0922.read_text())
    now_1036, before_1036 = chosen["1036"], prior["controls"]["1036"]
    version_path = STEAM / "steamapps/common/MarvelRivals/MarvelGame/version.json"
    version = json.loads(version_path.read_text())
    versions = {tool: run([tool, "-version"]).splitlines()[0] for tool in ("ffprobe", "ffmpeg")}
    doc = dict(
        session=c.sid, media={"path": c.video, "sha256": got, "bytes": os.path.getsize(c.video)},
        metadata={"sha256": sha(c.raw / "metadata.json"), **{k: c.meta[k] for k in (
            "status", "complete", "clean_stop", "obs_version", "logger_version", "width", "height", "fps_num", "fps_den",
            "queue_dropped_events", "raw_input_errors", "writer_failed", "events_attempted", "video_packets",
            "input_events", "started_utc", "start_ns", "end_ns", "capture_latency_calibrated")}},
        raw_files={n: sha(c.raw / n) for n in ("inputs.jsonl", "frames.csv", "metadata.json")},
        anchor_applicability=dict(
            accepted_derivation="data/human/inspection/20260922T033319-205Z-24328-2/independent-review-resolution.md",
            accepted_derivation_sha256=sha(ROOT / "data/human/inspection/20260922T033319-205Z-24328-2/independent-review-resolution.md"),
            first_16_packets={"video_ms": video, "audio_ms": audio},
            predicted={"video_ms": ANCHOR_VIDEO_MS, "audio_ms": ANCHOR_AUDIO_MS},
            matches=video == ANCHOR_VIDEO_MS and audio == ANCHOR_AUDIO_MS,
            streams=json.loads(streams), note="no fitting: the forward prediction of the accepted derivation"),
        obs_log=log_hit,
        build=dict(content_log={"path": str(content_log), "sha256": sha(content_log), "app_2767030_lines": app_lines[-6:]},
                   appmanifest_buildid=buildid,
                   version_json={"path": str(version_path), "sha256": sha(version_path),
                                 **{k: version.get(k) for k in ("version", "changelist")},
                                 "mtime_utc": datetime.fromtimestamp(version_path.stat().st_mtime, timezone.utc).isoformat()},
                   note="no app update line after the 2026-09-17 install of build 25364676 in the lines shown"),
        settings_receipt=dict(path=str(SETTINGS), sha256=sha(SETTINGS),
                              mtime_utc=datetime.fromtimestamp(SETTINGS.stat().st_mtime, timezone.utc).isoformat(),
                              recording_started_utc=c.meta["started_utc"],
                              written_after_recording=SETTINGS.stat().st_mtime > datetime.fromisoformat(
                                  c.meta["started_utc"].replace("Z", "+00:00")).timestamp(),
                              saved_NoCDSaved=remote.get("NoCDSaved"), controls=chosen,
                              equals_2026_09_22_receipt={"1036": now_1036 == before_1036,
                                                         "0": chosen["0"] == prior["controls"]["0"]},
                              note="Later local state, not a recording-time attestation. DPI is not stored here; "
                                   "motor fields stay unknown until James's dated statement (lead, R2)."),
        tools=versions)
    write_once(c.out / "provenance.json", doc)
    print("anchor matches", doc["anchor_applicability"]["matches"], "settings equal 09-22:",
          doc["settings_receipt"]["equals_2026_09_22_receipt"], "after recording:",
          doc["settings_receipt"]["written_after_recording"])


def step_verify(c):
    sys.path.insert(0, CHECKER)
    import check_session
    real, captured = check_session.subprocess.run, {}

    def limited(cmd, **kw):
        need(cmd[0] == "ffprobe", 'failed: cmd[0] == "ffprobe"')
        cmd = [cmd[0], "-threads", "4", *cmd[1:]]
        kw.setdefault("creationflags", BELOW)
        result = real(cmd, **kw)
        captured.update(cmd=cmd, stdout=result.stdout)
        return result

    check_session.subprocess.run = limited
    report = check_session.check(c.raw, verify_video=True)
    frames = [float(r["best_effort_timestamp_time"]) for r in json.loads(captured["stdout"])["frames"]]
    (c.scratch / "decoded-pts.json").write_text(json.dumps(frames))
    report.update(verification_decoder_threads=4, decoded_pts_sha256=sha(c.scratch / "decoded-pts.json"),
                  checker={"path": f"{CHECKER}/check_session.py", "sha256": sha(check_session.__file__),
                           "ffprobe_cmd": captured["cmd"]})
    write_once(c.out / "recorder-verification.json", report)
    print({k: report.get(k) for k in ("integrity_ok", "decoded_video_frames", "matched_video_frames",
                                      "unwritten_muxer_tail_packets", "muxer_pts_offset_seconds",
                                      "max_video_pts_residual_seconds", "errors")})


def step_profile(c):
    hi = c.hi
    events = c.events()
    focused = hi.focus_intervals(events, c.meta["start_ns"], c.meta["end_ns"])
    scope = hi.device_scope_report(events)
    hi.assert_human_device_scope(scope)
    controls = hi.control_times(events)
    marks = []
    for a, b in focused:
        inside = [t for t in controls if a <= t < b]
        pts = [a] + inside + [b]
        marks += [(p, q) for p, q in zip(pts, pts[1:]) if q - p >= hi.AFK_NS]
    kinds = {}
    for e in events:
        kinds[e["type"]] = kinds.get(e["type"], 0) + 1
    vks = {}
    for e in events:
        if e["type"] == "key" and e["down"]:
            vks[str(e["vk"])] = vks.get(str(e["vk"]), 0) + 1
    t0 = c.meta["start_ns"]
    doc = dict(session=c.sid, raw_files={n: sha(c.raw / n) for n in ("inputs.jsonl", "frames.csv", "metadata.json")},
               event_counts=kinds, focus_events=[dict(seq=e["seq"], t_ns=e["t_ns"], t_rel_s=(e["t_ns"] - t0) / 1e9,
                                                      active=e["active"], held_vk=e["held_vk"])
                                                 for e in events if e["type"] == "focus"],
               focused_intervals=[list(i) for i in focused],
               focused_s=sum(b - a for a, b in focused) / 1e9, recording_s=(c.meta["end_ns"] - t0) / 1e9,
               device_scope=scope, key_make_counts_by_vk=dict(sorted(vks.items(), key=lambda kv: int(kv[0]))),
               ui_key_presses=[dict(t_ns=t, t_rel_s=(t - t0) / 1e9, vk=vk, key=hi.UI_KEYS[vk], down=down)
                               for t, vk, down in hi.ui_key_presses(events)],
               afk_spans=[dict(start_ns=p, end_ns=q, seconds=(q - p) / 1e9) for p, q in marks],
               raw_input_gap_events=hi.raw_input_gaps(events),
               pause_events=[e for e in events if e["type"] == "pause"])
    write_once(c.out / "input-profile.json", doc)
    print(json.dumps({k: doc[k] for k in ("event_counts", "focused_s", "recording_s", "ui_key_presses", "afk_spans",
                                          "raw_input_gap_events")}, indent=1)[:3000])
    print("devices", scope)


def _scan(c, extra, scratch):
    cmd = [sys.executable, str(c.snapshot / SCAN_REL), "--video", c.video, "--session", str(c.raw),
           "--scratch", str(scratch), "--workers", "4", *extra]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(cmd, capture_output=True, text=True, creationflags=BELOW, env=env)
    need(proc.returncode == 0, proc.stderr[-3000:])
    return proc.stdout


def step_vote(c):
    out = _scan(c, ["--t", "60"], c.scratch / "vote")
    mapping = json.loads(re.search(r"^MAPPING (.*)$", out, re.M).group(1))
    doc = dict(session=c.sid, mapping=mapping, method="reused scan.py voting rule on every 24th frame of the first 60 s",
               equals_051828_and_032454={"swing": "swing", "get_over_here": "uppercut",
                                         "uppercut": "get_over_here"} == mapping)
    write_once(c.out / "slot-mapping.json", doc)
    print(doc)


def step_scan(c):
    scratch = c.scratch / "scan"
    need(not (scratch / "samples.jsonl").exists(), 'failed: not (scratch / "samples.jsonl").exists()')
    _scan(c, ["--mapping", json.dumps(c.mapping())], scratch)
    target = c.out / "hud-scan-samples.jsonl"
    need(not target.exists(), 'failed: not target.exists()')
    target.write_bytes((scratch / "samples.jsonl").read_bytes())
    rows = [json.loads(l) for l in target.read_text().splitlines()]
    print("hud-scan-samples.jsonl", sha(target), len(rows), "samples;", sum(r["hud_present"] for r in rows), "HUD present")


def _samples(c):
    return [json.loads(l) for l in (c.out / "hud-scan-samples.jsonl").read_text().splitlines()]


def step_regime(c):
    rows = _samples(c)
    keys = ("C", "LSHIFT", "E", "F")
    t0 = c.meta["start_ns"]
    intervals = []
    span = max(r["composition_ns"] for r in rows) - t0
    for s in range(0, int(span / 1e9) + 5, 5):
        sel = [r for r in rows if s <= (r["composition_ns"] - t0) / 1e9 < s + 5]
        if not sel:
            continue
        webs = [r["webs"] for r in sel if r["webs"] is not None]
        dec = sum(1 for a, b in zip(webs, webs[1:]) if b < a)
        countdowns = sum(any(r["positions"][k]["countdown"] is not None for k in keys) for r in sel)
        hud = sum(r["hud_present"] for r in sel)
        normal = hud > 0 and (countdowns > 0 or dec > 0 or 0 in webs)
        intervals.append(dict(t_rel_s=[s, s + 5], samples=len(sel), hud_present=hud, webs_min=min(webs, default=None),
                              webs_max=max(webs, default=None), web_decrements=dec, countdown_samples=countdowns,
                              reading="normal_depletion_observed" if normal else ("no_hud" if hud == 0 else "no_evidence")))
    counts = {}
    for i in intervals:
        counts[i["reading"]] = counts.get(i["reading"], 0) + 1
    session_regime = "normal" if counts.get("normal_depletion_observed") else None
    doc = dict(session=c.sid, scan_samples={"path": "hud-scan-samples.jsonl", "sha256": sha(c.out / "hud-scan-samples.jsonl")},
               interval_s=5, counts=counts, intervals=intervals, session_regime_from_scan=session_regime,
               rule="normal when depletion is observed (countdown numerals, web decrements or 0 webs); no interval "
                    "evidence is ever read as no-cooldown; no_evidence stays no_evidence",
               drop_note=None, cross_check=c.hi.regime_cross_check(None, session_regime))
    write_once(c.out / "regime-timeline.json", doc)
    print(counts, session_regime)


RECORDING_LOG = ROOT / "docs/recording-log.md"
USER_SETTINGS_0921 = ROOT / "data/human/notes/2026-09-21-user-settings.json"
# The 2026-09-21 reported bindings with their physical codes (scan code, or mouse button) for the fit (R7).
BINDINGS_0921 = {"Shift": ("swing", "key", 42), "Caps Lock": ("ez swing", "key", 58), "E": ("uppercut", "key", 18),
                 "F": ("pull", "key", 33), "Q": ("ultimate", "key", 16), "Left mouse": ("punch", "button", 1),
                 "Mouse 5": ("punch", "button", 5), "Right mouse": ("web cluster", "button", 2),
                 "C": ("team-up", "key", 46)}


def step_motor(c):
    log = RECORDING_LOG.read_text(encoding="utf-8")
    need("mouse DPI **800**" in log and "unchanged since the 2026-09-21 sessions" in log, 'failed: "mouse DPI **800**" in log and "unchanged since the 2026-09-21 sessions" in log')
    note = json.loads(USER_SETTINGS_0921.read_text())
    prov = json.loads((c.out / "provenance.json").read_text())
    commit = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%H", "--", "docs/recording-log.md"],
                            capture_output=True, text=True, check=True).stdout.strip()
    statement = dict(path="docs/recording-log.md", sha256=sha(RECORDING_LOG), commit=commit,
                     section="Motor settings (James's statements)",
                     text="2026-09-23: mouse DPI 800 (James, from the mouse's software; chat statement ~14:50 CDT). "
                          "In-game sensitivity unchanged since the 2026-09-21 sessions (same statement).")
    settings = dict(dpi=800, horizontal_sensitivity=note["mouse"]["horizontal_sensitivity"],
                    vertical_sensitivity=note["mouse"]["vertical_sensitivity"], swing_mode=note["swing_hold_or_toggle"])
    bindings = {k: v[0] for k, v in BINDINGS_0921.items()}
    doc = dict(
        session=c.sid,
        settings=dict(value=settings,
                      source="DPI: James's statement 2026-09-23 ~14:50 CDT. Sensitivity 1.89/1.89 and hold swing: James's "
                             "2026-09-21 report, carried forward by the same 2026-09-23 statement (sensitivity unchanged).",
                      per_session_source="James's statement dated 2026-09-23 ~14:50 CDT, applied by lead decision to every "
                                         "existing session",
                      evidence=[{k: statement[k] for k in ("path", "sha256")},
                                {"path": "data/human/notes/2026-09-21-user-settings.json", "sha256": sha(USER_SETTINGS_0921)},
                                {"path": f"data/human/sessions/{c.sid}/provenance.json", "sha256": sha(c.out / "provenance.json")}],
                      statement=statement,
                      corroboration=dict(saved_settings_sha256=prov["settings_receipt"]["sha256"],
                                         saved_profile_equals_2026_09_22=prov["settings_receipt"]["equals_2026_09_22_receipt"],
                                         saved_1036_mouse_sensitivity=[prov["settings_receipt"]["controls"]["1036"].get(k)
                                                                       for k in ("MouseHorizontalSensitivity",
                                                                                 "MouseVerticalSensitivity")],
                                         note="later local state; stores sensitivity and bindings, not DPI"),
                      limits=["swing mode is from the 2026-09-21 report; the 2026-09-23 statement names sensitivity only",
                              "counts/inch and counts/degree await the ruler and 360-degree takes (fit R8)"]),
        bindings=dict(value=bindings, physical={k: {"action": a, "kind": kind, "code": code}
                                                for k, (a, kind, code) in BINDINGS_0921.items()},
                      source="James's 2026-09-21 report (bindings_reported); HUD key labels C/LSHIFT/E/F inspected on this "
                             "session's own frames (slot-mapping.json)",
                      per_session_source="James's statement 2026-09-23 (settings unchanged since 2026-09-21); the lead is "
                                         "asking James what C and Alt are bound to",
                      evidence=[{"path": "data/human/notes/2026-09-21-user-settings.json", "sha256": sha(USER_SETTINGS_0921)},
                                {"path": f"data/human/sessions/{c.sid}/slot-mapping.json",
                                 "sha256": sha(c.out / "slot-mapping.json")}],
                      pending=["C binding confirmation (reported team-up on 2026-09-21)", "any Alt binding"]),
        settings_identity=c.hi.settings_identity(settings, bindings),
        calibration_takes=dict(dpi_ruler=None, turn_360=None, note="pointers are added when the takes arrive"))
    write_once(c.out / "motor-settings.json", doc)
    print(settings, doc["settings_identity"])


def _proposal_inputs(c):
    hi = c.hi
    events = c.events()
    focused = hi.focus_intervals(events, c.meta["start_ns"], c.meta["end_ns"])
    packets = c.packets()
    decoded = json.loads((c.out / "recorder-verification.json").read_text())["decoded_video_frames"]
    ordered = sorted(packets[:decoded], key=lambda r: r["pts"])
    frame_times = [r["composition_ns"] for r in ordered]
    frame_gap = (2 * 10**9 * c.meta["fps_den"] + c.meta["fps_num"] - 1) // c.meta["fps_num"]
    gaps = hi.capture_gaps(frame_times, frame_gap)
    samples = _samples(c)
    hud = [(r["composition_ns"], r["hud_present"]) for r in samples]      # True/False/None kept as read (review I6)
    dead = [r["composition_ns"] for r in samples if r.get("hp") == 0]
    regime = json.loads((c.out / "regime-timeline.json").read_text())["session_regime_from_scan"]
    return dict(intervals=focused, hud_samples=hud, ui_keys=hi.ui_key_presses(events), controls=hi.control_times(events),
                gaps=gaps, session_regime=regime or "unknown", dead=dead), ordered


def step_propose(c):
    kw, _ = _proposal_inputs(c)
    segs, flags = c.hi.propose_segments(**kw)
    write_once(c.out / "candidates-pass1.json", dict(session=c.sid, flags=flags, capture_gaps=[list(g) for g in kw["gaps"]],
                                                    segments=segs))
    for s in segs:
        print(s["segment_id"], s["machine_reason"], s["proposal"], round((s["start_ns"] - c.meta["start_ns"]) / 1e9, 3),
              round((s["end_ns"] - c.meta["start_ns"]) / 1e9, 3))
    print("flags", flags)


def _decode(c, file_ms_list, keep_frames=False):
    """Decode exactly the frames at these file ms (CPU, 4 threads, below normal). Returns [(ms, bgr ndarray)]."""
    import numpy as np
    wanted = sorted(set(file_ms_list))
    out = []
    # decode contiguous windows so each frame is selected by its exact PTS
    windows, cur = [], [wanted[0]]
    for ms in wanted[1:]:
        if ms - cur[-1] <= 500:
            cur.append(ms)
        else:
            windows.append(cur)
            cur = [ms]
    windows.append(cur)
    for win in windows:
        expr = "+".join(f"eq(pts\\,{ms})" for ms in win)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-copyts", "-threads", "4",
               "-ss", f"{max(0, win[0] / 1000 - 0.2):.3f}", "-i", c.video, "-an", "-sn", "-dn", "-filter_threads", "1",
               "-vf", f"select='{expr}'", "-fps_mode", "passthrough", "-frames:v", str(len(win)),
               "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
        raw = subprocess.run(cmd, capture_output=True, check=True, creationflags=BELOW).stdout
        size = W * H * 3
        need(len(raw) == size * len(win), (len(raw) / size, len(win)))
        for i, ms in enumerate(win):
            out.append((ms, np.frombuffer(raw[i * size:(i + 1) * size], np.uint8).reshape(H, W, 3)))
    return out


def step_evidence(c):
    import cv2
    hi = c.hi
    below_normal()
    cv2.setNumThreads(2)
    scan = c.scan_module()
    mapping = c.mapping()
    layout = scan.source_layout(mapping)
    kw, ordered = _proposal_inputs(c)
    ms_of = {r["composition_ns"]: round(r["pts"] * 1000 / 120) + 21 for r in ordered}
    index_of = {r["composition_ns"]: i for i, r in enumerate(ordered)}
    times = [r["composition_ns"] for r in ordered]
    pass1 = json.loads((c.out / "candidates-pass1.json").read_text())["segments"]
    # 1. native HUD reads for every frame inside each gameplay edge bracket
    native, reads = {}, []
    for s in pass1:
        if s["machine_reason"] != hi.GAMEPLAY:
            continue
        for edge in ("start", "end"):
            lo, hi_ = s["edges"][edge]["refine"]
            frames = [t for t in times if lo <= t < hi_]
            decoded = _decode(c, [ms_of[t] for t in frames])
            by_ms = dict(decoded)
            row = []
            for t in frames:
                present = scan.read_sample(by_ms[ms_of[t]], layout, mapping)["hud_present"]
                row.append((t, bool(present)))
            native[(edge, s["edges"][edge]["sample_ns"])] = row
            reads.append(dict(segment=s["segment_id"], edge=edge, sample_ns=s["edges"][edge]["sample_ns"], bracket=[lo, hi_],
                              frames=[dict(composition_ns=t, frame_index=index_of[t], file_ms=ms_of[t], hud_present=p)
                                      for t, p in row]))
    segs, flags = hi.propose_segments(**kw, native=native)
    # 2. review frames: both edges plus stratified interior frames, decoded exactly and hashed
    review_dir = c.out / "review-frames"
    review_dir.mkdir(exist_ok=True)
    picks = {}
    from bisect import bisect_left, bisect_right
    for s in segs:
        first = bisect_left(times, s["start_ns"])
        last = bisect_right(times, s["end_ns"] - 1) - 1
        if first > last:
            picks[s["segment_id"]] = []
            continue
        n = max(1, (s["end_ns"] - s["start_ns"]) // REVIEW_INTERIOR_EVERY_NS)
        chosen = {first, last} | {first + (last - first) * (k + 1) // (n + 1) for k in range(n)}
        picks[s["segment_id"]] = sorted(chosen)
    all_ms = sorted({ms_of[times[i]] for v in picks.values() for i in v})
    frames = dict(_decode(c, all_ms))
    for s in segs:
        s["review_frames"] = []
        for i in picks[s["segment_id"]]:
            t = times[i]
            img = frames[ms_of[t]]
            name = f"{s['segment_id']}-{i:05d}.jpg"
            cv2.imwrite(str(review_dir / name), cv2.resize(img, REVIEW_THUMB, interpolation=cv2.INTER_AREA),
                        [cv2.IMWRITE_JPEG_QUALITY, 88])
            s["review_frames"].append(dict(frame_index=i, composition_ns=t, file_ms=ms_of[t],
                                           decoded_bgr_sha256=hashlib.sha256(img.tobytes()).hexdigest(),
                                           hud_present=bool(scan.read_sample(img, layout, mapping)["hud_present"]),
                                           image=f"review-frames/{name}", image_sha256=sha(review_dir / name),
                                           role="start" if i == picks[s["segment_id"]][0] else
                                           ("end" if i == picks[s["segment_id"]][-1] else "interior")))
    t0 = c.meta["start_ns"]
    for s in segs:
        s["t_rel_s"] = [(s["start_ns"] - t0) / 1e9, (s["end_ns"] - t0) / 1e9]
        s["seen"] = None   # filled by the owner's inspection; what the frames actually show (R9)
    doc = dict(session=c.sid, session_group=c.place.session_group, split=c.place.split, media_sha256=c.media_sha,
               snapshot=c.snapshot.name, snapshot_manifest_sha256=sha(c.snapshot / "manifest.json"),
               registry={"path": "data/human/session-splits.corpus.json", "sha256": sha(REGISTRY)},
               denylist={"path": "data/human/sealed-denylist.json", "sha256": sha(DENYLIST)},
               inputs={n: {"path": n, "sha256": sha(c.out / n)} for n in (
                   "provenance.json", "recorder-verification.json", "input-profile.json", "slot-mapping.json",
                   "hud-scan-samples.jsonl", "regime-timeline.json", "candidates-pass1.json")},
               parameters=dict(ui_keys=hi.UI_KEYS, settings_menu_keys=sorted(hi.SETTINGS_MENU_KEYS),
                               ui_settle_ns=hi.UI_SETTLE_NS, afk_ns=hi.AFK_NS, max_hud_gap_ns=hi.MAX_HUD_GAP_NS,
                               review_interior_every_ns=REVIEW_INTERIOR_EVERY_NS),
               session_regime=kw["session_regime"], focused_intervals=[list(i) for i in kw["intervals"]],
               capture_gaps=[list(g) for g in kw["gaps"]], flags=flags, native_edge_reads=reads, segments=segs,
               earlier_steps=dict(snapshot=c.earlier_snapshot or c.snapshot.name,
                                  manifest_sha256=sha(HERE / (c.earlier_snapshot or c.snapshot.name) / "manifest.json"),
                                  steps="provenance, verify, profile, vote, scan, regime, motor"),
               motor={"path": "motor-settings.json", "sha256": sha(c.out / "motor-settings.json")},
               note="`proposal` is the proposer's; nothing here is a verdict. Accepted comes only from a verdict "
                    "record with reviewer, time and inspected native frame hashes (review R5).")
    write_once(c.out / "segments-evidence.json", doc)
    for s in segs:
        print(s["segment_id"], s["machine_reason"], s["proposal"], [round(x, 3) for x in s["t_rel_s"]],
              len(s["review_frames"]), "frames")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", choices=["provenance", "verify", "profile", "vote", "scan", "regime", "motor", "propose",
                                     "evidence"])
    ap.add_argument("session")
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--earlier-snapshot", help="the snapshot the earlier steps ran from, when it differs")
    args = ap.parse_args()
    below_normal()
    globals()[f"step_{args.step}"](Ctx(args))


if __name__ == "__main__":
    main()
