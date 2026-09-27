# IDM SSL sampled pilot — EXPLORATORY

Owner idm-owner. Whole-file admission f641ef3 is independently LAND. Its frozen
JSON hash is `864e54350343a26ce0111d03d6e76d39bddef2f1e3e1c5cdb898b93e1f42dd02`.

The first training packet contains **80 clips / 1,280 frames**, 20 clips per
source session, half at 60 Hz and half at 8 Hz. This is a pipeline smoke, much
smaller than the research memo's proposed ten-hour pilot: the selected clips
span approximately 85 seconds in total. It cannot settle representation value.
The 128 candidate anchors covered a 128-second grid per source; neither that
grid nor the admitted 7.44-hour whole-file total is counted as training duration.

Preparation used the separately approved PC exception: one CPU ffmpeg process,
two threads, BelowNormal, less than 3 GiB per process, free-RAM refusal below
4 GiB and a stop on Marvel/OBS. The 128-clip batch completed 17:39:42–17:47:39 UTC.
All 2,048 candidate frames were inspected in 16 contact sheets. Death,
spectator, scoreboard and respawn-fade clips were rejected. Every decoded native
frame between samples also passed through ffmpeg scdet; scores >=10 reject a
clip. This conservative detector sometimes rejects ability transitions. It is
evidence against cuts, not a proof against undetectable edits. The remaining
clips were selected at evenly spread eligible indices, with equal source/rate
counts. Four new native-resolution first frames matched the selected PTS exactly
and confirmed Spider-Man own-POV gameplay; one source contributes practice-range
gameplay, the others live historical matches. No input labels are inferred.

Artifacts under `data/idm/cloud-20260927/`:

- `ssl-candidates-02/packet.json`: all candidates, frame hashes, integer source
  PTS/timebases and dense scene scores; contact-0 through contact-15 retain views.
- `ssl-inspection-verdicts.json`: explicit per-clip exclusions and selection.
- `ssl-native-selected/receipt.json`: four native checks and exact-PTS matches.
- `ssl-input/packet.json`: selected packet, SHA256
  `3f56e98f573131bf8eaad2446a27bebcdc9c04d1124a85d820adf0c18454dc64`.
- `ssl-packet.tar`: 81,827,840 bytes, SHA256
  `5dfce91f59ca2a96ace7a6482d4eff8238b502afde47890d7c691dcd81916a25`.

The cloud runner uses frozen pinned DINOv2-small CLS + 4x4 grid features, a fixed
union of HUD masks and exact elapsed times. It fits the causal temporal predictor
for ten passes with seeds 0/1/2, reporting copy-last error and feature variance.
All losses are in-training; there is no downstream gain or Gate 2 claim. The
native-HUD and grey-difference camera paths are unchanged. Matched downstream
random-vs-SSL temporal initialization and real-vs-zero visuals remain required.

The smoke reserves **$2 hard within the approved $12 SSL allocation**; the other
$10 remains unlaunched. Expected extraction/fits are a few minutes, unmeasured
on this packet; the reservation includes the existing $0.75 setup allowance and
120-second teardown. It reuses the reviewed budget/watchdog/AppCreate path, with
only its namespace and cap configuration changed. Separate app and volumes,
no fit retry, global creation-window coordination and proven teardown apply.

Failures retained: the first candidate invocation refused a UTF-8 BOM before
video access; the parser now accepts UTF-8 with optional BOM. A native-check
helper initially lacked the repository import path and stopped before decoding.
The first 32-clip packet was inspection-only and lacks the dense scene check;
it is not included in training. Nothing reads held-out, sealed or DayMR footage.
