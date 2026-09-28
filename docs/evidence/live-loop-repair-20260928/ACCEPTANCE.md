# Independent review accepted; measurement still pending

`review-v1.md` and `review-v1.json` were issued by live-review (Claude Opus 5.5):
**LAND for the live-input boundary**, with 128 independently rerun CPU tests
passing in 11.96 s. The owner's 128 tests passed in 15.63 s; Ruff passed. The
reviewer checked additional native translation, occlusion, blur, zoom and roll
controls. This supersedes the candidate's earlier "review pending" wording in
RESULT.md and the diagnosis note; those reviewed bytes are preserved.

Use `docs/evidence/live-loop-repair-20260928/review-v1.json`. It covers all 12
driver dependencies, including the new pose analyzer, and additionally records
the FPS source/tests and analyzer tests. The old a4 receipt is stale. Receipt
verification passed before commit; the owner re-verifies on the committed
checkout and reports that result in the handback.

## Limitations accepted for this retry

- Raw whole-band correlation is now diagnostic, not an acceptance gate. The
  patches prove bounded pose, not unchanged content throughout the scenery
  band. Reviewer probes changed the centre strip and still passed; a bot or
  effect in an unchecked region can invalidate a measurement. The independent
  review's LAND is **input safety**, not measurement validity. The lead inspects
  the ready image and native recording; no rate is automatically accepted.
- Motion with low phase confidence may be classified unprovable and wait up to
  one second while neutral. It never authorizes input; "motion stops
  immediately" applies only when classified confidently as changed.
- This native scene has only three contributing patches. Another disturbance
  may refuse safely; do not lower thresholds to obtain a pass. The new deferred
  retention preserves the exact pair for that next failure.
- FPS startup copies a full fresh frame for refusal evidence. This may add
  startup latency; the submit-age check still prevents stale submission.
- The missing .9438 refusal image is still not qualified. Retained neighbor
  replay passes, but no video decode or real capture/GPU qualification was run
  in this repair. No focal, signed map, game-FPS cost or learned-policy acceptance
  is established.

## Operator delta

The lead owns the desktop. Arrive through `reenter.py`; **no hand-posing**.
Use the existing yaw-then-FPS command order in
`docs/lanes/live-loop-operator-20260927.md`, replacing its stale receipt variable:

```powershell
$camPython = 'C:/Users/volpe/.venvs/rivals-live-cu128/Scripts/python.exe'
$camReceipt = 'docs/evidence/live-loop-repair-20260928/review-v1.json'
```

Verify on this checkout before the live command (this verification opens no
capture or pad):

```powershell
uv run --no-project --python $camPython python -c "from scripts.measure_camera_turns import verify_receipt; verify_receipt('docs/evidence/live-loop-repair-20260928/review-v1.json'); print('receipt verified')"
```

Supply fresh sitting/output/PID/video values as before. Inspect `ready-attach`
before atomically writing `continue-attach.json`; after prime and neutral settle,
inspect each fresh `ready-N` before its new `continue-N.json`. Token paths and
report limits are unchanged. A poor arrival view or refusal ends the attempt;
there is no automatic pose search. Pulse blocks still require an accepted focal,
so this retry is yaw + FPS only. DXCAM remains fixed across A/B/A; no GDI switch.

On pose refusal, retain `pose-refusal.json`, `refusal-reference.png`,
`refusal-current.png` and their `*-frame.json` timestamps/hashes. On FPS startup
refusal, retain `startup-refusal.json` and its named PNGs along with the events.
Missing frames or write failure are reported explicitly. Image encoding occurs
after the pad is closed or after the actuator-free startup loop has stopped.

## VUH-1384 current-result text for the lead

Offline ready-pose/FPS startup repairs have independent input-safety LAND and
128 passing CPU tests. Thirty retained yaw-01 frames pass the fixed-reference
patch guard; motion controls refuse. Replaying the six recorded FPS capture/
proof durations changes the old stale-proof refusal to ready using a fake
worker. Neutral quality recovery and startup re-prime are bounded; live shift
bounds and measured 100/250 ms limits are unchanged. Exact refusal image pairs
are now retained after neutralization. Next: lead-operated reenter.py arrival,
no hand-posing, then yaw + FPS retry using review-v1.json. Original failing image
is missing; scene-content coverage is limited. No camera map, focal or game-FPS
cost has been established.
