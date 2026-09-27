# First expanded range store: complete

Owner: idm-owner / VUH-1353. EXPLORATORY preparation; no fit or Gate 2 claim.

045729 completed on Mac at 21:19:59 UTC with exit0: 36,978 exact-PTS frames,
852.689 seconds, peak Python RSS546,734,080 bytes. Both payloads were rehashed.
Manifest SHA256: `410176acef5c7fe48c8be7da7142d9bbc66b500120a59ff1cf3ffefe3337fa95`.
The store is under `/Users/james/dev/idm-data/range-stores-a730f75/stores/20260926T045729-166Z-79780-1/`.

The owner inspected three grey/HUD samples plus one native source frame at the
first sample's exact PTS65971 (65.971s). Scene geometry, pose and HUD placement
agree; web count4 and ultimate68 percent match in that control. The other two
samples show a correctly placed M&K HUD and range scene. This is a small decode
control, not semantic re-admission. See first-inspection.json and native-control
receipt. Native PNG SHA256 `e800c71889be8c2d4193e04ba4636b3ab8b790fa12fc0546c5aae59ff216032e`.
The collected packet SHA256 was `01e10f68c5a5707c6e56c28259c9f4567c34e6614b9a055a1582ce888488a2b5`;
all collected members were checked against their Mac hashes before inspection.

After that check, the remaining serial queue started at 21:22:10 UTC,
PID87635, job `idm-range-stores-remaining-20260927`: 035932 then203745.
A failure stops the queue; no partial output is retried or overwritten. Both use
the same pinned a730f75 archive and worker recorded in
`../idm-expanded-preparation-20260927/`. The queue retains the Mac heavy slot.
Explore-policy's dual-grid extraction is next; IDM releases directly after final
collection and inspection. No release is claimed by this packet.

-4 corrected accepted-a1 landed in3b6680c. The existing single-receipt builder
validated its corrected table/demo and produced 24,378 targets,17,846 eligible.
Target SHA256 `6f2d688ddb3479cda839f763d0bd2dc0b273d05f79657672f1b4b3aac0e0176f`;
receipt copied here. It is table-only, no video read or fit.
Admission-codex owns -4/-6 originals/session relocations after -7 admission;
IDM owns target/receipt transfers. -5's corrected artifacts are already verified
on Mac. Current admitted eight-range plus -4/-5/-6 scope is **181.888048 min**
before context trimming. Native match stores and receipt-set review of5554ec1
remain prerequisites; no further recording is required for this refit.
