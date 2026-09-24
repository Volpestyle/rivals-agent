# Range BC plumbing fit, 2026-09-24 (VUH-1346, VUH-1359)

The nine pre-registered plumbing runs of the end-to-end range policy (`policy/range_bc`, commit `afff279`, plan
`range_bc_plumbing_prereg.json` `b0ce04df…`) on the four admitted recordings (train 051828 + 200129, 33.59 counted
minutes; dev 171533 + 205528), run as one niced durable queue on the Mac (MPS, torch 2.14.0), 05:09 to 14:12 CDT.
Every run exited 0. The lane's account is `fit-plumbing.md` (the runs, curves, scaling, unexpected findings) and
`fit-plumbing-2.md` (the parity re-emission and derive). Owner: the end-to-end fit lane (`docs/lanes/end-to-end-fit.md`,
"Plumbing fit result (2026-09-24)").

**Result, in one line:** MPS training is byte-repeatable; the real fit is pre-registered at 13 epochs, weight decay
1e-4, stride 64, lag 0, seeds 0-2; the history-only twin still has the lowest dev loss (1.3717 against no-HUD 1.4310),
the frame arms lead only on press-F1, and the scaling gap is positive from half the data but flat.

| File | sha256 (raw bytes; this folder is `-text`, so git keeps them) |
|---|---|
| `runs/plumb-p1-curve/report.json` | `dfa7a31704b17529638c8ea524a97109774ccbd8487975f41bc87d49d72cd032` |
| `runs/plumb-p2-repeat/report.json` | `68b4f046cb45bc1261488f36016dd7091cea1695bf3748c4c7f7c1e1e3a2efde` |
| `runs/plumb-p3-wd/report.json` | `4717291514219e9f4777b8049c300b743ef4f144b55c73b93b3dad818a639d9f` |
| `runs/plumb-p4-lag1/report.json` | `e39d65ac32a4d5e51f5458da706eb7e42df6c067be18e7c8f8f22bbddf85244c` |
| `runs/plumb-p4-lag2/report.json` | `38b6fff1d1bb4a29941a2d08e355ce21f4fcc2fc4a066c7dd2e0d2998557a5db` |
| `runs/plumb-p5-scale-0.25/report.json` | `8c6ae56f929e11b8d0c68963512070cf70a85fd0cf9303dadb432cfd896910ea` |
| `runs/plumb-p5-scale-0.50/report.json` | `f3dd378526da5fe42b07d79103fe9564db3c3a6af9ae05b8a8899e5bb630de20` |
| `runs/plumb-p5-scale-0.75/report.json` | `e1f14ab36952943ed94b12db7bf265c59a6b5747eac414baf064befa39b7d9ae` |
| `runs/plumb-p5-scale-1.00/report.json` | `7d07ae9ed288c80fbd345a11edd2a607abd3afd7101df000495eea2023f583c3` |
| `plan.json` (the driver's plan, `commands --commit afff279`) | `850aeded7c099ebcea55c4ae96ef251377528b6194d7226b4fa4577863b2c868` |
| `hud-parity-1-p2.json` (run 1 re-emitted with `hudparity --rule p2` on its exact 653 sources; CRLF) | `e9efe999e4b7f7e9df14f3e311ae5bbf71ab476101af40d07ed5d2ac02c48801` (LF-normalised `4ecb5e3e…`) |
| `preregistration.json` (derive's output; pins the parity file by its raw sha256) | `e1b2cefb095b65bd64bb78b32596821f0384966151b6127e86660c873eb9c03a` |
| `fit-plumbing.md` | `e6f4da9e20b34086` (prefix; the lane's hand-back) |
| `fit-plumbing-2.md` | `6951618894133aa6` (prefix) |
| `analysis.json`, `reemit_run1.py`, `preflight_check.py`, `poll.log` | the lane's read-only summary, the re-emission wrapper, the pre-flight call, the 10-minute poll record |

**The real fit must be given `hud-parity-1-p2.json` as these exact bytes** (scp from a checkout of this folder, never a
`git archive` on the Mac, which would not carry `.gitattributes`): `train.parity_record` refuses a file whose sha256
differs from `preregistration.json`'s `hud_parity_sha256`.

Checkpoints, logs and `.exit` files stay on the Mac under `/Users/james/dev/range-bc-data/runs/plumb-*`. The queue was
launched by hand by the lead at 05:09 CDT (the driver's `launch.ps1` had hung on ssh under PowerShell 5.1; the driver
now generates bash scripts, `fit-driver-bash.md` in the lane's hand-backs).
