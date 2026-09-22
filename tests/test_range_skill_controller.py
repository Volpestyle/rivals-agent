"""Pure Controller boundary: synthetic State only, no capture or pad factories."""
from dataclasses import FrozenInstanceError, replace

import pytest

from agent.controller import ARM_FRAMES, NEUTRAL, Cal, Controller
from agent.intents import (BURST, Combo, Engage, Idle, RangeSkill,
                           RangeSkillResources, Search)
from agent.state import Detection, ENEMY, State


FRAME = (1280, 720)
BOT = Detection(ENEMY, (610, 310, 670, 410), .9, distance=13., track=1)


def decision(t, n, request="no_new_start", target=BOT, **changes):
    value = RangeSkill(target, request, n, t + .1, RangeSkillResources(5, t))
    return replace(value, **changes)


def step(c, t, intent, anchor=None, detections=None, **changes):
    state = State(t, FRAME, detections=[intent.target] if detections is None and isinstance(intent, RangeSkill)
                  else detections, **changes)
    return c.step(state, intent, t if anchor is None else anchor)


def warm(c=None, target=BOT):
    c = c or Controller()
    for k in range(ARM_FRAMES):
        step(c, k * .02, decision(k * .02, k, target=target))
    return c


def offensive(pad):
    return pad["lt"] or pad["rt"] or pad["buttons"]


def start(c, **kwargs):
    req = decision(.1, 10, "start", **kwargs)
    pad = step(c, .1, req)
    return req, pad


def test_no_new_start_moves_and_aims_without_offensive_selection():
    offset = replace(BOT, bbox=(720, 310, 780, 410))
    c = warm(target=offset)
    pad = step(c, .1, decision(.1, 10, target=offset))
    assert pad["ly"] == 1 and pad["rx"] != 0
    assert not offensive(pad)
    assert c.seq == []
    assert c.range_skill_trace["reason"] == "no_new_start"
    # Near targets never fall back to uppercut/melee, even after many decisions.
    near = replace(BOT, bbox=(600, 210, 680, 510), distance=3.)
    c = warm(target=near)
    for k in range(10, 35):
        assert not offensive(step(c, k / 50, decision(k / 50, k, target=near)))


def test_one_start_repeated_decision_and_bounded_release():
    c = warm()
    req, pad = start(c)
    assert pad["ly"] == 1 and pad["lt"] == 1
    assert c.range_skill_trace["accepted"] is True
    assert c.range_skill_trace["press_edge"] is True
    for t in (.11, .12):
        assert step(c, t, req, anchor=.1)["lt"] == 1
        assert c.range_skill_trace["accepted"] is False
        assert c.range_skill_trace["press_edge"] is False
    pad = step(c, .134, req, anchor=.1)
    assert pad["lt"] == 0 and pad["ly"] == 1
    assert c.range_skill_trace["release_edge"] is True
    assert c.range_skill_trace["pulse_decision_id"] == 10
    assert not offensive(step(c, .17, req, anchor=.1))
    assert c.range_skill_trace["pulse_outcome"] == "completed"
    assert not offensive(step(c, .18, req, anchor=.1))
    assert c.range_skill_trace["reason"] == "duplicate_accepted"


def test_no_new_keeps_only_accepted_pulse_and_resource_snapshot_is_immutable():
    c = warm()
    req, _ = start(c)
    with pytest.raises(FrozenInstanceError):
        req.resources.webs = 0
    no = decision(.12, 11, resources=RangeSkillResources(None, -1))
    assert step(c, .12, no)["lt"] == 1
    assert c.range_skill_trace["pulse_decision_id"] == 10
    assert c.range_skill_trace["accepted"] is False
    assert step(c, .14, no, anchor=.12)["lt"] == 0
    assert c.range_skill_trace["release_edge"] is True
    step(c, .18, decision(.18, 12))
    assert c.range_skill_trace["pulse_outcome"] == "completed"


def test_rejected_before_alignment_is_consumed_not_buffered():
    offset = replace(BOT, bbox=(850, 310, 910, 410))
    c = warm(target=offset)
    req, pad = start(c, target=offset)
    assert not offensive(pad)
    assert c.range_skill_trace["reason"] == "unaligned_target"
    # A subsequent current measurement can align, but cannot resurrect the ID.
    for t in (.12, .14, .16, .18):
        assert not offensive(step(c, t, req, anchor=.1, detections=[BOT]))
        assert c.range_skill_trace["accepted"] is False
    assert not offensive(step(c, .2, req, anchor=.1, detections=[BOT]))
    assert c.stable >= ARM_FRAMES
    assert c.range_skill_trace["reason"] == "decision_expired"


def test_busy_rejection_cannot_fire_after_old_pulse_completes():
    c = warm()
    start(c)
    busy = decision(.11, 11, "start")
    assert step(c, .11, busy)["lt"] == 1
    assert c.range_skill_trace["reason"] == "pulse_busy"
    assert c.range_skill_trace["accepted"] is False
    step(c, .14, busy, anchor=.11)
    assert not offensive(step(c, .18, busy, anchor=.11))
    assert c.range_skill_trace["reason"] == "duplicate_pulse_busy"


@pytest.mark.parametrize("changes", [
    {"web_cluster_request": "engage"}, {"web_cluster_request": None},
    {"decision_id": True}, {"decision_id": -1}, {"decision_id": "10"},
    {"valid_until": float("nan")}, {"valid_until": float("inf")},
    {"valid_until": .1}, {"valid_until": .3}, {"target": None},
    {"target": replace(BOT, track=None)}, {"target": replace(BOT, bbox=(0, 0, float("nan"), 200))},
])
def test_malformed_decision_cancels_owned_pulse(changes):
    c = warm()
    start(c)
    bad = replace(decision(.11, 11, "start"), **changes)
    assert step(c, .11, bad, detections=[BOT]) == NEUTRAL
    assert c._range_pulse is None
    assert c.range_skill_trace["pulse_outcome"] == "truncated"
    assert c.range_skill_trace["release_edge"] is True


@pytest.mark.parametrize("anchor", [None, float("nan"), .12, -.5])
def test_missing_future_or_stale_decision_anchor_refuses(anchor):
    c = warm()
    req = decision(.1, 10, "start")
    assert c.step(State(.1, FRAME, detections=[BOT]), req, intent_t=anchor) == NEUTRAL
    assert not c.range_skill_trace["accepted"]


@pytest.mark.parametrize("resources,reason", [
    (None, "invalid_resources"),
    (RangeSkillResources(5, float("nan")), "invalid_resource_time"),
    (RangeSkillResources(5, float("inf")), "invalid_resource_time"),
    (RangeSkillResources(5, .101), "future_resources"),
    (RangeSkillResources(5, -.001), "stale_resources"),
    *[(RangeSkillResources(value, .1), "unsupported_or_empty_ammo") for value in (None, 0, -1, 6, True, 1.0, "5")],
])
def test_unsupported_ammo_is_terminal_even_with_reflex_ammo(resources, reason):
    c = warm()
    req = decision(.1, 10, "start", resources=resources)
    pad = step(c, .1, req, webs=5)
    if reason in ("invalid_resources", "invalid_resource_time", "future_resources"):
        assert pad == NEUTRAL
    else:
        assert pad["ly"] == 1 and not offensive(pad)
    assert c.range_skill_trace["reason"] == reason
    corrected = replace(req, resources=RangeSkillResources(5, .1))
    assert step(c, .12, corrected, anchor=.1, webs=5) == NEUTRAL
    assert c.range_skill_trace["reason"] == "decision_reused_or_reordered"


def test_original_resource_clock_is_checked_at_acceptance():
    c = warm()
    req = decision(.08, 10, "start", resources=RangeSkillResources(5, 0))
    assert not offensive(step(c, .101, req, anchor=.08))
    assert c.range_skill_trace["reason"] == "stale_resources"


def test_late_start_requires_whole_calibrated_press_and_never_extends_deadline():
    c = warm()
    late = decision(.02, 10, "start")
    assert not offensive(step(c, .1, late, anchor=.02))
    assert c.range_skill_trace["reason"] == "insufficient_press_time"
    assert c._range_pulse is None
    c = warm(Controller(cal=Cal(press_s=.05)))
    req = decision(.05, 10, "start")
    assert step(c, .1, req, anchor=.05)["lt"] == 1
    assert step(c, .151, decision(.151, 11))["lt"] == 0
    assert c.range_skill_trace["cancel_reason"] == "pulse_expired"
    assert c.range_skill_trace["pulse_outcome"] == "cancelled_after_press"


@pytest.mark.parametrize("kind", ["melee_combo", "burst", "uppercut", "web_cluster", "swing"])
def test_entry_discards_every_legacy_sequence(kind):
    c = Controller()
    c.play(kind, 0)
    c.intent_key = ("Search", None)
    pad = step(c, .01, decision(.01, 0))
    assert not offensive(pad) and c.seq == []
    assert c._range_pulse is None


def test_actual_engage_melee_and_burst_do_not_leak_into_range_mode():
    near = replace(BOT, bbox=(600, 210, 680, 510))
    for intent, next_uppercut in ((Engage(near), 10), (Combo(BURST, near), 0)):
        c = Controller(next_uppercut_t=next_uppercut)
        for k in range(6):
            pad = step(c, k * .02, intent, detections=[near])
        assert offensive(pad)
        assert not offensive(step(c, .12, decision(.12, 10, target=near)))
        assert c.seq == []


@pytest.mark.parametrize("dets,coasting", [([], ()), (None, ()), ([BOT], (1,)),
                                         ([replace(BOT, track=2)], ()), ([BOT, BOT], ())])
def test_target_coast_loss_wrong_id_and_detector_fault_cancel(dets, coasting):
    c = warm()
    req, _ = start(c)
    pad = c.step(State(.11, FRAME, detections=dets, coasting=coasting), req, intent_t=.1)
    assert pad == NEUTRAL
    assert c.range_skill_trace["release_edge"] is True
    assert c.range_skill_trace["pulse_outcome"] == "truncated"


def test_target_switch_cancels_and_old_id_cannot_replay_after_no_new_or_return():
    c = warm()
    req, _ = start(c)
    other = replace(BOT, track=2)
    pad = step(c, .11, decision(.11, 11, target=other))
    assert not offensive(pad)
    assert c.range_skill_trace["cancel_reason"] == "target_switch"
    assert c.range_skill_trace["pulse_outcome"] == "truncated"
    assert step(c, .12, req, anchor=.1) == NEUTRAL
    assert c.range_skill_trace["reason"] == "decision_reused_or_reordered"


def test_history_refusal_idle_releases_and_cannot_resurrect_request():
    # History/model support is caller-owned. Its required refusal is Idle.
    c = warm()
    req, _ = start(c)
    assert step(c, .11, Idle(), detections=[]) == NEUTRAL
    assert c.range_skill_trace["release_edge"] is True
    assert c.range_skill_trace["pulse_outcome"] == "truncated"
    assert not offensive(step(c, .12, req, anchor=.1))
    assert c.range_skill_trace["accepted"] is False


def test_expired_decision_cancels_even_when_loop_one_second_gate_would_pass():
    c = warm(Controller(cal=Cal(press_s=.07)))
    req, _ = start(c)
    assert not offensive(step(c, .201, req, anchor=.1))
    assert c.stable >= ARM_FRAMES
    assert c.range_skill_trace["reason"] == "decision_expired"
    assert c._range_pulse is None


def test_trace_is_detached_and_every_press_has_an_accepted_start():
    c = warm()
    rows = []
    for k in range(10, 70):
        t = k / 50
        pad = step(c, t, decision(t, k, "start" if k % 4 == 0 else "no_new_start"))
        trace = c.range_skill_trace
        assert trace["pad"] == pad
        assert pad["rt"] == 0 and pad["buttons"] == ()
        rows.append(trace)
    accepted = {r["decision_id"] for r in rows if r["accepted"]}
    assert len(accepted) >= 2
    assert all(r["pulse_decision_id"] in accepted for r in rows if r["lt_down"])
    assert sum(r["press_edge"] for r in rows) == len(accepted)
    detached = c.range_skill_trace
    detached["pad"]["lt"] = 99
    assert c.range_skill_trace["pad"]["lt"] != 99
    step(c, 2, Search(), detections=[])
    step(c, 2.02, Search(), detections=[])
    assert c.range_skill_trace is None


@pytest.mark.parametrize("resources", [None, RangeSkillResources(5, float("nan")),
                                      RangeSkillResources(5, .13)])
def test_malformed_or_future_resource_clock_is_a_fault_even_for_no_new(resources):
    c = warm()
    start(c)
    assert step(c, .12, decision(.12, 11, resources=resources)) == NEUTRAL
    assert c.range_skill_trace["pulse_outcome"] == "truncated"


def test_snapshot_not_reflex_ammo_authorizes_the_start():
    c = warm()
    # The actual loop reflex State omits HUD. Only the original snapshot counts.
    assert step(c, .1, decision(.1, 10, "start"), webs=None)["lt"] == 1
    c = warm()
    assert not offensive(step(c, .1, decision(.1, 10, "start", resources=RangeSkillResources(None, .1)), webs=5))


def test_shot_spacing_rejects_once_then_a_fresh_later_start_can_fire():
    c = warm()
    start(c)
    step(c, .14, decision(.14, 11))
    step(c, .18, decision(.18, 12))
    blocked = decision(.2, 13, "start")
    assert not offensive(step(c, .2, blocked))
    assert c.range_skill_trace["reason"] == "shot_spacing"
    assert not offensive(step(c, .24, blocked, anchor=.2))
    assert c.range_skill_trace["reason"] == "duplicate_shot_spacing"
    assert step(c, .45, decision(.45, 14, "start"))["lt"] == 1


@pytest.mark.parametrize("t", [.1, .09, float("nan"), float("inf")])
def test_nonmonotonic_or_invalid_reflex_clock_cancels(t):
    c = warm()
    req, _ = start(c)
    assert step(c, t, req, anchor=.1) == NEUTRAL
    assert c.range_skill_trace["reason"] == "invalid_state_time"


def test_foreign_sequence_inserted_during_new_mode_faults_neutral():
    c = warm()
    start(c)
    c.play("burst", .105)
    assert step(c, .11, decision(.11, 11)) == NEUTRAL
    assert c.seq == [] and c._range_pulse is None
    assert c.range_skill_trace["reason"] == "foreign_sequence"


@pytest.mark.parametrize("target", [replace(BOT, distance=41.),
                                    replace(BOT, bbox=(630, 358, 650, 362))])
def test_unreachable_or_implausible_target_does_not_walk_or_fire(target):
    c = warm(target=target)
    pad = step(c, .1, decision(.1, 10, "start", target=target))
    assert pad["ly"] == 0 and not offensive(pad)


def test_malformed_trace_still_serializes_as_strict_json():
    import json

    c = warm()
    step(c, .1, decision(.1, 10, "start", resources=RangeSkillResources(5, float("nan"))))
    trace = c.range_skill_trace
    assert trace["resources"]["observed_t"] is None
    assert trace["reason"] == "invalid_resource_time"
    json.dumps(trace, allow_nan=False)


def test_rsc1_expired_request_keeps_current_measurements_armed_without_firing():
    c = Controller()
    expired = decision(0., 0, "start")
    for k in range(ARM_FRAMES):
        pad = step(c, .12 + k * .02, expired, anchor=0.)
        assert not offensive(pad)
    assert c.stable == ARM_FRAMES
    assert c.track.confirmed and c.track.seen_t == .2
    assert step(c, .22, decision(.22, 1, "start"))["lt"] == 1


def test_rsc2_work_delay_cannot_start_after_authority_deadline():
    c = warm()
    state = State(.1002, FRAME, detections=[BOT])
    req = decision(.1002, 10, "start")
    pad = c.step(state, req, intent_t=.1002, execution_t=.2505)
    assert not offensive(pad)
    assert c.range_skill_trace["accepted"] is False
    assert c.track.seen_t == .1002
    assert state.t == .1002


def test_rsc3_source_end_cancels_original_pulse_without_new_decision():
    c = warm()
    req, _ = start(c)
    assert c.cancel_range_skill(.11, "source_end") == NEUTRAL
    trace = c.range_skill_trace
    assert trace["decision_id"] is None
    assert trace["pulse_decision_id"] == req.decision_id
    assert trace["cancel_reason"] == "source_end"
    assert trace["execution_t"] == .11
    assert trace["release_edge"] is True
    assert trace["pulse_outcome"] == "truncated"
    assert c._range_pulse is None
    assert not offensive(step(c, .12, req, anchor=.1))
    assert c.range_skill_trace["accepted"] is False


@pytest.fixture
def guarded_device(monkeypatch):
    """Real Live actuator methods, fake device/clock/lock; no device factory."""
    import threading
    from types import SimpleNamespace
    import agent.controller as C
    from tests.test_live_pad import FakePad

    clock = SimpleNamespace(t=10., real=100.)
    monkeypatch.setattr(C, "time", SimpleNamespace(perf_counter=lambda: clock.t))
    monkeypatch.setattr(C, "_real_clock", lambda: clock.real)
    lv = C.Live.__new__(C.Live)
    lv._pad, lv._codes = FakePad(), {n: n for n in C.ALLOWED}
    lv._lock, lv._dead, lv._lease_until = threading.Lock(), False, None
    lv.sent, lv.frame, lv.frame_t = dict(NEUTRAL), "range", clock.t
    lv._in_range = lambda frame: frame == "range"
    return lv, clock


@pytest.mark.parametrize("delay_where", ["proof", "lock"])
def test_rsc2_guarded_actuator_refuses_deadline_after_proof_or_lock(guarded_device, delay_where):
    from agent.controller import RangeLost

    lv, clock = guarded_device
    if delay_where == "proof":
        def slow_proof(frame):
            clock.t += .04  # range proof remains fresh; event authority expires
            return True
        lv._in_range = slow_proof
    else:
        class SlowLock:
            def __enter__(self):
                clock.t += .04
            def __exit__(self, *args):
                pass
        lv._lock = SlowLock()
    with pytest.raises(RangeLost, match="deadline"):
        lv.send_guarded({**NEUTRAL, "lt": 1.}, not_after=10.03, release_at=10.06)
    assert lv._pad.neutral()
    assert all(axes["lt"] == 0 for _, axes in lv._pad.reports)


def test_rsc2_guarded_actuator_lease_uses_remaining_perf_time(guarded_device):
    lv, clock = guarded_device
    lv.send_guarded({**NEUTRAL, "lt": 1.}, not_after=10.03, release_at=10.05)
    assert lv.sent["lt"] == 1
    assert lv._lease_until == pytest.approx(100.05)


def test_rsc1_expiry_does_not_mask_missing_target_or_hard_faults():
    for dets in (None, [], [replace(BOT, track=2)]):
        c = warm()
        req = decision(0., 10, "start")
        assert c.step(State(.12, FRAME, detections=dets), req, intent_t=0.) == NEUTRAL
        assert c.stable == 0 and c.track is None
    c = warm()
    assert step(c, .12, decision(0., 10, "start", resources=RangeSkillResources(5, float("nan"))), anchor=0.) == NEUTRAL
    assert c.stable == 0


def test_rsc1_expired_id_cannot_gain_a_new_deadline():
    c = warm()
    req = decision(0., 10, "start")
    assert not offensive(step(c, .12, req, anchor=0.))
    assert step(c, .14, decision(.14, 10, "start")) == NEUTRAL
    assert c.range_skill_trace["reason"] == "decision_reused_or_reordered"


@pytest.mark.parametrize("now", [float("nan"), float("inf"), True, .09])
def test_rsc2_invalid_execution_clock_consumes_and_cancels(now):
    c = warm()
    start(c)
    req = decision(.11, 11, "start")
    assert c.step(State(.11, FRAME, detections=[BOT]), req, intent_t=.11, execution_t=now) == NEUTRAL
    trace = c.range_skill_trace
    assert trace["reason"] == "invalid_execution_time"
    assert trace["execution_clock_valid"] is False
    assert trace["pulse_outcome"] == "truncated"
    assert not offensive(step(c, .12, req, anchor=.11))
    assert c.range_skill_trace["accepted"] is False


def test_rsc2_execution_clock_cannot_move_back_even_with_newer_observation():
    c = warm()
    req = decision(.1, 10, "start")
    c.step(State(.1, FRAME, detections=[BOT]), req, intent_t=.1, execution_t=.12)
    assert c.step(State(.11, FRAME, detections=[BOT]), req, intent_t=.1, execution_t=.115) == NEUTRAL
    assert c.range_skill_trace["reason"] == "invalid_execution_time"


def test_rsc2_full_press_and_resource_budget_use_execution_clock():
    c = warm()
    req = decision(.1, 10, "start")
    assert not offensive(c.step(State(.1, FRAME, detections=[BOT]), req, intent_t=.1, execution_t=.18))
    assert c.range_skill_trace["reason"] == "insufficient_press_time"
    c = warm()
    req = decision(.1, 10, "start", resources=RangeSkillResources(5, .04))
    assert not offensive(c.step(State(.1, FRAME, detections=[BOT]), req, intent_t=.1, execution_t=.15))
    assert c.range_skill_trace["reason"] == "stale_resources"


def test_rsc2_pulse_starts_and_releases_on_execution_clock_without_restamping():
    c = warm()
    req = decision(.1, 10, "start")
    state = State(.1, FRAME, detections=[BOT])
    assert c.step(state, req, intent_t=.1, execution_t=.12)["lt"] == 1
    trace = c.range_skill_trace
    assert trace["pulse_press_until"] == pytest.approx(.153)
    assert trace["t"] == trace["observation_t"] == c.track.seen_t == state.t == .1
    assert trace["execution_t"] == .12
    assert c.cam_hist[-1][0] == .1
    assert c.next_shot_t == pytest.approx(.46)
    assert c.step(State(.11, FRAME, detections=[BOT]), req, intent_t=.1, execution_t=.152)["lt"] == 1
    assert c.step(State(.12, FRAME, detections=[BOT]), req, intent_t=.1, execution_t=.154)["lt"] == 0
    assert c.range_skill_trace["release_edge"] is True
    assert c.track.seen_t == .12


def test_rsc3_cancel_is_detached_idempotent_and_does_not_invent_observation():
    c = warm()
    req, _ = start(c)
    c.cancel_range_skill(.11, "exception")
    trace = c.range_skill_trace
    assert trace["event"] == "cancel" and trace["observation_t"] == .1
    assert trace["resources"] is None and trace["proposal"] is None
    assert c.last_t == .1 and c._range_seen_id == req.decision_id
    trace["pad"]["lt"] = 1
    assert c.range_skill_trace["pad"]["lt"] == 0
    assert c.cancel_range_skill(.12, "finish") == NEUTRAL
    assert c.range_skill_trace["release_edge"] is False
    assert c.range_skill_trace["ended_pulse_decision_id"] is None
    assert c.range_skill_trace["pulse_outcome"] is None


def test_rsc3_invalid_cancel_clock_still_releases_without_claiming_full_press():
    c = warm()
    start(c)
    assert c.cancel_range_skill(float("nan"), "clock_fault") == NEUTRAL
    assert c.range_skill_trace["execution_clock_valid"] is False
    assert c.range_skill_trace["pulse_outcome"] == "truncated"
    assert c.range_skill_trace["execution_t"] is None


@pytest.mark.parametrize("latest,release", [(float("nan"), 11.), (10., float("inf")),
                                          (True, 11.), (11., 10.), ("10", 11.)])
def test_rsc2_guarded_actuator_releases_for_invalid_deadlines(guarded_device, latest, release):
    from agent.controller import Forbidden

    lv, clock = guarded_device
    lv.send_guarded({"lt": 1.}, not_after=10.02, release_at=10.05)
    with pytest.raises(Forbidden, match="deadlines"):
        lv.send_guarded({"lt": 1.}, not_after=latest, release_at=release)
    assert lv._pad.neutral() and lv._lease_until is None


@pytest.mark.parametrize("delay_where", ["proof", "lock"])
def test_rsc2_guarded_actuator_valid_delay_uses_remaining_lease(guarded_device, delay_where):
    lv, clock = guarded_device
    def delay():
        clock.t += .02
        clock.real += .02
    if delay_where == "proof":
        lv._in_range = lambda frame: delay() or True
    else:
        class SlowLock:
            def __enter__(self):
                delay()
            def __exit__(self, *args):
                pass
        lv._lock = SlowLock()
    lv.send_guarded({"lt": 1.}, not_after=10.03, release_at=10.05)
    assert lv.sent["lt"] == 1
    assert lv._lease_until == pytest.approx(100.05)


def test_rsc2_watchdog_uses_capped_lease_and_renewal_cannot_extend_it(guarded_device):
    lv, clock = guarded_device
    lv.send_guarded({"lt": 1.}, not_after=10.05, release_at=10.05)
    clock.t += .02
    clock.real += .02
    lv.send_guarded({"lt": 1.}, not_after=10.05, release_at=10.05)
    assert lv._lease_until == pytest.approx(100.05)
    class OneTick:
        n = 0
        def wait(self, timeout):
            self.n += 1
            clock.real += .04
            return self.n > 1
    lv._closed = OneTick()
    lv._watchdog()  # actual watchdog loop, one fake tick; no thread or device
    assert lv._pad.neutral() and lv._lease_until is None


def test_rsc2_legacy_send_lease_and_neutral_guarded_release_remain_compatible(guarded_device):
    from agent.controller import LEASE_S

    lv, clock = guarded_device
    lv.send(lt=1.)
    assert lv._lease_until == pytest.approx(clock.real + LEASE_S)
    # A neutral request always releases, including after its offensive deadlines.
    lv.send_guarded(NEUTRAL, not_after=9., release_at=9.1)
    assert lv._pad.neutral()


def test_rsc2_guarded_whitelist_still_refuses_buttons(guarded_device):
    from agent.controller import Forbidden

    lv, _ = guarded_device
    with pytest.raises(Forbidden):
        lv.send_guarded({"buttons": ("BACK",)}, not_after=10.02, release_at=10.05)
    assert lv._pad.neutral()
