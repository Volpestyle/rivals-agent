# Finalized 20-second run: counts and audit locators

JSON-only analysis of `data/l1/range-request-20s-20260922-1`. **196 unique decisions, 835 normal rows plus one failed-send row (836 ticks), 13 accepted owners, 25 returned LT calls, two returned explicit releases; stop `max_time`.** No cast, hit, KO or physical-delivery conclusion follows from these counts. F owns native verification. Source files are unchanged and pinned in `receipts.json`; this analysis imports no runtime/model/native code and opens no media.

## Decisions and controls

- 141 model-event decisions: **84 start / 57 no-new**. All 57 first reached Controller `no_new_start`.
- The 84 starts first reached: 13 accepted, 24 shot-spacing, 35 unsupported/empty-ammo, seven unstable-target, three unaligned-target, one busy and one expired-request result. These are original reasons, not reconstructed labels.
- 55 other decisions: 30 target-unobserved, 19 warmup, five low-confidence and **one scripted low-HP gate**. There are 146 logged probability vectors (141 model events plus five confidence refusals), not 196 model inferences claimed from tick count.
- All 196 first-decision State/trace/timing records match their metadata acquisition and first-consumption links. None is unconsumed. Of 200 phase slots, 196 were offered and four late slots skipped (31, 41, 94, 167; offsets 34.964, 32.794, 36.255, 27.065 ms). Worker-queue misses and invalid-history reasons are zero. No broad stage-distribution comparison was repeated.

The retained thread receipt records unchanged 24 intra-op / 24 inter-op. Loader receipt records the original `6ee38807…1aeef` checkpoint, confidence 0.7, and zero loader inference/input. That receipt was read as metadata; no checkpoint was opened or policy replayed.

## Why metadata says 19.99 seconds

Phase origin is loop **6.543811100**, phase deadline **26.543811100**. The absolute session cutoff is **33.637337900** (this experiment's recorded 14-second startup + 20-second phase authorization is 34 seconds, not the earlier 24-second scope).

| Recorded boundary | Phase age (s) |
|---|---:|
| Last processed acquisition | 19.972172900 |
| Last normal send returned | 19.989806100 |
| Terminal observation timestamp | 19.989965500 |
| Terminal release event clock | 20.000981100 |
| Terminal neutral release returned | 20.001105300 |

The metadata duration follows the observation clock and rounds to **19.99**. The release clock is already beyond 20 seconds. These distinct clocks explain the apparent early finish; do not restamp the observation to the release time or invent a missing final decision. Phase deadline is the earlier effective send/lease scope. The timestamps do not establish the exact physical neutralization instant.

## Pulse ownership and continuation failure

Accepted owners are **29, 38, 46, 50, 54, 58, 62, 66, 70, 91, 109, 129, 171**. The first twelve target local track 1; owner 171 targets local track 11. There are 13 initial LT returns and 12 continuation LT returns. Twelve owners have two returned calls; owner 62 has one return plus one failed continuation. Request interpretation remains `request-start-owned-pulse-v1`; no old 67 ms gate was applied. Every owner preserves A/D/E with E=A+33 ms and original resources. Three returned continuations enter after D (owners 38, 54, 129), under their fixed E.

Owner **62**, target 1, is the useful failure locator:

| Boundary | Loop seconds / detail |
|---|---|
| Original decision State (JSONL line 249) | 12.863176000; webs=1 |
| Controller A | 12.929042300; resource age 65.8663 ms |
| First LT entry → returned | 12.929421400 → 12.930637400 |
| Fixed pulse E / original request D | 12.962042300 / 12.963176000 |
| Continuation observation (line 251) | 12.930827200; phase age 6.387016100 |
| Continuation entry → failed return | 12.961412700 → 12.962660000 |
| E slack at entry / overrun at return | +0.629600 ms / 0.617700 ms |

The failed return is still **0.516 ms before D**: this is pulse-end expiry, not a late new start. `press_edge=False`, `accepted=False`, owner 62 unchanged; `InputExpired` follows the guarded deadline check. The failure row has proposed LT and **no delivered pad**. The returned cancellation is line 250, written before the originating failure at line 251; metadata mirrors the same event. Outcome `cancelled_after_press` describes Controller time relative to E, not proof the physical hold completed.

Recovery retained **134 later decisions**. Fresh owners 66, 70, 91, 109, 129 and 171 were subsequently accepted. Owner 62 was neither reaccepted nor sent LT again. The final explicit release also returned; errors and range-gap lists are empty.

## Target/loss locators for F

Times below are **loop seconds**, with phase ages separately identified in `report.json`; they are not synchronized native-video PTS. Track IDs are local associations, not bot or kill identities.

| JSONL location | Recorded event |
|---|---|
| Lines 542–543; loop 20.123121–20.146097 | Decision 133 reflex refuses `target_coasting`: intended track 1, observed IDs `[7]`, coasting `[1]`. |
| Decisions 134–162; anchor 20.146097–22.948456 | 29 consecutive `target_unobserved` decisions. Other detections remain present; this is not evidence that the detector saw nothing. Report retains each actual ID/coasting set. Decision 1 is the other target-unobserved case. |
| Line 689, decision 163; anchor 23.067742, consumption observation 23.131518 | First subsequent non-null model-selected target is 11 (phase anchor 16.5239305). No claim this is a different native bot. |
| Lines 754–755 and 758; loop 24.641100, 24.658194, 24.750034 | Decisions 177/178 reflex refuse `target_missing_or_ambiguous`; observed IDs contain duplicate track 11 (`[11,13,11]`, then `[11,13,13,11]`). Preserve the actual ambiguity rather than inferring loss or a kill. |

Model-event decisions select track 1 in 113 cases and track 11 in 28. All pulse acceptance times and target IDs are retained in the report for native alignment.

## Five scripted Disengage ticks, one HP observation

All five ticks reuse **decision 173**, reason `scripted_low_hp_retreat`, no probability vector. Its original State anchor is **24.147567700** (phase 17.603756600), **HP=50, max_hp=250, webs=1**, detection track 11 and coasting track 12. This State is persisted only on line 733; the later four ticks are not four new HP readings.

| JSONL line | Loop observation | Phase age |
|---|---:|---:|
| 733 | 24.190062000 | 17.646250900 |
| 734 | 24.215826000 | 17.672014900 |
| 735 | 24.244251500 | 17.700440400 |
| 736 | 24.266350200 | 17.722539100 |
| 737 | 24.287194900 | 17.743383800 |

Line 734 references `000158.jpg`; it was not opened. All five returned pads command `rx=1`, zero other axes/triggers, no buttons. They are scripted turn commands, not learned escape/routing evidence. Adjacent decision 172 (anchor 24.054490800) reports 250/250 HP, and decision 174 (24.244251500) reports 250/250 with low-confidence refusal. Do not substitute either into decision 173. The isolated 50/250 report is an upstream observation whose native truth remains unverified here.

`analyze.py` uses stdlib JSON arithmetic only, verifies input hashes before/after and refuses to overwrite its outputs. Reproduce in a clean copy at the same repository-relative path with the seven pinned JSON inputs. Original archives remain unchanged; this report issues no acceptance or further runtime authority.
