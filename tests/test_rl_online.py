"""rl.online on CPU: the exploration gates, episode targets and rewards, returns/weights, the AWR update and bundles."""
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

np = pytest.importorskip("numpy")
torch = pytest.importorskip("torch")

from rl.online import data, explore, update  # noqa: E402

RUN = Path("data/calibration/compat-check-20260929/learned-01-a")


def test_gate_temperature_zero_is_the_threshold_and_sampling_matches_sigmoid():
    assert explore.gate(.7, .7, 0, .5) == 1 and explore.gate(.69, .7, 0, .5) == 0
    import random
    rng = random.Random(0)
    p, thr, temp = .3, .6, .5
    rate = sum(explore.gate(p, thr, temp, rng.random() or 1e-12) for _ in range(20000)) / 20000
    logit = lambda x: math.log(x / (1 - x))
    want = 1 / (1 + math.exp(-(logit(p) - logit(thr)) / temp))
    assert abs(rate - want) < .01


class FakeBase:
    """The LivePolicy surface the wrapper uses."""
    def __init__(self, probs):
        from policy.range_bc import vocab
        self.names, self.levels = vocab.NAMES, [.5] * vocab.N
        self.mask = tuple(n not in ("ultimate", "team_up") for n in vocab.NAMES)
        self.p = probs
        self.index = 0

    def reset(self):
        from policy.range_bc import vocab
        self.prev = {"held": [0] * vocab.N, "press": [0] * vocab.N, "release": [0] * vocab.N}
        self.index = 0

    def step(self, frame, t=None):
        from policy.live_policy import Step
        from policy.range_bc import executor
        held_p = [self.p] * len(self.names)
        h, p, r = executor.decode_step(held_p, [0.] * len(self.names), [0.] * len(self.names), self.prev["held"],
                                       self.mask, threshold=.5)
        self.prev = {"held": h, "press": p, "release": r}
        self.index += 1
        named = lambda bits: {n: bool(b) for n, b in zip(self.names, bits)}
        return Step(held=named(h), press=named(p), release=named(r), yaw_deg=.1, pitch_deg=0., yaw_deg_s=3.,
                    pitch_deg_s=0., probs={n: (self.p, 0., 0.) for n in self.names}, latency_ms=1., index=self.index - 1)

    def close(self):
        self.closed = True


def test_wrapper_at_zero_temperature_changes_nothing(tmp_path):
    base = FakeBase(.8)
    pol = explore.ExploringPolicy(base, temperature=0, log_path=tmp_path / "x.jsonl")
    pol.reset()
    s = pol.step(None)
    assert s.held["move_forward"] and not s.held["ultimate"]
    pol.close()
    rows = [json.loads(line) for line in (tmp_path / "x.jsonl").read_text().splitlines()]
    assert rows[0]["event"] == "reset" and rows[1]["exec"] == rows[1]["det"] | {"release": []}


def test_wrapper_explores_but_never_fires_masked_actions():
    pol = explore.ExploringPolicy(FakeBase(.45), temperature=1.0, seed=1)
    pol.reset()
    fired = masked = 0
    for _ in range(300):
        s = pol.step(None)
        fired += s.held["move_forward"]
        masked += s.held["ultimate"] or s.press["ultimate"] or s.held["team_up"]
        assert s.yaw_deg == .1                               # the camera is untouched
    assert 60 < fired < 240 and masked == 0                 # p just under threshold: fires ~45% of steps at T=1


def test_returns_decay_and_weights_have_mean_one():
    t = np.arange(0, 3, .1)
    r = np.zeros(len(t))
    r[-1] = 10
    g = update.returns(r, t, half_life_s=1.)
    assert g[-1] == 10 and abs(g[-11] - 5) < 1e-6
    ws, stats = update.weights([{"reward": r, "t": t}, {"reward": np.zeros(len(t)), "t": t}])
    assert abs(np.concatenate(ws).mean() - 1) < 1e-9 and ws[0][-1] > ws[1][-1]


@pytest.mark.skipif(not (RUN / "frames.jsonl").exists(), reason="retained learned-runner run not present")
def test_targets_from_a_real_learned_run():
    rows, saved, result = data.decisions(RUN)
    assert len(saved) >= len(rows) and all(a["t"] <= b["t"] for a, b in zip(saved, saved[1:]))
    live = {"move_forward", "jump", "spider_power", "web_cluster"}
    act, known, cam, cam_known = data.targets(rows, live, yaw_enabled=True)
    ready = np.array([r.get("disposition") == "ready" for r in rows])
    assert act.shape[0] == len(rows) and known[~ready].sum() == 0
    assert (known[ready].any(axis=(1, 2))).all() if ready.any() else True
    assert data.intervals([0, .1, .2, 1.])[1] == pytest.approx(3.) and data.intervals([0, .1, .2, 1.])[3] == 3.


def tiny_policy():
    from policy.bc2.model import Config, Policy2
    cfg = Config(embed=8, motion=8, hidden=16, feat_dropout=0., use_dt=True)
    return Policy2(cfg).eval(), cfg


def fake_episode(n=24, ko_at=18, seed=0):
    from policy.bc2.model import FEAT
    from policy.range_bc import vocab
    rng = np.random.default_rng(seed)
    act = np.zeros((n, 3, vocab.N), np.uint8)
    act[:, 0, vocab.NAMES.index("spider_power")] = rng.integers(0, 2, n)
    known = np.zeros((n, 3, vocab.N), bool)
    known[:, :2, vocab.NAMES.index("spider_power")] = True
    r = np.zeros(n)
    r[ko_at] = 10
    return {"t": np.arange(n) * .1, "dt": np.full(n, 3., np.float32), "act": act, "act_known": known,
            "cam_class": np.full((n, 2), vocab.ZERO_CLASS), "cam_known": np.zeros((n, 2), bool), "reward": r,
            "feats": rng.normal(size=(n, 2, FEAT)).astype(np.float16),
            "gray_g": rng.integers(0, 255, (n, 72, 128), dtype=np.uint8),
            "gray_c": rng.integers(0, 255, (n, 64, 64), dtype=np.uint8)}


def test_update_runs_on_cpu_and_keeps_kl_small(tmp_path):
    model, cfg = tiny_policy()
    new, summary = update.update(model, model, [fake_episode(), fake_episode(seed=1)], steps=6, device="cpu",
                                 log=lambda m: None)
    assert summary["episodes"] == 2 and math.isfinite(summary["last"]["loss"])
    assert summary["first"]["kl"] < 1e-4                      # starts at the base policy
    assert any((a != b).any() for a, b in zip(model.state_dict().values(), new.state_dict().values()))


def test_write_bundle_points_at_base_tower_files(tmp_path):
    model, cfg = tiny_policy()
    base = tmp_path / "base"
    base.mkdir()
    (base / "vision.safetensors").write_bytes(b"v")
    (base / "cfg.json").write_text("{}")
    (base / "bundle.json").write_text(json.dumps({"kind": "bc2", "live": {}, "thresholds": {}, "files": {
        "checkpoint": {"path": "selected.pt", "sha256": "x"}, "vision": {"path": "vision.safetensors", "sha256": "y"},
        "vision_config": {"path": "cfg.json", "sha256": "z"}}}))
    out = update.write_bundle(model, cfg.as_dict(), base, tmp_path / "rl-001", name="rl-001")
    spec = json.loads((out / "bundle.json").read_text())
    assert Path(spec["files"]["vision"]["path"]).is_absolute() and spec["files"]["vision"]["sha256"] == "y"
    payload = torch.load(out / "selected.pt", weights_only=True)
    from policy.bc2.model import Config, Policy2
    Policy2(Config(**payload["config"])).load_state_dict(payload["model"])
    assert spec["files"]["checkpoint"]["sha256"] == update._sha256(out / "selected.pt")


def test_step_before_reset_works_like_the_live_warmup():
    base = FakeBase(.45)
    base.reset()                            # the base LivePolicy resets itself in __init__
    pol = explore.ExploringPolicy(base, temperature=.5, seed=2)
    pol.step(None)                          # learned_runner's warm-up steps before policy.reset()
    pol.reset()
    assert isinstance(pol.step(None).held["move_forward"], bool)


def test_curve_plot_falls_back_to_cv2(tmp_path):
    pytest.importorskip("cv2")
    from rl.online import sitting
    curve = [{"episode": 0, "arm": "bc", "kos_per_min": 2.}, {"episode": 1, "arm": "rl", "kos_per_min": 3.}]
    sitting._plot_cv2(curve, tmp_path / "c.png")
    assert (tmp_path / "c.png").stat().st_size > 1000


def test_options_hold_one_live_action_for_a_bounded_time():
    base = FakeBase(.01)                    # an idle policy: nothing fires on its own
    base.reset()
    pol = explore.ExploringPolicy(base, temperature=0., seed=4, option_rate_hz=1.0)
    pol.reset()
    runs, current, length, masked = [], None, 0, 0
    for k in range(3000):                   # 100 s at 30 Hz
        s = pol.step(None, t=k / 30)
        on = [n for n, v in s.held.items() if v]
        assert len(on) <= 1
        masked += s.held["ultimate"] or s.held["team_up"]
        name = on[0] if on else None
        if name == current and name is not None:
            length += 1
        else:
            if current is not None:
                runs.append(length)
            current, length = name, 1 if name else 0
    assert masked == 0
    assert 40 <= len(runs) <= 110           # ~1 option/s, each lasting 0.2-0.8 s, over 100 s
    assert max(runs) <= .8 * 30 + 1 and min(runs) >= 1


def test_no_options_and_zero_temperature_is_still_the_plain_decode():
    base = FakeBase(.8)
    pol = explore.ExploringPolicy(base, temperature=0., option_rate_hz=0.)
    pol.reset()
    assert pol.step(None, t=0.).held == base.step(None).held


def test_guard_frame_rewards_are_credited_to_the_preceding_decision():
    r = data.credit([0.05, 0.12, 0.31, 0.9], [1., 0., 10., 1.], [0.0, 0.1, 0.3])
    assert list(r) == [1., 0., 11.]          # 0.12 -> decision 0.1; 0.31 and 0.9 -> decision 0.3


def test_after_episode_only_a_pixel_confirmed_death_continues_and_safety_stops_end_the_sitting():
    from rl.online.sitting import after_episode, reset_status
    assert after_episode("deadline", False) == (True, None)
    assert after_episode("deadline", False, "ready") == (True, None)
    assert after_episode("deadline", False, "failed")[0] is False       # a reset that is not ready stops the sitting
    assert after_episode("range_lost", True, "ready") == (True, None)     # a fall seen on the pixels (hp 0 twice)
    assert after_episode("range_lost", False, "ready")[0] is False        # HUD loss alone proves nothing
    for stop in ("focus_lost", "takeover", "idle", "stale_or_nonmonotonic_frame", "exception:ValueError:x", None):
        assert after_episode(stop, True, "ready")[0] is False
    assert reset_status({"reset": {"status": "ready"}}) == "ready" and reset_status({}) is None


@pytest.mark.skipif(not Path("data/calibration/rl-sitting-20260930-01/ep-005-rl/stop.png").exists(),
                    reason="first live RL sitting not present")
def test_the_live_fall_is_seen_on_the_last_frame_and_stop_png():
    e = data.episode("data/calibration/rl-sitting-20260930-01/ep-005-rl", {"jump"})
    assert e["events"]["death"] == 1 and e["events"]["hit"] == 0     # the 000052 "hit" was water foam (HIT_RUN 6)


@pytest.mark.skipif(not (RUN / "frames.jsonl").exists(), reason="retained learned-runner run not present")
def test_confirmed_death_puts_the_penalty_on_the_last_decision():
    e0 = data.episode(RUN, {"jump"})
    e1 = data.episode(RUN, {"jump"}, death=True)
    assert e1["events"]["death"] == 1 and e1["reward"][-1] == e0["reward"][-1] - 10
    assert (e1["reward"][:-1] == e0["reward"][:-1]).all()


def test_camera_sampling_follows_the_tempered_distribution():
    import random
    rng = random.Random(0)
    probs = [0.] * 31
    probs[15], probs[20] = .75, .25
    draws = [explore.sample_class(probs, 1., rng.random()) for _ in range(4000)]
    assert abs(draws.count(20) / 4000 - .25) < .03 and set(draws) <= {15, 20}
    hot = [explore.sample_class(probs, .25, rng.random()) for _ in range(4000)]
    assert hot.count(20) / 4000 < .05                           # low temperature sharpens toward the mode


def test_turn_options_yaw_toward_the_outline_and_stop_when_centred():
    bearing = {"v": .4}
    base = FakeBase(.01)
    base.reset()
    pol = explore.ExploringPolicy(base, seed=3, turn_rate_hz=2., bearing=lambda frame: (True, bearing["v"]))
    pol.reset()
    yaws = [pol.step(None, t=k / 30).yaw_deg for k in range(300)]
    turning = [y for y in yaws if y != .1]
    assert turning and all(.6 <= y <= 2.5 for y in turning)     # toward +bearing, within TURN_DEG
    bearing["v"] = -.3
    yaws = [pol.step(None, t=10 + k / 30).yaw_deg for k in range(300)]
    assert any(y < 0 for y in yaws) and all(y <= 2.5 for y in yaws)
    bearing["v"] = .01                                          # centred: no turn
    pol.turn = None
    assert all(pol.step(None, t=30 + k / 30).yaw_deg == .1 for k in range(60))


def test_no_outline_means_no_turn_and_zero_settings_leave_the_step_alone():
    base = FakeBase(.8)
    base.reset()
    pol = explore.ExploringPolicy(base, seed=1, turn_rate_hz=2., bearing=lambda frame: (False, 0.))
    pol.reset()
    assert all(pol.step(None, t=k / 30).yaw_deg == .1 for k in range(120))
    plain = explore.ExploringPolicy(FakeBase(.8))
    plain.reset()
    s = plain.step(None, t=0.)
    assert s.yaw_deg == .1 and s.held["move_forward"]


class CamBase(FakeBase):
    """FakeBase whose step goes through _bc2_predict, returning camera probs shaped [2, C] like LivePolicy's bc2 path."""
    def __init__(self, probs, cam_rows):
        super().__init__(probs)
        self.cam_rows = cam_rows

    def _bc2_predict(self, frame, t=None):
        return [], self.cam_rows

    def step(self, frame, t=None):
        _, cams = self._bc2_predict(frame, t)
        s = super().step(frame, t)
        assert len(cams) == 2
        return s


def test_camera_sampling_on_the_real_two_row_shape():
    from policy.range_bc import vocab
    yaw = [0.] * vocab.CAMERA_CLASSES
    pitch = [0.] * vocab.CAMERA_CLASSES
    yaw[vocab.ZERO_CLASS + 5], pitch[vocab.ZERO_CLASS - 2] = 1., 1.
    base = CamBase(.01, [yaw, pitch])
    base.reset()
    pol = explore.ExploringPolicy(base, cam_temperature=1., seed=0)
    pol.reset()
    s = pol.step(None, t=0.)
    assert s.yaw_deg == vocab.class_degrees(vocab.ZERO_CLASS + 5) and s.pitch_deg == vocab.class_degrees(vocab.ZERO_CLASS - 2)
    assert math.isfinite(s.yaw_deg_s) and abs(s.yaw_deg) <= vocab.CLAMP_DEG


@pytest.mark.skipif(not Path("data/calibration/rl-sitting-20260930-04/ep-001-rl/stop.png").exists(),
                    reason="sitting 04 not present")
def test_a_fall_seen_only_on_stop_png_is_a_death():
    e = data.episode("data/calibration/rl-sitting-20260930-04/ep-001-rl", {"jump"})
    assert e["events"]["death"] == 1 and e["reward"][-1] <= -10
    from rl.online.sitting import after_episode
    assert after_episode(e["result"], bool(e["events"]["death"]), "ready") == (True, None)
