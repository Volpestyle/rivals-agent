# Range BC countermeasures, round 1: neither works (2026-09-26, VUH-1346)

The pre-registered test (`fit-countermeasures-prereg.md`, 078d5351; v1 de00d589 kept) of two countermeasures to the
copycat collapse found in `range-bc-selffed-diag-20260925/`, on the interim 80.5-minute data and dev, code 807d35f:
arm A (the interim no-HUD model re-read, the control), arm B (`frames_only_nohud`) and arm C (no-HUD with one-step
self-conditioning, p 0.5, ramp 0.5, prev dropout 0.2), three seeds each. **Outcome: NEITHER WORKS.** No seed of any arm
passes any self-fed check S1-S4; A fails as expected, so the checks are sound. C raises executed teacher-forced press-F1
(0.035 -> 0.052, K holds) but self-fed stays collapsed (onset recall <= 0.24 %, any-hold <= 1.4 %). B's seed 0 never
trained (dev flat at 2.39); seeds 1-2 tap at about the right count but hold almost nothing (any-hold 19 % vs the human
70 %). Per the pre-registration no real fit runs on these arms. The lead's reading, from the producer's inference
(`fit-countermeasures.md`): one-step self-conditioning feeds a lagged copy of the true history and prev dropout feeds
"unknown"; neither trains the known-idle absorbing state, so round 2 tests known-idle corruption and sequential
self-conditioning. The six checkpoints stay on the Mac, pinned by `mac-sha256-cm.txt`.

| File | sha256 |
|---|---|
| `A-reread.exit` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| `A-reread.json` | `8a13a3fd20057a4d9289c732c9897439665f6f7076ca8e5ec9dfb016b28925b9` |
| `A-reread.log` | `5f8228b281d1f32c13923202858a2130eabd434ca7d930de4bde8378aa1e1cf5` |
| `brief-hud-review-countermeasures.md` | `80aa1f231d72b7573cb92e1da96a32677f4f96f94b213d23f08877bd875665b4` |
| `fit-countermeasures-launch.md` | `2b58bd94dc5fc8a67d8030aa81ba56832d9620d191f95a38cda2c3bcf96212ad` |
| `fit-countermeasures-prereg-v1.md` | `de00d5892629b1589fb54622958abd39e003eff1fc6e3179003419a5075c89c9` |
| `fit-countermeasures-prereg.md` | `078d53513f311a1503fb3b0d40ac58ba42a2e4e3496d303f18f735f26ec2293f` |
| `fit-countermeasures.md` | `ee5f43b5234d320b4cccfc12364822f299f834a72730cc9b84dc9fbda3ef83bb` |
| `judge_cm.py` | `6f77e938e689f64c74a2a21ddf4f7ec5d22ac232e8099e94f62a74a7f1692e1f` |
| `mac-sha256-cm.txt` | `0578ddfd1ae3ccf89fa5e548b0906f681a041768d4bde770754af840a05c8137` |
| `proof-b-receipt.json` | `c9cf7aaf5a2585527d35487e97aa31c89334312044deac5b5c99d41b94e81036` |
| `proof_b_receipt.py` | `7fc3e753aa1eac54d0b1d66ab2546ef0239382851a81ca7d56eec62434327023` |
| `queue.status` | `32a882ad18172c95598217ee494cbc05e8de35a7c2392f826021c045ff5148ff` |
| `queue.zsh` | `0093fc05f88c0664b482876282eb8a2a01bf86b1dca60df76debd15287cf5a65` |
| `reading-cm.json` | `50378f032997862cf94bd583a2f7aa304344ede4aca6229bcfbfd502f332f8a1` |
| `repro-metrics-interim94-s012-v2.json` | `8a13a3fd20057a4d9289c732c9897439665f6f7076ca8e5ec9dfb016b28925b9` |
| `repro-train.zsh` | `5aacaa02f2049c51ef03a1b432b57c5bea491297520b16c8308c49017649ea3c` |
| `repro_metrics.py` | `2eb3f58b637af099d689855baf3d3aa0975f834180b0e117ee7084a251a2438e` |
| `runs/cm-s012.exit` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| `runs/cm-s012.log` | `e3b03473a426006c08ad7dc939d4261807ab992984b400eefde5922d597233a6` |
| `runs/cm-s012/report.json` | `82adfc7ea730bd1fe6e074a061e163f116848e2d927cc6013b3c0898bc4d6528` |
| `test_judge_cm.py` | `a5f09d3d0dce5b5235c1d5a41a35ed33ab14626afb07a4f6f7090b7566df7740` |
| `verify-cm.exit` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| `verify-cm.json` | `d23b8b9efee7faeea469d3f10b4bf4ed5d765d00ceded4a2645edf9417a889d7` |
