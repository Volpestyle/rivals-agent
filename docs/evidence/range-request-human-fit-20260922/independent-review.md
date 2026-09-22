# Independent request-timing candidate review ? VUH-1309

Independent Codex reviewer for root, 2026-09-22. Reviewed the frozen `032454-request-timing-v1` packet, seven exact HUD crops and their named originals, finalized received-input/CTS evidence, and the previously accepted visual/feature artifacts. This is a semantic/association recommendation; root retains admission and production API compatibility decisions.

**Conclusion: the evidence supports one `start_request` (n141) and four `no_new_request` controls (n137/n144/n200/n206) for a new TRAIN-only received-request numerical cohort. Keep n198 unknown.** There is one concrete footprint-bookkeeping correction below; it does not change these five labels or require more footage. Do not certify the frozen packet's ?full? footprints as covering every retained input dependency without that correction. This review supplies no live authority or validation result.

## Frozen identities and independent checks

- candidate-rows.json: `4e85b6fd8af84db8a2f99d4b076861f834b83b343ae76167d9650182d2d4e8fc`
- artifact-hashes.json: `41d937720e8d37a1a6eca21008d1764b3e5f6b7b16af819123131a64a5741f00`
- request-evidence.json: `513738c2552c02d36e94768e2a79dc0eaa28ccb12a1d827dd18f6f7acf89556a`
- crop-receipt.json: `b755c4b40de263101d1f8028c13193a2740a54ddfe21d99a7d46f26c0cbcf803`
- build.py: `06dc22993c035a4d9aae38f732f8a8d67793baf812d732ccdd8b36117af12037`

Verified all 14 manifested files against hashes/lengths. Independently checked all 30 histories against the frozen admitted source rows and all 780 feature values/known bits against the frozen measurements, without importing current policy, consumer or Controller. Masks remain binary with zero fillers for unknown values. Earlier absent/different targets and unknown readers were preserved, not repaired using later observations. Verified unique track-0 CTS/PTS/packet joins and accepted original-specific +21 ms file mapping for the referenced evidence; hashed 129 unique referenced PNGs without decoding those sequences. No new video decoding or perception replay occurred.

Viewed all seven HUD crops. Independently decoded only their seven specifically named originals and verified every crop is pixel-exact nearest-neighbor 3x enlargement of rectangle [260,1290,720,1410]. Also viewed the existing full n141 anchor and n142 emission frames for the local association. Reused the accepted complete cast/impact review rather than repeating it.

## Association and exact label disposition

The native glyphs consistently show the highlighted **right half of a mouse under projectile/ammo** and **left half under infinite melee**, including the causal n141 image, accepted emission, and each control's local anchor. These are actual displayed source controls, not guessed from raw button presence. Their appearance is binding evidence, not a physical button-state meter or proof of all alternate bindings.

For n141, the causal 14.121 file image selects the named Luna at bbox [1093,729,1287,1019]. Its actual composition time is 14.099999436. Raw RMB seq2757 on device65618 is received at 14.197983651, inside fixed `(14.1,14.2]`, 97.983651 ms after the anchor and 97.984215 ms after the final actual feature frame. The preceding RMB transition is release2528; there is exactly one received RMB down between that release and the linked cast confirmation. It is a fresh initiation, not a repeat or held continuation.

The independently accepted later event `032454-web-file14313-14321-luna` has withdrawn wrist at file14.313, emission/pose at14.321 with ammo3?2, and impact at14.329 on that same Luna. Native control distinction, unique received rise, same causal recipient, and separately confirmed execution together support this bounded association. LMB2692 through release2798 still overlaps request/cast. The association does not assert that earlier obscured impacts were webs, exclude concurrent melee, or erase the old n141 visual-onset unknown. It links this one RMB receipt to the later distinct reviewed web event, without claiming measured delivery or the player's physical decision time.

| Bin | Independent received-horizon check | Disposition |
|---|---|---|
| 137 | 14 received packets; RMB up from2528 throughout; only control transition Space-up2651. Local Luna, ammo3. | no_new_request |
| 141 | 15 packets; only control transition RMB-down2757; fresh up?down, same Luna. | start_request |
| 144 | 3 packets; RMB up from2791; E/A transitions2804/2806/2812. Local Luna recovery, ammo3. | no_new_request |
| 198 | 14 packets; fresh RMB-down3983. Anchor selects distant bbox[1525,261,1593,343]; later cast hits nearby Galacta. | unknown; no target substitution |
| 200 | 14 packets; RMB already held from3983, then up4018; E4033. No new down. Local-reset nearby target, ammo0. | no_new_request; held continuation |
| 206 | 15 packets; RMB up from4018; LMB4173 and E4184 are different controls. Local-reset nearby target, ammo1. | no_new_request |

Checked all received packets in each exact `(anchor,anchor+.1]`, original event fields, prior/end states and active focus. No intervening reset boundary invalidates the retained states. Independent transition replay agrees with every listed rise and continuation; repeated downs would not constitute fresh rises. The finalized source's already accepted loss/error facts are reused. No assertion that every physical event reached the logger follows.

The negatives are **no fresh received RMB initiation**, not no ability, no motion, no visible cast or no alternate-binding activity. n137 and n141 have identical all-3 ammo histories and opposite labels, so this contrast exceeds an ammo-only distinction. n200 remains an ammo-zero/continuation control and cannot alone establish ready-state restraint. n206 preserves other actions. There is still only one positive event, not evidence of generalization or learned-live initiation.

## Causal histories and masks

Actual composition times, unchanged from each bin's own source history:

| Bin | Five actual feature times (seconds) |
|---|---|
|137|13.299999468, 13.399999464, 13.499999460, 13.599999456, 13.699999452|
|141|13.699999452, 13.799999448, 13.899999444, 13.999999440, 14.099999436|
|144|13.999999440, 14.099999436, 14.199999432, 14.299999428, 14.399999424|
|198|19.399999224, 19.499999220, 19.599999216, 19.699999212, 19.799999208|
|200|19.599999216, 19.699999212, 19.799999208, 19.899999204, 19.999999200|
|206|20.199999192, 20.299999188, 20.399999184, 20.499999180, 20.599999176|

Every actual State/available time is at or before its own tick within the retained tolerance; all five n141/n198 observations precede their respective receipts. Later emission/impact evidence never enters n141's feature block. n144/n200 may contain prior cast execution because their task is absence of a new receipt, not absence of a prior cast. The offline availability assumption remains unchanged; CTS does not prove the player saw that image before acting.

Fresh Tracker/Memory per window remains part of the numerical contract. Continuous anchor boxes agree for137/141/144 and the excluded198; continuous200 instead selects the distant target and continuous206 has none. This packet cannot establish live continuous-selector equivalence. Source/group remain `20260922T032454-642Z-24328-1` / `james-2026-09-21-evening`, TRAIN only. Luna remains explicitly named and is not designated Galacta evidence.

Coverage independently reconciles to108 fixed coordinates: one start, four no-new, one inspected mismatch unknown and102 uninspected unknown. Old visual labels were not inherited elsewhere. Null origin/review fields and explicit candidate vocabulary correctly preserve the non-admitted boundary; `feature_source_identity` remains historical visual feature provenance, not a minted request approval.

## Concrete correction: retained input dependencies outside ?full? footprint

The latest endpoints correctly cover all reused local image/cast evidence and supporting releases: n137=13.808332781, n141=14.384998151, n144=14.508332753, n198=20.058332531, n200=20.108332529, n206=20.708332505. In particular, n141 includes LMB-up2798 beyond the later cast confirmation.

However, `build.py` computes `earliest` from history, prior **RMB** transition and explicit supporting events only. It omits retained LMB state and focus provenance:

- n137 retains LMB-up seq1930 at **10.415016051**, while both its input/history footprint starts13.299999468 and its supposedly full calibration footprint starts13.099999476.
- All six rows retain active focus seq37 at **0.421919351**, outside those full footprints.

This is a real under-description of the retained evidence dependencies, not a wrong receipt label. The existing same-session TRAIN-only group prevents it from creating a train/validation separation in this numerical cohort. For a genuine derived review-bound artifact, record a separate session-continuity dependency to seq37 and include the retained LMB carry-in where applicable, or conservatively extend the all-evidence interval to0.421919351 through each existing endpoint. If LMB state is deliberately merely ancillary for a row, that exclusion must be explicit rather than calling the current footprint all-inclusive. Do not change the frozen packet to conceal the discrepancy. No new recording or media inspection is needed to resolve it.

With that bookkeeping represented honestly by the owner, the five labels provide a defensible new received-request numerical cohort. This is not acceptance as the current visual EventExample, an independent-validation claim, a complete binding profile, motor/pad equivalence, physical-input timing, or deployment permission. Root owns the final disposition and API compatibility.

Only this new independent-review file was written. No candidate/source artifacts, labels, Examples, code, statuses, shared environment or prior reviews were modified.
