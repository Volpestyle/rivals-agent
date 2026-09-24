"""scripts/replay_steps.py: the first replay-source step table (DayMR), and its labelling rules.

The rules are tested on synthetic inputs (stdlib only). The table itself is checked where it was built on this machine
(data/ is not committed): it loads through policy.range_bc.steps.load, withheld spans are absent, and the known casts
are the ones counted in build.json. The zero-movement-gradient check runs the fit lane's own machinery (its fake
cache, Batches and loss) on a real slice of the table, and needs torch.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import replay_steps as S  # noqa: E402
from policy.range_bc import steps, vocab  # noqa: E402

TABLE = S.OUT / f"{S.CAPTURE}.jsonl"
BUILD = S.OUT / "build.json"
built = pytest.mark.skipif(not (TABLE.is_file() and BUILD.is_file()), reason="the DayMR replay table was not built here")
STEP = S.STEP_NS


class Identity:
    """File seconds == composition seconds: to_comp for synthetic tests."""

    def __call__(self, t):
        return round(t * 1e9)


# --- labelling rules ----------------------------------------------------------------------------------------------

LAGS = {"web_cluster": {"first_seen": (0.09, 0.10, 0.12), "cooldown_start": None},
        "get_over_here": {"first_seen": (1.0, 1.7, 1.9), "cooldown_start": (0.6, 0.9, 1.0)},
        "teamup": {"first_seen": None, "cooldown_start": None},
        "uppercut": {"first_seen": (0.3, 0.32, 0.47), "cooldown_start": None},
        "ult": {"first_seen": (0.008, 0.008, 0.008), "cooldown_start": None}}


def anchors(t0=10.0, seconds=10.0):
    return [round(t0 * 1e9) + k * STEP for k in range(int(seconds * 1e9 / STEP))]


def test_even_a_window_inside_one_step_is_null_never_a_1():
    """Lead contract (replay-steps-3): a cast's window is unknown on every step it touches, however narrow; the table
    holds no 1. The window itself goes to the press-windows file."""
    events = [{"ability": "web_cluster", "t_lo": 12.49, "t_hi": 12.5, "basis": "transition", "count": 1}]
    lags = {"web_cluster": {"first_seen": (0.095, 0.10, 0.105), "cooldown_start": None}}
    windows = S.press_windows(events, lags)
    (w,) = windows["web_cluster"]
    assert w.lo == pytest.approx(12.49 - 0.105) and w.hi == pytest.approx(12.5 - 0.095) and w.lag_measured
    a = [round(12.38e9) + k * STEP for k in range(-60, 60)]                  # a step boundary just before the window
    press = S.label_rows(a, windows, {"web_cluster": [(a[0] / 1e9, a[-1] / 1e9)]}, Identity())
    c = vocab.INDEX["web_cluster"]
    inside = [k for k in range(len(a)) if a[k] < w.hi * 1e9 and a[k] + STEP > w.lo * 1e9]
    assert len(inside) == 1 and press[inside[0]][c] is None
    assert not any(p[c] == 1 for p in press) and sum(p[c] == 0 for p in press) == len(a) - 2  # the edges: not inside
    (rec,) = S.window_records(windows, a, ["r0"] * len(a), Identity())
    assert rec["action"] == "web_cluster" and rec["cast"] and rec["complete"] and rec["rows"] == [inside[0], inside[0]]
    assert rec["lo_ns"] == round(w.lo * 1e9) and rec["hi_ns"] == round(w.hi * 1e9)


def test_a_window_record_is_complete_only_over_one_runs_consecutive_rows():
    events = [{"ability": "get_over_here", "t_lo": 15.0, "t_hi": 15.04, "basis": "countdown", "count": 1}]
    lags = {"get_over_here": {"first_seen": (1.0, 1.7, 1.9), "cooldown_start": (0.6, 0.9, 1.0)}}
    windows = S.press_windows(events, lags)                                   # press window 14.0-14.44 s
    a = anchors(12.0, 4.0)
    ok = S.window_records(windows, a, ["r0"] * len(a), Identity())
    assert ok[0]["complete"]
    gap = [x for x in a if not 14.2e9 <= x <= 14.3e9]                        # rows missing inside the window
    assert not S.window_records(windows, gap, ["r0"] * len(gap), Identity())[0]["complete"]
    runs = ["r0" if x < 14.2e9 else "r1" for x in a]                          # a run break inside the window
    assert not S.window_records(windows, a, runs, Identity())[0]["complete"]
    late = [x for x in a if x >= 14.1e9]                                      # the rows start inside the window
    assert not S.window_records(windows, late, ["r0"] * len(late), Identity())[0]["complete"]
    assert S.window_records(windows, anchors(20.0, 2.0), ["r0"] * 60, Identity())[0]["rows"] is None


def test_review_r1_a_wide_transition_blocks_from_t_lo_and_places_no_1():
    """The reviewer's ult at 617.063-619.629 s: 307 unread frames between the reads. The press lies in
    [t_lo - Lmax, t_hi - Lmin]; every step there is null, and no 1 is placed (the window spans many steps)."""
    pytest.importorskip("cv2")   # lag_ranges imports perception.replay_hud (cv2); the stdlib suite skips this one
    ult = S.lag_ranges({"abilities": {"ult": {"first_seen_lag_s": {"n": 1, "min": 0.0085, "median": 0.0085,
                                                                   "max": 0.0085},
                                              "cooldown_start_lag_s": {"n": 0}}}})
    lo_lag, _, hi_lag = ult["ult"]["first_seen"]
    assert lo_lag == 0.0 and hi_lag >= 0.0085 + 0.5                            # one sample: +-0.5 s, clamped at 0
    events = [{"ability": "ult", "t_lo": 617.063, "t_hi": 619.629, "basis": "transition", "count": 1}]
    windows = S.press_windows(events, ult)
    (w,) = windows["ultimate"]
    lo, hi = w.lo, w.hi
    assert lo == pytest.approx(617.063 - hi_lag) and hi == pytest.approx(619.629 - lo_lag)
    a = anchors(610.0, 15.0)
    press = S.label_rows(a, windows, {"ult": [(610.0, 625.0)]}, Identity())
    c = vocab.INDEX["ultimate"]
    inside = [k for k in range(len(a)) if a[k] < hi * 1e9 and a[k] + STEP > lo * 1e9]
    assert inside and all(press[k][c] is None for k in inside)                  # the reviewer's 76 false 0s: none
    assert not any(p[c] == 1 for p in press)
    assert any(p[c] == 0 for p in press)                                         # coverage outside it still counts


def test_a_countdown_cast_uses_the_cooldown_start_lag_from_t_lo():
    events = [{"ability": "get_over_here", "t_lo": 15.0, "t_hi": 15.04, "basis": "countdown", "count": 1}]
    lags = {"get_over_here": {"first_seen": (1.0, 1.7, 1.9), "cooldown_start": (0.6, 0.9, 1.0)}}
    (w,) = S.press_windows(events, lags)["get_over_here"]
    assert w.lo == pytest.approx(14.0) and w.hi == pytest.approx(14.44) and w.lag_measured


def test_no_negatives_outside_press_time_coverage_and_none_for_unlabelled_actions():
    a = anchors()
    windows = S.press_windows([], {})
    press = S.label_rows(a, windows, {"get_over_here": [(11.0, 12.0)]}, Identity())
    goh = vocab.INDEX["get_over_here"]
    zeros = [k for k, p in enumerate(press) if p[goh] == 0]
    assert zeros and all(11e9 <= a[k] and a[k] + STEP <= 12e9 for k in zeros)
    for name in ("move_forward", "jump", "web_swing", "simple_swing", "spider_power", "melee", "goh_targeting"):
        assert all(p[vocab.INDEX[name]] is None for p in press)


def test_an_ability_without_a_measured_lag_and_flagged_stretches_are_null():
    events = [{"ability": "teamup", "t_lo": 12.0, "t_hi": 12.02, "basis": "countdown", "count": 1},
              {"ability": "uppercut", "t_lo": 14.0, "t_hi": 14.5, "basis": "flagged", "count": 1}]
    lags = {"teamup": {"first_seen": None, "cooldown_start": None},
            "uppercut": {"first_seen": (0.3, 0.32, 0.47), "cooldown_start": None}}
    windows = S.press_windows(events, lags)
    assert [w.lag_measured for w in windows["team_up"]] == [False]
    assert [w.lag_measured for w in windows["amazing_combo"]] == [False]
    a = anchors()
    press = S.label_rows(a, windows, {"teamup": [(10.0, 20.0)], "uppercut": [(10.0, 20.0)]}, Identity())
    tu, ac = vocab.INDEX["team_up"], vocab.INDEX["amazing_combo"]
    assert not any(p[tu] == 1 or p[ac] == 1 for p in press)
    recs = S.window_records(windows, a, ["r0"] * len(a), Identity())
    assert {(r["action"], r["cast"], r["lag_measured"]) for r in recs} == {("team_up", True, False),
                                                                          ("amazing_combo", False, False)}
    assert all(press[k][ac] is None for k in range(len(a)) if a[k] < 14.5e9 and a[k] + STEP > (14.0 - 0.47) * 1e9)


def frames_of(spec):
    """[(t, why, hp)] from [(n frames, why, hp)] at 120 fps."""
    out, t = [], 0.0
    for n, why, hp in spec:
        for _ in range(n):
            out.append((round(t, 4), why, hp))
            t += 1 / 120
    return out


ON = {s_: {"on_target": True, "timeline_visible": False} for s_ in range(0, 60)}


def test_an_hp_blip_is_forgiven_only_between_frames_read_alive():
    alive = frames_of([(60, None, 250), (10, "dead (hp 0)", None), (60, None, 250)])
    out, forgiven = S.forgive_blips(alive, ON)
    assert forgiven.get("dead (hp 0)") == 10 and all(w is None for _, w in out)
    abstained = frames_of([(60, None, None), (10, "dead (hp 0)", None), (60, None, None)])   # hp unread around it
    out, forgiven = S.forgive_blips(abstained, ON)
    assert "dead (hp 0)" not in forgiven and sum(w is not None for _, w in out) == 10


def test_review_r2_a_death_cam_alternating_with_abstentions_is_out_entirely():
    """The reviewer's 529.96-539.95 s death: the reader alternates hp 0 and abstentions (hp unread) for seconds. The
    hp-0 cluster, widened over every frame not read alive, is out; the alive frames around it stay in."""
    spec = [(120, None, 180)]
    for _ in range(30):                                                        # 5 s of death cam
        spec += [(10, "dead (hp 0)", None), (10, None, None)]
    spec += [(12, "no HUD drawn", None), (120, None, 250)]
    frames = frames_of(spec)
    out, forgiven = S.forgive_blips(frames, ON)
    first_dead = next(t for t, w, _ in frames if w)
    last_dark = max(t for t, w, hp in frames if w or hp is None)
    assert forgiven["death_spans"] == 1
    assert all(w is not None for t, w in out if first_dead <= t <= last_dark)   # abstentions inside: out too
    assert all(w is None for t, w in out if t < first_dead or t > last_dark)    # read-alive frames: in


def test_follow_bar_blips_are_forgiven_only_where_the_route_map_agrees():
    frames = frames_of([(120, None, 200), (240, "viewer not following B5", None), (120, None, 200)])
    out, forgiven = S.forgive_blips(frames, ON)
    assert forgiven.get("viewer not following B5") == 240
    off = {**ON, 2: {"on_target": False, "timeline_visible": False}}
    out, forgiven = S.forgive_blips(frames, off)
    assert "viewer not following B5" not in forgiven


# --- the camera hook ----------------------------------------------------------------------------------------------

def rows_at(a):
    return [{"anchor_ns": x, "yaw_deg": None, "pitch_deg": None, "beyond_pad_envelope": False} for x in a]


CAPTURE_VIDEO = "C:/Users/volpe/Videos/2026-09-23 00-43-25.mkv"
META = {"type": "meta", "video": CAPTURE_VIDEO, "spectator_mask": True, "t_offset": 0.0, "hz": 120}


def pair(k, yaw=0.5, pitch=0.25, source="main", abstain=None):
    return {"t0": 10.0 + k / 120, "t1": 10.0 + (k + 1) / 120, "yaw_deg": yaw, "pitch_deg": pitch, "abstain": abstain,
            "source": source}


def fill(rows, pairs, meta=META, **kw):
    return S.fill_camera(rows, (meta, pairs), Identity(), capture_video=CAPTURE_VIDEO, **kw)


def test_fill_camera_sums_tiling_pairs_and_flips_pitch():
    rows = rows_at(anchors(10.0, 0.2))
    assert fill(rows, [pair(k) for k in range(40)]) == len(rows)
    assert rows[0]["yaw_deg"] == pytest.approx(2.0) and rows[0]["pitch_deg"] == pytest.approx(-1.0)   # down positive
    assert rows[0]["beyond_pad_envelope"] is False


def test_fill_camera_leaves_a_step_unknown_on_abstention_or_a_gap_and_flags_saturation():
    pairs = [pair(k, yaw=4.0, pitch=0.0) for k in range(12) if k != 1]         # a missing pair in step 0
    pairs[5]["abstain"] = "unconfirmed zero"                                   # step 1 has an abstention
    rows = rows_at(anchors(10.0, 0.1))
    fill(rows, pairs)
    assert rows[0]["yaw_deg"] is None and rows[1]["yaw_deg"] is None
    assert rows[2]["yaw_deg"] == pytest.approx(16.0) and rows[2]["beyond_pad_envelope"] is True     # > 13.8 deg/step


def test_fill_camera_honours_the_pair_source():
    """The camera reviewer: "centre" pairs (imprecise, ~0.5 deg) leave their step unknown unless opted in."""
    pairs = [pair(k, source="centre" if k == 1 else "main") for k in range(12)]
    rows = rows_at(anchors(10.0, 0.1))
    assert fill(rows, pairs) == 2 and rows[0]["yaw_deg"] is None and rows[1]["yaw_deg"] == pytest.approx(2.0)
    rows = rows_at(anchors(10.0, 0.1))
    assert fill(rows, pairs, sources=("main", "centre")) == 3


@pytest.mark.parametrize("meta, match", [
    ({**META, "video": "C:/Users/volpe/Videos/2026-09-23 00-18-28.mkv"}, "not this session's capture"),
    ({**META, "spectator_mask": False}, "not the replay run"),
    ({**META, "t_offset": 0.5}, "clock offset"),
    ({k: v for k, v in META.items() if k != "type"}, "meta line"),
])
def test_fill_camera_takes_only_the_estimators_replay_run_for_this_session(meta, match):
    rows = rows_at(anchors(10.0, 0.1))
    with pytest.raises(ValueError, match=match):
        fill(rows, [pair(k) for k in range(12)], meta=meta)
    assert all(r["yaw_deg"] is None for r in rows)


# --- the DayMR table ----------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def table():
    return steps.load(TABLE, denylist=steps.load_denylist(ROOT / steps.DENYLIST))


@built
def test_the_table_loads_through_the_fit_reader(table):
    h = table.header
    assert h["source_kind"] == "replay" and h["expert_context"]["viewer_fov_assumption"] == "viewer, unverified"
    assert h["expert_context"]["player"] == "DayMR" and h["calibration"]["kind"] == "replay_degrees"
    assert "fill_camera" in h["calibration"]["label_sources"]["camera"]
    assert h["split"] == "replay"                                          # never train, val or test
    with pytest.raises(steps.StepError, match="replay-split recording is never train"):
        steps.load_cohort([TABLE], splits=("train",), denylist=steps.load_denylist(ROOT / steps.DENYLIST))


@built
def test_movement_holds_releases_and_camera_are_unknown_everywhere(table):
    moves = [vocab.INDEX[n] for n in ("move_forward", "move_left", "move_back", "move_right", "jump", "web_swing",
                                      "simple_swing", "spider_power", "melee", "goh_targeting")]
    for r in table.rows:
        assert not any(r["held_known"]) and not any(r["release_known"])
        assert all(r["press"][c] is None for c in moves)
        assert r["yaw_deg"] is None and r["pitch_deg"] is None


@built
def test_known_casts_are_the_ones_counted(table):
    report = json.loads(BUILD.read_text(encoding="utf-8"))
    assert report["table"]["sha256"] == steps.sha256(TABLE)
    ev = json.loads((S.HUD / "events.json").read_text(encoding="utf-8"))
    for action, counts in report["press_by_action"].items():
        c = vocab.INDEX[action]
        assert counts["positives"] == 0 and not any(r["press"][c] == 1 for r in table.rows)   # lead contract: no 1
        assert sum(1 for r in table.rows if r["press"][c] == 0) == counts["negatives"]
        casts = sum(1 for e in ev["events"] if e["ability"] == S.CASTS[action] and e["basis"] != "flagged")
        assert counts["windows"] == counts["casts_in_events"] == casts


@built
def test_the_press_windows_file_names_every_cast_and_its_rows_are_unknown(table):
    """Lead contract: the windows file carries [lo, hi, action] per cast; every row a window overlaps is null for
    its action; a complete window's rows are one run's consecutive steps covering it."""
    report = json.loads(BUILD.read_text(encoding="utf-8"))
    path = ROOT / report["press_windows"]["path"]
    assert steps.sha256(path) == report["press_windows"]["sha256"] == table.header["source"]["press_windows"]["sha256"]
    doc = json.loads(path.read_text(encoding="utf-8"))
    anchors = [r["anchor_ns"] for r in table.rows]
    assert doc["session_id"] == S.CAPTURE and doc["windows"]
    for w in doc["windows"]:
        c = vocab.INDEX[w["action"]]
        assert w["lo_ns"] < w["hi_ns"] and w["lo_s"] < w["hi_s"]
        ks = [k for k in range(len(anchors)) if anchors[k] < w["hi_ns"] and anchors[k] + STEP > w["lo_ns"]]
        assert w["rows"] == ([ks[0], ks[-1]] if ks else None)
        assert all(table.rows[k]["press"][c] is None for k in ks), w
        if w["complete"]:
            assert anchors[ks[0]] <= w["lo_ns"] and w["hi_ns"] <= anchors[ks[-1]] + STEP
            assert len({table.rows[k]["run"] for k in ks}) == 1 and ks == list(range(ks[0], ks[-1] + 1))
            assert all(anchors[k] - anchors[k - 1] == STEP for k in ks[1:])


def _independent_frames():
    """Per frame (t, frame-level reason, hp) straight from the reader's rows, without the builder's code."""
    import gzip
    frames = {}
    for f in sorted((S.REPLAY / "hud").glob("rows-*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for line in fh:
                d = json.loads(line)
                slot = frames.setdefault(d["t"], [None, None])
                if d["state"] == "unknown" and d["reason"] and not d["reason"].endswith(("unread", "abstained")):
                    slot[0] = d["reason"]
                if d["ability"] == "hp" and d["state"] == "count":
                    slot[1] = d["numeral"]
    return sorted((t, w, hp) for t, (w, hp) in frames.items())


@built
def test_withheld_spans_are_absent(table):
    """Independent of the builder: no row's frame is another POV, timeline or no HUD beyond the route map's blip rule,
    or in the route map's off-target seconds or an excluded span; each run is one clock."""
    follow = json.loads((S.REPLAY / "route-map" / "followed_player.json").read_text(encoding="utf-8"))
    per_second = {p["s"]: p for p in follow["per_second"]}
    frames = {round(t * 1000): (w, hp) for t, w, hp in _independent_frames()}
    for r in table.rows:
        pts = r["frame"]["pts"]
        why, _ = frames[pts]
        assert why is None or why.startswith("viewer not following"), (r["i"], why)
        t = pts / 1000
        sec = per_second[int(t)]
        assert sec["on_target"] and not sec["timeline_visible"]
        assert not any(a <= t <= b for a, b, _ in S.EXCLUDE)
    report = json.loads(BUILD.read_text(encoding="utf-8"))
    assert report["frames"]["unmapped"] == 0 and report["frames"]["max_residual_ms"] < 1.0


# The reviewer's deaths, confirmed on decoded frames (review-replay-steps.md R2): no row may fall inside one.
PINNED_DEATHS = ((529.96, 539.95), (1213.6, 1214.85), (1335.25, 1335.75), (1477.54, 1477.87))


@built
def test_review_r2_no_row_inside_a_death(table):
    """Independent of the builder's code: hp-0 frames clustered at gaps up to 1 s (at least 30 frames), widened over
    every contiguous frame not read alive (hp > 0 with no frame-level reason), hold no row; nor do the pinned deaths."""
    frames = _independent_frames()
    dead = [k for k, (t, w, hp) in enumerate(frames) if w and w.startswith("dead")]
    spans, cur = [], []
    for k in dead + [None]:
        if k is None or (cur and frames[k][0] - frames[cur[-1]][0] > 1.0):
            if len(cur) >= 30:
                i, j = cur[0], cur[-1]
                while i > 0 and not (frames[i - 1][1] is None and (frames[i - 1][2] or 0) > 0):
                    i -= 1
                while j + 1 < len(frames) and not (frames[j + 1][1] is None and (frames[j + 1][2] or 0) > 0):
                    j += 1
                spans.append((frames[i][0], frames[j][0]))
            cur = []
        if k is not None:
            cur.append(k)
    assert spans
    ts = sorted(r["frame"]["pts"] / 1000 for r in table.rows)
    import bisect
    for a, b in list(spans) + list(PINNED_DEATHS):
        k = bisect.bisect_left(ts, a)
        assert k == len(ts) or ts[k] > b, f"a row at {ts[k]} s inside the death {a}-{b}"


@built
def test_review_r1_no_zero_inside_any_casts_press_window(table):
    """Independent recomputation from events.json: no step overlapping [t_lo - Lmax, t_hi - Lmin] of a cast (floored
    lags) is labelled 0 for its action; the reviewer's ult at 617.063-619.629 s keeps no 0 in its rows."""
    pytest.importorskip("cv2")   # lag_ranges imports perception.replay_hud (cv2); the stdlib suite skips this one
    ev = json.loads((S.HUD / "events.json").read_text(encoding="utf-8"))
    lags = S.lag_ranges(json.loads(S.LAGS.read_text(encoding="utf-8")))
    clock = S.capture_clock()
    to_comp = S.FileToComposition([(v[2] / 1000, v[0]) for v in clock.values()])
    anchors = [r["anchor_ns"] for r in table.rows]
    rev = {v: k for k, v in S.CASTS.items()}
    import bisect
    for e in ev["events"]:
        action = rev.get(e["ability"])
        if action is None:
            continue
        lag = lags[S.LAG_NAME[e["ability"]]]
        r = lag["cooldown_start" if e["basis"] == "countdown" else "first_seen"] or (0.0, 0.0, 2.0)
        a, b = to_comp(e["t_lo"] - r[2]), to_comp(e["t_hi"] - r[0])
        c = vocab.INDEX[action]
        k = max(0, bisect.bisect_left(anchors, a - STEP))
        while k < len(anchors) and anchors[k] < b:
            if anchors[k] + STEP > a:
                assert table.rows[k]["press"][c] != 0, (action, e, table.rows[k]["anchor_ns"])
            k += 1
    c = vocab.INDEX["ultimate"]
    assert not any(r["press"][c] == 0 for r in table.rows if 617071 <= r["frame"]["pts"] <= 619571)


@built
def test_a_real_slice_gives_zero_movement_and_camera_gradient(table, tmp_path):
    torch = pytest.importorskip("torch")
    from policy.range_bc import cache, train
    from test_range_bc_torch import fake_cache
    # the run holding the most known press labels, at most 1000 rows, renumbered into a valid table of its own
    by_run = {}
    for r in table.rows:
        by_run.setdefault(r["run"], []).append(r)
    run = max(by_run.values(), key=lambda rs: sum(v is not None for r in rs for v in r["press"]))[:1000]
    rows = [dict(r, i=k) for k, r in enumerate(run)]
    path = tmp_path / f"{S.CAPTURE}.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in [table.header] + rows) + "\n", encoding="utf-8")
    session = steps.load(path)
    fake_cache(tmp_path / "caches" / "slice", session)
    arr = train.SessionArrays(session, cache.open_cache(tmp_path / "caches" / "slice", session))
    batches = train.Batches([arr])
    assert batches.windows
    moves = [vocab.INDEX[n] for n in ("move_forward", "move_left", "move_back", "move_right", "jump", "web_swing")]
    casts = [vocab.INDEX[n] for n in S.CASTS]
    grad_on_casts = 0.0
    for w in range(len(batches.windows)):
        b = batches.batch([w])
        assert not b["act_mask"][..., moves].any() and not b["camera_mask"].any()
        acts = torch.zeros(1, b["act"].shape[1], 3, vocab.N, requires_grad=True)
        cams = torch.zeros(1, b["act"].shape[1], 2, vocab.CAMERA_CLASSES, requires_grad=True)
        train.total_loss(train.loss_terms(acts, cams, b, torch.ones(2, vocab.N))).backward()
        assert acts.grad[..., moves].abs().sum() == 0 and cams.grad.abs().sum() == 0
        grad_on_casts += float(acts.grad[:, :, 1][..., casts].abs().sum())
    assert grad_on_casts > 0                                   # the known cast labels do reach the loss
