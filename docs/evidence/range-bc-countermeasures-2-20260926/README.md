# Range BC countermeasures, round 2: neither works (2026-09-26, VUH-1346)

The pre-registered test (`fit-countermeasures-2-prereg.md`, 4d4576db) of two more countermeasures to the copycat
collapse, on the interim 80.5-minute data and dev, code 3670d0e. Arm A is the interim no-HUD model re-read (the control).
Arm D is known-idle corruption (P 0.5, runs 8-48). Arm E is sequential self-conditioning (P 0.5, 32 steps, ramp 0.5).
Three seeds each.

**Outcome: NEITHER WORKS.** No seed of D or E passes all four self-fed checks. A also fails, so the checks are sound.
Both arms keep executed teacher-forced skill (K passes).
- **D** lifts onset recall (0.07-0.11, S1 passes on all seeds), but presses at 1-5 % of the human rate, and every camera fails.
- **E** gives the best self-fed press-F1 so far (mean 0.072, against 0 for A and 0.052 for round 1's frames-only arm).
  It also lifts teacher-forced skill (0.043 against 0.035). But it presses at 27-42 % of the human rate,
  only 2 of 10 actions are in band, and every camera fails. Seed 0's S1 of 0.0481 against 0.05 is a near-miss and stays a failure.
- No self-fed camera beats persistence (0.418 degrees) or ar2 (0.376 degrees).

Per the pre-registration, no real fit runs. Round 3 is designed next (VUH-1346).

Judged by admission-review (Codex) with the judge written at 10:44, before any D/E result. The lead pinned it at 17:09,
before retrieval (`judge-pins-before-results-20260926T1715.txt`), and the file hashes were verified before and after
judging. The six checkpoints stay on the Mac, pinned by `mac-sha256-cm2.txt`.

| File | sha256 |
|---|---|
| `A-reread.json` | `8a13a3fd20057a4d9289c732c9897439665f6f7076ca8e5ec9dfb016b28925b9` |
| `A-reread.log` | `5f8228b281d1f32c13923202858a2130eabd434ca7d930de4bde8378aa1e1cf5` |
| `brief-hud-review-countermeasures-2.md` | `99c9659977b60ef389353e0503c75c5d9e7b8be9ce7a854551084e72217666da` |
| `fit-countermeasures-2-prereg.md` | `4d4576db90f65bb62f7fb4fb7a462a99d13b3d7c9898a8277a615e3d39608a17` |
| `fit-countermeasures-2.md` | `74436ef3c5bbd8e145f238d8c6d17a750a94e26a55cfb230f8081a9d59a6f446` |
| `judge-output.log` | `0ab39be909f56c9795ab8bf56def6643f11f1e189fb0800ae3cb3af3e1a456c5` |
| `judge-pins-before-results-20260926T1715.txt` | `d12fe78bfe487f38ce0b73ddc40cdcae73e6dde3482666d234e9386404170672` |
| `judge_cm2.py` | `d3a99f0ae8e1c89490cb0aacf30963f70b81b4df80b5e852f49759c059700f06` |
| `mac-sha256-cm2.txt` | `637249e9b01fa44b17da1cd3c766de94b5ae13a613f25ff663f82b6b5c6694d1` |
| `queue.status` | `c702813865e4cb35c4d8ac28d889d1495da7a130533682103accb1f74314c0fe` |
| `queue.zsh` | `bc34abbd02787adcc985f9a1613b197744171fa875afe755cc0a9d80ea01c7c3` |
| `reading.json` | `43e2a73eef8f0afe36dc2dabf2d40bd3263f99dbc92cb114a752474931df0db0` |
| `runs/cm2-d-s012.exit` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| `runs/cm2-d-s012.log` | `aac9861755914273c6a6d93bbf1478b05fb873bde59d161cfb57de830d1e09f6` |
| `runs/cm2-d-s012/report.json` | `6695baa4efa105e0cd52d34e1fad2ffafbc47349faaa8196be0c4cb51cb03117` |
| `runs/cm2-e-s012.exit` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| `runs/cm2-e-s012.log` | `af0e90b6e74d19aa71d273f1a119e99192e8277bfbe627ac4f14fdf399335b00` |
| `runs/cm2-e-s012/report.json` | `06feb07450319cacab07f8d780261a37299034fc86ae28baba034f94094c7000` |
| `test_judge_cm.log` | `46089617956beb84b7bfdc7cf220d0323eac327ba0c2aead94231e5788811f1b` |
| `test_judge_cm2.log` | `9c0536eff31cb658b7e17283d1b2bf914b6ee4dca280d4b269af57705f039004` |
| `test_judge_cm2.py` | `fa54b216d1736e752de0ae672a82fc1a66874e7bf3537b1a47fe6b077f8b9b74` |
| `verify-cm2.json` | `d23b8b9efee7faeea469d3f10b4bf4ed5d765d00ceded4a2645edf9417a889d7` |
