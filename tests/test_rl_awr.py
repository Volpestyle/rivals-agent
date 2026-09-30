"""rl.awr pure parts: event-to-step alignment, run-bounded returns, weights and the quintile table."""
import json

import pytest

np = pytest.importorskip("numpy")

from rl import awr  # noqa: E402

STEP = 33_333_333


def test_events_land_in_their_step_bin_and_gaps_drop(tmp_path):
    t0 = 1_000_000_000
    anchors = [t0 + k * STEP for k in range(10)]
    labels = {"t0_composition_ns": t0, "ko": [0.05, 10.0], "hit": [0.0, 0.2], "death": []}
    r, counts = awr.step_rewards(anchors, STEP, labels)
    assert r[1] == 10 and r[0] == 1 and r[6] == 1      # 0.05 s -> step 1; 0.2 s -> step 6 (0.2 / 0.0333 = 6.0)
    assert counts == {"kept": 3, "dropped": 1}         # 10 s is past the last step


def test_returns_do_not_cross_runs():
    r = np.array([0, 0, 1, 0, 0, 5.])
    run_start = np.array([1, 0, 0, 1, 0, 0], bool)
    g = awr.discounted_returns(r, run_start, gamma=.5)
    assert g[2] == 1 and g[1] == .5 and g[0] == .25
    assert g[3] == 1.25 and g[5] == 5                   # run 2 sees only its own reward


def test_weights_mean_one_and_clipped():
    w = awr.awr_weights(np.array([-5., 0., 5., 100.]), beta=1.)
    assert abs(w.mean() - 1) < 1e-9
    assert w.max() / w[1] == pytest.approx(awr.W_CLIP)


def test_quintiles_see_a_shift_toward_high_advantage():
    rng = np.random.default_rng(0)
    a = rng.normal(size=1000)
    table = awr.quintile_table(a, .1 * a + rng.normal(scale=.01, size=1000), np.ones(1000, bool))
    assert table["top_minus_bottom"] > 0 and table["spearman"] > .9


def test_anchors_reads_header_and_rows(tmp_path):
    p = tmp_path / "s.jsonl"
    p.write_text(json.dumps({"step_ns": STEP}) + "\n" + "\n".join(json.dumps({"i": k, "anchor_ns": 5 + k * STEP})
                                                                  for k in range(3)) + "\n")
    anc, step = awr.anchors(p)
    assert step == STEP and anc[2] == 5 + 2 * STEP
