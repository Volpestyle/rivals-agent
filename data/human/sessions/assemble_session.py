"""Assemble one reviewed session: settings, review.json, import, the fit's step file, minutes, freeze (VUH-1359).

    python assemble_session.py SESSION_ID --independent-verdicts PATH [--snapshot code-snapshot-XXXXXXX]

Requires the session's frozen intake evidence (`segments-evidence.json`, `owner-verdicts.json`) and the independent
per-session verdict record (copied beside them). Accepted comes only from the independent verdict record, which
must agree with the owner verdicts on every segment; its inspected frames inside each segment are the verdict
frames. Code runs from the archived snapshot. The import's ffprobe decode runs at four threads, below normal.
Writes, each exclusively: copies of the cited recording log (at its last commit) and of the registry revision used,
settings.json, review.json, imported-demo.jsonl, <SESSION_ID>.steps.jsonl, sampling.json, minutes.json, then
artifact-hashes.json. Living documents are pinned through those copies, never as live files.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


class Refused(RuntimeError):
    pass


def need(condition, message):
    """An explicit guard that survives `python -O` (review I3); asserts are not used for refusals here."""
    if not condition:
        raise Refused(message)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DENYLIST = ROOT / "data/human/sealed-denylist.json"
DENYLIST_SHA256 = "57cfe01f29f6e1a55293f968ec697aa293c268bd87d7cf247ef648279e2fba7c"   # pinned (review I3)
REGISTRY = ROOT / "data/human/session-splits.corpus.json"
RECORDING_LOG = ROOT / "docs/recording-log.md"
USER_SETTINGS_0921 = ROOT / "data/human/notes/2026-09-21-user-settings.json"
ANCHOR = ROOT / "data/human/inspection/20260922T033319-205Z-24328-2/independent-review-resolution.md"
RAW = Path("C:/Users/volpe/Videos/RivalsInput")
BELOW = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
STEP_NS = 33_333_333
PATCH = "1.1.3870120/build25364676"

# The campaign's settings from James's dated statements (docs/recording-log.md, 2026-09-23) and the saved profile.
# The swing mode is the {automatic_swing, hold_to_swing} dict the step header carries (review I1): hold to swing
# on, simple (automatic) swing off, from the settings look; Simple Swing itself is a separate key (Caps Lock).
MOTOR = dict(dpi=800, horizontal_sensitivity=1.89, vertical_sensitivity=1.89,
             swing_mode={"automatic_swing": False, "hold_to_swing": True}, mouse_acceleration=True, mouse_smoothing=True)
CALIBRATION = ROOT / "data/human/calibration/20260923T204707-487Z-45572-2/calibration.json"
# The session binding table as James's settings look shows it (calibration take, keyboard pages): every semantic
# action -> its physical ids (key:scan:E0E1-bits, mouse:button), primary first.
BINDINGS = {
    "move_forward": ["key:17:0"], "move_left": ["key:30:0"], "move_back": ["key:31:0"], "move_right": ["key:32:0"],
    "jump": ["key:57:0"], "web_swing": ["key:42:0"], "get_over_here": ["key:33:0"],
    "amazing_combo": ["key:18:0", "key:3:0"], "ultimate": ["key:16:0"], "melee": ["key:47:0", "mouse:5"],
    "spider_power": ["mouse:1"], "web_cluster": ["mouse:2"], "team_up": ["key:46:0"], "team_up_b": ["key:45:0"],
    "simple_swing": ["key:58:0"], "goh_targeting": ["mouse:4", "key:3:0"], "slow_walk": ["key:29:0"]}
# Second bindings the fit counts under the action (lead decision 2026-09-23: Mouse 5 is melee). "2" (key:3:0) is
# bound to two actions, so it stays unsupported.
ALIASES = {"mouse:5": "melee"}
BINDING_NOTES = {
    "team_up": "C = Team-Up A, fires in the solo range with a visible effect (James; 051828/team-up-check.json). A real "
               "action with positives, trained but masked live (Y is off the pad whitelist).",
    "melee": "V and Mouse 5 (settings look; lead decision): Mouse 5 presses count as melee (header binding_aliases).",
    "goh_targeting": "Get Over Here Targeting: Mouse 4 (X1) and 2; a fit action (lead decision), structurally "
                     "unsupported on the pad, counted. Only Mouse 4 is in the step header (2 is shared).",
    "amazing_combo": "E and 2; 2 is also Get Over Here Targeting, so it is not aliased (unsupported).",
    "simple_swing": "Caps Lock (VK 20, scan 58), off as a mode; not in the fit vocabulary (unsupported).",
    "team_up_b": "X, Team-Up B; not in the fit vocabulary (unsupported).",
    "slow_walk": "LCtrl, hold; not in the fit vocabulary (unsupported).",
    "alt": "Alt is unbound in game (James); Alt presses are Alt-Tab and stay UI-key cuts.",
}


def header_calibration():
    cal = json.loads(CALIBRATION.read_text())
    return dict(cal["header_calibration"], source=f"{cal['header_calibration']['source']} ({sha(CALIBRATION)[:16]})")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def rel(p):
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(p).as_posix()


def cite(*paths):
    return [{"path": rel(p), "sha256": sha(p)} for p in paths]


def write_json(path, doc):
    need(not path.exists(), f"{path.name} already written")
    path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(path.name, sha(path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--independent-verdicts", required=True)
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--sessions-dir", help="assemble a copy of the session folder here (rehearsal); default: this folder")
    ap.add_argument("--supersedes", help="reason: earlier assembly outputs were renamed .vN and are pinned by this one")
    args = ap.parse_args()
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    snapshot = HERE / args.snapshot
    sys.path.insert(0, str(snapshot))
    from agent import human_intake as hi
    from agent import human_demos as hd
    denylist = hi.load_denylist(DENYLIST, sha256_pin=DENYLIST_SHA256)
    registry = hi.check_registry(REGISTRY, denylist=denylist)
    place = registry[args.session]
    need(place.split in ("train", "val") and place.session_group == args.session, 'failed: place.split in ("train", "val") and place.session_group == args.session')
    hi.assert_not_sealed(args.session, place.expected_media_sha256, denylist)
    d = Path(args.sessions_dir or HERE) / args.session   # --sessions-dir: a scratch copy, for a rehearsal run
    raw = RAW / args.session
    meta = json.loads((raw / "metadata.json").read_text())
    ev = json.loads((d / "segments-evidence.json").read_text())
    owner = json.loads((d / "owner-verdicts.json").read_text())
    ind_path = Path(args.independent_verdicts)
    ind = json.loads(ind_path.read_text())
    profile = json.loads((d / "input-profile.json").read_text())
    reg_rows = {r["session_id"]: r for r in json.loads(REGISTRY.read_text())["sessions"]}
    sitting = reg_rows[args.session]["sitting"]

    # 0. immutable copies of the living documents this assembly cites: the recording log at its last commit (the
    # working file must equal that blob) and the registry revision used; the freeze pins the copies
    log_commit = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%h", "--", "docs/recording-log.md"],
                                capture_output=True, text=True, check=True).stdout.strip()
    blob = subprocess.run(["git", "-C", str(ROOT), "show", f"{log_commit}:docs/recording-log.md"], capture_output=True,
                          check=True).stdout
    need(blob.replace(b"\r\n", b"\n") == RECORDING_LOG.read_bytes().replace(b"\r\n", b"\n"), "uncommitted log edits")
    log_copy = d / f"recording-log.{log_commit}.md"
    need(not log_copy.exists(), 'failed: not log_copy.exists()')
    log_copy.write_bytes(blob)
    reg_copy = d / f"registry.{sha(REGISTRY)[:12]}.json"
    need(not reg_copy.exists(), 'failed: not reg_copy.exists()')
    reg_copy.write_bytes(REGISTRY.read_bytes())

    # 1. settings: actual values with per-session sources (review R2, fit R7)
    settings = dict(value=MOTOR, source="James's statements in docs/recording-log.md (2026-09-23): DPI 800 (~14:50 CDT), "
                    "sensitivity unchanged since 2026-09-21 (1.89/1.89 in the 09-21 report), default swing settings on "
                    "Shift with Simple Swing on Caps Lock; confirmed on native frames of the settings look (calibration.json: "
                           "1.89/1.89, hold to swing on, simple swing off)",
                    per_session_source="James's dated statements of 2026-09-23, applied by the lead to every existing session",
                    evidence=cite(log_copy, USER_SETTINGS_0921, d / "provenance.json", CALIBRATION))
    bindings = dict(value=BINDINGS, aliases=ALIASES, notes=BINDING_NOTES,
                    source="native frames of James's settings look (calibration take 2026-09-23, keyboard pages, "
                           "calibration.json), agreeing with his 2026-09-21 report and 2026-09-23 statements; HUD key "
                           "labels on this session's frames (slot-mapping.json)",
                    per_session_source="James's dated statements of 2026-09-23 (docs/recording-log.md)",
                    evidence=cite(log_copy, USER_SETTINGS_0921, d / "slot-mapping.json", CALIBRATION))
    identity = hi.settings_identity(MOTOR, BINDINGS)
    calibration = header_calibration()
    caps = [e for e in (json.loads(x) for x in (raw / "inputs.jsonl").read_text().splitlines())
            if e.get("type") == "key" and e.get("vk") == 20]
    write_json(d / "settings.json", dict(session=args.session, settings=settings, bindings=bindings,
                                         settings_identity=identity, caps_lock_packets=len(caps),
                                         calibration=calibration,
                                         no_pad_attestation="James, 2026-09-23 ~15:55 CDT: no physical controller was "
                                                            "plugged in during any recording session"))

    # 2. review.json: accepted only from the independent verdict record, which must agree with the owner's
    need(ind["session"] == args.session, 'failed: ind["session"] == args.session')
    verdicts = {}
    for s in ind["segments"]:
        cand = next(c for c in ev["segments"] if c["segment_id"] == s["segment_id"])
        need((s["start_ns"], s["end_ns"]) == (cand["start_ns"], cand["end_ns"]), 'failed: (s["start_ns"], s["end_ns"]) == (cand["start_ns"], cand["end_ns"])')
        need(s["verdict"] == owner["verdicts"][s["segment_id"]]["suitability"], s["segment_id"])
        frames = [{k: f[k] for k in ("frame_index", "composition_ns", "decoded_bgr_sha256")} for f in s["frames"]
                  if cand["start_ns"] <= f["composition_ns"] < cand["end_ns"]]
        frames = list({f["frame_index"]: f for f in frames}.values())
        verdicts[s["segment_id"]] = dict(suitability=s["verdict"], reason=s["reason"], reviewer=ind["reviewer"],
                                         reviewed_at=ind["reviewed_at"], evidence=f"{rel(ind_path)} ({sha(ind_path)[:16]})",
                                         frames=frames)
    rows = hi.review_segments(ev["segments"], verdicts)
    review = hi.assemble_review(
        session_id=args.session, media_sha256=place.expected_media_sha256,
        reviewer=f"owner admission-owner ({sha(d / 'owner-verdicts.json')[:16]}) + independent {ind['reviewer']}",
        reviewed_at=ind["reviewed_at"],
        device_scope=dict(kind="single_keyboard_mouse",
                          source=f"input-profile.json: keyboard {list(profile['device_scope']['keyboard_handles'])}, "
                                 f"mouse {list(profile['device_scope']['mouse_handles'])}; "
                                 f"{profile['device_scope']['injected_zero_effect_packets']} zero-effect handle-0 packets "
                                 "allowed (lead decision), no injected control input",
                          no_pad_attestation="James, 2026-09-23 ~15:55 CDT (docs/recording-log.md): no physical "
                                             "controller plugged in during any recording session"),
        pts_anchor=dict(kind="independent_muxer_offset", offset_num=21, offset_den=1000,
                        source="accepted blank-scene derivation plus this session's own first-16-packet forward "
                               "prediction (provenance.json anchor_applicability), no fitting",
                        evidence=cite(ANCHOR, d / "provenance.json")),
        provenance=dict(hero="Spider-Man", settings=settings, bindings=bindings,
                        game_patch=dict(value=PATCH, source="Steam content log and appmanifest: build 25364676, no later "
                                        "update", evidence=cite(d / "provenance.json")),
                        cooldown_regime=dict(value=ev["session_regime"], source="5 fps HUD scan: depletion observed",
                                             evidence=cite(d / "regime-timeline.json")),
                        segments_evidence={"path": rel(d / "segments-evidence.json"), "sha256": sha(d / "segments-evidence.json")},
                        owner_verdicts={"path": rel(d / "owner-verdicts.json"), "sha256": sha(d / "owner-verdicts.json")},
                        lead_decisions=({"path": rel(d / "lead-decisions.json"), "sha256": sha(d / "lead-decisions.json")}
                                        if (d / "lead-decisions.json").exists() else None)),
        alignment=dict(kind="assumption", statement="OBS composition time is the labelling clock; capture, display and "
                       "input-delivery latency are uncalibrated (no measured bound is asserted)",
                       source="lead decision for the whole-session campaign; as for the 2026-09-22/23 request packets"),
        segments=rows, session_start_ns=meta["start_ns"], session_end_ns=meta["end_ns"],
        focused=[tuple(i) for i in ev["focused_intervals"]], denylist=denylist,
        independent_review={"path": rel(ind_path), "sha256": sha(ind_path), "reviewer": ind["reviewer"]})
    write_json(d / "review.json", review)

    # 3. import from the snapshot: ffprobe at four threads, below normal
    real = hd.subprocess.run

    def limited(cmd, **kw):
        cmd = [cmd[0], "-threads", "4", *cmd[1:]]
        kw.setdefault("creationflags", BELOW)
        return real(cmd, **kw)

    hd.subprocess.run = limited
    dataset = hd.import_session(raw, review=d / "review.json", splits=REGISTRY, output=d / "imported-demo.jsonl")
    hd.subprocess.run = real
    audit = json.loads(dataset.audit_json)
    print("import", audit)

    # 4. the fit's step file
    steps = d / f"{args.session}.steps.jsonl"
    header, n = hi.write_steps(dataset, steps, sitting=sitting, calibration=calibration,
                               denylist=hi.load_denylist(DENYLIST, sha256_pin=DENYLIST_SHA256), step_ns=STEP_NS,
                               settings_hash=identity, patch=PATCH, regime=ev["session_regime"],
                               source=dict(importer_git_blob=next(f["git_blob"] for f in json.loads(
                                   (snapshot / "manifest.json").read_text())["files"] if f["path"] == "agent/human_demos.py"),
                                   snapshot=args.snapshot, snapshot_manifest_sha256=sha(snapshot / "manifest.json"),
                                   imported_demo_sha256=sha(d / "imported-demo.jsonl"), review_sha256=sha(d / "review.json")))
    table = [json.loads(x) for x in steps.read_text(encoding="utf-8").splitlines()[1:]]
    accepted = [r for r in table if r["suitability"] == "accepted"]
    eligible = [r for r in accepted if r["gap_free"]]
    print("steps", n, "accepted", len(accepted), "gap-free accepted", len(eligible))

    # 5. sampling and minutes
    write_json(d / "sampling.json", dict(session=args.session, format=header["format"], step_ns=STEP_NS,
                                         frame_period_ns=header["frame_period_ns"], rows=n, accepted_rows=len(accepted),
                                         eligible_rows=len(eligible), steps={"path": steps.name, "sha256": sha(steps)},
                                         export_digest=sha(steps),
                                         grid="anchors every step_ns from the first frame inside each segment ∩ focus "
                                              "span, while the step fits strictly before the span end; stale-frame "
                                              "anchors (age > 2 frame periods) are not emitted"))
    minutes = hi.session_minutes(session_start_ns=meta["start_ns"], session_end_ns=meta["end_ns"],
                                 focused=[tuple(i) for i in ev["focused_intervals"]], segments=rows,
                                 eligible_anchors=len(eligible), stride_ns=STEP_NS)
    minutes["counted"] = hi.counted_minutes([tuple(i) for i in ev["focused_intervals"]], rows,
                                            [tuple(g) for g in ev["capture_gaps"]])
    write_json(d / "minutes.json", dict(session=args.session, regime=ev["session_regime"], split=place.split, **minutes))

    # 6. freeze: everything in the folder plus the external inputs
    external = [meta["video_path"], raw / "metadata.json", raw / "inputs.jsonl", raw / "frames.csv", DENYLIST,
                USER_SETTINGS_0921, ANCHOR, snapshot / "manifest.json", CALIBRATION]
    doc = hi.freeze(d, root=ROOT, external=external,
                    extra=dict(session=args.session, status="assembled", split=place.split, sitting=sitting,
                               settings_identity=identity, counted_minutes=minutes["counted"]["counted_minutes"],
                               snapshot=args.snapshot, calibration=calibration,
                               supersedes=None if not args.supersedes else dict(
                                   reason=args.supersedes,
                                   files={p.name: sha(p) for p in sorted(d.iterdir()) if p.is_file() and ".v" in p.name
                                          and p.name.split(".v")[-1].split(".")[0].isdigit()})))
    print("artifact-hashes", sha(d / "artifact-hashes.json"), "files", len(doc["files"]), "external", len(doc["external"]))
    print("minutes", {k: minutes[k] for k in ("accepted_s", "admitted_minutes", "trainable_minutes")}, minutes["counted"])


if __name__ == "__main__":
    main()
