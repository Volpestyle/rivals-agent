# Frame-verdict contract: match-mode pilot 20260927T052001-827Z-150600-5 (from admission-owner, for frame-review)

**Scope.** One live Quick Match, registry split `idm_train` (match mode).
- Out of scope; never open them: V-C (-150600-1/-2), V-Q (-150600-3) and every sealed or denylisted file.
- Inputs, sent when ready: `data/human/sessions/20260927T052001-827Z-150600-5/segments-evidence.json` (with
  `review-frames/`) and my `owner-verdicts.json`.

**Your record** is a new file, `independent-review.verdicts.json`, in this folder, with work files beside it. It is not
committed; I copy it into the session folder at assembly. Required JSON keys (`assemble_session.py` reads them):
- `kind` = "independent_session_review", `session`, `reviewer` = "frame-review (Opus)", `reviewed_at` (UTC ISO).
- `inputs` {`segments_evidence_sha256`, `owner_verdicts_sha256`, `media_sha256`}.
- `method`: how you decoded, and what you looked at.
- `matches_owner` (bool), `blocking_findings` [], `differences` [], `findings` [], `session_findings` [].
- `segments`: one per `segment_id` in the evidence, each with:
  - `segment_id`, and `start_ns` and `end_ns` copied exactly;
  - `verdict` ("accepted" | "rejected") and `reason`;
  - `frames` [{`frame_index`, `composition_ns`, `decoded_bgr_sha256`}]: the native frames you decoded and inspected
    inside that segment, hashing raw BGR24 at 2560x1440.

**Agreement.**
- Assembly takes "accepted" only from your record, and your verdict must equal the owner's on every segment.
- Where you disagree, record it under `differences` and tell me. Don't copy mine.

**"accepted"** means every frame of the segment is the player's own live control of Spider-Man. That includes the
pre-match setup room, doors closed: the mouse and keys drive this camera and this body.

**Reject a segment** if any part of it shows:
- hero select or loading;
- a death, the blurred death screen, a kill cam, or spectating a teammate (the camera is not the player's own);
- a respawn wait;
- a menu, the Tab scoreboard or chat;
- a victory, defeat or MVP screen, or any other end sequence;
- a cinematic or a replay;
- the desktop or an unfocused window.

Also check that the HUD match timer and the health HUD are drawn, and that the guard key `match_timer` is true at both
edges.

**Decoding.**
- Exact-PTS ffmpeg on CPU, 4 threads, below-normal priority, one frame at a time or in small windows.
- Keep each process under ~3 GB.
- Check that `obs64` and `Marvel*` are not running before every decode window, and stop if either starts (James may
  relaunch).
- `file_ms` is the evidence's `file_ms`.
