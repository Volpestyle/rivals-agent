# IDM plumbing on the Mac, 2026-09-24 (VUH-1353)

The inverse-dynamics model's first run on real data: frame stores for the four admitted recordings (170,112 frames,
26 GB, on the Mac), the MPS determinism smoke (twice, byte-identical checkpoints), and the leave-one-session-out
plumbing fit (four folds, 3 epochs, seed 0, scope `gate1-dev`), all at commit `1df31e7` from the worktree
`/Users/james/dev/rivals-agent-worktrees/idm`. Owner: the inverse-dynamics lane (`docs/lanes/inverse-dynamics.md`,
entry "2026-09-24: first IDM plumbing run on the Mac"). The lane's accounts are `idm-prep.md` (steps 0-4),
`idm-stores.md` (steps 5-6) and `idm-loso.md` (steps 7-9).

**Read as plumbing, not as a gate.** Camera magnitude beats the zero baseline in every fold (yaw moving median
0.35-0.85° against 1.22-1.46°) but is far short of the label-built persistence ceiling; yaw direction agreement is
0.96 on the dev fold and at chance (0.47-0.54) on the three fast-heavy folds, unexplained; the stated std under-covers
above the calibrated band; the edge head has no usable skill (only jump fires). Nothing here feeds a replay label.

| File | sha256 (raw bytes; the folder is `-text`) |
|---|---|
| `*runs/loso-051828/report.json` | `7249186ca7f5ef736bc246213321ef4690999ced7e180ad1fa77437f4ca11a45` |
| `*runs/loso-171533/report.json` | `dfbfc7420a8cfedd615469ec03279ded3782ac968b1e524b8297843d84069022` |
| `*runs/loso-200129/report.json` | `aa048e3006c5974a015e31bcf6897a318ab289781d9d5fbedc1744434bacc78b` |
| `*runs/loso-205528/report.json` | `621ad66e3a13c8f1ef22097ad3c9845995abb81f64af2a6a3a5212cde632c5ab` |
| `*runs/smoke-a/report.json` | `bb8cc823dc75021d0e1bd1eb025dd496285921af848e973b61578663b3418dce` |
| `*runs/smoke-b/report.json` | `e947b3027ffb09351c506aca0b2f7637aa454806ceb98c2152cb7e56ad7fc01e` |
| `*runs/20260923T051828-422Z-33696-1.frames.json` | `457637aa99f61327d70bf5775d3a711a001e0a742888ae3b2fd3e7be8059ab2c` |
| `*runs/20260923T171533-187Z-33696-5.frames.json` | `8780ea7c10884a943c38a5a006a40854ee58b2a56978bd76f8249d98b644af8b` |
| `*runs/20260923T200129-346Z-33696-6.frames.json` | `a111ba075390634d2e658f7db28cdd6222b176a5be6d615b4a642b74f24a1939` |
| `*runs/20260923T205528-900Z-45572-3.frames.json` | `14190df6abcf0b8af7dbdc828f6c326c124bee30f96eb1f6f68a2e52920bdae6` |
| `*idm-prep.md` | `bc5f8fca3aa9588f57f59fc4067e75c2da5a2111050d99325b48f758689ea4d8` |
| `*idm-stores.md` | `7d509fadeaa9d9cfec5cf1c62e14e71d62ba1bd41a837dccb4c94d910d809a70` |
| `*idm-loso.md` | `056624745f88dc10d129b2224802525c93d514ca18177fca7f793fd6c8e74a53` |

Checkpoints (`idm-seed0.pt`, hashes in `idm-loso.md`), logs and `.exit` files stay in gitignored `data/idm/runs/`
on the PC and under `/Users/james/dev/idm-data/` on the Mac, with the stores.
