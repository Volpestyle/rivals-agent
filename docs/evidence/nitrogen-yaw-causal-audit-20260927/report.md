# Native causal-track audit — 2026-09-27

**EXPLORATORY, $0. The current detector/tracker output is not ready to become a trusted
yaw-conditioning feature.** No fit, game input, GPU use, data admission or sealed read.
The six NitroGen confirmation runs are unchanged. This result concerns the proposed
next experiment's input prerequisite, not the confirmation's scientific decision.

Owner: explore-policy. Lead authorized the bounded CPU audit while confirmation ran.
Existing `perception.outline` and `agent.tracker.Tracker` were reused without changes.
Script: `docs/research/nitrogen-yaw-audit/audit.py`; source hashes are in `summary.json`.

## What ran

Four fixed 3-second sequences around previously inspected TRAIN challenge anchors,
90 policy-time frames each, native 2560×1440. These are purposive difficult cases,
not a random sample or a population performance estimate. Only these three admitted
TRAIN identities were opened: 200129, 203745, 035932 (full IDs in the receipts).

Before reading step bodies: explicit constant whitelist, admitted tally, registry TRAIN
placement, expected media identity, original step header and existing sealed denylist
checks. Every selected row is accepted, normal, gap-free and relative-motion-known;
each sequence stays inside one run with exact step spacing. Video paths must equal
the three explicit immutable original paths. Existing admission media hashes were
reused; **the 26–42 GB originals were not rehashed in this audit**. Their path, size
and modification time are retained so this is not mistaken for fresh byte validation.

PyAV sought each short sequence and matched **all 360 requested PTS exactly**; all
frame composition timestamps precede their anchors. The finder processes whole native
frames. `auto` behavior is green detections when present, otherwise red-nameplate
fallback. Tracker updates proceed in timestamp order, use only current/past detections,
reset between sequences, and receive **`cam=None`**: no human camera commands, future
frames or commanded-camera model. Recorded yaw labels are reporting metadata only.

Execution: Windows CPU, asserted BelowNormal priority; two decode threads and two
OpenCV threads. **92.25 seconds; peak working set 303,996,928 bytes (~290 MiB)**,
below 3 GB. Ruff passes. No synthetic test is claimed as evidence of native correctness.
The job receipt is `C:/Users/volpe/jobs/nitrogen-yaw-native-causal-audit.status.json`.

## Mechanical observations over all processed frames

| Sequence | Frames | Raw detections | Frames with no detections | Distinct assigned IDs | Frames with coasting IDs | Green path frames |
|---|---:|---:|---:|---:|---:|---:|
| 200129, anchor 7469; close aerial fight | 90 | 125 | 10 | 42 | 51 | 80 |
| 200129, anchor 11401; multiple bots/turn | 90 | 163 | 8 | 21 | 82 | 66 |
| 203745, anchor 40584; turning/occlusion | 90 | 201 | 6 | 56 | 75 | 78 |
| 035932, anchor 1676; red-enemy account | 90 | 202 | 3 | 16 | 84 | 0 |

Distinct IDs are **not** an identity-switch count: entrances, fragments and false boxes
also create IDs. No-detection frames are **not** verified no-bot frames. Coasting is an
uncertain prediction, not an observed bot. We did not hand-label every bot in 360 frames,
so this report does not claim full-sequence precision, recall or ID-switch rates.

## Native visual inspection: six fixed frames per sequence

All 24 full-resolution native stills, four annotated contact sheets and complete
per-frame observations are retained. `manifest.json` pins the original audit outputs;
this written interpretation is separate. Inspection is by the owner, not independent
data-admission review. These observations are diagnostic evidence, not new training labels.

- **Valid short continuity exists.** In [7469](20260923T200129-i7469/contact.jpg),
  one purple bot retains ID1 from row 7424 through the sampled rows 7442 and 7460
  while the player approaches. In the multi-bot sequence, far ID13 is retained across
  sampled rows 11392/11410. The tracker is not universally broken.
- **Close fragmentation is visible.** By row 7478 the close body is represented by
  separate ID4/ID5 pieces while old IDs coast. Later broad camera movement introduces
  many short-lived IDs. In [40584](20260925T203745-i40584/contact.jpg), row 40557 shows
  two pieces sharing ID1, while row 40575 assigns different IDs26/27 to pieces near
  another close bot. A raw box is not reliably one complete target.
- **Red fallback produces definite non-bot boxes.** In
  [red-account 1676](20260926T035932-i1676/contact.jpg), row 1631's ID1 is on the
  right-side scenery below the KO banner. At row 1667, boxes ID4/ID8/ID1 lie over
  ground/planter areas below that banner rather than bot bodies. This repeats on
  the green-account sequence's red fallback: row 11356 in
  [11401](20260923T200129-i11401/contact.jpg) contains boxes beneath the triple-KO
  overlay on scenery. The overlays' red marks can enter the nameplate/body heuristic.
  This is a repeated observed failure, not merely a proposed detector risk.
- **The fallback can also see a real red-account bot.** Row 1649 boxes the purple bot
  at the right (ID4), and row 1703 boxes the close foreground bot (ID12). Thus simply
  disabling the fallback would discard useful observations along with its false boxes.
- **Visible bots are missed.** At row 40628 in 40584, the large purple bot on the
  right platform is unboxed. A separate tiny detection at the very top edge remains
  in the JSON (the contact-sheet title can obscure it). “There is some detection”
  therefore does not establish recall of the relevant visible bot. In 11401 the
  downed/close purple bodies and the active bot are not represented consistently.
- **Identity attribution remains uncertain.** In red-account rows 1703→1720, the
  close left bot appears to acquire ID16 while ID12 is drawn on a right-hand bot.
  This is a candidate identity handoff requiring dense identity annotation to count
  confidently, not a certified switch-rate measurement. The input is not suitable
  for treating a tracker ID as ground-truth human intent.

## Decision for the proposed yaw experiment

Do **not** bulk-extract these current outputs into trusted target tracks or pay for
the object-conditioned yaw comparison yet. First address the demonstrated false
nameplate/body detections around the KO overlay and the observed fragmentation/misses,
then recheck these exact challenge sequences alongside ordinary valid controls.
If track motion needs ego-motion compensation, it must come from causal pixels;
injecting true human yaw would recreate privileged history unavailable at inference.

Unknown/missing/coasting flags and all visible candidates remain necessary. Neither
nearest-to-crosshair nor tracker ID establishes the bot James intends to fight.
No target-relative relabeling or scripted-aim path follows from this audit. The approved
proposal remains a learned yaw head with original human yaw labels, conditional on
its visual input prerequisite being demonstrated. Any paid comparison still waits for
the NitroGen confirmation and a separate lead approval. No detector fix is made here.

The planned $0 frozen-dev James/H1/NitroGen replay remains an **offline prediction**
comparison; it cannot demonstrate autonomous turning or fighting on recorded frames.
