"""scripts/place.py without a game: dry mode on a fake capture, replay on recorded and simulated finder output, the
live gate's refusals, and the live loop on a fake Live whose pad moves the simulated lane.

Stdlib only; no pad, no capture, no display. tests/test_place_frames.py replays the real slot archives and stills
from pixels where they are present. These tests pin the driver's contract with agent.placement: PITCH_RESET and
EDGE_X_M, which live refuses while unmeasured, the M1 camera prime before any planner pulse, and --measure-pitch on a
simulated camera.
"""
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import place  # noqa: E402
from agent import placement as P  # noqa: E402
from agent import placement_sim as sim  # noqa: E402

FRAMES = json.loads((ROOT / "tests/fixtures/placement/frames.json").read_text(encoding="utf-8"))


class LanePerception:
    """The loop's reader interface over a simulated lane: frames are tokens, boxes come from the lane."""

    def __init__(self, lane, in_range=True):
        self.lane, self.range_ok = lane, in_range

    def size(self, frame):
        return (2560, 1440)

    def wide(self, frame):
        return [SimpleNamespace(bbox=tuple(b)) for b in self.lane.boxes()]

    def in_range(self, frame):
        return self.range_ok


class TokenCapture:
    def grab(self):
        return object()


@pytest.fixture
def measured_pitch(monkeypatch):
    monkeypatch.setattr(place, "PITCH_DOWN_S", 0.1)
    monkeypatch.setattr(place, "PITCH_UP_S", 0.1)


@pytest.fixture
def measured(monkeypatch, measured_pitch):
    """Everything live needs from James's session, set as if measured (values are placeholders, not findings)."""
    monkeypatch.setattr(P, "EDGE_X_M", 4.5)


# --- pulses -----------------------------------------------------------------------------------------------------

def test_every_action_maps_to_bounded_sticks_and_no_button(measured_pitch):
    for act in (P.Action("TURN", 60.0), P.Action("TURN", -15.0), P.Action("WALK", 0.4), P.Action("WALK", -0.4),
                P.Action("STRAFE", 0.3), P.Action("STRAFE", -0.05), P.Action("PITCH_RESET")):
        steps = place.pulse_for(act)
        assert steps
        for pad, secs in steps:
            assert len(pad) == 1 and "buttons" not in pad and set(pad) <= {"rx", "ry", "ly", "lx"}
            assert secs <= max(P.turn_seconds(act.value), P.PULSE_S, 0.1) + 1e-9
    assert place.pulse_for(P.Action("TURN", 60.0))[0][1] == pytest.approx(60 / 172.0)
    assert place.pulse_for(P.Action("READY")) == [] and place.pulse_for(P.Action("HAND_BACK")) == []
    assert place.pulse_for(P.Action("PITCH_RESET")) == [({"ry": -1.0}, 0.1), ({"ry": place.PITCH_UP_STICK}, 0.1)]


def test_the_hold_refuses_keys_outside_its_allowance():
    live = FakeLive(sim.Lane(0, -20, 0))
    with pytest.raises(place.Refused, match="outside"):
        place._hold(live, [({"ly": 1.0}, 0.2)], lambda f: None, clock=Clock(), sleep=lambda s: None,
                    allowed=frozenset({"ry"}))
    assert live.sent == [] and live.releases == 1


def test_an_unmeasured_pitch_reset_is_refused():
    with pytest.raises(place.Refused, match="unmeasured"):
        place.pulse_for(P.Action("PITCH_RESET"))


# --- dry --------------------------------------------------------------------------------------------------------

def test_dry_prints_what_it_would_send_and_sends_nothing():
    lane = sim.Lane(x=0.0, y=-20.0, heading_deg=0.0)
    out = []
    lines = place.dry(TokenCapture(), LanePerception(lane), "mid", steps=3, sleep=lambda s: None, out=out.append)
    assert lines and all(l["sent"] is False for l in lines) and all(o.startswith("DRY ") for o in out)
    assert lines[0]["action"] == "PITCH_RESET" and "unmeasured" in lines[0]["would_send"]
    assert lines[0]["view"] == "UNLEVELLED" and lines[0]["pose"] is None
    assert lane.moves == []


def test_dry_plans_each_decision_from_a_fresh_state():
    """Nothing moved, so no decision may inherit a state that believes the last printed move happened."""
    lane = sim.Lane(x=0.0, y=-24.0, heading_deg=0.0)
    lines = place.dry(TokenCapture(), LanePerception(lane), "mid", steps=4, sleep=lambda s: None, out=lambda s: None,
                      assume_level=True)
    lane.pitch_reset()
    first = lines[0]
    assert all((l["action"], l["value"]) == (first["action"], first["value"]) for l in lines)
    assert first["pose"] is not None and first["action"] in ("WALK", "TURN") and lane.moves == []


def test_dry_assume_level_is_what_gives_a_pose():
    lane = sim.Lane(x=0.0, y=-24.0, heading_deg=0.0)
    plain = place.dry(TokenCapture(), LanePerception(lane), "mid", sleep=lambda s: None, out=lambda s: None)
    level = place.dry(TokenCapture(), LanePerception(lane), "mid", sleep=lambda s: None, out=lambda s: None,
                      assume_level=True)
    assert plain[0]["pose"] is None and plain[0]["assume_level"] is False
    assert level[0]["pose"] is not None and level[0]["assume_level"] is True and level[0]["sent"] is False


def test_dry_save_keeps_frames_and_lines(tmp_path):
    written = []
    lane = sim.Lane(x=0.0, y=-24.0, heading_deg=0.0)
    place.dry(TokenCapture(), LanePerception(lane), "mid", steps=2, sleep=lambda s: None, out=lambda s: None,
              save=tmp_path / "look", imwrite=lambda path, f: written.append(Path(path).name))
    rows = [json.loads(l) for l in (tmp_path / "look" / "dry.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2 and rows[1]["frames"] == ["001-0.jpg", "001-1.jpg", "001-2.jpg"]
    assert written == [n for r in rows for n in r["frames"]]
    with pytest.raises(FileExistsError):                          # never into an existing folder
        place.dry(TokenCapture(), LanePerception(lane), "mid", sleep=lambda s: None, out=lambda s: None,
                  save=tmp_path / "look", imwrite=lambda path, f: None)


def test_dry_on_the_lower_plaza_never_moves():
    lane = sim.Lane(x=5.5, y=-12.0, heading_deg=0.0)
    lane.fallen = True
    lines = place.dry(TokenCapture(), LanePerception(lane), "mid", steps=8, sleep=lambda s: None, out=lambda s: None)
    assert {l["action"] for l in lines} <= {"PITCH_RESET", "TURN", "HAND_BACK"}


def test_dry_refuses_when_capture_delivers_nothing():
    cap = SimpleNamespace(grab=lambda: None)
    with pytest.raises(place.Refused, match="no frame"):
        place.dry(cap, LanePerception(sim.Lane(0, -20, 0)), "mid", sleep=lambda s: None, out=lambda s: None)


# --- replay -----------------------------------------------------------------------------------------------------

def test_replay_of_recorded_frames_of_unknown_pitch_never_moves_and_compares_nothing():
    records = [(r["size"], r["boxes"], r["in_range"]) for r in FRAMES]
    report = place.replay(records, "mid", window=1)
    assert report["compared"] == 0 and report["moves_without_pose"] == []
    assert set(report["actions"]) <= {"PITCH_RESET", "TURN", "HAND_BACK"}
    assert not report["ok"] and report["why"] == "nothing compared"            # review D2: no vacuous pass
    assert place.replay(records, "mid", window=1, allow_none=True)["ok"]


def test_replay_says_what_it_compared():
    report = place.replay([((2560, 1440), sim.render(0.0, -20.0, 20.0), True)] * 3, "mid", pitch_ref=True)
    assert "circular" in report["method"] and "FIRST action" in report["method"]
    assert report["compared_pose"] == 1 and report["compared_label"] == 0


def test_replay_at_the_reference_pitch_agrees_with_the_simulator():
    """The recorded frames treated as if at the reference pitch (the low-pitch cluster levels): each posed decision is
    checked against the simulator rendered at its central pose (circular: planner consistency only)."""
    records = [(r["size"], r["boxes"], r["in_range"]) for r in FRAMES for _ in range(3)]
    report = place.replay(records, "mid", window=3, pitch_ref=True)
    assert report["moves_without_pose"] == [] and report["compared"] >= 5
    assert report["ok"], report["mismatches"][:3]


def test_replay_of_simulated_runs_including_flicker_agrees_with_their_true_positions():
    """Labelled by the simulator's true position: the independent basis, not the pose from the same boxes."""
    for start, bin_ in (((0.0, -20.0, 0.0), "mid"), ((1.5, -24.5, 4.0), "far"), ((-1.0, -15.0, -10.0), "mid")):
        lane = sim.Lane(*start, flicker=0.2, seed=3)
        lane.pitch_reset()
        records, state = [], P.PlanState(bin_, pitched=True, pitch_resets=1)
        for _ in range(60):
            label = {"x": lane.x, "y": lane.y, "heading_deg": lane.heading}
            window = [((2560, 1440), lane.boxes(), True, label) for _ in range(3)]
            records += window
            act, state = P.plan(state, P.decide([P.classify(*w[:3], True) for w in window]))
            if act.kind in ("READY", "HAND_BACK"):
                break
            lane.act(act)
        report = place.replay(records, bin_, pitch_ref=True)
        assert report["ok"], report["mismatches"][:3]
        assert report["compared_label"] >= 1 and report["compared_pose"] == 0


def test_replay_fails_a_label_outside_the_feasible_set():
    """A pose that is wrong but self-consistent: the circular check passes it, the label check does not."""
    boxes = sim.render(1.0, -18.0, 0.0)
    circular = place.replay([((2560, 1440), boxes, True)] * 3, "mid", pitch_ref=True)
    wrong = {"x": -3.0, "y": -12.0, "heading_deg": 0.0}
    labelled = place.replay([((2560, 1440), boxes, True, wrong)] * 3, "mid", pitch_ref=True)
    assert circular["ok"] and not labelled["ok"]
    assert any("feasible" in m.get("why", "") for m in labelled["mismatches"])


def test_replay_reports_a_disagreement_instead_of_hiding_it(monkeypatch):
    records = [((2560, 1440), sim.render(0.0, -20.0, 20.0), True)] * 3
    real_plan = P.plan
    calls = {"n": 0}

    def skewed(state, view, dt=0.0):
        calls["n"] += 1
        act, st = real_plan(state, view, dt)
        return (P.Action("TURN", act.value + 30.0, "skewed") if calls["n"] % 2 == 1 else act), st

    monkeypatch.setattr(place.P, "plan", skewed)
    report = place.replay(records, "mid", pitch_ref=True)
    assert not report["ok"] and report["mismatches"]


def test_main_replay_exits_2_when_nothing_was_compared(tmp_path, monkeypatch, capsys):
    import agent.loop
    monkeypatch.setattr(agent.loop, "default_perception", lambda: None)
    monkeypatch.setattr(place, "records_from_images", lambda *a, **k: [((2560, 1440), [], True)] * 3)
    monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace(imread=lambda p: None))
    assert place.main(["--replay", str(tmp_path)]) == 2 and "nothing compared" in capsys.readouterr().out
    assert place.main(["--replay", str(tmp_path), "--allow-none"]) == 0


# --- the declarations -------------------------------------------------------------------------------------------

NOW = datetime(2026, 9, 24, 18, 30, tzinfo=timezone.utc)
STARTED = "2026-09-24T17:00:00.0000000Z"


def _pin(path, text):
    path.write_text(text, encoding="utf-8")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _entry(tmp_path, pid=10668, entered="2026-09-24T18:00:00+00:00", started=STARTED):
    record = _pin(tmp_path / "entry.json", json.dumps({"game_pid": pid, "entered_utc": entered,
                                                        "process_started_utc": started}))
    return {"entered_utc": entered, "binding_id": record["sha256"], "record": record}


def _common(tmp_path, mode, **over):
    entry = over.pop("range_entry", None) or _entry(tmp_path)
    auth_text = over.pop("auth_text", None) or json.dumps(
        {"kind": place.AUTH_KIND, "binding_id": entry["binding_id"], "modes": [mode]})
    return {"game_pid": 10668, "range_entry": entry, "issued_utc": "2026-09-24T18:05:00+00:00",
            "expires_utc": "2026-09-24T19:00:00+00:00", "authorization": _pin(tmp_path / "auth.txt", auth_text),
            **over}


def _write(tmp_path, d):
    path = tmp_path / "decl.json"
    path.write_text(json.dumps(d), encoding="utf-8")
    return path


FINDINGS = {"strafe_m_per_s": 3.7, "lane_half_width_m": 4.5, "pitch_down_s": 0.1, "pitch_up_s": 0.1, "edge_x_m": 4.5}


def _declaration(tmp_path, findings=None, sign=None, look=None, range_entry=None, auth_text=None, **top):
    ev = _pin(tmp_path / "look.txt", "placement look: lane edges, strafe, drop, three states")
    findings = dict(FINDINGS if findings is None else findings)
    sign = sign if sign is not None else f"reviewed: findings {place.findings_sha256(findings)} evidence {ev['sha256']}"
    d = _common(tmp_path, "live", range_entry=range_entry, auth_text=auth_text,
                supervised_look={"done": True, "evidence": [ev], "findings": findings,
                                 "countersignature": _pin(tmp_path / "countersign.txt", sign)})
    d.update({"kind": place.DECLARATION_KIND, "target_bin": "mid", **top})
    d["supervised_look"].update(look or {})
    return _write(tmp_path, d)


def GAME(pid):
    return {"name": place.GAME_EXE, "started_utc": STARTED}


def _check(path):
    return place.check_declaration(path, process_info=GAME, now=NOW)


@pytest.mark.parametrize("unset", ["PITCH_DOWN_S", "PITCH_UP_S", "EDGE_X_M"])
def test_the_live_gate_refuses_while_anything_is_unmeasured(tmp_path, measured, monkeypatch, unset):
    monkeypatch.setattr(P if unset == "EDGE_X_M" else place, unset, None)
    with pytest.raises(place.Refused, match="unmeasured.*" + unset):
        _check(_declaration(tmp_path))


def test_today_the_live_gate_refuses_every_declaration(tmp_path):
    """As committed, nothing is measured: no declaration, however complete, passes."""
    assert place.unmeasured() == ["place.PITCH_DOWN_S", "place.PITCH_UP_S", "agent.placement.EDGE_X_M"]
    with pytest.raises(place.Refused, match="unmeasured"):
        _check(_declaration(tmp_path))


def test_a_complete_declaration_passes_and_is_pinned(tmp_path, measured):
    d = _check(_declaration(tmp_path))
    assert d["game_pid"] == 10668 and len(d["sha256"]) == 64 and d["binding_id"] == d["range_entry"]["record"]["sha256"]


@pytest.mark.parametrize("over, match", [
    ({"kind": "other"}, "kind"),
    ({"game_pid": "10668"}, "positive integer"),
    ({"look": {"done": False}}, "not recorded as done"),
    ({"look": {"evidence": []}}, "no evidence"),
    ({"look": {"evidence": [{"path": "C:/nope.txt", "sha256": "0" * 64}]}}, "missing or changed"),
    ({"findings": {"strafe_m_per_s": 3.7}}, "findings must give"),
    ({"findings": {**FINDINGS, "strafe_m_per_s": 2.0}}, "strafe 2.0 m/s differs"),
    ({"findings": {**FINDINGS, "lane_half_width_m": 3.6}}, "no margin"),
    ({"findings": {k: v for k, v in FINDINGS.items() if k != "edge_x_m"}}, "must give edge_x_m"),
    ({"findings": {**FINDINGS, "pitch_up_s": 0.3}}, "pitch_up_s 0.3 differs"),
    ({"findings": {**FINDINGS, "edge_x_m": 5.0}}, "edge_x_m 5.0 differs"),
    ({"target_bin": "point-blank"}, "target_bin"),
    ({"target_bin": "far"}, "far is not piloted"),
    # D3: the look is countersigned, not self-attested
    ({"sign": "looks fine to me"}, "countersignature must quote"),
    ({"look": {"countersignature": {"path": "C:/nope.txt", "sha256": "0" * 64}}}, "countersignature missing"),
    # D3: one range entry, one window
    ({"issued_utc": "2026-09-24T17:30:00+00:00"}, "at or after the range entry"),
    ({"expires_utc": "2026-09-24T20:00:00+00:00"}, "exceeds 3600"),
    ({"expires_utc": "2026-09-24T18:20:00+00:00"}, "not valid now"),
    ({"issued_utc": "2026-09-24T18:05:00"}, "UTC offset"),
    ({"auth_text": "lead authorizes live"}, "not free text"),
])
def test_the_live_gate_refuses(tmp_path, measured, over, match):
    over = dict(over)
    if over.get("findings") is not None and "sign" not in over:
        over["sign"] = None
    with pytest.raises(place.Refused, match=match):
        _check(_declaration(tmp_path, **over))


def test_a_findings_change_after_countersigning_is_refused(tmp_path, measured):
    ev_sign = _declaration(tmp_path)
    d = json.loads(ev_sign.read_text(encoding="utf-8"))
    d["supervised_look"]["findings"]["edge_x_m"] = 4.52                     # within tolerance, but not what was signed
    with pytest.raises(place.Refused, match="countersignature must quote"):
        _check(_write(tmp_path, d))


@pytest.mark.parametrize("entry_over, info, match", [
    ({"binding_id": "0" * 64}, None, "binding_id must be"),
    ({"entered_utc": "2026-09-24T18:01:00+00:00"}, None, "different game PID or entry time"),
    ({}, {"name": place.GAME_EXE, "started_utc": "2026-09-24T17:40:00Z"}, "restart or PID reuse"),
    ({}, {"name": "notepad", "started_utc": STARTED}, "is not the running"),
    ({}, None, None),
])
def test_the_range_entry_binding(tmp_path, measured, entry_over, info, match):
    entry = {**_entry(tmp_path), **entry_over}
    path = _declaration(tmp_path, range_entry=entry)
    process_info = (lambda pid: info) if info else GAME
    if match is None:
        assert place.check_declaration(path, process_info=process_info, now=NOW)["binding_id"] == entry["binding_id"]
        return
    with pytest.raises(place.Refused, match=match):
        place.check_declaration(path, process_info=process_info, now=NOW)


def test_a_record_that_names_another_pid_is_refused(tmp_path, measured):
    with pytest.raises(place.Refused, match="different game PID"):
        _check(_declaration(tmp_path, range_entry=_entry(tmp_path, pid=999)))


def test_an_entry_before_the_process_started_is_refused(tmp_path, measured):
    entry = _entry(tmp_path, entered="2026-09-24T16:00:00+00:00")
    with pytest.raises(place.Refused, match="before the game process started"):
        _check(_declaration(tmp_path, range_entry=entry, issued_utc="2026-09-24T18:05:00+00:00"))


def test_a_missing_declaration_is_refused(measured):
    with pytest.raises(place.Refused, match="--declaration"):
        place.check_declaration(None, process_info=GAME, now=NOW)


# --- the measurement declaration (review D1) ---------------------------------------------------------------------

def _measurement(tmp_path, mode="measure-pitch", **over):
    d = _common(tmp_path, mode)
    d.update({"kind": place.MEASURE_DECLARATION_KIND, "modes": [mode], "james_present_recording": True, **over})
    return _write(tmp_path, d)


def test_a_complete_measurement_declaration_passes(tmp_path):
    d = place.check_measurement_declaration(_measurement(tmp_path), "measure-pitch", process_info=GAME, now=NOW)
    assert d["binding_id"] == d["range_entry"]["record"]["sha256"]


@pytest.mark.parametrize("over, mode, match", [
    ({"kind": place.DECLARATION_KIND}, "measure-pitch", "kind"),
    ({}, "reset-check", "modes must include 'reset-check'"),
    ({"modes": ["measure-pitch", "live"]}, "measure-pitch", "name only"),
    ({"james_present_recording": False}, "measure-pitch", "James present"),
    ({"expires_utc": "2026-09-24T18:10:00+00:00"}, "measure-pitch", "not valid now"),
    ({"game_pid": 4242}, "measure-pitch", "different game PID"),
])
def test_the_measurement_gate_refuses(tmp_path, over, mode, match):
    with pytest.raises(place.Refused, match=match):
        place.check_measurement_declaration(_measurement(tmp_path, **over), mode, process_info=GAME, now=NOW)


def test_the_measurement_authorization_must_name_the_mode(tmp_path):
    d = json.loads(_measurement(tmp_path).read_text(encoding="utf-8"))
    d["authorization"] = _pin(tmp_path / "auth2.txt", json.dumps(
        {"kind": place.AUTH_KIND, "binding_id": d["range_entry"]["binding_id"], "modes": ["reset-check"]}))
    with pytest.raises(place.Refused, match="does not list the mode 'measure-pitch'"):
        place.check_measurement_declaration(_write(tmp_path, d), "measure-pitch", process_info=GAME, now=NOW)


def test_review_e1_free_text_that_mentions_live_does_not_authorize_live(tmp_path, measured):
    """The reviewer's case: a measurement authorization in prose, naming the binding and saying 'No live input is
    authorized', passed the old substring check for live. Free text is now refused outright."""
    entry = _entry(tmp_path)
    text = (f"Measurement session for range entry {entry['binding_id']}: measure-pitch and reset-check only. "
            "No live input is authorized.")
    with pytest.raises(place.Refused, match="not free text"):
        _check(_declaration(tmp_path, range_entry=entry, auth_text=text))


@pytest.mark.parametrize("auth, match", [
    ({"binding_id": "B", "modes": ["measure-pitch", "reset-check"]}, "does not list the mode 'live'"),
    ({"binding_id": "B", "modes": "live"}, "must be a list"),
    ({"binding_id": "B", "modes": ["live-ish"]}, "must be a list drawn from"),
    ({"binding_id": "B", "modes": ["No live input is authorized"]}, "must be a list drawn from"),
    ({"binding_id": "0" * 64, "modes": ["live"]}, "different range entry"),
    ({"kind": "other", "binding_id": "B", "modes": ["live"]}, "kind must be"),
    (["live"], "kind must be"),
])
def test_the_live_authorization_is_exact_membership(tmp_path, measured, auth, match):
    entry = _entry(tmp_path)
    if isinstance(auth, dict):
        auth = {"kind": place.AUTH_KIND, **auth}
        if auth.get("binding_id") == "B":
            auth["binding_id"] = entry["binding_id"]
    with pytest.raises(place.Refused, match=match):
        _check(_declaration(tmp_path, range_entry=entry, auth_text=json.dumps(auth)))


def test_one_authorization_may_list_several_modes(tmp_path, measured):
    entry = _entry(tmp_path)
    auth = json.dumps({"kind": place.AUTH_KIND, "binding_id": entry["binding_id"], "modes": ["measure-pitch", "live"]})
    assert _check(_declaration(tmp_path, range_entry=entry, auth_text=auth))["binding_id"] == entry["binding_id"]


# --- main refuses before any pad opens ---------------------------------------------------------------------------

class _FixedNow(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


@pytest.fixture
def no_pad(monkeypatch):
    """main() with no pad (Live fails the test if constructed) and the clock at NOW."""
    import agent.controller
    monkeypatch.setattr(agent.controller, "Live", lambda *a, **k: pytest.fail("Live must not open"))
    monkeypatch.setattr(place, "datetime", _FixedNow)


@pytest.mark.parametrize("setup", ["as committed", "pid not the game", "bin differs", "expired"])
def test_main_live_refuses_before_opening_anything(tmp_path, monkeypatch, capsys, no_pad, setup):
    monkeypatch.setattr(place, "_process_info",
                        lambda pid: {"name": "notepad", "started_utc": STARTED} if setup == "pid not the game"
                        else GAME(pid))
    if setup != "as committed":
        monkeypatch.setattr(place, "PITCH_DOWN_S", 0.1)
        monkeypatch.setattr(place, "PITCH_UP_S", 0.1)
        monkeypatch.setattr(P, "EDGE_X_M", 4.5)
    over = {"expires_utc": "2026-09-24T18:06:00+00:00"} if setup == "expired" else {}
    bin_ = "near" if setup == "bin differs" else "mid"
    assert place.main(["--live", "--declaration", str(_declaration(tmp_path, **over)), "--bin", bin_]) == 2
    out = capsys.readouterr().out
    assert "REFUSED" in out and {"as committed": "unmeasured", "pid not the game": "is not the running",
                                 "bin differs": "differs from the declaration",
                                 "expired": "not valid now"}[setup] in out


@pytest.mark.parametrize("argv, match", [
    (["--measure-pitch"], "needs --declaration"),
    (["--measure-pitch", "--declaration", "LIVE"], "kind must be placement-measurement"),
    (["--measure-pitch", "--declaration", "RESET"], "modes must include 'measure-pitch'"),
])
def test_main_measure_pitch_needs_its_declaration(tmp_path, monkeypatch, capsys, no_pad, argv, match):
    monkeypatch.setattr(place, "_process_info", GAME)
    paths = {"LIVE": lambda: str(_declaration(tmp_path)),
             "RESET": lambda: str(_measurement(tmp_path, "reset-check"))}
    argv = [paths[a]() if a in paths else a for a in argv]
    assert place.main(argv) == 2 and match in capsys.readouterr().out


# --- the live loop on a fake Live -------------------------------------------------------------------------------

class FakeLive:
    """Live's surface (fresh, send, release) over the simulated lane: each 50 ms write moves the lane."""

    def __init__(self, lane):
        self.lane = lane
        self.sent, self.releases = [], 0

    def fresh(self):
        return object()

    def send(self, **pad):
        self.sent.append(pad)
        dt = place.WRITE_EVERY_S
        if "rx" in pad:
            self.lane.turn(math.copysign(P.YAW_DEG_PER_S * dt, pad["rx"]))
        if "ry" in pad and pad["ry"] > 0:
            self.lane.pitch_reset()
        if "ly" in pad:
            self.lane.walk(math.copysign(dt, pad["ly"]))
        if "lx" in pad:
            self.lane.strafe(math.copysign(dt, pad["lx"]))

    def release(self):
        self.releases += 1


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def _run(lane, bin_="mid", **kw):
    clock, log = Clock(), []
    live = FakeLive(lane)
    kw.setdefault("focused", lambda: True)
    result = place.run_live(live, LanePerception(lane), bin_, idle=lambda f: False, log=log.append,
                            clock=clock, sleep=clock.sleep, **kw)
    return result, live, log


@pytest.mark.parametrize("partly", [False, True])
def test_live_loop_refuses_while_unmeasured_before_any_write(monkeypatch, partly):
    if partly:                                                   # the pitch measured, the edge not
        monkeypatch.setattr(place, "PITCH_DOWN_S", 0.1)
        monkeypatch.setattr(place, "PITCH_UP_S", 0.1)
    lane = sim.Lane(x=0.0, y=-20.0, heading_deg=0.0)
    result, live, _ = _run(lane)
    assert result["result"] == "STOPPED" and "unmeasured" in result["reason"] and "EDGE_X_M" in result["reason"]
    assert live.sent == [] and lane.moves == []


def test_the_prime_is_a_camera_turn_before_any_planner_pulse(measured):
    """M1's pulse (right stick +0.45 for 0.3 s) ends the attach drift; nothing else is sent until the settle is over."""
    from agent.startup import START_SETTLE_S, START_TURN_RX, START_TURN_S
    lane = sim.Lane(x=0.0, y=-20.0, heading_deg=0.0)
    result, live, log = _run(lane)
    n = math.ceil(START_TURN_S / place.WRITE_EVERY_S - 1e-9)
    assert live.sent[:n] == [{"rx": START_TURN_RX}] * n and live.sent[n] != {"rx": START_TURN_RX}
    assert log[0] == {"step": "prime", "writes": n} and set(live.sent[n]) == {"ry"}   # then the planner's PITCH_RESET
    assert START_SETTLE_S >= 4.3                                 # M1: the device-switch banner ended 4.2-4.3 s after


def test_the_prime_stops_on_a_failed_proof(measured):
    lane = sim.Lane(x=0.0, y=-20.0, heading_deg=0.0)
    calls = {"n": 0}

    def focused():
        calls["n"] += 1
        return calls["n"] < 3

    result, live, log = _run(lane, focused=focused)
    assert result["result"] == "STOPPED" and "foreground" in result["reason"] and log[0]["step"] == "prime"
    assert set().union(*live.sent) <= {"rx"} and live.releases >= 1


def test_live_loop_places_from_the_25_m_end(measured):
    lane = sim.Lane(x=0.0, y=-20.0, heading_deg=0.0)
    result, live, log = _run(lane)
    assert result["result"] == "READY" and not lane.fallen, result
    assert all(set(p) <= {"rx", "ry", "ly", "lx"} for p in live.sent)
    moves = [e for e in log if e.get("action") in ("WALK", "STRAFE")]
    assert moves and all(e["pose"] is not None for e in moves)           # no move without a pose


def test_live_loop_from_the_slot3_end_never_falls(measured):
    lane = sim.Lane(x=3.0, y=-2.2, heading_deg=-35.0)
    result, live, log = _run(lane)
    assert not lane.fallen and result["result"] in ("READY", "HAND_BACK", "STOPPED"), result
    assert live.releases >= sum(1 for e in log if "writes" in e)


def test_focus_loss_mid_pulse_is_the_kill_switch(measured):
    lane = sim.Lane(x=0.0, y=-24.0, heading_deg=0.0)
    state = {"n": 0}

    def focused():
        state["n"] += 1
        return state["n"] < 60                                   # past the prime and its settle, into the planner

    result, live, log = _run(lane, focused=focused)
    assert result["result"] == "STOPPED" and "foreground" in result["reason"]
    assert live.releases >= 1 and log[-1].get("stop")


def test_the_range_hud_going_away_stops_before_any_write(measured):
    lane = sim.Lane(x=0.0, y=-24.0, heading_deg=0.0)
    clock = Clock()
    live = FakeLive(lane)
    result = place.run_live(live, LanePerception(lane, in_range=False), "mid", focused=lambda: True,
                            idle=lambda f: False, log=lambda e: None, clock=clock, sleep=clock.sleep)
    assert result["result"] == "STOPPED" and live.sent == []


def test_the_executor_refuses_a_move_without_a_pose():
    live = FakeLive(sim.Lane(0, -20, 0))
    with pytest.raises(place.Refused, match="without a pose"):
        place.execute(live, P.Action("WALK", 0.4), P.View("NEAR_ONE", h=0.4), proof=lambda f: None)
    assert live.sent == [] and live.releases == 1


# --- measure-pitch on a simulated camera ------------------------------------------------------------------------

class PitchCamera:
    """A camera with a pitch: stick rates from the l4 map (99 deg/s full, 43 at half), a floor clamp, and the pair
    rendered by the simulator at the resulting offset. `ref_deg` is where the level fit's reference sits above the
    clamp; `lag_writes` drops the first writes of each stick segment (the ramp) so the measurement must absorb it. A
    callable `lag_writes` is drawn afresh per segment: a reset whose landing pitch varies from one run to the next."""

    PX_PER_DEG = 930 * math.tan(math.radians(1.0))

    def __init__(self, ref_deg=60.0, top_deg=170.0, lag_writes=1):
        self.draw = lag_writes if callable(lag_writes) else (lambda: lag_writes)
        self.pitch, self.ref, self.top, self.lag = 95.0, ref_deg, top_deg, 0
        self.sent, self.releases, self.run, self.last = [], 0, 0, None

    def fresh(self):
        return object()

    def send(self, **pad):
        self.sent.append(pad)
        if pad != self.last:                                     # a new segment: the stick ramps again
            self.run, self.lag, self.last = 0, self.draw(), pad
        self.run += 1
        if self.run <= self.lag:
            return
        v = pad.get("ry", 0.0)
        rate = 99.0 if abs(v) >= 0.99 else 43.0 * abs(v) / 0.5
        self.pitch = min(self.top, max(0.0, self.pitch + math.copysign(rate * place.WRITE_EVERY_S, v)))

    def release(self):
        self.releases += 1
        self.last = None

    def boxes(self):
        px = (self.pitch - self.ref) * self.PX_PER_DEG
        return [b for b in sim.render(0.0, -20.0, 0.0, pitch_px=px) if b[3] > 0 and b[1] < 1440]


class PitchPerception:
    def __init__(self, cam):
        self.cam = cam

    def size(self, frame):
        return (2560, 1440)

    def wide(self, frame):
        return [SimpleNamespace(bbox=tuple(b)) for b in self.cam.boxes()]

    def in_range(self, frame):
        return True


def _measure(cam, **kw):
    clock = Clock()
    return place.measure_pitch(cam, PitchPerception(cam), lambda f: None, clock=clock, sleep=clock.sleep,
                               log=lambda s: None, **kw)


def test_measure_pitch_finds_the_reference_and_sends_only_the_right_stick_y():
    cam = PitchCamera()
    report = _measure(cam)
    assert report["ok"], report["why"]
    assert report["pitch_down_s"] == place.MEASURE_DOWN_S and report["pitch_up_s"] in place.MEASURE_UP_GRID_S
    lo, hi = P.LEVEL_RESIDUAL_PX
    assert all(lo <= r["residual_px"] <= hi for r in report["repeats"])
    assert set().union(*cam.sent) == {"ry"}                        # a camera measurement: never a translation
    # the chosen durations, run as the planner's PITCH_RESET from any pitch, level the pair
    for start in (0.0, 95.0, 170.0):
        cam.pitch, clock = start, Clock()
        place._hold(cam, place.reset_pulses(report["pitch_down_s"], report["pitch_up_s"]), lambda f: None,
                    clock=clock, sleep=clock.sleep)
        assert lo <= place.pair_residual([object()], PitchPerception(cam)) <= hi


def test_measure_pitch_fails_when_the_down_hold_does_not_reach_the_clamp(monkeypatch):
    monkeypatch.setattr(place, "MEASURE_DOWN_S", 0.6)             # ~60 deg: not to the floor from looking up
    report = _measure(PitchCamera())
    assert not report["ok"] and "clamp" in report["why"]


def test_measure_pitch_fails_on_an_unrepeatable_reset():
    import random
    rng = random.Random(4)
    report = _measure(PitchCamera(lag_writes=lambda: rng.choice([0, 1, 2, 3])))    # 0-3 writes: ~0-105 px
    assert not report["ok"] and ("spread" in report["why"] or "left the level band" in report["why"]), report


def test_measure_pitch_fails_without_the_pair():
    cam = PitchCamera()
    cam.boxes = lambda: []
    report = _measure(cam)
    assert not report["ok"] and "never seen" in report["why"]


def test_measure_pitch_stops_on_the_kill_switch():
    cam = PitchCamera()
    calls = {"n": 0}

    def proof(f):
        calls["n"] += 1
        return "game not in the foreground (kill switch)" if calls["n"] > 30 else None

    clock = Clock()
    with pytest.raises(place.Stopped, match="foreground"):
        place.measure_pitch(cam, PitchPerception(cam), proof, clock=clock, sleep=clock.sleep, log=lambda s: None)
    assert cam.releases >= 1


def test_reset_check_reports_the_level_on_the_lane_and_the_plaza_offset(measured_pitch, monkeypatch):
    """--reset-check at a failure spot: the measured reset, then every box's residual. On the lane the pair lands in
    the level band; from the lower plaza the pair's offset (~+214 px) must survive the reset."""
    cam = PitchCamera()
    report = _measure(cam)
    monkeypatch.setattr(place, "PITCH_DOWN_S", report["pitch_down_s"])
    monkeypatch.setattr(place, "PITCH_UP_S", report["pitch_up_s"])
    lo, hi = P.LEVEL_RESIDUAL_PX
    for spot, extra, want in (("post-ko", 0.0, (lo, hi)), ("plaza", sim.PLAZA_LEVEL_PX, (150.0, 280.0))):
        cam.pitch, clock, kept = 150.0, Clock(), []
        base = cam.boxes
        cam.boxes = lambda: [[b[0], b[1] + extra, b[2], b[3] + extra] for b in base()]
        r = place.reset_check(cam, PitchPerception(cam), lambda f: None, spot, clock=clock, sleep=clock.sleep,
                              keep=lambda tag, f: kept.append(tag))
        cam.boxes = base
        assert want[0] <= r["pair_residual_px"] <= want[1], (spot, r["pair_residual_px"])
        assert kept == [f"{spot}-0", f"{spot}-1", f"{spot}-2"] and len(r["frames"]) == 3
        if spot == "plaza":
            assert all(f["view"] != "PAIR" for f in r["frames"])  # a reset plaza view still yields no pose
    assert set().union(*cam.sent) == {"ry"}


def test_reset_check_refuses_unmeasured_or_unknown_spot(measured_pitch, monkeypatch):
    cam = PitchCamera()
    with pytest.raises(place.Refused, match="--spot"):
        place.reset_check(cam, PitchPerception(cam), lambda f: None, "roof", clock=Clock(), sleep=lambda s: None)
    monkeypatch.setattr(place, "PITCH_UP_S", None)
    with pytest.raises(place.Refused, match="unmeasured"):
        place.reset_check(cam, PitchPerception(cam), lambda f: None, "nook", clock=Clock(), sleep=lambda s: None)
    assert cam.sent == []


def test_main_reset_check_refuses_before_opening_anything(tmp_path, monkeypatch, capsys, no_pad):
    monkeypatch.setattr(place, "_process_info", GAME)
    decl = str(_measurement(tmp_path, "reset-check"))
    assert place.main(["--reset-check", "--declaration", decl, "--spot", "nook"]) == 2   # as committed: unmeasured
    assert "measured PITCH_DOWN_S" in capsys.readouterr().out


def test_the_measurement_prime_turns_back_after_the_settle():
    from agent.startup import START_TURN_RX, START_TURN_S
    live, clock = FakeLive(sim.Lane(0.0, -20.0, 0.0)), Clock()
    n = math.ceil(START_TURN_S / place.WRITE_EVERY_S - 1e-9)
    writes = place.prime(live, lambda f: None, clock=clock, sleep=clock.sleep, undo=True)
    back = writes - n                                            # the hold is timed, so +-1 write (as live)
    assert live.sent == [{"rx": START_TURN_RX}] * n + [{"rx": -START_TURN_RX}] * back and abs(back - n) <= 1
    assert abs(live.lane.heading) <= P.YAW_DEG_PER_S * place.WRITE_EVERY_S + 1e-6   # within one write of the start
