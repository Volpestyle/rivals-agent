# Target identity audit — 2026-09-29

**Decision: Support is sparse or neither helps.** This 48-case TRAIN diagnostic does not justify another policy fit. Only **6/24 onsets** have a single causally supported focus; three are in the fixed center band. On the remaining **three directional pairs**, causal focus and nearest bot each agree with yaw **1/3**, with **zero paired wins and zero losses**. Hindsight gives **2/4** on its separately supported directional cases, exactly equal to nearest bot on those same four. Off-center causal focus is present in **8/24 still controls**.

The result is inconclusive about target identity in general and negative as evidence for this next bet. Keep policy fits parked. This does not authorize a controller, another fit, an IDM run, or more annotation. VUH-1346; bounded assignment from the [spec at 7e2b2e3](../../research/policy-next-bet-intent-audit-20260929.md). The lead owns acceptance and subsequent scope.

## What was inspected

Exactly eight admitted TRAIN sessions, three randomly selected onset clusters and three distinct quiet/still blocks per session: **24 + 24**, seed **29**. No shortages. Positive anchors are the first eligible anchor in each selected cluster; still anchors are random eligible anchors in selected blocks. All selected anchors within a session are at least two seconds apart. Selection did not rank errors or inspect pixels. The 48 IDs were shuffled together before annotation; session, onset/control membership, labels, predictions and traces were hidden during both visual passes.

The probe's target is unchanged: signed yaw over seven whole **33,333,333 ns** bins, **0.233333331 s**, including the anchor bin. Quiet history is the preceding seven bins' absolute travel at most **0.4630332°**. Left/right requires a strict excursion beyond ±threshold; otherwise still. [prepare.py](prepare.py) imports the exact completed probe's window/target functions from the pinned runtime, uses its TRAIN roster and verifies dataset and label hashes.

The owner personally inspected all eight causal source images per example using full-frame sheets and unscaled native center crops, with direct native anchors where needed. Sources are **2560×1440**. Candidate boxes are manual approximations of visible bodies at the anchor; IDs are local to an example. Nearest means Euclidean distance from body-box center to the reticle at (1280,720). Normalized horizontal center is (x1+x2)/(2×2560). The fixed **2%-wide center band [0.49,0.51]** abstains; it was not tuned. Mere proximity or visibility did not establish focus.

Outcome inspection used ten evenly spaced following native frames across one second, as full-frame sheets and unscaled center crops; all 30 following admitted native frames per example were decoded and retained. Only independently visible attack/contact/damage supports an eventual recipient. A prior marker, camera centering, or movement toward a bot alone does not. When several recipients occur, the primary is the first defensibly resolved one, with transitions recorded in the note. No mouse/action traces or model predictions were inspected. Native yaw was exposed only after the outcome freeze.

## Blinding and provenance

- Audit began **06:52:37 UTC**. All eight sources were recorded available by **06:55:31 UTC**, inside the ten-minute location bound.
- Causal decode finished **06:56:52 UTC**. All 48 causal annotations were saved and committed as **5b55f96 at 07:11:20 UTC**, before outcome decoding/viewing. LF SHA256: `73d29d5c8964de4f41d4c22b9fac9330a2ab943e8bf0a1fe13ed2e0d5be2ddc7`.
- Outcome decoding checked that causal hash before running and completed **07:15:05 UTC**. All 48 outcome annotations were finished **07:23:51 UTC**, then committed as **004c858 at 07:24:01 UTC**, before the sample key/yaw was opened. LF SHA256: `e3ddf65c0e649c39d0a08710ff4e99fdea7b681307a9888c62765a538b5602f2`.
- Both annotation files remain byte-identical to their freezes. Outcome judgments never backfilled causal ones. E13/E15 were conservatively made outcome-unknown before that freeze: a finishing animation and already falling corpse do not resolve a fresh attack.
- Preparation and outcome decode used the Mac queue, one niced job, at most two configured ffmpeg threads. Peak preparation parent RSS was **1,265,991,680 bytes**; outcome parent **1,246,478,336**, child **173,785,088**. Conservative sum remains under 3 GB. Compact-sheet packaging peaked at **119,373,824 bytes**. Cost **$0**; no cloud function, GPU fit, training, live input, new recording or sealed-data read.
- [Verification](verification.json) checks all **1,824 decoded PTS** against requested admitted frame references, all causal composition timestamps at/before anchors, all outcome frames within the next second, and exact TRAIN membership. The [denylist snapshot](denylist-snapshot.json) contains eight protected records, including the 2026-09-27 test take and Gate 2 pairs. No selected ID, admitted media hash or source basename intersects it. Its JSON matches the current PC denylist semantically; runtime bytes hash `4bafb1741026871a5f7ba4d8eb8b2e0bc8757c3cbd786af0f847289dc1c71716`. V-C/V-Q and DayMR/ReqMR remain excluded by the exact TRAIN allowlist.
- Reporting and artifact checks completed within the 90-minute deadline of **08:22:37 UTC**; see [delivery receipt](delivery-receipt.json) for the final timestamp.

Runtime: `/Users/james/dev/range-bc-data/explore/turn-onset-probe-20260929/runtime-ca1444c`, **Python 3.11 .venv311** (the exact loaders require 3.11; the earlier 3.12 sum drift is not accepted). Existing cache: `/Users/james/dev/range-bc-data/explore/turn-onset-probe-20260929/cache`, dataset SHA256 `71e344f4f17d9e537c87c154b30f6aae12c14cc601b59d668299ac799715660e`. [Source availability](source-availability.json) retains native paths/sizes. Originals were matched by admitted basename and header media identity; whole videos were not rehashed for this bounded audit.

## Paired causal result, including abstentions

Each session contributes three onsets. “Supported” is a single frozen causal focus, regardless of center position. Correct counts in the first section use that exact supported set and do not credit abstention. W/L means focus correct/nearest not correct, versus nearest correct/focus not correct. The directional section excludes a case only if either side abstains, and compares the same cases for both methods.

| TRAIN session | Supported | Center abstain focus/nearest | Correct focus/nearest on supported | W/L on supported | Both directional | Correct focus/nearest directional | Directional W/L |
|---|---:|---:|---:|---:|---:|---:|---:|
| 20260923T051828-422Z-33696-1 | 1 | 1/1 | 0/0 | 0/0 | 0 | 0/0 | 0/0 |
| 20260923T200129-346Z-33696-6 | 1 | 0/0 | 0/0 | 0/0 | 1 | 0/0 | 0/0 |
| 20260924T232304-170Z-12024-1 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0/0 | 0/0 |
| 20260925T021320-371Z-7804-1 | 1 | 1/1 | 0/0 | 0/0 | 0 | 0/0 | 0/0 |
| 20260925T025230-605Z-7804-2 | 2 | 1/0 | 1/2 | 0/1 | 1 | 1/1 | 0/0 |
| 20260925T203745-207Z-49728-2 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0/0 | 0/0 |
| 20260926T035932-508Z-63684-14 | 0 | 0/0 | 0/0 | 0/0 | 0 | 0/0 | 0/0 |
| 20260926T045729-166Z-79780-1 | 1 | 0/0 | 0/0 | 0/0 | 1 | 0/0 | 0/0 |
| **Total** | **6** | **3/2** | **1/2** | **0/1** | **3** | **1/1** | **0/0** |

All six supported onsets are shown, so center exclusions cannot hide an identity advantage or failure:

| ID | Native yaw ° | Causal focus side | Nearest side | Interpretation |
|---|---:|---|---|---|
| E17 | +1.2237306 | B1 center | B1 center | Both abstain; outcome target unknown |
| E30 | +3.3735276 | B1 left | B1 left | Both wrong; clear continued combat does not explain this short yaw sign |
| E34 | +0.9591402 | B1 left | B1 left | Both wrong; outcome recipient unknown |
| E43 | +0.6945498 | B1 center | B1 center | Both abstain despite clear projectile engagement |
| E45 | +32.4453978 | B1 right | B1 right | Both correct |
| E47 | +0.5953284 | B1 center | B2 right | Causal abstention, nearest correct; outcome resolves B2 |

There is **no case where a causal identity choice fixes a nearest-bot directional error** in this sample. E47 illustrates the distinction between a previously supported interaction and the next recipient: the frozen causal call remains B1 at medium confidence, and its note already records ambiguity about the next choice. Hindsight resolves B2 and does not repair that causal annotation. The two wrong directional cases cannot establish whether timing, translation, combat animation or another goal explains yaw.

## Hindsight/oracle, reported separately

There are **16/48 visible outcome recipients**, of which **15** defensibly link to an anchor ID. Of the 24 onsets, six have a visible recipient: five linked, plus **E04**, whose lower-lane bot was occluded at the anchor. E04 has no oracle anchor bearing. **18/24 onsets** remain outcome-unknown.

| TRAIN session | Linked onset recipients | Center abstain | Both directional | Correct oracle/nearest | Paired W/L |
|---|---:|---:|---:|---:|---:|
| 20260923T051828-422Z-33696-1 | 0 | 0 | 0 | 0/0 | 0/0 |
| 20260923T200129-346Z-33696-6 | 1 | 0 | 1 | 0/0 | 0/0 |
| 20260924T232304-170Z-12024-1 | 0 | 0 | 0 | 0/0 | 0/0 |
| 20260925T021320-371Z-7804-1 | 2 | 1 | 1 | 0/0 | 0/0 |
| 20260925T025230-605Z-7804-2 | 2 | 0 | 2 | 2/2 | 0/0 |
| 20260925T203745-207Z-49728-2 | 0 | 0 | 0 | 0/0 | 0/0 |
| 20260926T035932-508Z-63684-14 | 0 | 0 | 0 | 0/0 | 0/0 |
| 20260926T045729-166Z-79780-1 | 0 | 0 | 0 | 0/0 | 0/0 |
| **Total** | **5** | **1** | **4** | **2/2** | **0/0** |

Directional IDs are **E30, E33, E45, E47**; E43 is centered. E33's first resolved recipient is nearer B2 (then B3), both on the right while native yaw is left. E45/E47 agree with right yaw. Nearest and oracle have the same side on every supported oracle case. **2/4 is not an improvement over causal 1/3**: those denominators contain different cases. On the two cases directional in both passes (E30/E45), causal, oracle and nearest are all 1/2. This does not meet “Only hindsight helps.”

## Unknowns and still-control false starts

Across 48 causal cases: **16 one**, **15 unknown**, **8 multiple**, **9 none**. Onsets: 6/8/4/6 respectively; still controls: 10/7/4/3. There are **21/24 onset side abstentions** (18 lack a single supported focus, three centered) and **16/24 still side abstentions** (14 lack single focus, two centered).

U/M/N below is causal unknown/multiple/none. Outcome unknown counts omit E04's known-but-unlinked recipient. Every row has three onset and three still cases.

| TRAIN session | Onset U/M/N | Still U/M/N | Center focus onset/still | Outcome unknown onset/still | Off-center focus in still | Optional directional prediction in still |
|---|---|---|---|---|---|---|
| 20260923T051828-422Z-33696-1 | 1/1/0 | 2/0/1 | 1/0 | 3/3 | 0/3 | 0/3 |
| 20260923T200129-346Z-33696-6 | 1/0/1 | 2/1/0 | 0/0 | 2/2 | 0/3 | 0/3 |
| 20260924T232304-170Z-12024-1 | 1/0/2 | 0/1/0 | 0/0 | 3/2 | 2/3 | 1/3 |
| 20260925T021320-371Z-7804-1 | 0/2/0 | 1/1/0 | 1/0 | 1/1 | 1/3 | 0/3 |
| 20260925T025230-605Z-7804-2 | 1/0/0 | 0/1/2 | 1/0 | 1/3 | 0/3 | 0/3 |
| 20260925T203745-207Z-49728-2 | 2/0/1 | 2/0/0 | 0/0 | 2/1 | 1/3 | 1/3 |
| 20260926T035932-508Z-63684-14 | 1/0/2 | 0/0/0 | 0/0 | 3/2 | 3/3 | 1/3 |
| 20260926T045729-166Z-79780-1 | 1/1/0 | 0/0/0 | 0/2 | 3/0 | 1/3 | 1/3 |
| **Total** | **8/4/6** | **7/4/3** | **3/2** | **18/14** | **8/24** | **4/24** |

Treating any supported off-center focus as a turn-start cue would falsely start in **8/24 (33.3%)** still controls: **E06, E13, E14, E15, E16, E19, E35, E40**. That is 8/10 of the still cases with a single focus; the other two, E26/E36, are centered. E13/E15 are explicitly just-ended engagements in the causal notes. Excluding those two still leaves 6/24 such cues. The more conservative optional visual prediction actually chose left/right in **4/24 (16.7%)** still controls: E14/E16/E19/E35. Onsets had three directional optional predictions, three “none,” and 18 abstentions; still controls had four directional, five “none,” and 15 abstentions. “None” is a predicted no-turn, distinct from abstention.

Nearest-bot side alone is off-center in **18/24** still controls. This is a descriptive balanced case sample, not population precision, onset F1, a trained model comparison or an acceptance gate. Visible combat can coexist with a quiet camera; target availability is not itself a timing signal.

Outcome categories overlap: traversal/reorientation **33**, continued engagement **13**, multiple-target choice **12**, acquisition **5** (the frozen file uses “acquisition” and “visible acquisition” as synonymous tags), unknown **11**. These are interpretations of observed behavior, not ground truth about James's intent.

## Artifacts and limitations

- [Contact-sheet index: all 48 cases, both passes](contacts/index.md).
- [Frozen causal annotations](causal-annotations.json) and [frozen outcome annotations](outcome-annotations.json), including every manual box, ID, confidence and reason.
- [Unblinded frame/sample key](frame-key.json), [case-level comparisons](comparisons.csv), [per-session results](results.json).
- [Preparation](prepare.py), [outcome decode](decode_outcome.py), [evaluation](evaluate.py), [decode verification](verify_decode.py), [sheet packaging](package.py).
- [Causal receipt](causal-complete.json), [outcome receipt](outcome-complete.json), [package receipt](package-receipt.json), [native artifact manifest](native-artifacts.json).

All native frames, full sheets, native zoom crops and decode logs remain under `/Users/james/dev/range-bc-data/explore/target-identity-audit-20260929/{causal,outcome}/`, pinned by the manifest. Repository contact sheets are compact review copies, **not** the resolution used for annotation. They total about 51 MB.

The annotation is one owner's visual interpretation, with no second-rater agreement estimate. Approximate boxes, partial occlusion, very small bots and short context make some calls uncertain; confidence and unknowns are preserved. Ten outcome samples through the second can miss a brief intervening cue even though all 30 decoded frames are retained. Native sources are JPEG decode copies, not lossless crops. A known recipient does not imply the observer can infer the next camera turn, and low support prevents a broad claim that identity never matters.

Recompute the tables without opening corpus files: `uv run --no-project python docs/evidence/target-identity-audit-20260929/evaluate.py` (write outputs only in a scratch copy of this frozen evidence directory). It asserts annotation hashes, 48 unique IDs, three onset/three still per session, two-second separation and the fixed side rule. The final decision remains **Support is sparse or neither helps; stop**.
