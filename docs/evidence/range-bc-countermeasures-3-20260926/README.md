# Range BC countermeasures, round 3: reviewed design, pinned before any implementation (2026-09-26, VUH-1346)

Round 2 read out as neither works (`range-bc-countermeasures-2-20260926/`). The round 3 design tests three suspected causes
of the self-fed idle collapse, with four matched no-HUD arms on the same 80.53-minute interim cohort and dev:
- **H (headline):** a frozen DINOv2-S/14 scene encoder, no previous-action input, and idle-target downweighting (weight 0.1
  on fully idle runs of at least 30 steps; fully idle means no input of any kind);
- **I:** the same, but with a normalised trainable IMPALA encoder;
- **W:** H with a weakened previous-action input (dropout 0.8);
- **N:** H with no idle downweighting.

A reader-vector arm R is conditional on a core pass. S1-S4 and K are unchanged. The compute device (Mac MPS or AWS CUDA)
is chosen after the cloud benchmark and before any result; if CUDA, the control A is retrained on the same hardware.

Drafted by fit-review (Codex), from James's proposal (VUH-1346 comment 417cfdf9) and round 2's candidates. admission-review
(Codex) reviewed it: LAND WITH FIXES, then LAND on the delta. The original draft bytes (5926f7ac, fd73259c) were amended in
place and not kept; the first review pins their hashes. The pre-registration is still a draft until its launch fields are
filled (§13).

| File | sha256 |
|---|---|
| `brief.md` | `6ed1c2347764f19127ec5459e5b8d80073a9c93a97d587bde232df7ef8e8e6ee` |
| `fit-countermeasures-3-prereg-draft.md` | `d15a9254a8e4dfb7b28ad6b2dab38ea060cd59ef66105bc8ae24b818774ea246` |
| `james-proposal-417cfdf9.md` | `a2800c03a31d2eb3e47faa71cf961a6e8a4a127ec639f94b72ddd238dede76e0` |
| `review-round3-20260926.md` | `0f9e905367d5975df1c445db233eea7f837f1e2199126fb85bc47a31f30ffbf5` |
| `review-round3-delta-20260926.md` | `723b563d56e6350b59a36d1df1ceb3665a217f0c9be45de4737def7b13137ce0` |
| `round3-design.md` | `29087a467ca0f9ce934189c354c46a99677208e1e8ede65bb40229e8197a427b` |

## Amendment 2 (2026-09-26 18:58 CDT, pre-result, approved by James): arm N dropped

The train-only sidecars weight 753 of 148,963 rows (0.51 %), so the idle-target contrast is untested; downweighting stays in H, I and W.
The current contract is the `-a2` pair. The files above are the pinned Amendment 1 versions, unchanged. admission-review: FIX
(routing references only), which the lead corrected; the substantive checks all pass.

| File | sha256 |
|---|---|
| `fit-countermeasures-3-prereg-draft-a2.md` | `93fc8ecaba9668b53bc3c0da4a4fdea211a9339535b0a06e050c46fa9cd50928` |
| `round3-design-a2.md` | `b36a50c1967891777b5f8ed4a80ed58112891370b3eaae74bbbeac256da32905` |
| `review-round3-a2-20260926.md` | `5de5b160f4e1fddc68735769569df9e9604e837780759d02668ec76680b8434a` |
