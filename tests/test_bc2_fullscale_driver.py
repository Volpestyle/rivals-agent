"""policy.bc2.fullscale_driver's state machine against a fake world (no processes, ssh or Modal)."""
import json

import pytest

from policy.bc2 import fullscale_driver as fd


class Fake(fd.Env):
    def __init__(self, n=4):
        self.t, self.idm, self.r1_state, self.game, self.free = 0, "queued", None, False, 5.
        self.p = {0: True, 1: False}
        self.shard = [[f"expert-1-c{i}", i % 2 == 0, False, False] for i in range(n)]
        self.actions, self.shipper = [], True

    def now(self): return self.t
    def sleep(self, s): self.t += s; self.tick()
    def log(self, m): pass
    def status(self, progress, stage="running"): self.actions.append(("status", stage))
    def game_running(self): return self.game
    def free_gb(self): return self.free
    def idm_stage(self): return self.idm
    def r1(self): return self.r1_state
    def extractor_running(self, part): return self.p[part]
    def shipper_running(self): return self.shipper
    def start_extractor(self, part): self.actions.append(("start", part)); self.p[part] = True
    def shards(self): return [tuple(x) for x in self.shard]
    def build_overlays(self): self.actions.append(("overlays",)); return {"shards": len(self.shard) + 33}
    def put_dir(self, local, path, timeout): self.actions.append(("put", path))
    def push_code(self): self.actions.append(("code",)); return "~/code"
    def launch(self, code, spec, name, timeout): self.actions.append(("launch", [s["name"] for s in spec])); return 0

    def tick(self):                      # the world moves on: scan ends at t=600, work finishes after
        if self.t >= 600:
            self.idm = "running"
        if self.p[1]:
            for x in self.shard:
                x[1] = x[2] = True
        if self.t >= 3000:
            self.r1_state = "done"


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(fd, "ROOT", tmp_path)
    (tmp_path / "overlays-r1").mkdir()
    for s in json.loads((fd.REPO / "policy/bc2/grid-l-static.json").read_text())[0]["expert_sessions"]:
        (tmp_path / "overlays-r1" / s).mkdir()
    monkeypatch.setattr(fd, "expert_windows", lambda dirs: (100, [110, 120]))
    return tmp_path


def test_driver_waits_restarts_once_and_launches_both_arms(world):
    env = Fake()
    fd.drive(env, world / "state.json", poll=60)
    starts = [a for a in env.actions if a[0] == "start"]
    assert starts == [("start", 1)]                                   # once, after the scan
    names = [a for a in env.actions if a[0] == "launch"][0][1]
    assert names == ["fs-A-s0", "fs-B-s0"]
    assert [a[1] for a in env.actions if a[0] == "put"] == [f"/features/{fd.STILL}-hold", "/expert-targets-r1"]
    assert json.loads((world / "state.json").read_text())["step"] == "done" and env.t >= 3000
    assert env.actions[-1] == ("status", "done") and not (world / "FAILED.json").exists()


def test_driver_does_not_restart_while_the_scan_runs_or_the_game_is_up(world):
    env = Fake()
    state = {"step": "restart_p1"}
    assert not fd.step(env, state)                                   # scan still queued, 5 GB free
    env.idm, env.game = "running", True
    assert not fd.step(env, state)                                   # game up
    env.game = False
    assert fd.step(env, state) and env.actions == [("start", 1)]


def test_driver_failure_writes_failed_json_and_stops(world):
    env = Fake()
    env.p[1] = True
    env.r1_state = "failed"
    with pytest.raises(RuntimeError, match="FAILED.json"):
        fd.drive(env, world / "state.json", poll=60)
    failed = json.loads((world / "FAILED.json").read_text())
    assert failed["step"] == "wait_ready" and ("status", "failed") in env.actions
    assert not [a for a in env.actions if a[0] in ("overlays", "launch")]


def test_arm_specs_are_identical_but_for_the_pool():
    a, b = fd.arm_specs(500, ["expert-1-s0"], ["expert-1-s0", "expert-2-c0"])
    diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert diff == {"name", "expert_sessions", "stream_expert", "big"}
    assert a["expert_windows"] == 500 and a["cam_weight"]["weight"] == 5.0
    assert a["expert_mask"]["rdpaco"]["actions"] and a["expert_mask"]["daymr"]["camera"]
