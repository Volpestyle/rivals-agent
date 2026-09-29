# Expanded IDM refit: complete eligible range cohort

**Status (2026-09-29): HISTORY.** The expanded refit it planned ran as full01 to full03 ([full03 result](../evidence/idm-expanded-full03-result-20260928/)); the IDM is parked ([decision](../research/policy-next-bet-scripted-baseline-20260928.md)).

---

## History (superseded)

Owner: idm-owner, VUH-1353. Metadata checked 2026-09-27 around 20:25 UTC. EXPLORATORY preparation; no new decode or fit launched. Press02 continues unchanged.

The next expanded refit includes every currently eligible whole-session TRAIN range, including the three without native IDM stores. The earlier five-range refit was explicitly interim, not the full corpus. Missing range stores are IDM's work and do not wait for more match admission.

| TRAIN range session | Counted minutes | Native IDM store |
|---|---:|---|
| 20260923T051828-422Z-33696-1 | 6.972500 | Mac, present |
| 20260923T200129-346Z-33696-6 | 26.617638 | Mac, present |
| 20260924T232304-170Z-12024-1 | 8.765416 | Mac, present |
| 20260925T021320-371Z-7804-1 | 34.516388 | Mac, present |
| 20260925T025230-605Z-7804-2 | 3.664028 | Mac, present |
| 20260925T203745-207Z-49728-2 | 45.978054 | Missing; target table built |
| 20260926T035932-508Z-63684-14 | 30.152221 | Missing; target table built |
| 20260926T045729-166Z-79780-1 | 10.259861 | Missing; target table built |

Source: each named session's admitted `minutes.json`, `counted.counted_minutes`. Their fresh sum is **166.926104 minutes (166.93 rounded)**, comprising 80.535969 existing-store minutes plus **86.390135 missing-store minutes**. Older notes' 80.53/166.92 were approximate totals. Context and known-label trimming will reduce the final per-head fit support, which the run must report separately.

Native stores for `171533` and `205528` also exist, but these are frozen development sources and remain held out; their registry `train` spelling does not authorize fitting them. Neither the roughly 180-minute total including those sources nor validation minutes is the fit total. The legacy `032454` is recorded as a request-cohort admission, not yet established as whole-session IDM admission; `055841` is a pending range fragment. Admission-codex was asked to resolve those metadata-only boundaries. Neither is silently counted or decoded. Permanently unadmitted `033319`, calibration/pad recordings, sealed/test, Gate 2/V-C/V-Q families and archive sources remain excluded. In particular, the newly sealed `20260927T195110-265Z-152960-1` and its 14-51-10 video/logger/frames were not opened, hashed, copied or intaken.

## Store build trigger and remaining work

Admission-codex subsequently confirmed from metadata that neither `032454` nor `055841` has whole-session paired IDM admission, and that -4/-5 accepted-a1 receipts have not landed. No additional range is omitted on its authority. This confirms the eight-session total above.

Use **Mac CPU decode**, serially, niced and with two FFmpeg threads, after explore-policy explicitly releases the heavy Mac slot and the lead's game-closed decode condition is met. No Mac job starts merely because press02 is on Modal. The five existing training stores report `Darwin arm64`; the refit refuses mixed decode platforms. A PC store cannot simply be added without parity evidence or rebuilding the entire cohort on one platform. The current homogeneous Mac route avoids that unnecessary rebuild.

All three missing originals already exist under `/Users/james/dev/range-bc-data/explore/originals/`:

- `2026-09-25 15-37-45.mkv`, 42,276,178,384 bytes.
- `2026-09-25 22-59-32.mkv`, 26,996,242,485 bytes.
- `2026-09-25 23-57-29.mkv`, 8,782,661,544 bytes.

The source tables/imports also have existing Mac policy locations under `explore/steps` and `explore/sessions`; the admitted target tables have already been built on the PC. `data/idm/cloud-20260927/expanded-range-targets/target-receipt.json` pins all three targets and their exact source tables/imports. Remaining work is to stage these small target/receipt files in IDM's own Mac directory, verify source-table/import/media relocation identities against their pins, run `policy.idm.decode build` into three new exclusive directories, inspect a small native/stored-frame control sample, and verify final `frames.json`/payload hashes. Reuse the originals; do not duplicate their roughly 78 GB. No DINO extraction is needed for this camera/legacy-head refit store build; the seconds-context edge experiment is separate.

Fresh Mac metadata inventory is `data/idm/cloud-20260927/range-inventory-20260927.json`, SHA-256 `6e2a38f476866ae036da58f0f6a9296cbf4e8a5b0992ff1a3ef0d72c8387bcaf`. It reads only named store manifests and source file metadata, never video contents. Free space was about 338 GB. The three grey/HUD stores forecast about **50.04 GB** at nominal 60 Hz, plus boundary frames and metadata; reserve 60 GB before decoding. This is not the larger DINO edge-store estimate in the earlier plan. Initial throughput/RSS must be measured on the first source; no precise decode ETA is claimed yet.

## Match inclusion and fit trigger

The currently consumable -6 match contributes 257.649989703 seconds = **4.2941665 minutes**, making the presently accepted range-plus-match scope **171.220271 minutes** before context trimming. Its target table is prepared, but its original/inputs have not yet been relocated or decoded on the Mac. -4/-5 historical receipts remain held after the ping-wheel finding until their corrected accepted-a1 receipts are independently accepted. Other matches join only after their own accepted receipts and homogeneous native stores exist; no speculative match minutes enter this total.

The fit trigger is all eight eligible range stores ready, plus the accepted match stores ready at the run's roster freeze, exact source/target/store pins and separate frozen-dev roles passing preflight, and a measured run forecast within the approved $7 expanded-refit allocation. The cloud manifest currently binds one match admission per manifest; including multiple separately issued match receipts requires a scoped adapter with refusal tests, not selecting the first receipt. This preparation gap is owned by IDM. No new cloud run, cap change, sealed access or recording request is implied by this plan.
