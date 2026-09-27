"""Build frame-review's independent-review.verdicts.json for 20260927T052001-827Z-150600-5 (match-mode pilot)."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SID = "20260927T052001-827Z-150600-5"
SESS = Path(f"C:/Users/volpe/repos/rivals-agent/data/human/sessions/{SID}")
S0 = 554275865572800   # logger start_ns; every "s" below is logger-relative seconds
REVIEWED_AT = "2026-09-27T14:43:32Z"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


ev = json.loads((SESS / "segments-evidence.json").read_text())
owner = json.loads((SESS / "owner-verdicts.json").read_text())
frames = {}
for line in (HERE / "run/frames.jsonl").read_text().splitlines():
    r = json.loads(line)
    frames.setdefault(r["frame_index"], r)

ACCEPT = {
    "seg-004": "Own live control in the pre-match setup room (doors closed, timer 00:36 to 00:25): Spider-Man runs, "
               "jumps and web-zips; own HUD 250/250 with web counter on every inspected frame (117 at 0.25 s plus "
               "edge frames every 0.1 s). No UI key, no focus change, longest input gap 0.28 s.",
    "seg-008": "Own live play from the drop at 'AWAITING MISSION AREA UNLOCK' (70.37 s; the first ~0.1 s the camera is "
               "against geometry so the body renders faded, own HUD 250/250 webs 5) to hp 33 under the damage "
               "vignette at 175.03 s, before the first death. 501 inspected frames at 0.25 s: own HUD throughout; "
               "the cyan translucent body at 155-157 s is a teammate's invisibility buff (own HUD unchanged). No "
               "spectate, kill cam or death frame inside. No UI key, longest input gap 0.56 s.",
    "seg-014": "Own live play from respawn (186.70 s) to hp 2 at 209.69 s; the first frame after the end edge "
               "(f25153) still shows hp 2, so the cut is before the death. An enemy 'Charm' label at 209.39 s is "
               "crowd control on own play, not a camera change. 166 inspected frames, own HUD throughout; no UI key, "
               "longest input gap 0.21 s.",
    "seg-020": "Own live play from respawn (222.11 s, overtime) to hp 12 at 247.08 s, ending at the Tab press "
               "(247.09 s). 174 inspected frames, own HUD throughout (max 300 = bonus health); no UI key inside, "
               "longest input gap 0.21 s.",
    "seg-032": "Own live play from respawn (437.69 s) through his ultimate (bonus health 480-490/490 from ~498.7 s) "
               "to 501.00 s, the frame before the Tab press (501.008 s); the scoreboard follows and the end summary "
               "is at 505.7 s. 332 inspected frames, own HUD throughout. The last ~0.9 s shows little camera motion "
               "and near-still mouse, but the scene animates, the own HUD is live and W is pressed at 500.47 s: "
               "read as live control, not an end freeze. No UI key inside, longest input gap 0.42 s.",
}
SEG026 = ("Rejected as bounded. The segment contains the emote wheel, a menu: key T (vk 84) held 281.414-282.751 s "
          "and the EMOTES radial menu (EMOJI / SPRAY) drawn on native frames 281.70-282.80 s (f33793-f33925), the "
          "highlighted wedge moving top to right, so the mouse drives the menu, not the camera. The contract rejects "
          "a segment if any part shows a menu. Also inside: (a) the PARKER POWER-UP team-up splash covers most of "
          "the screen from before the start edge (262.32 s) to 263.5 s, with no input at all 260-267.8 s; (b) "
          "Spider-Man sits on a stool from ~283.3 s (after the wheel) to ~305.6 s with no key pressed 283.58-305.12 "
          "s and no mouse at all ~297-305.1 s, which reads as an emote playing out rather than live piloting. The "
          "live play 307-425.49 s is own control with own HUD (831 inspected frames in the segment; the max_hp 275 reader value at "
          "408.3 s is a misread of own play, no spectate).")

segs = []
for s in ev["segments"]:
    sid = s["segment_id"]
    ov = owner["verdicts"][sid]["suitability"]
    inside = sorted((r for r in frames.values() if s["start_ns"] <= r["composition_ns"] < s["end_ns"]),
                    key=lambda r: r["frame_index"])
    fr = [{"frame_index": r["frame_index"], "composition_ns": r["composition_ns"],
           "decoded_bgr_sha256": r["decoded_bgr_sha256"]} for r in inside]
    if sid == "seg-026":
        verdict, reason = "rejected", SEG026
    elif sid in ACCEPT:
        verdict, reason = "accepted", ACCEPT[sid]
    else:
        assert ov == "rejected", sid
        verdict = "rejected"
        reason = f"{s['machine_reason']}: concur, rejected by rule; confirmed on native frames and raw inputs (see findings)."
        if not fr:
            reason = f"{s['machine_reason']}: sub-frame sliver with no native frame inside; rejected by rule."
    segs.append({"segment_id": sid, "start_ns": s["start_ns"], "end_ns": s["end_ns"],
                 "machine_reason": s["machine_reason"], "owner_verdict": ov, "verdict": verdict,
                 "reason": reason, "frames": fr})

diffs = [{"segment_id": "seg-026", "owner": "accepted", "frame_review": "rejected",
          "why": "emote wheel (a menu) drawn 281.70-282.80 s inside the segment; T key 281.414-282.751 s.",
          "suggested_recut": "If the owner re-proposes, frame-review would expect to accept a span from the first "
                             "clean frame after the splash (~263.6 s) to before the T press (281.414 s) and a span "
                             "from Spider-Man standing up (~305.6 s) to 425.494 s, each with its own edge proof and "
                             "a fresh verdict. The emote sit ~283.3-305.6 s: frame-review would call it unresolved "
                             "(canned emote animation, camera orbit only, no input for ~8 s), not accepted."}]

record = {
    "kind": "independent_session_review",
    "session": SID,
    "reviewer": "frame-review (Opus)",
    "reviewed_at": REVIEWED_AT,
    "inputs": {"segments_evidence_sha256": sha(SESS / "segments-evidence.json"),
               "owner_verdicts_sha256": sha(SESS / "owner-verdicts.json"),
               "media_sha256": "3e0a1ebe52d957655357b68cfaaf0e196cff6954a3b1d72706cbec6b00a5f61f"},
    "method": ("Own decoder (fr_decode.py beside this file): ffmpeg 8.0.1 CPU, 4 threads, below-normal priority, "
               "-copyts coarse seek then select=eq(pts,file_ms) with showinfo after the select; each window is refused "
               "unless showinfo's pts list equals the requested file_ms list. Frames streamed one at a time (~11 MB); "
               "obs64/Marvel checked absent before every window. frame_index -> composition_ns re-derived from the "
               "logger frames.csv by pts rank (file_ms = round(pts*1000/120)+21); all evidence frames agree. "
               "Decoded-BGR sha256 at 2560x1440 for 2215 frames: all 141 owner review frames (hashes equal 141/141), "
               "every 30th frame (0.25 s) across the six owner-accepted segments, every 6th frame through 2 s at each "
               "accepted edge plus the frames just outside, and dense 0.05-0.1 s frames at 262.2-264.6, 281.2-283.9 "
               "and 304.8-306.2 s. Inspected visually as contact sheets (1 s bulk, 0.1 s edges, all owner frames of "
               "rejected segments). The snapshot scan.py own-HUD read (hp/max_hp/webs) was computed as a secondary "
               "signal only. Raw inputs.jsonl replayed independently for UI keys, focus and input gaps. Media "
               "re-hashed."),
    "matches_owner": False,
    "blocking_findings": [
        "seg-026 differs from the owner (owner accepted, frame-review rejected): the emote wheel menu is drawn "
        "281.70-282.80 s inside it. Assembly's owner/independent agreement check will refuse the session until "
        "the owner re-proposes or re-verdicts seg-026."],
    "differences": diffs,
    "findings": [
        "Proposer gap: the emote wheel key T (vk 84) is not in UI_KEYS (Esc, H, B, F1, Tab, Enter, Alt, Win), so an "
        "emote-wheel span stays inside a gameplay candidate. Suggest adding James's emote-wheel binding (T in this "
        "session) to the match-mode UI keys, with the same settle.",
        "Judgement calls asked about: (a) seg-026 opening splash 262.3-263.5 s covers most of the frame with no "
        "input at all; frame-review would not accept it; (b) the stool sit is an emote after the wheel, ~283.3-305.6 s "
        "(longer than the owner's 291.1-300.7 s), unresolved at best; (c) seg-004 setup room: accept, own control; "
        "(d) seg-032 ends inside the ultimate at 501.00 s: accept, own HUD live, ends before the Tab press.",
        "Hard check near 175, 210 and 425 s: no spectate, kill cam or respawn wait inside any accepted segment. The "
        "last in-segment frames are own play at hp 33 (175.03 s), hp 2 (209.69 s) and hp 80 (425.49 s); spectate "
        "('DEFEATED BY' panel, teammate HUD) first appears in seg-012 (182.24 s) and seg-016/017 (214.5-219.5 s).",
        "The own-HUD reader is noisy on own play (web counter missed on 1-24% of inspected frames per accepted segment, most in fights; max_hp reads "
        "300/500/490 for bonus health and one 275 at 408.3 s on own play). It is a fine edge guard, but a max_hp "
        "value alone cannot tell spectate from own play.",
    ],
    "session_findings": [
        "Media sha256 re-hashed: 3e0a1ebe...5f61f (matches the registry/evidence).",
        "Owner review frames: 141/141 decoded-BGR hashes equal; composition_ns and file_ms equal frames.csv by pts.",
        "Inside the six owner-accepted spans: no UI key, no focus change; longest input gaps 0.28/0.56/0.21/0.21/"
        "8.11/0.42 s (the 8.11 s is the seg-026 emote sit).",
        "Rule rejections verified on raw inputs: every ui_key segment contains or follows (within 2 s) a Tab or Alt "
        "press (seg-043's Alt at 530.326 s precedes focus loss at 530.467 s); afk segments seg-002 and seg-006 have "
        "26.1 s and 27.7 s no-input gaps. Visual: seg-000..002 hero select; seg-006 AFK then the pre-drop hold; "
        "dead/ui_key spans show death, kill cam, spectating a teammate with the 'DEFEATED BY' panel, the Tab "
        "scoreboard, the objective summary, the MVP screen and the match summary.",
    ],
    "segments": segs,
}
out = HERE / "independent-review.verdicts.json"
assert not out.exists(), "record already written"
out.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
print(out, sha(out))
print({v: sum(1 for s in segs if s["verdict"] == v) for v in ("accepted", "rejected")})
