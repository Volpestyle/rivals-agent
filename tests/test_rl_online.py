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
    rows, result = data.decisions(RUN)
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
