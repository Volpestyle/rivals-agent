LAND perception/match_timer.py (value reader only); REJECT perception/killfeed.py (failed reader); FIX perception/replay_cuts.py (separate acceptance evidence required); FIX tests/test_gate2_readers.py (split timer-only landing from rejected reader).

# Independent review: Gate 2 one re-validation, seed 20260927

Reviewer: fit-review. Date: 2026-09-26. Scope: the supplied re-validation artifacts, amendments 1/2/3/4 and amendment-3 addendum, and the four named uncommitted files. No code or truth was edited, no video was decoded, and no commit was made. The sole output is this review.

**The numerical verdict is supported:** K1 FAIL, K2 FAIL, K3 meets its conditional timing bars; T1 PASS on the sampled live centre-channel values; T2 and T3' remain information only because 69 changes are below 100. The replay half remains undecided. Neither reader is accepted to supply Gate 2 timing anchors by this result.

## Findings and landing boundary

1. **REJECT killfeed.py as an accepted reader.** K1 is 7/39 = 0.179487; K2 is 7/9 = 0.777778. K3 is 7/7 within one frame and consequently within two, but this describes the seven matched arrivals, not the 32 missed ones. Its layout decision violates the registered unknown-layout contract; see the code path below. Preserve the failed experiment and frozen bytes. A repair requires new development evidence, new recordings and a new pre-registration, not another score on these spent windows.

2. **LAND match_timer.py as a bounded value-reading utility, with its frozen glyph asset.** It imports no kill-feed or replay-cut code. Its native-size checks, glyph/rival/color checks and explicit None abstention are suitable for that narrow landing, and the measured T1 error/unknown rates meet the bars. This does not clear the complete reader gate or validate second_changes as a Gate 2 anchor source. Document live centre-channel T1 separately from undecided T2/T3' and replay validation; do not promote team-clock presence to a replay-layout classifier. Keep the original T3 failure on record.

3. **FIX the proposed test-file landing boundary.** tests/test_gate2_readers.py:22 imports both readers at collection time. Landing the file intact while omitting killfeed.py breaks collection. Split out the timer tests for the timer-only landing; retain the kill-feed tests with the failed experiment. The existing layout test at line 114 asserts that all-false viewer evidence is live: it does not test unfamiliar layouts and cannot establish fail-closed behavior. Its passing result is not evidence that the failed reader is safe to accept.

4. **FIX/hold replay_cuts.py acceptance evidence.** This file is not imported by either re-validation scorer, is not one of amendment 4's four frozen artifacts, and has separate S1/S2/S3 requirements in docs/lanes/idm-gate2-anchors.md. These timer/feed results cannot authorize its use. Its 18 synthetic tests pass, but that is not playback-span validation. This is an evidence/scope hold, not a newly demonstrated defect in its cut algorithm; reuse a separate accepted review if the lead has one.

## 1. Frozen artifacts and scoring

The current LF hashes match amendment 4:

| Artifact | SHA256 (LF) |
|---|---|
| perception/killfeed.py | c514727180493fcdf774c2730221e406a013368e44696e326f10d15dfd6fe377 |
| perception/spectator_prompt.json | 5aeab85063424bea29b538d4adc699989e85d77941b3e4ef5b2cfb709df88e2b |
| perception/match_timer.py | 945b36341ea77847e35cea6aff6c9ba9546d802ca9bfa27943c0c1be07146c78 |
| perception/match_timer_glyphs.json | 1f5ce4766fb1fb0deb7f46efc1c7d81a76375075ec9ac9805d528029178f0298 |

Each score JSON's code_sha256_lf equals its corresponding reader above. The scorers import the checkout modules, and their current dependencies match the freeze. The saved receipts record only the main reader hash, however: they are not an independently timestamped run-time attestation of both assets and every helper. Current hash agreement is verified; the stronger historical claim relies on the producer's pre-run freeze account.

The reported raw artifact hashes also match:
- r2_score_feed.py: eda9a938d513b937547028a310d5cdee9e91e2ae2b53bbb9e2b061b40fac18fd
- r2_score_timer.py: 79eb59f248d54ef5bb4276c0a5b4ce05b182178098b63e314bc77d684593e2c1
- score_feed.json: 8be58102cb0dc2262f80972171ac6dce436b875addaa419b18390fb802197142
- score_timer.json: 665128073a74be9335bc4db5446ff311b8904c1fc94a7eddfe0ce190db1e9534

These are raw-byte hashes; feed scorer/results contain CRLF, so their LF-normalized hashes differ. This is not code drift. The feed scorer's opening docstring still names the first reader hash e21e5a40; its actual saved hash is the correct c5147271.

I recomputed the feed summary from its saved detections and v2 truth, and independently recomputed the timer value/change totals. Every embedded feed-truth window equals the current v2 window.

| Item | Recomputed result | Registered interpretation |
|---|---|---|
| K1 | 7/39 | FAIL; needs >= 0.90, support 39 >= 30 |
| K2 | 7/9 | FAIL; needs >= 0.95 |
| K3 | within 2: 1.00; within 1: 1.00 | Meets >= 0.95 / >= 0.80 on matched entries |
| T1 | 1/750 wrong; 1/112 legible unknown | PASS; <= 0.5% / <= 10% |
| T2 | 65/69 detected, 61/65 exact, all matched within 1, zero false/wrong-valued | Information only; support below 100 |
| T3' | 10 truth segments, 9 matched, zero matched offset error, 1 unmatched | Information only; support below 100 |
| Replay | no source | Undecided |

The feed scorer uses one-to-one matching within 12 frames (1 ms rounding allowance for millisecond PTS), judges shifted arrivals only, and applies the correct K bars and floors. Empty-feed detections remain supplementary. T1 counts a read on none/illegible as wrong and uses legible frames for unknown share, correctly.

T2's current recall and exact fraction are both below 95%; calling these numbers “clean” must not imply they pass. The floor makes the verdict undecided, not pass or a new judged failure. T3' explicitly reports every_segment_within_1_frame=false because one segment is unmatched.

**Scorer limitation for future use:** r2_score_timer.py:104-116 matches each truth segment to the reader segment with the most shared displayed values, without a time/format correspondence constraint or one-to-one consumption, and does not separately account for extra reader segments. Its segmentation formula and offset formula match amendment 3, but that association is not a general implementation of “every segment.” This does not turn the present under-supported result into an accepted timing result. Clock rows missing composition time are silently dropped rather than counted; the registration requires reporting them. Neither issue invalidates the independently recomputed T1 result.

## 2. Truth v2 and the blind adjudication

**The content-only claim is verified strongly, even without a preserved v1 copy in this handoff.** I reversed only the seven declared entry changes, corresponding PTS fields, four coarse_only flags, appended adjudication notes, and the v2 format tag, in memory. Serializing the reconstructed v1 reproduces its exact frozen LF SHA256:

8842a476ff6b6a2ee65e256052d9c20a1266c1fe64a71e45d0f9bb7a396ff165

The current v2 is 856df87d68602e89b410f354293516243400f2c0a79d703148167dff2a849e11. The timer truth hashes and blind-label hash also match the receipts. Replaying only the seed-20260927 sampling logic against reconstructed v1 and frozen timer labels reproduces the blind IDs and whole-window selection.

| Blind evidence | Changed entry in v2 |
|---|---|
| e00 | 22-48-05_5: 5352 -> 5338 |
| e03, already present at crop 00 | 22-48-05_5: 4152 -> 4126 |
| e04 | 22-48-05_5: 2712 -> 2691 |
| e05 | 21-13-21_0: 1982 -> 1981 |
| e06 | 21-13-21_0: 5328 -> 5309 |
| e09 primary arrival | chickentendy71: 3081 -> 3082; shift 3079 -> 3080 |
| e09 second arrival in my notes | Cenxtii: 3095 -> 3094 |

All changed entries were disputed or bounded by the blind pass. No unrelated entry, exclusion or timer label changed. For e03, my packet begins at absolute frame 4128 with the entry already present; I did not label an exact onset at 4126. That final value comes from the producer's further re-inspection. RESULTS should say this explicitly rather than calling all four empty-feed changes adoption of my exact frame values. Its “14-24 frames earlier” range is also inaccurate for e03, which moves 26 frames.

I re-inspected v42 in this review: it reads **00:35**, agreeing with the adjudicated truth. My original 00:36 blind answer remains untouched.

**Chronology is consistent but not independently proven.** Local modification times are blind labels 20:30:31 UTC, v2/adjudication 20:32:42, copied score outputs 20:52:05. These mutable/copy-time metadata and current hashes cannot establish that no reader output was seen earlier. The supplied folder has no immutable pre-scoring event/run receipt proving that ordering. I requested the preserved freeze/run evidence; absent that, “nothing changed after reader output was seen” remains a producer assertion, not an independently certified finding. There is no content evidence here of an undisclosed v2 edit.

## 3. Competitive-clock failure and unknown layouts

The mechanism is confirmed from the executed scorer and reader path:

1. r2_score_feed.py:38 reads TEAM_A/TEAM_B and converts either successful clock read to a boolean.
2. Lines 40-45 OR that boolean with viewer_prompt. A missing prompt cannot veto a clock.
3. killfeed.py:116-122 selects spectator at share >= 0.30, live at share <= 0.02, and None only between them or on an empty list.
4. The scorer then selects LAYOUTS[layout].region. Spectator uses y=290..400, with its top band y=314..343; live uses y=20..150, top band y=48..82.
5. A live clock read on 115/120 samples would therefore force spectator even with zero prompt matches.

The saved output confirms **six** 22-48-05 windows (#0 through #5) are spectator; #6 is live. Four of the misclassified windows contain 30 judged shifted arrivals, all missed. The two correctly classified Quick Match windows contain nine, of which seven match. I did not independently rerun the producer's 115/120 pixel diagnostic; the code implication and persisted per-window layouts/misses are verified.

“Yes, unfamiliar layout must return unknown” is an explicit registered requirement. In particular, absence of a replay cue is not positive evidence of a supported live layout: an all-false list currently becomes live. entries also trusts its supplied layout; it only returns unknown when passed None and does not independently validate the declared geometry. Removing the team-clock OR alone would not establish recognition of unfamiliar layouts. A future fix needs positive, independently validated layout evidence and abstention on ambiguity, on newly registered development/validation sources.

## Verification and limits

- 41 focused tests passed: tests/test_gate2_readers.py and tests/test_replay_cuts.py, using the existing perception environment, bytecode disabled and pytest cache disabled.
- Hashes, blind-draw reproduction, exact v1 reconstruction and score recomputation ran in small in-memory processes.
- No video decode, large extraction, reader tuning, truth mutation or full scoring rerun occurred.
- replay_cuts.py LF: f50f57e39de75f0fec3962c3bbe696141b249e0bf3917c9c79d6c7fc4a31b92f.
- tests/test_gate2_readers.py LF: 41877ed7d048af7a4abae374d7eb5bc0dc9bc48f9e14901cdd84e1e0a7b7e3ab.

The recommended landing is the timer value utility plus its asset and separated tests. Keep kill-feed failure recorded and unaccepted, timing/replay results undecided, and playback-cut acceptance attached to its own evidence.
