"""Current alt profile through the executor and actual Live report writer; no device."""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.controller import Controller, NEUTRAL
from agent.loop import clean
from agent.pad_bindings import XUSB_NAMES, combat_controls
from policy.range_bc import executor, vocab
from test_live_pad import live


def state(*actions):
    held = [int(name in actions) for name in vocab.NAMES]
    return executor.pad_state(held, [0] * vocab.N, 0., 0.)


@pytest.mark.parametrize("action,buttons,lt,rt", [
    ("jump", {"LB"}, 0., 0.), ("web_swing", {"A"}, 0., 0.),
    ("get_over_here", {"RB"}, 0., 0.), ("amazing_combo", {"B"}, 0., 0.),
    ("goh_targeting", {"X"}, 0., 0.), ("team_up", {"RS"}, 0., 0.),
    ("ultimate", {"LS", "RS"}, 0., 0.), ("melee", set(), 0., 1.),
    ("spider_power", set(), 0., 1.), ("web_cluster", set(), 1., 0.),
    ("simple_swing", set(), 0., 0.),
])
def test_semantic_action_reaches_the_expected_device_report(action, buttons, lt, rt):
    lv, _, pad = live()
    try:
        lv.send(**clean(state(action)))
        sent, axes = pad.reports[-1]
        assert sent == buttons and axes["lt"] == lt and axes["rt"] == rt
    finally:
        lv.close()


def test_ultimate_is_atomic_in_guarded_reports_and_releases_both_together():
    import time
    lv, _, pad = live()
    try:
        for actions in (("ultimate",), ("ultimate", "team_up"), ()):
            now = time.perf_counter()
            lv.send_guarded(state(*actions), not_after=now + .1, release_at=now + .1)
        assert [buttons for buttons, _ in pad.reports] == [{"LS", "RS"}, {"LS", "RS"}, set()]
    finally:
        lv.close()


def test_melee_and_primary_combine_without_releasing_or_clicking_team_up():
    assert state("melee") == state("spider_power") == state("melee", "spider_power")
    assert state("melee", "team_up")["buttons"] == ("RS",)


def test_swing_and_jump_are_held_for_the_predicted_duration_then_released():
    lv, _, pad = live()
    try:
        for _ in range(3):
            lv.send(**state("web_swing", "jump"))
        lv.send(**state())
        assert [buttons for buttons, _ in pad.reports] == [{"A", "LB"}] * 3 + [set()]
        assert state() == NEUTRAL
        # Wall crawl has no distinct learned action: a sustained Jump is the hold.
        assert combat_controls("wall_crawl") == {"buttons": ("LB",)}
        assert combat_controls("wall_sprint") == {"buttons": ("LB",), "rt": 1.}
        swing = Controller().primitive("swing")
        assert swing[0][1]["buttons"] == ("A",) and swing[1][1]["buttons"] == ()
    finally:
        lv.close()


def test_preregistered_actions_stay_masked_even_with_high_support():
    counts = [1000] * vocab.N
    mask = vocab.live_mask(counts)
    assert mask[vocab.INDEX["spider_power"]] and mask[vocab.INDEX["amazing_combo"]]
    held, press, _ = executor.decode_step([1.] * vocab.N, [1.] * vocab.N, [1.] * vocab.N,
                                          [0] * vocab.N, mask)
    for action in ("ultimate", "melee", "team_up", "goh_targeting", "simple_swing"):
        assert held[vocab.INDEX[action]] == press[vocab.INDEX[action]] == 0


@pytest.fixture
def hand_tool(monkeypatch):
    # Importing the CLI cannot create a real device, even on a PC with vgamepad.
    codes = SimpleNamespace(**{value: key for key, value in XUSB_NAMES.items()})
    monkeypatch.setitem(sys.modules, "vgamepad", SimpleNamespace(XUSB_BUTTON=codes))
    spec = importlib.util.spec_from_file_location("offline_pad_tool", Path(__file__).parents[1] / "scripts/pad.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "time", SimpleNamespace(sleep=lambda _: None))
    return module


@pytest.mark.parametrize("token", ["combat:ultimate:0.15", "LS+RS"])
def test_hand_tool_ultimate_is_one_report_even_when_interrupted(hand_tool, monkeypatch, token):
    from test_live_pad import FakePad
    pad = FakePad()
    hand_tool.check([token])
    def interrupt(_):
        raise KeyboardInterrupt
    monkeypatch.setattr(hand_tool.time, "sleep", interrupt)
    with pytest.raises(KeyboardInterrupt):
        hand_tool.run(pad, token)
    assert [buttons for buttons, _ in pad.reports] == [{"LS", "RS"}, set()]


def test_hand_tool_preserves_raw_menu_controls_and_danger_checks(hand_tool):
    assert hand_tool.BUTTONS["A"] == "A" and hand_tool.BUTTONS["RB"] == "RB"
    for token in ("X", "START", "BACK", "combat:goh_targeting:0.1", "combat:environmental_interaction:0.1"):
        with pytest.raises(SystemExit):
            hand_tool.check([token])
    for token in ("combat:simple_swing:0.1", "combat:jump:nan", "combat:jump:inf", "combat:jump:0"):
        with pytest.raises(SystemExit):
            hand_tool.check([token])
