# Range BC interim fit on the 94-minute corpus, 2026-09-25 (VUH-1346, VUH-1359)

**An interim scaling-curve point, not the real fit. Nothing here is a policy acceptance or a live-pilot candidate.**

The same pre-registered plumbing recipe (13 epochs, weight decay 1e-4, stride 64, lag 0; no-HUD arm against the
history-only twin; dev = 171533 + 205528) on 80.5 train minutes (five sessions) and on the same-recipe 33.6-minute
control (051828 + 200129), three seeds each. Pre-registered in `fit-interim-prereg.md`, amended in
`fit-interim-amend-1.md` after the first queue's seed-1 invocation was refused by `train.py` (seed 0 is required in
every invocation; `runs/interim94-seed1.log`), so each group ran as one `--seeds 0 1 2` invocation. The result and its
limitations are in `fit-interim.md`; `reading.json` is `judge.py`'s output. The lead recomputed both gaps and all three
rules from the two reports independently of `judge.py`: identical.

**Outcome: Opens.** The no-HUD arm's teacher-forced macro press-F1 lead over the twin grows from +0.0072 (33.6 min)
to +0.0361 (80.5 min), a rise of 0.0289 against combined seed ranges of 0.0236. Closes is not met: the dev-loss gap
falls from +0.050 to -0.0007, short of the 0.063 bar. Reverses is not met (one of three seeds below zero). Neither arm
beats persistence (0.418 deg) or ar2 (0.376 deg) on camera. Seed 0 reproduced bit for bit across the two queues
(`runs/interim94-seed0/` against `runs/interim94-s012/`). Self-fed rollouts are degenerate in every model, so nothing
here says the policy acts on its own outputs.

The fourteen checkpoints stay on the Mac (`/Users/james/dev/range-bc-data/runs/`); `mac-sha256.txt` pins them and
each equals its report's `checkpoints` entry.

| File | sha256 |
|---|---|
| `fit-interim.md` | `3354120600148396a09d7b519e85b8c7395ac1604b4717fd9288872cf6c8c784` |
| `fit-interim-amend-1.md` | `d17c483ef3f058da19c066070f1fd3f516c430659d17ddfc49395de2d60f0c0f` |
| `fit-interim-launch.md` | `7a69f7870dfd38f043a1f3da3e44d97e79f474bdf5358911c1b193e57d847878` |
| `fit-interim-launch-2.md` | `29b50213c04b47a08bdb357b6956485d2a7a424a80fbb96f0342fc99f884cb8d` |
| `fit-interim-prereg.md` | `8094bdd1bf1f12a6068c3c5382bbf65c474dd1ed2bbada9c834512f9de17604c` |
| `judge.py` | `bfab9d36425c278bc26390e5bf3061fce0a57d5103187a8e69dcd796981f8477` |
| `judge-v1.py` | `628c432e398780a8d6b53d04e2ad41685dd02a8bd80a42434a4767634e83f412` |
| `mac-sha256.txt` | `47c032d2695247b1a4026a63357910af66db2d22885404a9f15d378b242d307e` |
| `queue.zsh` | `a79e06b933cd63fcbcf1dbc5096df2d1556cf28129aeeb67fe9199b8fc7fb4d2` |
| `queue2.zsh` | `460ebb4870e154e35a9e5588e26105b2c3c52c1115080fd2712385dcfc55a687` |
| `reading.json` | `5409459082ba32b0e43006350a67029933100bb737ef3b6bdba78441659260c6` |
| `runs/interim94-control47-s012.exit` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| `runs/interim94-control47-s012.log` | `4a516a7a3566ddd09aa604e3c7d2e07e29cb225950e37cf4c62835629a59d0bc` |
| `runs/interim94-control47-s012/report.json` | `f1a6a0b7f8d3c2f0fdece301685dd92684021b4bdfdc5e38a441166f3f9da43d` |
| `runs/interim94-s012.exit` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| `runs/interim94-s012.log` | `cd0dca0f2c71960dc32462b78189a9b14a1ef7eb04d13e5175dfc05c0dbffc64` |
| `runs/interim94-s012/report.json` | `e8d955c0faa59937456ed91485d731781850e316a1892a9544d24c93f47938d5` |
| `runs/interim94-seed0.exit` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| `runs/interim94-seed0.log` | `0bbe86ebafd2c67b0914825af43ac23b3e587588c24e9801c8d19706656e4e04` |
| `runs/interim94-seed0/report.json` | `a18e1f8e5149ac631bf6740867229ebfd485591c769336ad7d236fc1f9bab5a8` |
| `runs/interim94-seed1.exit` | `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |
| `runs/interim94-seed1.log` | `6d3cc1388698377e3643b48b51bcbb8da7d5a965d2eb5b2d544b0e34246d7d70` |
| `test_judge.py` | `c6523c64e272eb0c2d6d835e248039644972c554cd3390fe1647160af7a473ea` |
| `verify-7.json` | `d23b8b9efee7faeea469d3f10b4bf4ed5d765d00ceded4a2645edf9417a889d7` |
