import numpy as np
import pytest

pytest.importorskip("cv2")
from perception.replay_hud import Event  # noqa: E402
from policy.idm import refine  # noqa: E402


def test_hysteresis_holds_through_dips_and_fills_short_gaps():
    p = np.array([0.1, 0.6, 0.4, 0.35, 0.6, 0.1, 0.1, 0.6, 0.2, 0.1, 0.1, 0.1, 0.6])
    assert refine.hysteresis(p, 0.5, 0.3).tolist() == [0, 1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 1]
    assert refine.hysteresis(p, 0.5, 0.3, gap=2).tolist() == [0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1]
    assert refine.hysteresis(np.array([0.4, 0.4]), 0.5, 0.3).tolist() == [0, 0]   # never on: off-band does not start


def test_bad_windows_merge_and_ignore_unknown_order():
    scan = [{"t": 0.0, "sb": 0.9}, {"t": 0.1, "sb": 0.95}, {"t": 0.2, "sb": 0.1},
            {"t": 1.0, "sb": 0.1, "why": "dead (hp 0)"}, {"t": 2.0, "sb": 0.1, "why": "column order unknown"}]
    w = refine.bad_windows(scan, margin_s=0.2)
    assert [x[2] for x in w] == ["scoreboard", "dead (hp 0)"]
    assert w[0][0] == pytest.approx(-0.25) and w[0][1] == pytest.approx(0.35)


def test_apply_hud_adds_confirms_and_contradicts():
    actions = ["web_cluster", "amazing_combo"]
    t = np.arange(0, 3, 1 / 60)
    prob = np.zeros((len(t), 2))
    prob[30, 0] = 0.9                                   # below threshold: the HUD cast adds it here
    onset = np.zeros((len(t), 2), bool)
    onset[100, 0] = True                                # confirmed by a cast at 1.7-1.8 s
    onset[150, 1] = True                                # amazing_combo at 2.5 s with full charges and no drop
    events = [Event("web_cluster", 0.6, 0.7, 1, "transition"), Event("web_cluster", 1.7, 1.8, 1, "transition")]
    coverage = {"uppercut.charges": [(2.0, 2.1), (2.1, 2.2)] + [(2.2 + k / 10, 2.3 + k / 10) for k in range(12)]}
    out, basis = refine.apply_hud(onset, prob, t, actions, events, coverage)
    assert out[30, 0] and basis[30, 0] == "hud_added:ammo"
    assert basis[100, 0] == "hud_confirmed:ammo"
    assert basis[150, 1] == "hud_contradicted"
