# Second missing TRAIN range store verified

Owner: idm-owner, VUH-1353. EXPLORATORY preparation, $0 Mac CPU. Session `20260926T035932-508Z-63684-14`; frozen a730f75 recipe, two FFmpeg threads, serial/niced. Completed 2026-09-27 22:07:20 UTC, exit 0, 2,709.211 seconds and peak Python RSS 1,531,658,240 bytes. The third authorized range store (203745) started at 22:07:26; **the Mac slot has not been released**.

108,668 selected frames passed the decoder's exact-PTS checks and full payload rehash. Three stored grey/HUD pairs were collected, independently hash-verified on the PC, and visually inspected by the owner. Practice Range/own gameplay and matching HUD resource states were visible; no obvious crop displacement or blank/duplicated payload was seen. The unchanged decoder graph's native/stored control is the first 045729 store's evidence. This is a store-integrity check, not a new semantic admission verdict or a fit result.

| Artifact | SHA256 |
|---|---|
| Store frames.json | `6e7653c14bab459ec6d45ebc5018e6e1df3995ab92d8216794dd1cb8856167fa` |
| Grey payload | `556eacc58716e39a43403c5fea626e6f9192654e7076bacd84e0bdf54bc6d58f` |
| HUD payload | `e14321909dbde499202d89aa7600c8bfc1626a49ca23e2fbfb4d7f99c6377dfd` |
| Source recording | `7ab6b6083ac9aa38ad5b3ccde866ccb684d79332be42696ab36c2c7030f22494` |
| Targets | `52856414daefd6021af07109bc8425b55a3d9057974b6437153f0c9205991cb8` |
| Collection archive | `ac4957dbbfcb12b673e8c38eb7f21c3d4585d0784c0f2b20d71b1af214c55bc0` |
| Collection manifest | `6f3841c5f8cfcc32d59ab1362330fa4bf6ad6a61a350e8f4cb806899d5c6a2a0` |

Mac store: `/Users/james/dev/idm-data/range-stores-a730f75/stores/20260926T035932-508Z-63684-14/`. Full collected frames.json remains under `data/idm/cloud-20260927/range-stores-a730f75/second-control/stores/<sid>/`; it was verified against the collection manifest and is not duplicated in Git.

## Current match preparation, tables only

After independent LAND on authority refresh ebd9a8c, the existing `decode.prepare` passed for exactly -4a1/-5a1/-6: receipt/target/source-table/import identities, every target/step PTS against the imported frame table, and admitted needed-frame selection. No video was opened and no match store was decoded. An earlier attempt refused the newly changed receipt inventory before target rows; the reviewed explicit refresh resolved that refusal.

| Match | Target rows | Needed native store frames | Grey + HUD bytes |
|---|---:|---:|---:|
| -4a1 | 24,378 | 18,006 | 2,897,093,376 |
| -5a1 | 31,704 | 20,646 | 3,321,858,816 |
| -6 | 25,860 | 15,590 | 2,508,368,640 |

The combined payload forecast is **8,727,320,832 bytes** (about 8.13 GiB), before manifests. The pinned [table-only result](current-match-store-preflight.json) has SHA256 `bf7170001f8dfe52e6ee684d085526a97909b5c445411187fc3fc79859996f8b`. Native decode still waits for verified -4/-6 relocation receipts and the Mac slot after explore-policy's dual-grid cache work. No -7 payload was included.
