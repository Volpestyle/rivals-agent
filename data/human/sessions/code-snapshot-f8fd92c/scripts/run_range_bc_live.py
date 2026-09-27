"""Prepare a range_bc run, or execute an independently reviewed supervised sitting.

Default is preparation only: no capture or pad. --live requires the review receipt
and scheduled sitting identifier. See agent.live_range_bc for metric limitations.
Run inside the PC desktop session; this command never focuses or navigates menus.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import live_range_bc as harness
from agent.controller import Live
from policy.range_bc import vocab

REVIEWED_FILES = ("agent/live_range_bc.py", "scripts/run_range_bc_live.py", "tests/test_live_range_bc.py")
# Snapshot at import, then compare both this snapshot and on-disk bytes at launch.
# Editing source after this process loads it requires restarting and a new receipt.
LOADED_HASHES = {name: harness.sha256(ROOT / name) for name in REVIEWED_FILES}


def verify_review_receipt(path):
    raw = Path(path).read_bytes()
    receipt = json.loads(raw.decode("utf-8-sig"))
    harness.require(receipt.get("format") == "range-bc-live-review-v1", "unsupported live review receipt")
    pins = receipt.get("files")
    harness.require(isinstance(pins, dict) and set(pins) == set(REVIEWED_FILES), "review must pin all three files")
    for name in REVIEWED_FILES:
        harness.require(pins[name] == LOADED_HASHES[name] == harness.sha256(ROOT / name),
                        f"stale review or loaded source differs: {name}")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "files": pins}


def attach_live(cap, guard, *, settle_seconds=3., clock=time.perf_counter):
    """Enumeration/neutral settling is an explicitly excluded initial interval."""
    harness.require(3 <= settle_seconds <= 30, "settling must be 3..30 seconds")
    began = clock()
    live = Live(capture=cap, guard=guard, settle_s=settle_seconds)
    return live, {"reason": "pad_enumeration_and_neutral_settle", "started": began,
                  "stopped": clock(), "requested_settle_seconds": settle_seconds,
                  "commands_sent": False}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint", type=Path, required=True)
    p.add_argument("--checkpoint-sha256", required=True)
    p.add_argument("--support-json", type=Path, required=True,
                   help="checkpoint_sha256, press counts in vocab order, swing_mode, live_mask")
    p.add_argument("--settings-json", type=Path, required=True,
                   help="binding_profile, swing_mode, cooldowns, patch, calibration (maps, deadzones, evidence)")
    p.add_argument("--output", type=Path, required=True, help="new run directory; never overwritten")
    p.add_argument("--duration", type=float, default=60.)
    p.add_argument("--max-prediction-age", type=float, default=.25, help="seconds, <=1; late output stops the run")
    t = p.add_mutually_exclusive_group()
    t.add_argument("--threshold", type=float, default=.5, help="one threshold for every action/channel")
    t.add_argument("--thresholds-json", type=Path, help="checkpoint-pinned per-action decoder audit artifact")
    p.add_argument("--camera-disabled", action="store_true", help="explicit zero camera; no stale default calibration")
    p.add_argument("--dino-assets", type=Path, help="local frozen assets, required for CM3 H/W")
    p.add_argument("--dino-config-sha256")
    p.add_argument("--ffmpeg", default="ffmpeg")
    p.add_argument("--cpu-threads", type=int, default=2)
    p.add_argument("--settle-seconds", type=float, default=3., help="neutral pad enumeration settle, 3..30 seconds; excluded")
    p.add_argument("--live", action="store_true", help="attach a pad; requires review and a supervised sitting")
    p.add_argument("--review-receipt", type=Path, help="JSON range-bc-live-review-v1 receipt pinning all three reviewed files")
    p.add_argument("--sitting", help="lead/pad-binds scheduled supervised sitting identifier")
    p.add_argument("--game-pid", type=int, help="require this PID in the foreground; no focus injection")
    return p


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def code_receipt():
    paths = [p for directory in ("agent", "policy/range_bc", "perception", "scripts")
             for p in (ROOT / directory).rglob("*.py")]
    paths += [ROOT / "uv.lock", ROOT / "pyproject.toml", ROOT / "docs/spiderman-kit.md"]
    hashes = {p.relative_to(ROOT).as_posix(): harness.sha256(p) for p in sorted(paths)}
    return {"files": hashes, "sha256": hashlib.sha256(harness.canonical(hashes)).hexdigest(),
            "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                       capture_output=True, check=True).stdout.strip()}


def any_key_pressed():
    """Read-only desktop keyboard poll; excludes mouse buttons and controller keys."""
    import ctypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    # Call every key even when one is down. Low bit catches a short tap between polls.
    keys = [user32.GetAsyncKeyState(vk) for vk in range(8, 255)
            if not 0xC3 <= vk <= 0xDA]  # Win32 gamepad VKs are not human keypresses
    return any(value & 0x8001 for value in keys)


def main(argv=None):
    a = parser().parse_args(argv)
    harness.require(0 < a.duration <= 600 and 0 < a.max_prediction_age <= 1, "invalid duration/prediction age")
    harness.require(1 <= a.cpu_threads <= 8, "CPU threads must be 1..8")
    harness.require(3 <= a.settle_seconds <= 30, "settling must be 3..30 seconds")
    review = None
    if a.live:
        harness.require(platform.system() == "Windows", "live capture/input belongs to the Windows desktop")
        harness.require(a.review_receipt is not None and a.review_receipt.is_file() and a.sitting,
                        "live use requires binds-review receipt and the scheduled supervised sitting")
        harness.require(a.game_pid is not None and 0 < a.game_pid <= 0xffffffff, "explicit game PID required")
        review = verify_review_receipt(a.review_receipt)
    settings, support = read_json(a.settings_json), read_json(a.support_json)
    cal = harness.calibration(settings, camera_disabled=a.camera_disabled)
    mask = harness.support_mask(support, a.checkpoint_sha256)
    levels = harness.thresholds(read_json(a.thresholds_json) if a.thresholds_json else a.threshold,
                                a.checkpoint_sha256)
    import torch
    torch.set_num_threads(a.cpu_threads)
    model, metadata = harness.load_checkpoint(a.checkpoint, a.checkpoint_sha256)
    distribution = harness.validate_distribution(metadata, settings["cooldowns"])
    preprocess = harness.CachePreprocessor(a.ffmpeg)
    backbone = None
    if getattr(model.config, "arm", "I") in ("H", "W"):
        harness.require(a.dino_assets is not None and a.dino_config_sha256, "local pinned DINO assets required")
        from policy.range_bc.cm3_features import FrozenDino
        backbone = FrozenDino(a.dino_assets, config_sha256=a.dino_config_sha256).cpu()
    predictor = harness.Predictor(model, preprocess, cooldowns=settings["cooldowns"], backbone=backbone)
    files = {str(p.resolve()): harness.sha256(p) for p in
             (a.support_json, a.settings_json, a.thresholds_json, a.review_receipt) if p is not None}
    manifest = {"format": "range-bc-live-exploratory-v1", "created_utc": datetime.now(timezone.utc).isoformat(),
                "checkpoint": str(a.checkpoint.resolve()), "checkpoint_sha256": a.checkpoint_sha256,
                "checkpoint_metadata": metadata, "code": code_receipt(), "input_files": files,
                "review": review, "input_distribution": distribution,
                "thresholds": dict(zip(vocab.NAMES, levels)), "live_mask": list(mask), "settings": settings,
                "camera_disabled": a.camera_disabled, "duration": a.duration, "max_prediction_age": a.max_prediction_age,
                "device": "cpu", "cpu_threads": a.cpu_threads, "torch": torch.__version__,
                "python": sys.version, "platform": platform.platform(), "ffmpeg": preprocess.version,
                "cache_graph": preprocess.graph, "dino": backbone.asset_receipt if backbone is not None else None,
                "capture": "native BGR dxcam",
                "frame_retention": {"policy_and_send_proof": "native lossless PNG, background writer",
                                    "guard_trace_hz": 1., "queue_capacity": 2, "overflow": "drop new frame, count by role"},
                "settle_seconds": a.settle_seconds, "settle_excluded_from_scorecard": True,
                "camera_decoder": "median, executor saturation", "step_seconds": harness.executor.STEP_S,
                "sitting": a.sitting, "game_pid": a.game_pid, "live": a.live,
                "scope": "exploratory practice-range failure observation; no gate or performance claim",
                "parity_limits": "Exact RGB cache transform; capture/OBS encoding and pad/M&K HUD remain different."}
    journal = harness.Journal(a.output, manifest)
    if not a.live:
        journal.write("result.json", {"stop_reason": "prepared_only", "pad_opened": False})
        journal.close()
        return 0
    live = None
    try:
        from agent.loop import foreground_pid_guard
        from capture import Capture, preflight
        from record import in_range
        from perception.scoreboard import is_killfeed
        focused = foreground_pid_guard(a.game_pid)
        harness.require(focused(), "game is not in foreground")
        cap = Capture("dxcam")
        preflight(cam=cap)
        # Clear old GetAsyncKeyState tap bits before the sitting begins.
        any_key_pressed()
        harness.require(not any_key_pressed(), "release keyboard before attaching pad")
        # Verify again after model/dependency loading and before opening a pad.
        harness.require(verify_review_receipt(a.review_receipt) == review, "review changed during preparation")
        attach_deadline = time.perf_counter() + a.settle_seconds + a.duration
        guard = lambda frame: (focused() and time.perf_counter() < attach_deadline and in_range(frame))
        live, excluded = attach_live(cap, guard, settle_seconds=a.settle_seconds)
        attach_deadline = time.perf_counter() + a.duration
        journal.event(kind="excluded_interval", **excluded)
        # No startup movement. Settling does not prove the first command was
        # acknowledged by the game; commanded and observed actions remain distinct.
        result = harness.run(live, predictor, journal, mask=mask, levels=levels, cal=cal, duration=a.duration,
                             stop_requested=any_key_pressed, range_guard=guard, feed_reader=is_killfeed,
                             max_prediction_age=a.max_prediction_age, focused=focused, excluded_intervals=[excluded])
        return 0 if result["stop_reason"] in ("duration", "keypress", "keyboard_interrupt") else 1
    except BaseException as exc:
        if live is not None:
            live.close()
        if not journal.stream.closed:
            try:
                journal.write("result.json", {"stop_reason": "startup_error", "error": f"{type(exc).__name__}: {exc}"})
            finally:
                journal.close()
        raise


if __name__ == "__main__":
    raise SystemExit(main())
