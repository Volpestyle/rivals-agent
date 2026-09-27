# Final missing TRAIN range store

Owner: idm-owner, VUH-1353. EXPLORATORY preparation. 2026-09-27. No fit, paid compute or evaluation result.

Session `20260925T203745-207Z-49728-2` completed on the Mac at 23:18:07 UTC; its exit and the serial remaining-store driver's exit are both zero. The driver PID 87635 was absent on collection. One CPU decoder used two decoder/filter threads, nice10. The store contains **165,608 frames**, took **4,241.113790 s** including source/hash work, and recorded a **2,364,211,200-byte** Python peak. Decoder platform is Darwin arm64, matching the other range stores.

The original source pin, exact PTS mapping and streamed payload hashes passed, followed by an independent full FrameStore payload rehash. The collection archive and all eleven collected metadata/sample files were hash-verified on the PC. The large frames.json is retained with the local collected packet and in the Mac store, pinned here rather than duplicated in Git.

- Source media SHA256: `666c626d4c285e20b3444081b9a1813d743aec8ab6cb538f134c5b61a265125c`.
- Target SHA256: `e091b4fdae7e61d9e8dd564687a56aaf8bc9416768e23c38873e1896a984b1e0`.
- Store frames.json SHA256: `185a1cf964b21155f1530766d152baefee6d6bc124ddf0353bd00bc012607eed`.
- Grey payload SHA256: `887854d079c7848f1360bb82ab7e2ba33711bfc961bf2402f705faff0b312770`.
- HUD payload SHA256: `353f72e7e4f38176076fd8326a19f14218dec385ba766f14f02a1a4a672e04c9`.
- Collection archive SHA256: `c6553ed2ea275e59494e84136d01ca035a8c06dcafee1be84fc06054710256f6`.
- Collection manifest SHA256: `a6b0fbc3104f05e1aa856de1c6e1ddedf63e01d7a6205673b09e15fee360f7a5`.

Owner inspected grey/HUD pairs at frames 34,792 (PTS289954), 167,515 (PTS1395979) and 311,750 (PTS2597938). Each shows Spider-Man in the Practice Range, distinct scenes and aligned HUD crops without blank output or displaced crops. The first sample shows three webs and 25% ultimate, the second two webs and a ready ultimate, the third one web and a ready ultimate. This is a sparse stored-output check, not new admission or a complete visual audit. The unchanged native-to-store graph control from the first completed 045729 store is reused; no second native-original decode was performed here.

Together with 045729 (`bcddd15`) and 035932 (`4783506`), all three missing range stores are now complete, hash-verified and sample-inspected: 311,254 stored frames over about 86.39 admitted minutes. All eight approved TRAIN ranges now have native IDM stores, covering 166.926104 admitted minutes before context filtering.

**Mac slot explicitly released to explore-policy after inspection.** Its dual-grid caches run next; the three current match stores follow only after its release. Their originals and corrected tables are ready, but their store decode has not started. The -8 metadata authority refresh `9989f32` awaits independent review before use in a fresh match/cloud packet; neither -7 nor -8 joins the fit roster. The approved expanded refit remains 181.888048 admitted minutes, $7 hard. No IDM cloud hold or launch is active; prior terminal lane bound remains $6.335876068670252.
