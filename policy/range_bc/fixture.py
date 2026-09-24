"""Synthetic step tables and videos for tests and the plumbing smoke. Never admitted, never a human recording.

`session(...)` returns (header, rows) that satisfy `steps.load`'s contract: runs of 30 Hz anchors over a 120 fps
frame clock, holds that toggle, taps, multi-edge steps, unknown holds after a run start, unknown mouse steps,
autocorrelated camera motion with onsets, unsupported presses, rejected segments, both regimes and optional HUD reads.
`write(path, header, rows)` writes it as JSON Lines. `write_video` makes a lossless FFV1 video whose frames are solid
colours chosen per frame, so a cache can be checked pixel for pixel.
"""
import json
from pathlib import Path
import random
import subprocess

from . import steps, vocab

STEP_NS = 33_333_333
PERIOD_NS = 8_333_333
T0_NS = 1_000_000_000
CALIBRATION = {"kind": "slow_turn_constant", "yaw_deg_per_count": .0132, "pitch_deg_per_count": .0132,
               "pitch": {"kind": "derived_equal_sensitivity"}, "source": "synthetic"}

HOLDERS = ("move_forward", "move_left", "move_back", "move_right", "web_swing", "jump")   # toggle with a hold
TAPPERS = ("get_over_here", "amazing_combo", "spider_power", "web_cluster", "team_up")  # mostly taps


def media_sha256(session_id):
    """A synthetic recording's stand-in media hash."""
    import hashlib
    return hashlib.sha256(f"synthetic-media:{session_id}".encode()).hexdigest()


def header_for(session_id, *, split="train", sitting="sitting-1", **extra):
    return {"format": steps.FORMAT, "session_id": session_id, "media_sha256": media_sha256(session_id),
            "session_group": session_id, "sitting": sitting,
            "split": split, "step_ns": STEP_NS, "frame_period_ns": PERIOD_NS, "actions": list(vocab.NAMES),
            "bindings": dict(vocab.DEFAULT_BINDINGS), "calibration": dict(CALIBRATION), "hud_layout": "mk",
            "swing_mode": dict(vocab.PAD_SWING_MODE), "accel_on": True,
            "video_size": [2560, 1440], "device_scope": "single_keyboard_mouse", "injected_events": 0,
            "settings_hash": "synthetic-settings", "patch": "synthetic-patch",
            "source": {"generator": "policy.range_bc.fixture"}, **extra}


def session(session_id="synthetic-a", *, split="train", sitting="sitting-1", runs=(120, 60, 30), seed=0,
            video_path="synthetic.mkv", regime_every=0, reject_run=None, gap_frames=30,
            pts_of=lambda n: round(n * 1000 / 120), timebase=(1, 1000), unknown_mouse=.01, hud=False,
            pitch_gain=CALIBRATION["pitch_deg_per_count"]):
    """Build one synthetic recording. `regime_every` > 0 flips the regime to no_ability_cooldown for every such run;
    `reject_run` marks that run's segment rejected. `pts_of` maps a frame index to its pts in `timebase`."""
    rng = random.Random(seed)
    header = header_for(session_id, split=split, sitting=sitting)
    header["calibration"]["pitch_deg_per_count"] = pitch_gain      # None: an unknown pitch gain
    header["source"]["seed"] = seed
    rows, held, anchor = [], [0] * vocab.N, T0_NS + 5 * PERIOD_NS + 1_000_000
    fwd = vocab.INDEX["move_forward"]
    for ri, length in enumerate(runs):
        run = f"run{ri}"
        regime = "no_ability_cooldown" if regime_every and ri % regime_every == regime_every - 1 else "normal"
        suitability = "rejected" if ri == reject_run else "accepted"
        tags, source = (["near", "foot"], "james") if ri % 2 == 0 else ([], "untagged")
        dx = [0., 0.]
        webs = 5
        for k in range(length):
            frame_index = (anchor - T0_NS) // PERIOD_NS
            composition = T0_NS + frame_index * PERIOD_NS
            start = list(held)
            press, release = [0] * vocab.N, [0] * vocab.N
            for name in HOLDERS:
                c = vocab.INDEX[name]
                if rng.random() < .06:
                    if held[c]:
                        release[c], held[c] = 1, 0
                    else:
                        press[c], held[c] = 1, 1
            for name in TAPPERS:
                c = vocab.INDEX[name]
                if held[c] and rng.random() < .5:
                    release[c], held[c] = 1, 0
                elif not held[c] and rng.random() < .04:
                    press[c] = 1
                    if rng.random() < .7:      # a tap inside the step
                        release[c] = 1
                    else:
                        held[c] = 1
                    if release[c] and rng.random() < .1:   # a double tap: multi-edge
                        press[c], release[c] = 2, 2
            if press[vocab.INDEX["web_cluster"]]:
                webs = max(0, webs - 1)
            elif k % 60 == 0:
                webs = min(5, webs + 1)
            # camera: an AR(2) drift with occasional onsets, in counts
            onset = rng.random() < .03
            new = 1.35 * dx[0] - .42 * dx[1] + (rng.choice((-1, 1)) * rng.uniform(40, 300) if onset else
                                                rng.gauss(0, 6))
            dx = [new, dx[0]]
            rel = rng.random() >= unknown_mouse
            unsupported = {"key:56:0": 1} if rng.random() < .01 else {}     # Alt: bound to no action
            known = [True] * vocab.N
            if ri == 1 and k < 3:              # a hold unknown after the run's start (a focus snapshot)
                known[fwd] = False
            row = {
                "i": len(rows), "run": run, "anchor_ns": anchor,
                "frame": {"video_path": video_path, "frame_index": frame_index, "pts": pts_of(frame_index),
                          "timebase": list(timebase), "composition_ns": composition},
                "gap_free": not (k == length - 1 and ri < len(runs) - 1),
                "segment": f"seg{ri}", "suitability": suitability, "regime": regime,
                "tags": tags, "tag_source": source,
                "held_start": start, "held_end": list(held), "held_known": known, "press": press, "release": release,
                "mouse_dx": int(round(new)) if rel else None, "mouse_dy": int(round(new / 4)) if rel else None,
                "relative_known": rel, "wheel_v": 0, "wheel_h": 0, "unsupported": unsupported}
            if hud:
                row["hud"] = {"webs": webs}
            rows.append(row)
            anchor += STEP_NS
        anchor += gap_frames * PERIOD_NS       # a capture gap: the next run starts later
        held = [0] * vocab.N                   # a new run starts from a released state (a focus boundary)
    return header, _release_at_run_ends(rows)


def _release_at_run_ends(rows):
    """Each run ends released, so the next run's first row starts from zeros."""
    for k, r in enumerate(rows):
        last = k == len(rows) - 1 or rows[k + 1]["run"] != r["run"]
        if last:
            for c in range(vocab.N):
                if r["held_end"][c]:
                    r["held_end"][c] = 0
                    r["release"][c] += 1
    return rows


def write(path, header, rows):
    path = Path(path)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(header, sort_keys=True) + "\n")
        for r in rows:
            stream.write(json.dumps(r, sort_keys=True) + "\n")
    return path


# ---- replay source (expert replay labels; steps docstring "REPLAY source") ------------------------------------------

REPLAY_MOVE = ("move_forward", "move_left", "move_back", "move_right")
REPLAY_HOLDS = ("spider_power", "web_swing", "jump")                       # the IDM's hold head
REPLAY_CASTS = ("get_over_here", "amazing_combo", "web_cluster")           # replay-hud cast events: onsets only


def replay_header(session_id, *, split="replay", sitting="replay-1", **extra):
    return {"format": steps.FORMAT, "source_kind": "replay", "session_id": session_id,
            "media_sha256": media_sha256(session_id), "session_group": session_id, "sitting": sitting,
            "split": split, "step_ns": STEP_NS, "frame_period_ns": PERIOD_NS, "actions": list(vocab.NAMES),
            "calibration": {"kind": "replay_degrees", "source": "synthetic-idm",
                            "label_sources": {"camera": "idm-camera@synthetic", "movement": "idm-locomotion@synthetic",
                                              "edges": "replay-hud@synthetic"}},
            "expert_context": {"player": "synthetic-expert", "match_id": "match-0001",
                               "viewer_fov_assumption": "viewer_fov_103", "replay_source": "native replay"},
            "hud_layout": "mk", "swing_mode": {"automatic_swing": None, "hold_to_swing": None},
            "video_size": [2560, 1440], "patch": "synthetic-patch", **extra}


def replay_session(session_id="replay-a", *, split="replay", runs=(120, 60), seed=0, video_path="replay.mkv",
                   unknown_movement_every=5, unknown_span=3, pitch_unknown=.1, edge_abstain=.1):
    """A synthetic replay recording: movement unknown for `unknown_span` rows every `unknown_movement_every` x span
    rows; hold heads for primary, swing and crawl; cast onsets (no release label) with abstentions; everything the
    labellers never emit (ultimate, melee, team_up, goh_targeting, simple_swing) unknown; camera in degrees."""
    rng = random.Random(seed)
    header = replay_header(session_id, split=split)
    header["source"] = {"generator": "policy.range_bc.fixture.replay_session", "seed": seed}
    rows, anchor = [], T0_NS + 5 * PERIOD_NS + 1_000_000
    for ri, length in enumerate(runs):
        state = {n: 0 for n in REPLAY_MOVE + REPLAY_HOLDS}
        for k in range(length):
            frame_index = (anchor - T0_NS) // PERIOD_NS
            none = [None] * vocab.N
            hs, he, pr, rl = list(none), list(none), list(none), list(none)
            unknown_move = (k // unknown_span) % unknown_movement_every == unknown_movement_every - 1
            for name in REPLAY_MOVE + REPLAY_HOLDS:
                c = vocab.INDEX[name]
                before = state[name]
                if rng.random() < .07:
                    state[name] = 1 - state[name]
                if name in REPLAY_MOVE and unknown_move:
                    continue                                   # the IDM abstains on movement here
                hs[c], he[c] = before, state[name]
                pr[c], rl[c] = int(state[name] > before), int(state[name] < before)
            for name in REPLAY_CASTS:
                c = vocab.INDEX[name]
                pr[c] = None if rng.random() < edge_abstain else int(rng.random() < .04)
            yaw = rng.gauss(0, 2.)
            rows.append({
                "i": len(rows), "run": f"run{ri}", "anchor_ns": anchor,
                "frame": {"video_path": video_path, "frame_index": frame_index, "pts": round(frame_index * 1000 / 120),
                          "timebase": [1, 1000], "composition_ns": T0_NS + frame_index * PERIOD_NS},
                "gap_free": True, "segment": f"seg{ri}", "suitability": "accepted", "regime": "normal",
                "tags": [], "tag_source": "untagged",
                "held_start": hs, "held_end": he, "press": pr, "release": rl,
                "held_known": [a is not None and b is not None for a, b in zip(hs, he)],
                "press_known": [v is not None for v in pr], "release_known": [v is not None for v in rl],
                "yaw_deg": yaw, "pitch_deg": None if rng.random() < pitch_unknown else rng.gauss(0, .5),
                "beyond_pad_envelope": abs(yaw) > 415 / 30})
            anchor += STEP_NS
        anchor += 30 * PERIOD_NS
    return header, rows


# ---- video ------------------------------------------------------------------------------------------------------------

def frame_colours(n):
    """Background and centre-square colours of synthetic frame n."""
    return (n * 7 % 256, n * 13 % 256, 200), (255 - n * 5 % 256, 40, n * 3 % 256)


def write_video(path, frames, *, size=(640, 360), fps=120, ffmpeg="ffmpeg"):
    """A lossless FFV1/MKV video: solid background, a solid 256x256 square at the centre, colours by frame_colours."""
    w, h = size
    x0, y0 = (w - 256) // 2, (h - 256) // 2
    proc = subprocess.Popen([ffmpeg, "-v", "error", "-nostdin", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "ffv1", "-pix_fmt", "bgr0",
                             str(path)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for n in range(frames):
        bg, fg = frame_colours(n)
        row_bg = bytes(bg) * w
        row_mid = bytes(bg) * x0 + bytes(fg) * 256 + bytes(bg) * (w - x0 - 256)
        proc.stdin.write(b"".join(row_mid if y0 <= y < y0 + 256 else row_bg for y in range(h)))
    _, err = proc.communicate()
    if proc.returncode:
        raise RuntimeError(err.decode(errors="replace"))
    return Path(path)


def probe_pts(path, *, ffprobe="ffprobe"):
    """(timebase, [pts per decoded frame]) of stream 0."""
    tb = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=time_base",
                         "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout.strip()
    num, den = (int(v) for v in tb.split("/"))
    out = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=pts",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout
    return (num, den), [int(line.strip().rstrip(",")) for line in out.splitlines() if line.strip()]
