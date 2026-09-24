"""The first replay-source step table: DayMR's in-client replay, from the replay-HUD reader's full-rate outputs.

    uv run python scripts/replay_steps.py            # writes data/demos/replays/daymr-20260923-004325/steps/

Contract: policy/range_bc/steps.py ("REPLAY source") and docs/lanes/end-to-end-fit.md "Replay labels". Inputs, all
local and hash-pinned in steps/build.json:
- hud/rows-*.jsonl.gz and hud/events.json: the replay-HUD reader's per-frame table and cast events (file clock = the
  capture's PTS seconds);
- docs/evidence/replay-hud-20260923/press-lags.json: press -> HUD lags measured on James's own takes;
- route-map/followed_player.json: the per-second follow log (on_target, timeline_visible);
- the capture's logger frames.csv (RivalsInput/<CAPTURE>): each frame's composition time, the anchor clock.

Rows:
- 33.3 ms anchors on the capture's composition clock, over the followed player's spans only. A frame is in a span when
  the HUD reader read it (not "viewer not following", timeline up or unreadable, dead, no HUD), the route map's second
  is on target with the timeline hidden, and it lies outside EXCLUDE (duplicated setup footage, a pause). Short
  misreads are forgiven (forgive_blips): a follow-bar miss of at most 3 s inside on-target seconds (the route map's
  own hold rule) and an hp-0 read of at most 0.25 s between alive reads. A run breaks at every excluded frame, at a
  capture gap over 2 frame periods, and at every seek (SEEKS). Only steps whose (anchor, anchor + step] lies inside
  the run's frames are written.
- press (lead contract, replay-steps-3): team_up, get_over_here, amazing_combo, web_cluster and ultimate. Each cast's
  press lies in [t_lo - Lmax, t_hi - Lmin] (floored lags; for countdown casts the cooldown-start lag). Every step
  overlapping that window is null: never 0, and never a single-step 1 (the table holds no 1 at all). The windows
  themselves go to steps/<capture>.press-windows.json ([lo, hi, action] per cast, both clocks, the rows they span),
  for a pre-registered window-level loss ("at least one press in the window"). press = 0 only where a step overlaps
  no window and lies wholly inside the ability's PRESS-TIME coverage (hud/events.json press_coverage: max-count,
  merged, cut at every event and at withheld frames, seeks and excluded footage, shrunk by the floored lag).
  Anywhere else, null.
- Deaths: an hp-0 cluster (gaps up to 1 s, at least 30 frames), widened over every contiguous frame not read alive
  (hp > 0), is out entirely; an hp-0 blip is forgiven only between frames read alive.
- web_swing and simple_swing are null everywhere: a swing-charge drop does not tell which of the two was pressed.
- held_*, release, movement, jump, spider_power, melee, goh_targeting: null everywhere (no labeller yet).
- yaw_deg, pitch_deg: null. fill_camera() is the hook for perception/camera_motion.py's output (not applied here); it
  takes only the estimator's replay run over this capture, and only pairs whose source it accepts ("main" by default).
"""
import argparse
import bisect
import collections
import csv
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from policy.range_bc import steps, vocab  # noqa: E402

REPLAY = ROOT / "data" / "demos" / "replays" / "daymr-20260923-004325"
HUD = REPLAY / "hud"
OUT = REPLAY / "steps"
LAGS = ROOT / "docs" / "evidence" / "replay-hud-20260923" / "press-lags.json"
CAPTURE = "20260923T054325-507Z-33696-4"
RAW = Path("C:/Users/volpe/Videos/RivalsInput")
STEP_NS, PERIOD_NS = 33_333_333, 8_333_333
MUXER_OFFSET_MS = 21.0          # this OBS profile's muxer offset (intake's anchor; this capture's stream starts at 0.021)
WITHHELD = ("viewer not following", "replay timeline", "dead", "no HUD drawn", "column order unknown")
# (start, end, why), file seconds: excluded beyond the per-frame and per-second masks (route-map/README.md)
EXCLUDE = ((1642.75, 1645.25, "duplicate of round-2 setup footage first shown at ~1045.5-1048.5"),
           (1651.9, 1658.5, "duplicate of round-3 setup footage (seeks 1651.99, 1653.52)"),
           (1859.5, 1864.9, "operator pause 1859.57, seek 1862.66, unpause 1864.88"))
SEEKS = (468.58, 1030.92, 1608.09, 1639.95, 1645.32, 1651.99, 1653.52, 1862.66)
# step-table action <- (replay-HUD ability, press-lag entry)
CASTS = {"team_up": "teamup", "get_over_here": "get_over_here", "amazing_combo": "uppercut",
         "web_cluster": "web_cluster", "ultimate": "ult"}
LAG_NAME = {"teamup": "teamup", "get_over_here": "get_over_here", "uppercut": "uppercut", "web_cluster": "web_cluster",
            "ult": "ult"}
PRESS_COVERAGE_NAME = {"teamup": "teamup", "get_over_here": "get_over_here", "uppercut": "uppercut",
                       "web_cluster": "web_cluster", "ult": "ult"}
YAW_CAP_DEG, PITCH_CAP_DEG = 415 / 30, 99 / 30   # the executor's per-step caps: beyond them the label is saturated


def sha256(path):
    return steps.sha256(path)


# --- clocks ------------------------------------------------------------------------------------------------------

def capture_clock(session=CAPTURE):
    """{file pts ms (rounded): (composition_ns, frame_index)} from the logger's frames.csv, presentation order."""
    with (RAW / session / "frames.csv").open(encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["track"] == "0"]
    logged = sorted((int(r["pts"]) * 1000 * int(r["timebase_num"]) / int(r["timebase_den"]) + MUXER_OFFSET_MS,
                     int(r["composition_ns"])) for r in rows)
    return {round(ms): (comp, i, ms) for i, (ms, comp) in enumerate(logged)}


class FileToComposition:
    """File seconds -> composition ns, through the mapped frames (nearest frame, plus the offset from it)."""

    def __init__(self, pairs):
        pairs = sorted(pairs)
        self.t = [p[0] for p in pairs]
        self.c = [p[1] for p in pairs]

    def __call__(self, t):
        k = bisect.bisect_left(self.t, t)
        k = min(max(k, 0), len(self.t) - 1)
        if k and abs(self.t[k - 1] - t) < abs(self.t[k] - t):
            k -= 1
        return self.c[k] + round((t - self.t[k]) * 1e9)


# --- frames and runs ---------------------------------------------------------------------------------------------

def frame_reasons(hud=HUD):
    """[(file s, reason or None, hp or None)] per frame. The reason is the frame-level one (every field of a withheld
    frame carries it); hp is the frame's hp read (the reader's "hp" row), None when unread."""
    frames = {}
    for f in sorted(hud.glob("rows-*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                d = json.loads(line)
                if d["ability"] == "teamup":
                    why = d["reason"] if d["state"] == "unknown" and d["reason"].startswith(WITHHELD) else None
                    frames.setdefault(d["t"], [None, None])[0] = why
                elif d["ability"] == "hp":
                    frames.setdefault(d["t"], [None, None])[1] = d["numeral"] if d["state"] == "count" else None
    return sorted((t, why, hp) for t, (why, hp) in frames.items())


FOLLOW_BLIP_S = 3.0             # route map: the bar vanishes under tile icons for 0.25-2 s; no_pov only after 3 s
DEAD_BLIP_S = 0.25              # an hp-0 read this short, between frames READ ALIVE, is a misread, not a death
DEATH_GAP_S = 1.0               # hp-0 frames this close belong to one death (the death cam alternates with abstentions)
DEATH_MIN_FRAMES = 30           # ... and a cluster this large is a death


def alive(frame):
    """Read alive: no frame-level reason and an hp above 0 actually read. An abstention is never evidence of life."""
    return frame[1] is None and frame[2] is not None and frame[2] > 0


def death_spans(frames):
    """Deaths as file-time spans (review R2): hp-0 frames clustered at gaps up to DEATH_GAP_S, clusters of at least
    DEATH_MIN_FRAMES, widened over every contiguous frame that is not read alive (abstained, no HUD, other POV)."""
    dead = [k for k, f in enumerate(frames) if f[1] and f[1].startswith("dead")]
    clusters, cur = [], []
    for k in dead:
        if cur and frames[k][0] - frames[cur[-1]][0] > DEATH_GAP_S:
            clusters.append(cur)
            cur = []
        cur.append(k)
    if cur:
        clusters.append(cur)
    spans = []
    for c in clusters:
        if len(c) < DEATH_MIN_FRAMES:
            continue
        i, j = c[0], c[-1]
        while i > 0 and not alive(frames[i - 1]):
            i -= 1
        while j + 1 < len(frames) and not alive(frames[j + 1]):
            j += 1
        spans.append((frames[i][0], frames[j][0]))
    return spans


def forgive_blips(frames, per_second):
    """(file s, reason or None) per frame, after the death and blip rules; and the counts.

    - Every frame inside a death span (death_spans) is out, whatever the reader said about it.
    - A "viewer not following" stretch of at most FOLLOW_BLIP_S whose seconds the route map logs on target with the
      timeline hidden is a bar misread (the route map's own hold rule) and is forgiven.
    - An hp-0 stretch of at most DEAD_BLIP_S outside any death span is forgiven only when the frames on both sides
      were READ ALIVE (hp > 0), never when they were abstentions."""
    deaths = death_spans(frames)
    starts = [a for a, _ in deaths]

    def in_death(t):
        k = bisect.bisect_right(starts, t) - 1
        return k >= 0 and deaths[k][0] <= t <= deaths[k][1]

    out = [(t, "dead (death span)" if in_death(t) else why) for t, why, _ in frames]
    forgiven, k = {"death_spans": len(deaths)}, 0
    while k < len(out):
        t, why = out[k]
        kind = ("follow" if why and why.startswith("viewer not following")
                else "dead" if why and why.startswith("dead (hp") else None)
        if kind is None:
            k += 1
            continue
        j = k
        while j + 1 < len(out) and out[j + 1][1] == why:
            j += 1
        span = out[j][0] - out[k][0]
        if kind == "follow":
            secs = [per_second.get(s_) for s_ in range(int(out[k][0]), int(out[j][0]) + 1)]
            ok = span <= FOLLOW_BLIP_S and all(p and p["on_target"] and not p["timeline_visible"] for p in secs)
        else:
            ok = (span <= DEAD_BLIP_S and k > 0 and j + 1 < len(out)
                  and alive(frames[k - 1]) and alive(frames[j + 1]) and out[k - 1][1] is None and out[j + 1][1] is None)
        if ok:
            for m in range(k, j + 1):
                out[m] = (out[m][0], None)
            forgiven[why] = forgiven.get(why, 0) + (j - k + 1)
        k = j + 1
    return out, forgiven


def included(t, why, per_second):
    if why:
        return False, why
    sec = per_second.get(int(t))
    if sec is None or not sec["on_target"] or sec["timeline_visible"]:
        return False, "route map: not on target or timeline visible"
    for a, b, reason in EXCLUDE:
        if a <= t <= b:
            return False, reason
    return True, None


def build_runs(frames, clock):
    """Runs of included frames: [[(file s, composition ns, frame_index, pts ms)]], plus the mapping statistics."""
    runs, cur, stats = [], [], {"frames": 0, "included": 0, "unmapped": 0, "max_residual_ms": 0.0}
    seeks = list(SEEKS)
    prev_t = None
    for t, ok in frames:
        stats["frames"] += 1
        mapped = clock.get(round(t * 1000))
        if mapped is not None:
            stats["max_residual_ms"] = max(stats["max_residual_ms"], abs(mapped[2] - t * 1000))
        if not ok or mapped is None:
            if ok and mapped is None:
                stats["unmapped"] += 1
            if cur:
                runs.append(cur)
            cur, prev_t = [], None
            continue
        comp, index, _ = mapped
        crossed = prev_t is not None and any(prev_t < s <= t for s in seeks)
        if cur and (comp - cur[-1][1] > 2 * PERIOD_NS or crossed or index <= cur[-1][2]):
            runs.append(cur)
            cur = []
        cur.append((t, comp, index, round(t * 1000)))
        stats["included"] += 1
        prev_t = t
    if cur:
        runs.append(cur)
    return runs, stats


# --- labels ------------------------------------------------------------------------------------------------------

def lag_ranges(lags_doc):
    """{hud ability: {"first_seen": (lo, median, hi) | None, "cooldown_start": ... | None}}: measured ranges widened by
    perception.replay_hud.floored_lag (n < 3 gives at least +-0.5 s; one sample never gives zero width)."""
    from perception.replay_hud import floored_lag
    out = {}
    for name, d in lags_doc["abilities"].items():
        def rng(k):
            v = d[k]
            if not v.get("n"):
                return None
            lo, hi = floored_lag(v["min"], v["max"], v["n"], v["median"])
            return (lo, v["median"], hi)
        out[name] = {"first_seen": rng("first_seen_lag_s"), "cooldown_start": rng("cooldown_start_lag_s"),
                     "n": d["first_seen_lag_s"].get("n", 0), "n_cooldown_start": d["cooldown_start_lag_s"].get("n", 0)}
    return out


Window = collections.namedtuple("Window", "lo hi count lag_measured basis t_lo t_hi")


def press_windows(events, lags):
    """Per step-table action: the press window of every cast, [Window], file s.

    Review R1: the press lies in [t_lo - Lmax, t_hi - Lmin] for EVERY basis (t_lo is the last read before the HUD
    showed the cast, t_hi the first read after; for countdown casts the two bound the cooldown's start and the lag is
    the press -> cooldown-start one). Casts without a measured lag, and flagged stretches, give windows widened by the
    largest lag (lag_measured False)."""
    out = {a: [] for a in CASTS}
    rev = {v: k for k, v in CASTS.items()}
    for e in events:
        action = rev.get(e["ability"])
        if action is None:
            continue
        lag = lags.get(LAG_NAME[e["ability"]], {})
        key = "cooldown_start" if e["basis"] == "countdown" else "first_seen"
        r = lag.get(key) if e["basis"] != "flagged" else None
        widest = max((v[2] for v in (lag.get("first_seen"), lag.get("cooldown_start")) if v), default=2.0)
        if r is None:
            out[action].append(Window(e["t_lo"] - widest, e["t_hi"], e["count"], False, e["basis"], e["t_lo"],
                                      e["t_hi"]))
            continue
        lo_lag, _, hi_lag = r
        out[action].append(Window(e["t_lo"] - hi_lag, e["t_hi"] - lo_lag, e["count"], True, e["basis"], e["t_lo"],
                                  e["t_hi"]))
    return out


def _overlapping(anchors, a, b):
    """Indices of the steps (anchor, anchor + step] that overlap the composition span [a, b]."""
    k = max(0, bisect.bisect_left(anchors, a - STEP_NS))
    out = []
    while k < len(anchors) and anchors[k] < b:
        if anchors[k] + STEP_NS > a:
            out.append(k)
        k += 1
    return out


def label_rows(anchors, windows, press_cov, to_comp):
    """press per step. anchors: [anchor ns]; step k is (anchor_k, anchor_k + step].

    Lead contract (replay-steps-3): every step overlapping a cast's press window is null, never 0 and never 1; the
    table holds no 1. A step is 0 only when it overlaps no window and lies wholly inside the ability's press-time
    coverage. Anything else is null. The windows go to the press-windows file (window_records)."""
    n = len(anchors)
    press = [[None] * vocab.N for _ in range(n)]
    for action, hud_name in CASTS.items():
        c = vocab.INDEX[action]
        blocked = [False] * n
        for w in windows[action]:
            for k in _overlapping(anchors, to_comp(w.lo), to_comp(w.hi)):
                blocked[k] = True
        cov = sorted((to_comp(a), to_comp(b)) for a, b in press_cov.get(PRESS_COVERAGE_NAME[hud_name], []))
        starts = [a for a, _ in cov]
        for k, anchor in enumerate(anchors):
            if blocked[k]:
                continue
            j = bisect.bisect_right(starts, anchor) - 1
            if j >= 0 and cov[j][0] <= anchor and anchor + STEP_NS <= cov[j][1]:
                press[k][c] = 0
    return press


def window_records(windows, anchors, runs, to_comp):
    """The press-windows file's records, one per cast (and per flagged stretch), sorted by time.

    Each: action, HUD ability, basis, count (HUD casts in the event; a 2-count ammo drop is 2), cast (False for a
    flagged stretch: no cast is established), lag_measured, the window [lo, hi] in file seconds and in composition ns
    (the table's anchor clock), the evidence [t_lo, t_hi], and the table rows it overlaps: rows [first i, last i] or
    None, and complete = those rows are one run's consecutive steps covering the whole window (only then is "at least
    one press among these rows" a statement about rows that exist)."""
    out = []
    for action, ws in windows.items():
        for w in ws:
            a, b = to_comp(w.lo), to_comp(w.hi)
            ks = _overlapping(anchors, a, b)
            complete = bool(ks) and anchors[ks[0]] <= a and b <= anchors[ks[-1]] + STEP_NS and all(
                runs[k] == runs[ks[0]] and anchors[k] - anchors[k - 1] == STEP_NS for k in ks[1:])
            out.append({"action": action, "ability": CASTS[action], "basis": w.basis, "count": w.count,
                        "cast": w.basis != "flagged", "lag_measured": w.lag_measured,
                        "lo_s": round(w.lo, 4), "hi_s": round(w.hi, 4), "lo_ns": a, "hi_ns": b,
                        "evidence_s": [round(w.t_lo, 4), round(w.t_hi, 4)],
                        "rows": [ks[0], ks[-1]] if ks else None, "complete": complete})
    return sorted(out, key=lambda r: (r["lo_ns"], r["action"]))


# --- the camera hook ---------------------------------------------------------------------------------------------

CAMERA_STEP_SOURCES = ("main",)  # perception/camera_motion Step.source accepted by default: "centre" is imprecise
#                                  (camera lane: ~0.5 deg median error on 1.1-1.3 deg moves, n = 24), opt-in only


def check_camera_run(meta, capture_video):
    """Refused unless `meta` (camera_motion's meta line) is the estimator's REPLAY run over this session's capture:
    video naming the capture, the spectator-UI mask on (replay mode), and no clock offset (steps map file seconds)."""
    if not isinstance(meta, dict) or meta.get("type") != "meta":
        raise ValueError("camera output needs camera_motion's meta line first")
    video = meta.get("video") or meta.get("source") or ""
    if Path(str(video).replace("\\", "/")).name.lower() != Path(str(capture_video).replace("\\", "/")).name.lower():
        raise ValueError(f"camera run is over {video!r}, not this session's capture {capture_video!r}")
    if meta.get("spectator_mask") is not True:
        raise ValueError("camera run was not the replay run (spectator_mask off)")
    if (meta.get("t_offset") or 0.0) != 0.0:
        raise ValueError("camera run has a clock offset; steps map the capture's own file seconds")


def fill_camera(rows, camera, to_comp, *, capture_video, sources=CAMERA_STEP_SOURCES):
    """Fill yaw_deg / pitch_deg from perception/camera_motion.py output, `camera` = (meta, steps) as its read()
    returns (Step objects or their dicts: t0, t1 in video seconds, yaw_deg right positive, pitch_deg UP positive,
    abstain, source). NOT applied to this table yet (the camera lane's bytes are in final check).

    The run must be the estimator's replay run over this session's capture (check_camera_run), and a pair counts only
    when its `source` is in `sources`: any other pair leaves its step unknown. A step gets degrees only when accepted,
    non-abstaining pairs tile (anchor, anchor + step] with no gap over one frame period; pitch flips sign (the step
    table's pitch is positive downward, the mouse's +dy). beyond_pad_envelope flags a step over the executor's
    per-step caps; the label is kept, not clipped. Returns the number of steps filled."""
    meta, camera_steps = camera
    check_camera_run(meta, capture_video)
    records = [s if isinstance(s, dict) else vars(s) for s in camera_steps]
    pairs = sorted((to_comp(s["t0"]), to_comp(s["t1"]), s) for s in records)
    starts = [p[0] for p in pairs]
    filled = 0
    for r in rows:
        a, b = r["anchor_ns"], r["anchor_ns"] + STEP_NS
        j = max(0, bisect.bisect_right(starts, a) - 1)
        yaw = pitch = 0.0
        edge, ok = a, True
        while j < len(pairs) and pairs[j][0] < b:
            c0, c1, s = pairs[j]
            j += 1
            if c1 <= a:
                continue
            if (c0 - edge > PERIOD_NS or s.get("abstain") or s.get("yaw_deg") is None or s.get("pitch_deg") is None
                    or s.get("source", "main") not in sources):
                ok = False
                break
            share = (min(c1, b) - max(c0, a)) / (c1 - c0)
            yaw += s["yaw_deg"] * share
            pitch -= s["pitch_deg"] * share
            edge = c1
        if ok and b - edge <= PERIOD_NS and edge > a:
            r["yaw_deg"], r["pitch_deg"] = yaw, pitch
            r["beyond_pad_envelope"] = abs(yaw) > YAW_CAP_DEG or abs(pitch) > PITCH_CAP_DEG
            filled += 1
    return filled


# --- the table ---------------------------------------------------------------------------------------------------

def header(media_sha256, hud_manifest):
    reader = hud_manifest["reader"]["sha256"][:12]
    return {
        "format": steps.FORMAT, "source_kind": "replay", "session_id": CAPTURE, "media_sha256": media_sha256,
        "session_group": CAPTURE, "sitting": "daymr-replay-2026-09-23", "split": steps.REPLAY_SPLIT,
        "step_ns": STEP_NS, "frame_period_ns": PERIOD_NS, "actions": list(vocab.NAMES),
        "calibration": {"kind": "replay_degrees", "source": f"replay-hud perception/replay_hud.py@{reader}; "
                        "camera and movement not labelled yet",
                        "label_sources": {
                            "camera": "none: yaw/pitch null; hook scripts/replay_steps.py fill_camera for "
                                      "perception/camera_motion.py output, pending the camera lane's landing",
                            "movement": "none: not labelled (the inverse-dynamics model is not trained)",
                            "edges": f"replay-hud perception/replay_hud.py@{reader} cast events; press lags from "
                                     "docs/evidence/replay-hud-20260923/press-lags.json (James's takes)"}},
        "expert_context": {"player": "DayMR",
                           "match_id": "Competitive Convoy, Hellfire Gala: Arakko, 2026-09-22 11:30, 17:41, S10.0",
                           "viewer_fov_assumption": "viewer, unverified",
                           "replay_source": f"native in-client replay viewer, OBS capture {CAPTURE}"},
        "hud_layout": "mk", "swing_mode": {"automatic_swing": None, "hold_to_swing": None},
        "video_size": [2560, 1440],
        "patch": "client 1.1.3870120 (Steam build 25364676); kit numbers S10 v20260911 apply",
    }


def build(out_dir=OUT):
    lags_doc = json.loads(LAGS.read_text(encoding="utf-8"))
    ev = json.loads((HUD / "events.json").read_text(encoding="utf-8"))
    manifest = json.loads((HUD / "manifest.json").read_text(encoding="utf-8"))
    follow = json.loads((REPLAY / "route-map" / "followed_player.json").read_text(encoding="utf-8"))
    per_second = {p["s"]: p for p in follow["per_second"]}
    clock = capture_clock()
    frames, forgiven = forgive_blips(frame_reasons(), per_second)
    decided = [(t, included(t, why, per_second)) for t, why in frames]
    runs, stats = build_runs([(t, ok) for t, (ok, _) in decided], clock)
    to_comp = FileToComposition([(v[2] / 1000, v[0]) for v in clock.values()])
    video = manifest["video"]["path"].replace("\\", "/")
    rows, anchors_all, excluded = [], [], {}
    for t, (ok, why) in decided:
        if not ok:
            excluded[why.split(":")[0].split(" (")[0]] = excluded.get(why.split(":")[0].split(" (")[0], 0) + 1
    for ri, run in enumerate(runs):
        comps = [f[1] for f in run]
        a = comps[0]
        while a + STEP_NS <= comps[-1]:
            k = bisect.bisect_right(comps, a) - 1                     # the last frame with CTS <= anchor
            t, comp, index, pts = run[k]
            rows.append({"i": len(rows), "run": f"b5-{ri:03d}", "anchor_ns": a,
                         "frame": {"video_path": video, "frame_index": index, "pts": pts, "timebase": [1, 1000],
                                   "composition_ns": comp},
                         "gap_free": True, "segment": f"b5-{ri:03d}", "suitability": "accepted", "regime": "normal",
                         "tags": [], "tag_source": "untagged"})
            anchors_all.append(a)
            a += STEP_NS
    windows = press_windows(ev["events"], lag_ranges(lags_doc))
    press = label_rows(anchors_all, windows, ev.get("press_coverage", {}), to_comp)
    records = window_records(windows, anchors_all, [r["run"] for r in rows], to_comp)
    none = [None] * vocab.N
    for r, p in zip(rows, press):
        r.update({"held_start": list(none), "held_end": list(none), "held_known": [False] * vocab.N,
                  "press": p, "release": list(none), "press_known": [v is not None for v in p],
                  "release_known": [False] * vocab.N, "yaw_deg": None, "pitch_deg": None,
                  "beyond_pad_envelope": False})
    media = manifest["video"]["recorded_sha256"]
    h = header(media, manifest)
    h["source"] = {"builder": {"path": "scripts/replay_steps.py", "sha256": sha256(__file__)},
                   "hud_manifest": {"path": str((HUD / "manifest.json").relative_to(ROOT)).replace("\\", "/"),
                                    "sha256": sha256(HUD / "manifest.json")},
                   "hud_events": {"sha256": sha256(HUD / "events.json")},
                   "press_lags": {"path": str(LAGS.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(LAGS)},
                   "followed_player": {"sha256": sha256(REPLAY / "route-map" / "followed_player.json")},
                   "frames_csv": {"session": CAPTURE, "sha256": sha256(RAW / CAPTURE / "frames.csv"),
                                  "muxer_offset_ms": MUXER_OFFSET_MS}}
    out_dir.mkdir(parents=True, exist_ok=True)
    win_path = out_dir / f"{CAPTURE}.press-windows.json"
    win_doc = {"format": "rivals-replay-press-windows-v1", "session_id": CAPTURE,
               "clock": "lo_ns/hi_ns: the table's anchor (composition) clock; *_s: the replay capture's file seconds",
               "step_ns": STEP_NS,
               "contract": "a record with cast true says at least one press of `action` lies in [lo, hi]; the table's "
                           "press is null on every step overlapping it. For a pre-registered window-level arm only, "
                           "and only records with complete true",
               "windows": records}
    win_path.write_text(json.dumps(win_doc, indent=1) + "\n", encoding="utf-8")
    h["source"]["press_windows"] = {"path": str(win_path.relative_to(ROOT)).replace("\\", "/"),
                                    "sha256": sha256(win_path)}
    path = out_dir / f"{CAPTURE}.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(h) + "\n")
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    counts = {a: {"positives": sum(1 for p in press if p[vocab.INDEX[a]] == 1),
                  "negatives": sum(1 for p in press if p[vocab.INDEX[a]] == 0),
                  "unknown": sum(1 for p in press if p[vocab.INDEX[a]] is None),
                  "casts_in_events": sum(1 for e in ev["events"] if e["ability"] == CASTS[a] and e["basis"] != "flagged"),
                  "windows": sum(1 for r in records if r["action"] == a and r["cast"]),
                  "windows_complete": sum(1 for r in records if r["action"] == a and r["cast"] and r["complete"]),
                  "windows_complete_lag_measured": sum(1 for r in records if r["action"] == a and r["cast"]
                                                       and r["complete"] and r["lag_measured"]),
                  "flagged_windows": sum(1 for r in records if r["action"] == a and not r["cast"])} for a in CASTS}
    report = {"table": {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)},
              "press_windows": h["source"]["press_windows"],
              "rows": len(rows), "runs": len(runs), "seconds": round(len(rows) * STEP_NS / 1e9, 1),
              "frames": stats, "forgiven_blip_frames": forgiven, "excluded_frames_by_reason": excluded,
              "press_by_action": counts,
              "lags": lag_ranges(lags_doc), "source": h["source"]}
    (out_dir / "build.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return path, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.parse_args(argv)
    path, report = build()
    print(json.dumps({k: report[k] for k in ("table", "rows", "runs", "seconds", "frames", "forgiven_blip_frames",
                                             "excluded_frames_by_reason", "press_by_action")}, indent=1))


if __name__ == "__main__":
    main()
