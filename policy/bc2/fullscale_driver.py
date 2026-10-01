"""Overnight driver for the full-scale A/B (lead, 2026-09-30; VUH-1346). Detached, low priority, small; resumable
from its state file. Steps, in order:

  restart_p1  when idm's r1 scan is over (its export receipt left "queued", or r1 DONE.json exists, or free memory
              stayed above 8 GB for 10 minutes) and the game is not running: start extractor --part 1/2 again
  wait_ready  every planned shard extracted and shipped, none marked ship-failed, and r1's DONE.json present
  overlays    r1 target overlays for all shards (old -s: aligned tables; new -c: plain tables), then the still-start
              hold features and the overlays go to the volume
  launch      the approved EXPLORE arms, A (the grid-l 13-shard 3.7 h cohort) and B (all ~50 h), 1 seed each, from a
              code snapshot on the Mac; waits for both with a deadline (each Modal function has its own timeout)

Any failure writes FAILED.json (step, reason) and a failed board receipt and stops: no blind retry.

    python -m policy.bc2.fullscale_driver            (detached: see docs/lanes/policy.md)
"""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path("D:/rivals-policy/fullscale")
R1_PLAIN = Path("D:/rivals-agent-local/idm-labels-r1/v2-cd-r1")
R1_ALIGNED = Path("D:/rivals-agent-local/idm-labels-aligned-r1/v2-cd-r1")
IDM_RECEIPT = Path("C:/Users/volpe/jobs/idm-v2cd-r1-export.status.json")
REPO = Path(__file__).resolve().parents[2]
PY = "C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe"
OLD_LABELS = ("D:/rivals-policy/expert-labels", "D:/rivals-policy/expert-labels-mac")
STILL = "20260930T193113-731Z-163680-1"
LABEL_SOURCE = "idm v2-cd (v2-c-w8-wide.pt+v2-d-w12-wide.pt)"
STEPS = ("restart_p1", "wait_ready", "overlays", "launch", "done")
NAME = "policy-fullscale-driver"


class Env:
    """The real world. Tests replace it with a fake that records actions."""
    def now(self):
        return time.time()

    def sleep(self, s):
        time.sleep(s)

    poll_wait = staticmethod(time.sleep)

    def log(self, msg):
        print(time.strftime("%H:%M:%S"), msg, flush=True)

    def status(self, progress, stage="running"):
        try:
            sys.path.insert(0, str(REPO))
            from scripts.job_status import write
            write(NAME, owner="policy (VUH-1346)", stage=stage, host="pc", evidence=str(ROOT / "driver.log"),
                  progress=progress)
        except Exception as exc:
            self.log(f"status write failed: {exc}")

    def game_running(self):
        from policy.bc2.expert import game_running
        return game_running()

    def free_gb(self):
        from policy.bc2.expert import free_ram_gb
        return free_ram_gb()

    def idm_stage(self):
        try:
            return json.loads(IDM_RECEIPT.read_text())["stage"]
        except Exception:
            return None

    def r1(self):
        """'done', 'failed' or None."""
        return "done" if (R1_PLAIN / "DONE.json").exists() else "failed" if (R1_PLAIN / "FAILED.json").exists() else None

    def processes(self):
        out = subprocess.run(["powershell", "-NoProfile", "-c",
                              "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | % { $_.CommandLine }"],
                             capture_output=True, text=True, timeout=60).stdout
        return [line for line in out.splitlines() if "policy.bc2.fullscale " in line + " "]

    def extractor_running(self, part):
        return any(" run " in p and f"{part}/2" in p for p in self.processes())

    def shipper_running(self):
        return any(" ship " in p for p in self.processes())

    def start_extractor(self, part):
        """Via PowerShell Start-Process, so the extractor is not in the driver's process tree (a tree kill of the
        driver once stopped it, 2026-09-30) and runs at BelowNormal."""
        log = ROOT / f"extract-p{part}-driver"
        cmd = (f"$env:PYTHONUNBUFFERED='1'; $p = Start-Process -FilePath '{PY}' -ArgumentList '-m',"
               f"'policy.bc2.fullscale','run','{ROOT / 'labels'}','--out','{ROOT / 'features'}','--part','{part}/2' "
               f"-WorkingDirectory '{REPO}' -WindowStyle Hidden -RedirectStandardOutput '{log}.log' "
               f"-RedirectStandardError '{log}.err' -PassThru; Start-Sleep 2; "
               f"Get-CimInstance Win32_Process -Filter \"ParentProcessId=$($p.Id)\" | % {{ "
               f"(Get-Process -Id $_.ProcessId).PriorityClass = 'BelowNormal' }}")
        # no captured pipes: the detached extractor would inherit them and the call would wait for its exit
        subprocess.run(["powershell", "-NoProfile", "-c", cmd], check=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)

    def shards(self):
        """[(name, extracted, shipped, ship_failed)] for every planned shard."""
        out = []
        for p in sorted((ROOT / "labels").glob("expert-*-c*.steps.jsonl")):
            d = ROOT / "features" / p.name.replace(".steps.jsonl", "")
            out.append((d.name, (d / "meta.json").exists(), (d / "shipped").exists(), (d / "ship-failed").exists()))
        return out

    def run(self, args, timeout):
        r = subprocess.run(args, cwd=REPO, capture_output=True, text=True, timeout=timeout)
        if r.returncode:
            raise RuntimeError(f"{' '.join(map(str, args[:4]))} failed: {r.stderr[-400:]}")
        return r.stdout

    def build_overlays(self):
        out = self.run([PY, "-m", "policy.bc2.fullscale", "overlays", *OLD_LABELS, str(ROOT / "labels"),
                        "--aligned", str(R1_ALIGNED), "--plain", str(R1_PLAIN), "--meta", str(ROOT / "old-meta"),
                        str(ROOT / "features"), "--out", str(ROOT / "overlays-r1")], 4 * 3600)
        return json.loads(out.strip().splitlines()[-1])

    def put_dir(self, local, volume_path, timeout):
        """Copy a local directory to the Mac and `modal volume put` it, detached, polled with short ssh calls."""
        from policy.bc2.fullscale import MAC_SHIP, MODAL, Unknown, VOLUME, _query, marker, scp
        name = Path(local).name
        remote = f"{MAC_SHIP}/{name}"
        _query(f"mkdir -p {MAC_SHIP} && rm -rf {remote} {remote}.done {remote}.log")
        scp(local, f"{MAC_SHIP}/", timeout, recursive=True)
        _query(f"nohup sh -c '{MODAL} volume put --force {VOLUME} {remote} {volume_path} && rm -rf {remote} "
               f"&& echo ok > {remote}.done || echo fail > {remote}.done' > {remote}.log 2>&1 < /dev/null &")
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.poll_wait(20)
            try:
                done = marker(f"{remote}.done")
            except Unknown:
                continue
            if done is None:
                continue
            if done == "ok":
                return
            if done == "fail":
                raise RuntimeError(f"modal volume put {name} failed (see {remote}.log on the Mac)")
        raise TimeoutError(f"modal volume put {name} not done after {timeout} s")

    def push_code(self):
        """git archive of HEAD (the files cloud.py's image needs) unpacked on the Mac; returns the Mac path."""
        sha = self.run(["git", "rev-parse", "--short", "HEAD"], 60).strip()
        tar = ROOT / f"code-{sha}.tar"
        self.run(["git", "archive", "-o", str(tar), "HEAD", "agent", "policy", "scripts",
                  "data/human/sealed-denylist.v2.json", "data/human/patch-equivalence.json"], 300)
        from policy.bc2.fullscale import _query, scp
        scp(tar, "dev/policy-bc2/", 600)
        _query(f"cd ~/dev/policy-bc2 && rm -rf code-{sha} && mkdir code-{sha} && tar -xf code-{sha}.tar -C code-{sha}")
        return f"~/dev/policy-bc2/code-{sha}"

    def launch(self, code, spec, log_name, timeout):
        """Run the grid on the Mac (detached, niced); poll its exit file; return the exit code."""
        from policy.bc2.fullscale import Unknown, _query, marker, scp
        spec_file = ROOT / f"{log_name}.json"
        spec_file.write_text(json.dumps(spec, indent=1) + "\n")
        scp(spec_file, f"dev/policy-bc2/{spec_file.name}", 300)
        log = f"~/dev/policy-bc2/{log_name}.log"
        _query(f"cd {code} && nohup sh -c 'export PATH=$HOME/.local/bin:$PATH; MODAL_PROFILE=rivals nice -n 10 "
               f"taskpolicy -b modal run -m policy.bc2.cloud::grid --spec \"$(cat ../{spec_file.name})\" "
               f"--log {log}; echo $? > {log}.exit' > {log} 2>&1 < /dev/null &")
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.poll_wait(120)
            try:
                code_text = marker(f"{log}.exit")
            except Unknown:
                continue
            if code_text:
                return int(code_text)
            self.status(f"arms running on Modal; Mac log {log}")
        raise TimeoutError(f"grid not finished after {timeout} s (Mac log {log}); Modal fit timeouts still apply")


def expert_windows(a_overlay_dirs, trials=30):
    """Expert windows per epoch both arms draw: 98% of the smallest count A's pool gives over random phases."""
    import numpy as np
    import torch
    from policy.bc2.train import windows

    class Runs:
        def __init__(self, run_start):
            starts = np.flatnonzero(run_start).tolist()
            self.runs = list(zip(starts, starts[1:] + [len(run_start)]))
    sessions = [Runs(np.load(Path(d) / "targets.npz")["run_start"]) for d in a_overlay_dirs]
    counts = [len(windows(sessions, torch.Generator().manual_seed(k), jitter=True)) for k in range(trials)]
    return int(.98 * min(counts)), counts


def arm_specs(n_windows, a_shards, b_shards):
    grid = json.loads((REPO / "policy/bc2/grid-l-static.json").read_text())[0]
    mask = dict(grid["expert_mask"])
    for creator in ("rdpaco", "6fthumblearab"):          # new creators: ability slots unverified, as for the others
        mask[creator] = {"camera": False, "actions": ["amazing_combo", "get_over_here", "web_cluster"]}
    common = {k: grid[k] for k in ("seed", "epochs", "batch_size", "use_dt", "hidden", "layers", "static_aug")}
    common.update(expert=True, expert_mask=mask, expert_targets="/out/expert-targets-r1",
                  expert_label_source=LABEL_SOURCE, expert_windows=n_windows,
                  cam_weight=json.loads((REPO / "policy/bc2/kill-rows-onset5.json").read_text()),
                  press_unknown=["spider_power"], soft_targets=["press_soft"],
                  extra_train=[f"{STILL}-fit"], oversample={f"{STILL}-fit": .15},
                  eval_sessions=["20260925T212646-322Z-49728-6", f"{STILL}-hold"])
    return [dict(common, name="fs-A-s0", expert_sessions=list(a_shards)),
            dict(common, name="fs-B-s0", expert_sessions=list(b_shards), stream_expert=True, big=True)]


def step(env, state):
    """Advance one step if its condition holds; returns True when the state changed."""
    s = state["step"]
    if s == "restart_p1":
        if env.extractor_running(1) or all(e for i, (_, e, _, _) in enumerate(env.shards()) if i % 2 == 1):
            state["step"] = "wait_ready"
            return True
        free = env.free_gb()
        state["free_streak"] = state.get("free_streak", 0) + 1 if free > 8 else 0
        scan_over = env.idm_stage() in ("running", "done", "failed") or env.r1() is not None \
            or state["free_streak"] >= 10
        if scan_over and not env.game_running():
            env.start_extractor(1)
            env.log(f"started extractor 1/2 (idm stage {env.idm_stage()}, r1 {env.r1()}, free {free:.1f} GB)")
            state["step"] = "wait_ready"
            return True
        return False
    if s == "wait_ready":
        if env.r1() == "failed":
            raise RuntimeError("idm r1 export wrote FAILED.json")
        shards = env.shards()
        failed = [n for n, _, _, f in shards if f]
        if failed:
            raise RuntimeError(f"ship-failed shards need the owner: {failed}")
        if not all(e for _, e, _, _ in shards) and not env.game_running() and not env.extractor_running(0) \
                and not env.extractor_running(1):
            state["dead_polls"] = state.get("dead_polls", 0) + 1
            if state["dead_polls"] >= 3:
                raise RuntimeError("shards remain unextracted and no extractor is running")
        else:
            state["dead_polls"] = 0
        if not all(sh for _, _, sh, _ in shards) and all(e for _, e, _, _ in shards) and not env.shipper_running():
            raise RuntimeError("shards remain unshipped and the shipper is not running")
        state["progress"] = f"{sum(e for _, e, _, _ in shards)} extracted, {sum(sh for _, _, sh, _ in shards)} " \
                            f"shipped of {len(shards)}; r1 {env.r1()}"
        if all(sh for _, _, sh, _ in shards) and env.r1() == "done":
            state["step"] = "overlays"
            return True
        return False
    if s == "overlays":
        summary = env.build_overlays()
        env.log(f"overlays: {summary}")
        if summary["shards"] != len(env.shards()) + 33:
            raise RuntimeError(f"overlay count {summary['shards']} != {len(env.shards()) + 33} shards")
        env.put_dir(Path("D:/rivals-policy/local-features") / f"{STILL}-hold", f"/features/{STILL}-hold", 1800)
        env.put_dir(ROOT / "overlays-r1", "/expert-targets-r1", 3 * 3600)
        state["step"] = "launch"
        return True
    if s == "launch":
        grid = json.loads((REPO / "policy/bc2/grid-l-static.json").read_text())[0]
        a = grid["expert_sessions"]
        b = sorted(p.name for p in (ROOT / "overlays-r1").iterdir() if p.is_dir())
        n, counts = expert_windows([ROOT / "overlays-r1" / x for x in a])
        state["expert_windows"], state["window_counts"] = n, [min(counts), max(counts)]
        specs = arm_specs(n, a, b)
        code = env.push_code()
        env.log(f"launching A ({len(a)} shards) and B ({len(b)} shards), {n} expert windows/epoch, code {code}")
        rc = env.launch(code, specs, "fs-explore", 14 * 3600)
        if rc:
            raise RuntimeError(f"grid exited {rc}")
        state["step"] = "done"
        return True
    return False


def drive(env, state_path, poll=120):
    state = json.loads(Path(state_path).read_text()) if Path(state_path).exists() else {"step": STEPS[0]}
    failed = Path(state_path).parent / "FAILED.json"
    try:
        while state["step"] != "done":
            changed = step(env, state)
            Path(state_path).write_text(json.dumps(state, indent=1) + "\n")
            env.status(f"{state['step']}: {state.get('progress', '')}")
            if not changed:
                env.sleep(poll)
        env.status("A and B launched and finished; reports at /runs/fs-A-s0, /runs/fs-B-s0", stage="done")
        env.log("done")
    except Exception as e:
        failed.write_text(json.dumps({"step": state["step"], "reason": str(e)[:2000],
                                      "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, indent=1) + "\n")
        env.status(f"FAILED at {state['step']}: {str(e)[:150]}", stage="failed")
        env.log(f"FAILED at {state['step']}: {e}")
        raise


if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    drive(Env(), ROOT / "driver-state.json")
