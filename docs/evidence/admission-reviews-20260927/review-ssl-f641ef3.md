# f641ef3 SSL admission review — LAND

Independent fit-review (Codex), 2026-09-27. No blocking or fix-forward findings in this bounded metadata admission. Packet SHA256 `864e54350343a26ce0111d03d6e76d39bddef2f1e3e1c5cdb898b93e1f42dd02`.

Independently streamed all four current media files in 1 MiB blocks; every SHA256 matches admission.json. File size and mtime stayed stable throughout each hash, and the latest compression-log record stayed unchanged. Exact current sizes also equal the corresponding replaced record's new_bytes. Current log lines 56, 58, 108 and 109 are all replaced, and their raw-line hashes equal the packet pins. No non-finalized source was opened. The four sources total 90,920,475,225 bytes and 26,767.174 seconds (7.435326 hours).

| Raw session | Current bytes | SHA256 |
|---|---:|---|
| 2026-02-13 21-30-25 | 39775792417 | 2d8f97eb2b85eb0424d68f7b2dbee6dc106990a8904c0c7d8dae0be4c2e47c6e |
| 2026-02-14 14-27-37 | 13001590692 | 28772a0f0c1845d7a0048b9d2f45527c4737f7f63b1d37174bba2e91c19ae35e |
| 2026-02-17 16-51-17 | 28989212917 | 772d8062b7239082df5a95bb7cb815b2672bab46efdb3ebc90367e8304ca4479 |
| 2026-02-17 23-51-41 | 9153879199 | 7ec0fa46f84642d537c1706ee2a3d88abcc067fedcdbd35e2c819fb7a4faa18a |

All five committed packet files match f641ef3 after LF normalization. The metadata-pass, current split registry and pinned denylist hashes match admission.json. The four names are exactly the four smallest finalized metadata candidates and are raw-session entries in the inventory, not its derived clip or stub entries. The older inventory's pending labels on the two February 17 files are superseded by the current replaced log records.

Recomputed exclusion against all 18 forbidden metadata records (including duplicate denylist/registry coverage): 053616, 153835/153812, all Gate 2 pairs, V-C, V-Q and range validation. No filename or exact-media-digest overlap. Separately checked the documented DayMR September 23 replay filename and its recorded original SHA256 `a032a638183b31e9cfd59ae5f78691baad2dc33cb18bba175558d5dc98b0e5b3`; none matches. February raw-session provenance/date membership is distinct from those September families. No forbidden media or logger payload was opened. This accepts the documented metadata/family basis, not an exhaustive visual or perceptual deduplication claim; filenames and hashes alone cannot prove the absence of arbitrary embedded/re-recorded footage. The packet states that limitation explicitly.

The usage string is world-feature SSL only, no semantic labels and no evaluation. Every row has semantic_labels_allowed=false and eligible_intervals=[]. The interval contract requires consumer native-window inspection and a separate cut-free sampled-clip manifest before extraction/training. This review admits no intervals, labels, or evaluation use.

Static review of finalize.py confirms streaming SHA256 in 4 MiB blocks, current replaced checks before hashing and again after probing, exact size and stable size/mtime checks, and header-only ffprobe with no frame-decode command. Its log records the same hashes and final packet digest. The independent hash pass used bounded 1 MiB reads with game/OBS checks throughout; own process priority was explicitly verified/set to Idle during the pass. Its first metadata-only attempt stopped before any media read on a compression-log summary row lacking a file key; the corrected parser ignores those summary rows. This did not affect qualification or source bytes.

Independent machine-readable evidence: `review-ssl-f641ef3-results.json`; review script: `review-ssl-f641ef3.py`, alongside this report. No packet edits, media decode, transfer, training, game input or commits.

Anchor queue status: **5c20c8d already LAND**, F1 closed; see `review-pts-anchor-5c20c8d.md`. That accepted result is reused, not rerun.
