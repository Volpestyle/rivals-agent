# Independent native/outcome audit: range-request-20s-20260922-1

VUH-1346 / VUH-1311. Read-only, bounded audit of the one completed 20-second diagnostic. Root owns acceptance, archive and next measurement. This report makes no new runtime authorization.

## Outcome

**One visible Luna Snow KO, followed by a visible respawn. Eleven distinct Web-Cluster emissions/impact events are visible: ten through the lethal hit and one against the respawned Luna.** The final near-full health belongs to the respawned Luna and does not contradict the KO. The second life remains standing at the end. No second KO or unexpected attack type is visible in the inspected phase context.

The decisive original-video sequence is:

- PTS about 22.633 s: a distinct web emission, web ammo 1 -> 0, followed by impact on the nearly depleted Luna.
- PTS 22.767-23.300 s: KO marker and death animation. At **23.000 s**, `native-0092.jpg` clearly shows the player `cowboyboopbop`, the web-projectile kill-feed icon and `LUNA SNOW`, the red kill reticle, and Luna falling backward. This is affirmative native evidence, not a KO inferred from track loss or returned input.
- After death the platform is empty. At **25.633 s** it is still empty; by **25.733 s** Luna visibly materializes in gold with a full green health bar. The respawn interval is bracketed by these sampled video frames, not an exact server respawn timestamp.
- At about **26.900 s**, a further distinct web emission/impact reduces the respawned Luna's health. She remains alive through the terminal context. Saved `000178.jpg` shows the web marker, substantial remaining health, player HP 250/250 and web ammo 2 (a charge has replenished after the last shot).

The initial ready frame `000000.jpg` shows named Luna standing in the fresh range, player 250/250 and five web charges. The native pre-first-shot context shows the fresh target, and the subsequent visible health progression leads to the recorded KO. The fresh-entry/menu/PAD claim is joined to the new effective-setup receipt; I did not re-drive entry or re-audit unrelated settings media.

## Separate native events from software requests

The following are approximate original-video PTS locators for distinct visible emissions. Impact/target reaction and ammo loss were inspected around each. The owner column is the consistent temporal/ordered association to the logged pulse, not an exact synchronized game-input measurement.

| Event | Approx. video PTS (s) | Associated owner | Web ammo change | Native result |
|---|---:|---:|---|---|
| 1 | 12.333 | 29 | 5 -> 4 | Luna impact |
| 2 | 13.350 | 38 | 4 -> 3 | Luna impact |
| 3 | 14.250 | 46 | 3 -> 2 | Luna impact |
| 4 | 14.650-14.683 | 50 | 3 -> 2, after replenishment | Luna impact |
| 5 | 15.450 | 58 | 2 -> 1 | Luna impact |
| 6 | 16.217 | 66 | 1 -> 0 | Luna impact |
| 7 | 16.650 | 70 | 1 -> 0, after replenishment | Luna impact |
| 8 | 18.717 | 91 | 1 -> 0, after replenishment | Luna impact |
| 9 | 20.617 | 109 | 1 -> 0, after replenishment | Luna impact |
| 10 | 22.633 | 129 | 1 -> 0, after replenishment | Lethal Luna impact / KO |
| 11 | 26.900 | 171 | 2 -> 1 | Impact on respawned Luna |

There are **13 Controller owners and 25 returned LT API calls**, not 25 casts or 13 proven casts. Owners 29/38/46/50/54/58/66/70/91/109/129/171 each have two returned LT calls; owner 62 has one returned LT call and one failed continuation. There is no separate emission/ammo decrement in the bounded native windows associated with owners **54 or 62**. This does not establish why the game did not emit another shot, nor does a continuation failure erase owner 62's earlier returned call.

D's separately retained JSON analysis reports 196 decisions: 84 model starts, 57 model no-new requests and 55 other decisions. I reused that accounting instead of repeating a stage-distribution campaign. My limited ownership check independently found the same 13 owners, 25 returned LT calls, one failed continuation, two explicit returned releases, and 838 JSONL rows (835 ordinary rows, one failure origin, two releases). Every recorded delivered pad has RT zero and no buttons; bounded native context shows web attacks rather than melee/other abilities. Sampling cannot prove the absence of every sub-frame visual event.

## Failure, clocks and scope

Owner 62 remains a single owner. Its original resource/State time is 12.863176000, request deadline D=12.963176000, acceptance A=12.929042300, and nominal owned end E=12.962042300. Its first LT send returns. The later continuation attempts at 12.961412700 and fails with `InputExpired` at the actuator, recorded at 12.962660000. That is owned-end expiry, even though it is still before D. The failure origin has proposed LT and no delivered pad. Cancellation release returns at 12.962736700. The event is mirrored in metadata; it is not a second failure. Later fresh decisions continue, including accepted owner 66. Owner 62 is not retried or reaccepted.

For all 13 accepted starts, I checked original resource timestamps, A < original D/resource-age cap/owned end/phase cap, E=A+0.033, and returned first sends before their recorded start limits. All 25 returned LT timestamps precede their recorded owned end and phase scope. This is a check of recorded software clocks at the accepted API/watchdog resolution, not measurement of physical press duration, game render time or internal game input consumption. Continuing an owned pulse after D follows the accepted `request-start-owned-pulse-v1` interpretation; no rewritten resource clock is implied.

The learned phase origin is loop 6.543811100 and deadline 26.543811100; the absolute session deadline is 33.637337900, from the configured 14-second startup plus 20-second phase authorization. The final normal send returns at 26.533617200. Terminal observation time is 26.533776600, explaining metadata `seconds=19.99`; terminal neutral release returns at 26.544916400, phase age 20.001105300. Normal `max_time`, both releases returned, and no overall deadline/focus loss are recorded. The tiny release overrun is reported as observed software resolution, not a hard physical cutoff promise.

The target-1 coasting/unobserved interval and later track-11 reacquisition are consistent with the native death/respawn sequence. Track IDs alone were not used as kill or bot-identity evidence.

## Isolated low-HP observation

D identified decision 173's original State at loop 24.147567700 as HP=50/250, reused for five scripted Disengage ticks. Saved `000158.jpg` at loop 24.215826 shows **250/250**, and existing extracted native post-respawn context including `offense-0165.jpg` (PTS 27.033333) also shows **250/250**, with no visible player damage event. Thus the inspected native evidence does not substantiate a real low-health retreat. The saved frame is later than the original decision acquisition; that exact decision image is not proven by this correspondence. I retain the reported 50 rather than replace it, and do not identify the precise reader failure from later pixels. The five ticks are one reused scripted low-HP decision, with camera turn only and no offense, not five injuries or learned escape behavior. This limitation does not weaken the independently visible KO.

## Receipt and deployed-byte join

Actual `meta.json` source identity, runtime identity and deployment binding exactly equal their supplied JSON objects. The new binding SHA-256 is **5e21c2ee7fe665689f2fab7f691a25575dfcf7db5cecf2ce33b7bff223ad137b**. Its canonical source-identity digest is `082535863ad7773de498b872eccbacc21753da99966f2f64ff953d1871c5995e`. Source and PAD runtime identities remain distinct, with the original selector and request/feature semantic pins.

All **20** deployed file entries independently matched their current live-byte hashes and the LF-normalized accepted commit **676f99a** (including the accepted HUD content). `receipt-code-join.json` retains each file/hash comparison. This was byte comparison, not another implementation audit or an import of runtime code.

The receipts consistently name checkpoint `6ee388070599e3df042ea73876e391340bf228a9e626cc212c60875d8191aeef`, confidence 0.7, normal resources, no scoreboard, unchanged 24/24 Torch thread settings, and one 20-second exploratory learned phase with the 14/34-second startup/session limits. Checkpoint contents were not opened. The launcher carries `--max-s 20`, guards existing artifacts/consumed binding, records consumption before launch, and uses the supplied identities/binding in the live checkout. Launch result is exit 0. The binding-consumed receipt and finalized recorder belong to this one run; no rerun occurred as part of this audit. There is no new authorization in this report.

## Native timing method and limits

I sampled approximately video PTS 9-29.5 s for phase context, then inspected dense bounded windows around emissions, the lethal sequence and respawn. The remaining original 60-second recording was not exhaustively decoded/reviewed. `native-index.json` and `offense-index.json` retain source PTS, and decode logs retain extraction evidence. Contact-sheet context labels are coarse sample locators; fine event claims use the indexed native extracts.

Six moving saved-frame correspondences (000024-000029) near the first shot give video PTS minus original loop observation in **2.770431-2.780830 s**. This is a local empirical match with video frame spacing about 16.667 ms and additional acquisition/render/encoding uncertainty. A poor clip-edge match for 000023 is excluded. The recorder-launch wall/perf bracket is not the first rendered video frame, and stationary target/platform frames are not time anchors. I do not extrapolate the local interval into an exact global synchronization bound. It places the KO approximately 13.4-13.6 s into the learned phase, comfortably inside 20 s, consistent with ordered logs and the native sequence. No new primitive latency calibration is claimed.

This is one exploratory stationary-Luna diagnostic. It is not a designated-Galacta trial, an 8/10 quality result, matched-baseline evaluation, learned target selection, or evidence of performance against humans. The concrete demonstrated result is the visible KO/respawn and bounded attack sequence in this original run.

## Preservation and selected archive paths

All 28 initially pinned original artifacts remained byte-identical after inspection; all 32 initially selected saved JPEGs also matched. The additionally inspected 000158 hash was checked before/after. `original-hashes.json`, `original-hashes-after.json`, `integrity-check.json`, `saved-selection.json` and `additional-saved-hashes.json` preserve the checks. No source artifacts, code, model or original media were changed. Only temporary audit files were written.

Audit root: `C:\Users\volpe\AppData\Local\Temp\range-20s-audit-3ro2k553`

Retain this report, `selected/` (22 selected images/contact sheets), `native-index.json`, `offense-index.json`, their decode logs, `correspondence.json`, `receipt-code-join.json`, `bounded-attribution-check.json`, `offense-and-release-records.json`, the preservation manifests, and `audit-artifact-hashes.json`. Full-sized indexed extracts remain in the audit root if required for archive. The native KO/feed proof is `selected/native-0092.jpg`; respawn is `selected/native-0115.jpg` and `selected/native-0116.jpg`; terminal is `selected/saved-000178.jpg`.

Original SHA-256 pins follow. These hash values identify evidence, not a claim that every hashed file or all video frames were decoded.

| Original path | SHA-256 |
|---|---|
| `data/l1/range-request-20s-20260922-1/meta.json` | `4d005fe44444d7701f2c54d2beb93bcfb01398f1f33d345e91ba0dd2efaf8a9f` |
| `data/l1/range-request-20s-20260922-1/frames.jsonl` | `46002b2e42cff7e1a93dce161bd8f3d2cde77f5a7a606e5ff65f627fa36943ac` |
| `data/runtime/range-request-20s-preflight-20260922/actual-thread-settings.json` | `ea2f447462b3cbcf309e8823f32578eb81f33665c7d8e06d61f6c35b041d7b4c` |
| `data/runtime/range-request-20s-preflight-20260922/binding-consumed.json` | `6194ff86050560190087834810d6dfdc6de53332730897ba18b14dd6f003b8a4` |
| `data/runtime/range-request-20s-preflight-20260922/caller-review.md` | `93f513a990a5469a04e3b2cb375d830833cb5f080d32a5aaae3d572ab61cd832` |
| `data/runtime/range-request-20s-preflight-20260922/collect_settings.py` | `5f95ac7361f5d3dc75b465a9ed7fa63eafce19cb0b26294503e41692b4ae2204` |
| `data/runtime/range-request-20s-preflight-20260922/controller-deployed.json` | `bda2d130881c9275b1a8b3fc804be91563b40081cf75fde70c96cb87b3ad6cad` |
| `data/runtime/range-request-20s-preflight-20260922/deployment-binding.json` | `5e21c2ee7fe665689f2fab7f691a25575dfcf7db5cecf2ce33b7bff223ad137b` |
| `data/runtime/range-request-20s-preflight-20260922/deployment-check.json` | `ce25286707a0557633550a86acacf6fa51e5d334a8c0eb79a993584b3cce22fa` |
| `data/runtime/range-request-20s-preflight-20260922/deployment-review.json` | `dca45220cdd25a06e30508a1bcdedb5b42bee6422158d0def42f88e2c6a7ad11` |
| `data/runtime/range-request-20s-preflight-20260922/effective-setup.json` | `b281cd8fa33863606cc473d4428caae9ece00ab951aead3435269fa71f4b7f61` |
| `data/runtime/range-request-20s-preflight-20260922/freeze_deployed.py` | `560bdd9bd486b46b2de74b9d21b0e104674553a565c9d689d3d2d3d093bab561` |
| `data/runtime/range-request-20s-preflight-20260922/issue_binding.py` | `decd0c0fad1504193d41526ba648c945651b5fb134ee29b768b3ec1812829c03` |
| `data/runtime/range-request-20s-preflight-20260922/launch-result.json` | `109730c59584726d29f3c082e2ec77edfe8aadffc50c84ad65fa2d555f931653` |
| `data/runtime/range-request-20s-preflight-20260922/launch.ps1` | `90487d3477bc43350fff355ec7b1f69eb4c07e9ecf4949506c56aac655092184` |
| `data/runtime/range-request-20s-preflight-20260922/learned-native.mp4` | `d7e9bf361a1f75167b3df6577324fe5611ae88e42e6cc4231555d7e62e78c35e` |
| `data/runtime/range-request-20s-preflight-20260922/learned-recorder.json` | `a745f5134424f61e02782383476aad8a3cc70c6e4da5286493276008da10333e` |
| `data/runtime/range-request-20s-preflight-20260922/loader-preflight.json` | `7f7044bbeb308f50ace2b3ea15108044fb0428138f11c49534590f6211fe31d3` |
| `data/runtime/range-request-20s-preflight-20260922/perception-deployed.json` | `dc8b4447b93f4e97f9c486106f05930627ef06cfab5d6b58461f88f7a8eea69c` |
| `data/runtime/range-request-20s-preflight-20260922/README.md` | `8b94801e929e6981dd9af2583455770ff97a010f4ce471327f403405503c3d70` |
| `data/runtime/range-request-20s-preflight-20260922/runtime-identity.json` | `4da97df6e39178e4b83d18d3b7eec8950e831c8484d9ad814ddbb9f1a3257f86` |
| `data/runtime/range-request-20s-preflight-20260922/runtime-semantic-review.json` | `f5dbaf2658ad09183a1caa46b30f718e4f26a0eaa792d36ab1a2b17ab88572c1` |
| `data/runtime/range-request-20s-preflight-20260922/runtime-settings.json` | `d9002db02cec2e9fb1087b9a20ce6f1b95cd2a18f36e629f1cd607577a029624` |
| `data/runtime/range-request-20s-preflight-20260922/run_instrumented.py` | `d20bb27fbd3ce537e8dc66f3b82d431bfc8af53145c21df4f62a61c332234830` |
| `data/runtime/range-request-20s-preflight-20260922/saved-settings.json` | `69f27d6894764f922406ddf54197e4ffd82e805104a12f277a6f2151b2d621d5` |
| `data/runtime/range-request-20s-preflight-20260922/semantic-review.md` | `0a468ca604e741a89e472fe56eb3b005e577e43d5e4b03c4104896b453af5cce` |
| `data/runtime/range-request-20s-preflight-20260922/settings-native.mp4` | `06f4cc063d7b1b00911da235e370f3c0d14b7c8b0d0cb10bffca634a5aea65c2` |
| `data/runtime/range-request-20s-preflight-20260922/source-identity.json` | `72bf5e2be3db2e11e1820bd4a3d6fc73aabe3263e3778957de151bb66e27ef43` |
