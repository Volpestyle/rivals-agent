# Three current match stores complete

Owner: idm-owner, VUH-1353. EXPLORATORY preparation, 2026-09-27 UTC. No fit or paid compute.

All three stores completed serially on Mac CPU (two decoder/filter threads, nice10), with zero worker and supervisor exits. Full source identity, current admission, target, exact PTS and streamed payload checks passed, followed by full FrameStore payload rehash. Decoder platform is Darwin arm64, matching all eight TRAIN range stores. The complete nine-member current-receipt authority from independently accepted `9989f32` was used; -7/-8 remain metadata only.

| Match | Current receipt | Frames | Seconds including verification | Python peak bytes |
|---|---|---:|---:|---:|
| -4 | accepted-a1 `1aec7993` | 18,006 | 412.008196 | 366,460,928 |
| -5 | accepted-a1 `94701525` | 20,646 | 422.908644 | 445,218,816 |
| -6 | accepted `90694961` | 15,590 | 352.210478 | 369,262,592 |

Total: **54,242 stored frames, 8,727,320,832 raw payload bytes**, over 14.961944 admitted match minutes. All eight TRAIN range stores plus these three matches cover **181.888048 admitted minutes** before context/known-label filtering. Frozen range dev remains separate.

The owner inspected three stored grey/HUD pairs per match. Match -4 also passed an exact native-frame control: frame7544, PTS62888, source image SHA256 `89dccb51c043c57777b2f182f274e6912481257b295707e0f5fd7d5630c710da`. The images show aligned scenes/HUD crops without blank output or sampled menus/ping wheels. Detailed observations are in the inspection receipts. This sparse check validates store preparation, not label accuracy, new admission, model accuracy or Gate 2.

Mac stores: `/Users/james/dev/idm-data/match-stores-9989f32/stores/<session-id>`. Frames manifests and large raw payloads stay there; their hashes are pinned in the copied worker results. Collection manifests pin every original collected file, including the frames manifests retained under PC `data/idm/cloud-20260927/{match4-control,match56-control}`. All collection members were verified on the PC. Original worker `visual_inspection=pending` fields are immutable historical state; the separate owner inspection receipts supersede that status.

- Match4 collection archive SHA256: `1b6a44f230a95db978fb7189f3555c850f3da1a3fc21412be248b0bc055afa26`.
- Match56 collection archive SHA256: `35ebfb3ece2ef1d3f8c8f11274a9b0028e3fc69422704ca8b56f7a1aaee67afe`.
- Match56 collection manifest SHA256: `851c76c6ea7c05d1345ded60c92c6a13a2e9e5c78147b6d0e7eccaa7ef3b80c6`.

**Mac decode slot explicitly released/idle after inspection.** Explore-policy subsequently moved its extraction to cloud and confirmed IDM can retain availability; no Mac cache launch is assumed. No IDM heavy process or paid hold remains active.

Next: assemble and verify the exact expanded cloud input packet, run the single-app probe, then the approved three-epoch seed0 refit using accepted shared modal_guard v1.0.4 and $7 hard total ($0.40 setup, $0.40 probe, $6.20 full attempt). TRAIN-only press calibration and matched real/zero-visual reporting remain required. The final source mount and cloud upload have not yet been completed. Prior terminal IDM spend bound is unchanged at **$6.335876068670252/$25**; alert at $20. This preparation makes no accuracy or Gate 2 claim.
