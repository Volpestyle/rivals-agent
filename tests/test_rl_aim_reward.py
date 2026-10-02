"""rl.aim.reward: the dense aim shaping's pure logic (no frames, no corpus), and its wiring into rl.online."""
import math

import pytest

np = pytest.importorskip("numpy")

from rl.aim import reward  # noqa: E402
from rl.aim.reward import AimShaper, potential, shaping_series, window  # noqa: E402


def vec(px, py=360., h=200.):
    """A known target vector with its nearest (and largest) box centred at (px, py) in 1280x720 pixels."""
    dx, dy = px / 1280 - .5, py / 720 - .5
    return [1, 1, dx, dy, h / 720, 1, dx, dy, h / 720, math.log1p(1)]


UNKNOWN = [0.] * 10


def test_potential_is_zero_on_the_crosshair_minus_one_at_the_edge_and_none_when_unknown():
    assert potential(vec(640)) == 0
    assert potential(vec(0)) == pytest.approx(-1)
    assert potential(vec(1280)) == pytest.approx(-1)
    assert potential(vec(320)) == pytest.approx(-.5)
    assert potential(vec(640, 360 + 320)) == pytest.approx(-.5)   # vertical uses the same pixels
    assert potential(UNKNOWN) is None and potential(None) is None


def test_an_unbroken_run_telescopes_and_oscillation_nets_zero():
    xs = [200, 260, 330, 400, 470, 540, 600, 640]
    steps = shaping_series([vec(x) for x in xs], [k * .1 for k in range(len(xs))])
    f = [s.shaping for s in steps[1:]]
    assert all(v is not None and v > 0 for v in f)
    assert sum(f) == pytest.approx(potential(vec(640)) - potential(vec(200)))
    wobble = [640, 600, 560, 600, 640, 680, 720, 680, 640] * 5
    steps = shaping_series([vec(x) for x in wobble], [k * .1 for k in range(len(wobble))])
    assert sum(s.shaping for s in steps[1:]) == pytest.approx(0, abs=1e-9)
    still = shaping_series([vec(300)] * 10, [k * .1 for k in range(10)])
    assert sum(s.shaping for s in still[1:]) == 0


def test_unknown_is_none_and_reacquisition_after_a_gap_is_never_paid():
    seq = [vec(300), UNKNOWN, vec(640), vec(620)]
    steps = shaping_series(seq, [0, .1, .2, .3])
    assert [s.reason for s in steps] == ["first", "unknown", "gap", "ok"]
    assert steps[1].shaping is None and steps[2].shaping is None     # the flicker never pays the jump to centre
    assert steps[3].shaping == pytest.approx(potential(vec(620)) - potential(vec(640)))


def test_a_long_time_gap_re_anchors():
    steps = shaping_series([vec(300), vec(320)], [0, reward.MAX_GAP_S + .1])
    assert steps[1].reason == "gap" and steps[1].shaping is None


def test_a_box_appearing_or_vanishing_is_a_switch_not_a_reward():
    # A KO'd bot at the crosshair vanishes and the next nearest is far right: no penalty for the KO.
    steps = shaping_series([vec(640), vec(1100)], [0, .1])
    assert steps[1].reason == "switch" and steps[1].shaping is None
    # A box at the same place changing height a lot (a fragment, another bot behind) is a switch too.
    steps = shaping_series([vec(600, h=300), vec(610, h=100)], [0, .1])
    assert steps[1].reason == "switch"
    # Ordinary camera motion within the gate pays.
    steps = shaping_series([vec(400), vec(400 + .2 * reward.HALF_W)], [0, .1])
    assert steps[1].reason == "ok" and steps[1].shaping > 0


def test_two_bots_swapping_as_nearest_do_not_jump_the_potential():
    # Bots at -100 and +300 px from the crosshair; the camera pans right 10 px per frame. Nearest swaps from the
    # left bot to the right one at the midpoint; Phi stays continuous, so the cut at the swap drops ~nothing.
    def two(offset):
        left, right = 540 + offset, 940 + offset
        near = min((left, right), key=lambda x: abs(x - 640))
        return vec(near)
    seq = [two(-10 * k) for k in range(40)]
    steps = shaping_series(seq, [k * .1 for k in range(len(seq))])
    phis = [s.phi for s in steps]
    assert max(abs(a - b) for a, b in zip(phis, phis[1:])) <= 10 / reward.HALF_W + 1e-9
    switched = [s for s in steps if s.reason == "switch"]
    assert len(switched) == 1


def test_weight_and_gamma_follow_the_potential_form():
    s = AimShaper(weight=.3, gamma=.9)
    s.update(0, vec(320))
    step = s.update(.1, vec(480))
    assert step.shaping == pytest.approx(.3 * (.9 * potential(vec(480)) - potential(vec(320))))


def test_window_sums_the_next_horizon():
    t = np.arange(10) * .1
    v = np.arange(10, dtype=float)
    w = window(v, t, .25)                     # rows k, k+1, k+2
    assert w[0] == 0 + 1 + 2 and w[7] == 7 + 8 + 9 and w[9] == 9


def test_shaping_in_a_discounted_return_collapses_to_minus_phi():
    # Why the update uses a window, not `returns`: G_k of potential shaping is gamma^(n-k) Phi_n - Phi_k.
    from rl.online.update import returns
    gen = np.random.default_rng(0)
    t = np.arange(200) * .1
    phi = -gen.random(200)
    gamma = .5 ** (.1 / 2.)
    f = np.zeros(200)
    f[:-1] = gamma * phi[1:] - phi[:-1]       # F_k credited to the decision at k
    g = returns(f, t)
    n = len(t) - 1
    want = gamma ** (n - np.arange(200)) * phi[-1] - phi
    want[-1] = 0
    assert np.allclose(g[:-1], want[:-1])


def test_aim_arrays_credit_each_interval_to_the_decision_that_acted_over_it():
    from rl.online.data import aim_arrays
    steps = shaping_series([vec(300), vec(400), UNKNOWN, vec(500), vec(520)], [0., .1, .2, .3, .4])
    r, known = aim_arrays(steps, [0., .2, .3])
    assert r[0] == pytest.approx(potential(vec(400)) - potential(vec(300)))
    assert r[1] == 0 and not known[1]         # the unknown frame and the reacquisition earn no term
    assert r[2] == pytest.approx(potential(vec(520)) - potential(vec(500))) and known[2]
    assert known[0]


def test_update_weights_unchanged_without_aim_and_favour_aiming_with_it():
    from rl.online.update import weights
    t = np.arange(20) * .1
    ep = {"t": t, "reward": np.zeros(20), "reward_aim": np.zeros(20)}
    ep["reward_aim"][5] = .4                  # decision 5 brought the target closer
    ep2 = {"t": t, "reward": np.r_[np.zeros(10), 1., np.zeros(9)]}
    w0, _ = weights([ep, ep2])
    old = {"t": t, "reward": np.zeros(20)}
    w0_old, _ = weights([old, ep2])
    assert all(np.allclose(a, b) for a, b in zip(w0, w0_old))
    w1, stats = weights([ep, ep2], aim_weight=1.)
    assert stats["aim_weight"] == 1.
    assert w1[0][5] > w1[0][0] and w1[0][5] > w1[0][15]
