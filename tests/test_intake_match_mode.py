"""Match-mode intake (lead 2026-09-27): a logged live match's edge guard, vote window, no-controller attestation and
its pending IDM match-admission receipt. Stdlib only; no media, no frames."""
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from policy.idm import match_targets

ROOT = Path(__file__).resolve().parents[1]
SESSIONS = ROOT / "data/human/sessions"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


intake = module("intake_session_match_test", SESSIONS / "intake_session.py")
assemble = module("assemble_session_match_test", SESSIONS / "assemble_session.py")
receipt = module("match_admission_test", SESSIONS / "match_admission.py")


class Scan:
    @staticmethod
    def read_sample(img, layout, mapping):
        return {"hud_present": img["hud"]}


def test_the_match_guard_holds_only_on_spider_mans_own_live_hud():
    guard = intake.match_guard(lambda img: img)
    assert guard(dict(hp=219, webs=3)) is True                   # live play (pilot 052001, 140 s)
    assert guard(dict(hp=480, webs=4)) is True                   # his ultimate's bonus health (500 s)
    assert guard(dict(hp=275, webs=None)) is False               # a spectated teammate's HUD after a death (180 s)
    assert guard(dict(hp=0, webs=None)) is False                 # the death itself
    assert guard(dict(hp=None, webs=None)) is False              # hero select, the scoreboard, post-match (20, 250, 513 s)
    assert guard(dict(hp=250, webs=None)) is False               # a web-counter reader miss: the edge moves inward
    # present-at-0 is his own HUD, out of webs (lead, 2026-09-27): 0 is a read value, never "absent"
    assert guard(dict(hp=300, webs=0)) is True                   # 112.5 s, counter drawn reading 0


def test_a_match_edge_needs_both_the_hud_and_his_own_hud_and_names_its_guard():
    guard = intake.match_guard(lambda img: img)
    rows = {(hud, own): intake.edge_proof(dict(hud=hud, hp=250, webs=4 if own else None), Scan, None, None, guard,
                                          "own_hud")
            for hud in (True, False) for own in (True, False)}
    assert [r["proof"] for r in rows.values()] == [True, False, False, False]
    assert all(set(r) == {"hud_present", "own_hud", "proof"} for r in rows.values())
    # the range default is unchanged: its record key stays in_range
    assert set(intake.edge_proof(dict(hud=True), Scan, None, None, lambda img: True)) == {"hud_present", "in_range", "proof"}


def sample(t, hud=True, hp=250, webs=4):
    return dict(composition_ns=t, hud_present=hud, hp=hp, webs=webs)


def test_a_match_death_runs_to_spider_mans_own_hud_not_the_spectated_teammates():
    # pilot 052001 at 175-186 s: hp 0, a teammate's HUD (hp 257/275, no web counter), then respawn (webs 5)
    rows = [sample(1), sample(2, hp=40, webs=3), sample(3, hp=0, webs=None), sample(4, hud=False, hp=None, webs=None),
            sample(5, hp=257, webs=None), sample(6, hp=227, webs=None), sample(7, hud=False, hp=None, webs=None),
            sample(8, hp=250, webs=5), sample(9)]
    hud, dead = intake.match_hud(rows)
    assert dead == [3, 4, 5, 6, 7]
    assert [p for _, p in hud] == [True, True, True, False, True, True, False, True, True]


def test_a_death_ends_at_his_own_hud_even_when_it_reads_zero_webs():
    rows = [sample(1, hp=0, webs=None), sample(2, hp=275, webs=None), sample(3, hp=250, webs=0), sample(4)]
    assert intake.match_hud(rows)[1] == [1, 2]


def test_a_bright_post_match_scene_without_an_hp_read_is_not_hud():
    hud, dead = intake.match_hud([sample(1), sample(2, hp=None, webs=None), sample(3, hud=None, hp=None, webs=None)])
    assert [p for _, p in hud] == [True, False, None] and dead == []


def test_the_vote_window_is_required_in_match_mode_and_refused_in_range_mode():
    for mode, vote_from in (("match", None), ("range", 150.0)):
        with pytest.raises(intake.Refused, match="--vote-from"):
            intake.step_vote(SimpleNamespace(mode=mode, vote_from=vote_from))


def test_the_timed_practice_step_is_refused_in_match_mode():
    with pytest.raises(intake.Refused, match="never a match step"):
        intake.step_timed(SimpleNamespace(mode="match"))


def test_after_the_controller_take_a_recording_needs_its_own_no_controller_statement():
    before = datetime(2026, 9, 26, 5, 0, tzinfo=timezone.utc)
    after = datetime(2026, 9, 27, 5, 20, 1, tzinfo=timezone.utc)
    assert assemble.no_pad_attestation({}, before) is None          # the 2026-09-23 wording, kept at the call sites
    assert assemble.no_pad_attestation({"no_pad": "James: keyboard and mouse only"}, after) == \
        "James: keyboard and mouse only"
    with pytest.raises(assemble.Refused, match="no-controller"):
        assemble.no_pad_attestation({}, after)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


HEADER = dict(session_id="m1", split="idm_train", media_sha256="a" * 64, session_group="m1",
              bindings={"jump": "key:57:0"}, swing_mode={"automatic_swing": False, "hold_to_swing": True},
              accel_on=True, patch="p1", settings_hash="s" * 64, calibration={"yaw_deg_per_count": 0.033})


def session_dir(tmp_path, header=HEADER):
    d = tmp_path / header["session_id"]
    d.mkdir(parents=True)
    demo = d / "imported-demo.jsonl"
    demo.write_text('{"media_sha256": "' + header["media_sha256"] + '"}\n{}\n', encoding="utf-8")
    h = dict(header, source={"imported_demo_sha256": sha(demo)})
    (d / f"{header['session_id']}.steps.jsonl").write_text(json.dumps(h) + "\n{}\n", encoding="utf-8")
    (d / "motor-settings.json").write_text('{"statement": "verbatim"}\n', encoding="utf-8")
    return d


ROW = dict(session_id="m1", session_group="m1", split="idm_train", expected_media_sha256="a" * 64)
HI = SimpleNamespace(check_freeze=lambda d, root: [])


def make(tmp_path, rows):
    return receipt.entry("m1", sessions_dir=tmp_path, rows=rows, hi=HI, digest=match_targets.digest,
                         identity=match_targets.identity)


def test_the_receipt_entry_pins_what_the_match_target_check_reads(tmp_path):
    d = session_dir(tmp_path)
    e = make(tmp_path, {"m1": ROW})
    header = json.loads((d / "m1.steps.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert e == dict(source_kind="live", session_group="m1", media_sha256="a" * 64, steps_sha256=sha(d / "m1.steps.jsonl"),
                     imported_demo_sha256=sha(d / "imported-demo.jsonl"),
                     identity_sha256=match_targets.digest(match_targets.identity(header)),
                     motor_statement_sha256=sha(d / "motor-settings.json"))
    # the consumer's own check accepts the entry against the same registry row
    assert match_targets.Admission({"m1": e}, {"m1": ROW}, "0" * 64).check("m1", "a" * 64) == e


@pytest.mark.parametrize("change, message", [
    (dict(training_pending="main account"), "training_pending"),
    (dict(pair="live-1", session_group="live-1"), "replay"),
    (dict(split="train"), "not registered idm_train"),
    (dict(expected_media_sha256="b" * 64), "media differs"),
])
def test_the_receipt_refuses_a_session_the_match_path_must_not_train(tmp_path, change, message):
    session_dir(tmp_path)
    with pytest.raises(receipt.Refused, match=message):
        make(tmp_path, {"m1": dict(ROW, **change)})


def test_the_receipt_refuses_a_session_whose_freeze_fails(tmp_path):
    session_dir(tmp_path)
    with pytest.raises(receipt.Refused, match="freeze"):
        receipt.entry("m1", sessions_dir=tmp_path, rows={"m1": ROW},
                      hi=SimpleNamespace(check_freeze=lambda d, root: ["changed"]),
                      digest=match_targets.digest, identity=match_targets.identity)


def test_the_receipt_refuses_a_session_without_its_motor_record(tmp_path):
    d = session_dir(tmp_path)
    (d / "motor-settings.json").unlink()
    with pytest.raises(receipt.Refused, match="motor-settings"):
        make(tmp_path, {"m1": ROW})


FIX = ROOT / "tests/fixtures/intake_match"
MAPPING = {"swing": "swing", "get_over_here": "uppercut", "uppercut": "get_over_here"}   # -5's vote (slot-mapping.json)


@pytest.mark.parametrize("name, webs, own", [
    ("own-webs3", 3, True),           # 140 s: live play, counter reading 3
    ("own-webs0", 0, True),           # 112.5 s: his own HUD out of webs, counter drawn reading 0
    ("own-webs0-missed", None, False),  # 108.0 s: counter drawn at 0 but not read: fails closed (the edge moves inward)
    ("spectate", None, False),        # 180 s: a spectated teammate (Black Cat) after a death: no counter at all
])
def test_the_web_counter_on_native_match_frames_tells_zero_from_absent(name, webs, own):
    """Pilot 052001's native frames (JPEG q95; reads equal the native decode's). Needs cv2 (perception group)."""
    cv2 = pytest.importorskip("cv2")
    scan = module("reused_scan_match_test", ROOT / "data/human/inspection/20260922T033319-205Z-24328-2/regime-scan/scan.py")
    layout = scan.source_layout(MAPPING)
    img = cv2.imread(str(FIX / f"052001-{name}.jpg"))
    read = scan.read_sample(img, layout, MAPPING)
    assert read["webs"] == webs and read["hud_present"] and read["hp"] > 0
    assert intake.match_guard(lambda frame: scan.read_sample(frame, layout, MAPPING))(img) is own


def test_the_emote_wheel_is_cut_until_the_player_moves_again():
    """frame-review on pilot 052001 seg-026: T held 281.414-282.751 s drew the emote wheel (the mouse drove the wheel),
    then the chosen emote (a sit) animated Spider-Man until D at 305.124 s; a jump at 283.495 s did not end it."""
    from agent import human_intake as hi
    S = 10**9
    events = [dict(type="key", vk=84, down=True, t_ns=281 * S), dict(type="key", vk=84, down=True, t_ns=281 * S + 5),
              dict(type="mouse", button_flags=0, dx=40, dy=0, t_ns=282 * S),                 # moves the wheel
              dict(type="key", vk=84, down=False, t_ns=283 * S),
              dict(type="key", vk=32, down=True, t_ns=283 * S + 5), dict(type="key", vk=32, down=False, t_ns=284 * S),
              dict(type="mouse", button_flags=0x1, dx=0, dy=0, t_ns=290 * S),                # a click: not a move
              dict(type="key", vk=68, down=True, t_ns=305 * S), dict(type="key", vk=68, down=True, t_ns=305 * S + 9)]
    presses = hi.move_presses(events)
    assert presses == [305 * S]                                   # the jump, the click and D's repeat are not moves
    cuts, esc = hi.ui_cuts(hi.ui_key_presses(events), [(0, 400 * S)], presses=presses)
    assert cuts == [(281 * S, 305 * S + hi.UI_SETTLE_NS, "ui_key")] and esc == []
    # no later move: the cut runs to the focus interval's end
    assert hi.ui_cuts([(1 * S, 84, True), (2 * S, 84, False)], [(0, 9 * S)], presses=[])[0] == [(1 * S, 9 * S, "ui_key")]


def test_after_a_round_transition_gameplay_resumes_only_after_the_splash_settle():
    """Pilot 052001: HUD absent 250.9-262.3 s (round transition), then the PARKER POWER-UP splash 262.3-263.5 s."""
    S = 10**9
    ms = 200_000_000
    rows = [sample(250 * S)] + [sample(250 * S + k * ms, hud=False, hp=None, webs=None) for k in range(1, 61)] + \
           [sample(262 * S + k * ms) for k in range(1, 30)]
    hud = dict(intake.match_hud(rows)[0])
    assert hud[250 * S] is True
    returned = 262 * S + ms
    assert all(hud[t] is False for t in hud if returned <= t < returned + intake.HUD_RETURN_SETTLE_NS)
    assert all(hud[t] is True for t in hud if t >= returned + intake.HUD_RETURN_SETTLE_NS)
    # a short reader miss (under HUD_HOLE_NS) is not a round transition: no settle
    short = [sample(0), sample(ms, hud=False, hp=None, webs=None), sample(2 * ms), sample(3 * ms)]
    assert [p for _, p in intake.match_hud(short)[0]] == [True, False, True, True]


def test_movement_typed_in_chat_never_ends_the_emote_cut():
    """fit-review F1 (2026-09-27): T down 1 s, up 2 s, Enter 3 s (chat opens), W 4 s (typed in chat), Enter 5 s. The
    chat W is text, so the emote cut runs to the focus end; a real W after the chat (6 s) does end it."""
    from agent import human_intake as hi
    S = 10**9
    key = lambda t, vk, down=True: dict(type="key", vk=vk, down=down, t_ns=t * S)   # noqa: E731
    typed = [key(1, 84), key(2, 84, False), key(3, 13), key(3.1, 13, False), key(4, 87), key(4.1, 87, False),
             key(5, 13), key(5.1, 13, False)]
    assert hi.move_presses(typed) == []
    cuts, _ = hi.ui_cuts(hi.ui_key_presses(typed), [(0, 60 * S)], presses=hi.move_presses(typed))
    assert (1 * S, 60 * S, "ui_key") in cuts
    moved = typed + [key(6, 87), key(6.1, 87, False)]
    assert hi.move_presses(moved) == [6 * S]
    cuts, _ = hi.ui_cuts(hi.ui_key_presses(moved), [(0, 60 * S)], presses=hi.move_presses(moved))
    assert (1 * S, 6 * S + hi.UI_SETTLE_NS, "ui_key") in cuts
    # other input-consuming UI: a toggled overlay, a held Tab or T, and everything after a settings-menu Esc
    assert hi.move_presses([key(1, 112), key(1.1, 112, False), key(2, 87), key(3, 112), key(3.1, 112, False),
                            key(4, 65)]) == [4 * S]                                            # F1 overlay
    assert hi.move_presses([key(1, 9), key(2, 87), key(3, 9, False), key(4, 83)]) == [4 * S]    # Tab held
    assert hi.move_presses([key(1, 27), key(2, 87)]) == []                                     # the settings menu
    assert hi.move_presses([key(1, 112), key(1.1, 112, False), key(2, 27), key(3, 87)]) == [3 * S]   # Esc closes F1


def anchor_dir(tmp_path, matches, decision=True, matched=60835):
    d = tmp_path / "s"
    d.mkdir(parents=True)
    got = [21, 46, 29, 38, 71, 54, 63, 96, 79, 88, 121 if matches else 113]
    want = [21, 46, 29, 38, 71, 54, 63, 96, 79, 88, 121]
    (d / "provenance.json").write_text(json.dumps(dict(anchor_applicability=dict(
        matches=matches, first_16_packets=dict(video_ms=got, audio_ms=[0, 21, 42, 64, 85]),
        predicted=dict(video_ms=want, audio_ms=[0, 21, 42, 64, 85])))), encoding="utf-8")
    (d / "recorder-verification.json").write_text(json.dumps(dict(
        integrity_ok=True, errors=[], decoded_video_frames=60835, matched_video_frames=matched,
        muxer_pts_offset_seconds=0.021, max_video_pts_residual_seconds=0.00033333333340124227)), encoding="utf-8")
    if decision:
        (d / "lead-decisions.json").write_text(json.dumps(dict(decisions=[dict(item="pts_anchor")])), encoding="utf-8")
    return d


def test_the_pts_anchor_states_its_true_basis(tmp_path):
    """Lead decision 2026-09-27 (session -150600-12): when the first-16 forward prediction fails, the anchor rests on the
    whole-stream verify, under a lead decision, and the text names both facts; the range wording is unchanged."""
    src, ev = assemble.pts_anchor_basis(anchor_dir(tmp_path / "a", True))
    assert src == assemble.ANCHOR_SOURCE and [p.name for p in ev][1:] == ["provenance.json"]
    src, ev = assemble.pts_anchor_basis(anchor_dir(tmp_path / "b", False))
    assert src == ("whole-stream verify match at +21 ms (60835 of 60835 frames, max residual 0.33 ms); first-16 forward "
                   "prediction failed at video packet 11 (113 vs 121 ms); lead decision (lead-decisions.json)")
    assert [p.name for p in ev][1:] == ["provenance.json", "recorder-verification.json", "lead-decisions.json"]
    with pytest.raises(assemble.Refused, match="lead decision"):
        assemble.pts_anchor_basis(anchor_dir(tmp_path / "c", False, decision=False))
    with pytest.raises(assemble.Refused, match="whole-stream verify"):
        assemble.pts_anchor_basis(anchor_dir(tmp_path / "d", False, matched=60834))
