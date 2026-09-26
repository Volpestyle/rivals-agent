# Brief: seal the 2026-09-26 test take (VUH-1359)

- **Owner:** admission-owner
- **Reviewer:** admission-review (read-only, independent)
- **Lead:** herdr-lead lands the change and posts to Linear
- **Written:** 2026-09-26 11:00 CDT

## The take
James recorded a test take and named it in chat at 10:55 CDT: "one test take in, 16 mins". The lead registered it
as sealed test in `docs/recording-log.md` in commit de0b331 (on main), using the file and folder names only:

| Item | Value |
|---|---|
| Video | `C:/Users/volpe/Videos/2026-09-26 10-38-35.mkv` (13.6 GB) |
| Logger session | `20260926T153835-237Z-111496-2` |
| Held with it | `20260926T153812-936Z-111496-1`: a 23 s logger session from the same OBS process, 23 s earlier, with no video |

## Result
Both sessions are sealed in the pinned sealed denylist and registered as test, per `docs/recording-protocol.md`
("Validation and test takes"). The denylist entry carries the video's media sha256.

## The design question is yours
The current denylist, `data/human/sealed-denylist.json` (sha256 `57cfe01f…`), is pinned in three places:
- `policy/idm_targets.py`
- `policy/range_bc/steps.py`
- `scripts/transcode_recording.py`

Every admitted session's `artifact-hashes*.json` and `segments-evidence*.json` also pins it. Choose how to add the
entries (for example a versioned `sealed-denylist.v2.json` with the consumers re-pinned, or an in-place edit) so that:
- every existing admitted session's evidence stays valid and its verification still passes;
- no train or val registry content changes, and the corpus headline stays 180.57 train / 15.58 val.

Round 2 is running on the Mac from an archive of 3670d0e, so this change doesn't affect it. The real fit, launched
later from main, must load the new denylist.

## Hard rules
- Never open, list the contents of, or read either logger folder, or any frame of the video.
- Hash only the video file, streaming, keeping each process under ~3 GB. Hash only when neither `obs64` nor any
  `Marvel*` process is running: James is playing and recording now, and a 13.6 GB read competes with OBS.
- No game input. Edit only the paths this change needs, and name them in the hand-back.
- Load `shared-checkout` before touching git. Don't commit; the lead lands the change.

## Acceptance
1. The denylist lists both session ids, the video path and the media sha256, with `hashed_at` and a reason.
2. Every consumer loads and pins the new denylist.
3. Tests show a registry row naming either session outside split `test` is refused, and the existing corpus still
   verifies unchanged.
4. admission-review returns an independent LAND.

## Hand-back
Write `handoff/admission-test-take-20260926.md` containing:
- the files you changed, with LF sha256;
- the media sha256;
- the tests you ran;
- the review file.

Then hand back to the lead.

## Addendum, 11:31 CDT: the rest of today's takes go in the same registry change, with one review

The lead has already logged each of these in `docs/recording-log.md` (on main, pushed).

1. **Gate 2 pair 2, sealed.**
   - Live half: `2026-09-25 19-28-51.mkv`, session `20260926T002851-659Z-63684-3`, now registered `match_dev`. It holds
     two matches: Thebes 19:36, then Hall of Djalia 19:49.
   - Replay half: `2026-09-26 10-57-37.mkv`, session `20260926T155737-285Z-116800-1`, a first-person 1x replay of
     Hall of Djalia 19:49.
   - Move both into a new sealed gate2 group, `gate2-20260925-hall-of-djalia-1949`, following pair 1's pattern
     (`gate2-20260925-central-park-1928`).
   - Recommendation: seal the whole 19-28-51 file, both matches, so no window split is needed. Thebes was held in
     reserve and unused anyway.
   - The lead checked that no lane has read 19-28-51: the lane doc says it is held in reserve, and scoreboard-fix's
     validation media are the five other matches.
   - Hash the replay's media only after the game and OBS close.
2. **Heart of Heaven replay:** `2026-09-26 11-10-08.mkv`, session `20260926T161008-331Z-116800-2`. Register it as an
   evaluation session for reader development, beside its live match 20-06-20 (`match_dev`). Never train on it. Its
   tail runs long because James stepped away.
3. **Left-turn calibration:** `2026-09-26 11-26-48.mkv`, session `20260926T162648-153Z-116800-4`, about 48 s.
   - Register it as a calibration entry and run its content check the way the 030045 and 060921 calibrations went.
     It was planned as three leftward turns (slow, medium, fast) and then three pitch sweeps.
   - Calibration isn't sealed, so its logger folder may be read.
   - The 25 s session `20260926T162623-219Z-116800-3` just before it: check the OBS log for a deleted video, as you
     did for 153812. It is not sealed test, so you may read it, but register it only if it holds something.
