"""Build frame-review's independent-review.v2.verdicts.json (v2 evidence, emote-wheel rule) for 20260927T052001-827Z-150600-5.
Unchanged-bound segments reuse the v1 record's verdict and reason (their frame hashes are re-checked here); the new
segments seg-026..seg-030 are verdicted from fresh edge reads."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SID = "20260927T052001-827Z-150600-5"
SESS = Path(f"C:/Users/volpe/repos/rivals-agent/data/human/sessions/{SID}")
REVIEWED_AT = "2026-09-27T14:58:41Z"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


ev = json.loads((SESS / "segments-evidence.json").read_text())
owner = json.loads((SESS / "owner-verdicts.json").read_text())
v1 = json.loads((HERE / "independent-review.verdicts.json").read_text())
v1_by_bounds = {(s["start_ns"], s["end_ns"]): s for s in v1["segments"]}
frames = {}
for line in (HERE / "run/frames.jsonl").read_text().splitlines():
    r = json.loads(line)
    frames.setdefault(r["frame_index"], r)

NEW = {
    "seg-026": ("rejected", "Concur, rejected whole. [262.327, 281.411) opens under the PARKER POWER-UP team-up splash, "
                "which covers most of the frame to ~263.5 s with no input at all 260-267.8 s; no rule cuts round-start "
                "splashes yet. 263.6-281.41 s is own control in the round-2 spawn room (own HUD 250/250, webs 5), so this "
                "reject is conservative; it would become acceptable if a splash rule moved the start past ~263.6 s."),
    "seg-027": ("rejected", "unsampled_edge: 3 ms sliver before the T press; no native frame inside."),
    "seg-028": ("rejected", "Concur: ui_key (emote wheel). T (vk 84) down 281.414 s; the EMOTES wheel is drawn 281.70-282.80 s "
                "(f33793-f33925); Spider-Man then sits in an emote with no key until D at 305.124 s, and the cut runs to "
                "D + 2 s settle (307.124 s). Space at 283.495 s did not end the sit on frames (he is seated again by "
                "~287 s), which supports ending the cut on a movement key rather than any key."),
    "seg-029": ("rejected", "unsampled_edge: 3 ms sliver after the emote settle; no native frame inside."),
    "seg-030": ("accepted", "Own live play from the spawn-door run under 'AWAITING MISSION AREA UNLOCK' (first frame f36844, "
                "307.127 s: own HUD 250/250, webs 5; teammates pass in front of him 308.3-308.9 s, the camera is his) to "
                "hp 80 at 425.494 s before the third death. Frames every 0.25 s plus 0.1 s at both edges (v1 reads of this "
                "span reused, same hashes): own HUD throughout; bonus health 447/500 at 331-333 s; the max_hp 275 read at "
                "408.3 s is a misread on own play, no spectate. No UI key, no focus change, longest input gap 0.32 s."),
}

segs, reused = [], 0
for s in ev["segments"]:
    sid = s["segment_id"]
    ov = owner["verdicts"][sid]["suitability"]
    inside = sorted((r for r in frames.values() if s["start_ns"] <= r["composition_ns"] < s["end_ns"]),
                    key=lambda r: r["frame_index"])
    fr = [{"frame_index": r["frame_index"], "composition_ns": r["composition_ns"],
           "decoded_bgr_sha256": r["decoded_bgr_sha256"]} for r in inside]
    old = v1_by_bounds.get((s["start_ns"], s["end_ns"]))
    if sid in NEW:
        assert old is None, sid
        verdict, reason = NEW[sid]
    else:
        assert old is not None, f"{sid}: bounds changed but no fresh verdict"
        now = {f["frame_index"]: f["decoded_bgr_sha256"] for f in fr}
        assert all(now.get(f["frame_index"]) == f["decoded_bgr_sha256"] for f in old["frames"]), f"{sid}: v1 frame differs"
        verdict, reason = old["verdict"], old["reason"]
        if old["segment_id"] != sid:
            reason = f"[v1 {old['segment_id']}, same bounds and frames] " + reason
        reused += 1
    segs.append({"segment_id": sid, "start_ns": s["start_ns"], "end_ns": s["end_ns"],
                 "machine_reason": s["machine_reason"], "owner_verdict": ov, "verdict": verdict,
                 "reason": reason, "frames": fr})

diffs = [{"segment_id": s["segment_id"], "owner": s["owner_verdict"], "frame_review": s["verdict"]}
         for s in segs if s["owner_verdict"] != s["verdict"]]

record = {
    "kind": "independent_session_review",
    "session": SID,
    "reviewer": "frame-review (Opus)",
    "reviewed_at": REVIEWED_AT,
    "inputs": {"segments_evidence_sha256": sha(SESS / "segments-evidence.json"),
               "owner_verdicts_sha256": sha(SESS / "owner-verdicts.json"),
               "media_sha256": "3e0a1ebe52d957655357b68cfaaf0e196cff6954a3b1d72706cbec6b00a5f61f"},
    "supersedes": {"path": "independent-review.verdicts.json", "sha256": sha(HERE / "independent-review.verdicts.json"),
                   "note": "v1, against evidence 393163fc...; kept unchanged"},
    "method": ("Same decoder and checks as v1 (fr_decode.py: exact-PTS select with showinfo proof, streamed, CPU 4 threads "
               "below normal, obs64/Marvel absent before every window). v2: all 143 owner review frames hashed (equal "
               "143/143, own_hud flags equal); 169 new frames decoded for the new edges (every 6th frame through 2 s at each "
               "edge of seg-026..seg-030, plus the frames just outside); seg-030's start edge inspected at 0.1 s. "
               f"{reused} segments have v1 bounds, and every v1 frame inside them re-hashes equal: their v1 verdicts are reused. Raw inputs "
               "replayed for the new segments with the v2 UI key set (T included). Media hash from v1 (file unchanged "
               "since, same bytes read by the decoder)."),
    "matches_owner": not diffs,
    "blocking_findings": [],
    "differences": diffs,
    "findings": [
        "The emote rule (T down to the next W/A/S/D make + 2 s) matches the frames here: the wheel is 281.70-282.80 s, "
        "the Space at 283.495 s did not end the sit, D at 305.124 s did (standing by ~305.6 s).",
        "seg-026's 17.5 s of own spawn-room control after the splash (263.6-281.41 s) is lost to the conservative "
        "reject; a round-start splash rule would recover it. Not blocking.",
        "Unchanged from v1: no spectate, kill cam or respawn wait inside any accepted segment; the own-HUD reader "
        "misses the web counter on 1-24% of own-play frames and its max_hp cannot by itself separate spectate from own "
        "play.",
    ],
    "session_findings": v1["session_findings"],
    "segments": segs,
}
out = HERE / "independent-review.v2.verdicts.json"
assert not out.exists(), "record already written"
out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
print(out, sha(out))
print("reused", reused, {v: sum(1 for s in segs if s["verdict"] == v) for v in ("accepted", "rejected")}, "diffs", diffs)
