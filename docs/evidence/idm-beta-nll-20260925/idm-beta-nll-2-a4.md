# scoreboard-fix: A4, Gate 1 at scope with `--beta-nll` on the dev session (VUH-1353)

2026-09-25. The second file of `idm-beta-nll-2.md`, as pre-registered in the lane doc section `42beb90e` (A4).
- **β-NLL run:** the dev fold (171533 held out; train on 051828, 205528 and 200129), seed 0, 3 epochs,
  `--beta-nll 0.5`. Code `fe5c9ca`, clean; MPS; 160,772 train examples; 1,325 s. It records `camera_loss`
  `{"kind": "beta_nll", "beta": 0.5}` and cohort "Season 10, Version 20260911".
- **The plain side:** the plumbing checkpoint `loso-171533` (`67636921…`) **re-scored with the same `fe5c9ca`
  harness** (`policy.idm.train.gate1` plus the landed `idm_eval`), so both sides use one rule.
  - Its camera figures equal the plumbing report's, as they must, since the camera metrics are unchanged.
  - The recorded plumbing report stays as recorded, under the old edge rule.
- **No margin was pre-registered for A4.** The default-on call is yours.
- **Not done:** no commits, no Linear, no game input.

## Camera (171533 held out; answered moving rows unless noted)

Each cell reads: moving median error / direction agreement / 1 s summed-error median / abstention / calibrated median /
extrapolated median / > 4× median.

| Axis | Plain (re-scored) | **β-NLL** | Zero | Persistence (label-built) |
|---|---|---|---|---|
| Yaw | 0.352° / 0.964 / 3.35° / 3.7 % / 0.031 / 0.381 / 0.867 | **0.263° / 0.995 / 2.84° / 0.3 % / 0.038 / 0.276 / 0.502** | 1.224 / 0 / 12.63 / 0 | 0.198 / 0.993 / 0.36 / 0 |
| Pitch | 0.508° / 0.859 / 2.35° / 0.3 % / 0.024 / 0.333 / 0.508 | 0.568° / **0.887** / 2.98° / 0.0 % / 0.025 / 0.310 / 0.489 | 0.893 / 0 / 3.74 / 0 | 0.099 / 0.997 / 0.10 / 0 |

## The stated std's coverage, per true regime (within 1σ / within 2σ / abstention)

| Axis | Regime | Plain | β-NLL |
|---|---|---|---|
| Yaw | calibrated | 0.674 / 0.900 / 0.004 | 0.802 / 0.953 / 0.001 |
| Yaw | extrapolated | 0.730 / 0.927 / **0.142** | 0.734 / 0.916 / **0.009** |
| Pitch | calibrated | 0.827 / 0.941 / 0.000 | 0.866 / 0.982 / 0.000 |
| Pitch | extrapolated | 0.734 / 0.930 / 0.010 | **0.604 / 0.882** / 0.001 |

## Edges at the pre-registered 0.5 threshold (F1 / AUC / held-out onsets / abstained onsets)

Only jump, move_left, web_cluster, move_right and move_back have ≥ 30 held-out onsets on this small session (9,260
rows). Every other action is below F7's floor and decides nothing.

| Action | Plain | β-NLL |
|---|---|---|
| **jump** (88) | 0.128 / 0.890 / 88 / 39 | **0.239 / 0.940** / 88 / 16 |
| **web_cluster** (48) | 0.000 / 0.784 / 48 / 33 | **0.165 / 0.826** / 48 / 17 |
| **move_left** (53) | 0.000 / 0.549 / 53 / 36 | 0.000 / 0.621 / 53 / 32 |
| **move_right** (44) | 0.000 / 0.549 / 44 / 34 | 0.000 / 0.486 / 44 / 10 |
| **move_back** (32) | 0.000 / 0.569 / 32 / 7 | 0.000 / 0.580 / 32 / 0 |
| amazing_combo (14) | 0.000 / 0.900 / 14 / 7 | 0.191 / 0.943 / 14 / 1 |
| spider_power (24) | 0.000 / 0.732 / 24 / 9 | 0.094 / 0.777 / 24 / 1 |
| web_swing (25) | 0.000 / 0.721 / 25 / 5 | 0.000 / 0.785 / 25 / 1 |
| team_up (8), get_over_here (7), move_forward (26) | 0 across the board | 0 across the board |

## My reading (for your default-on call)

- **Yaw: β-NLL is better on every Gate 1 yaw figure on the dev session.**
  - The moving median error falls by 25 %, and the > 4× band's by 42 %.
  - Direction agreement is 0.995. Abstention falls from 3.7 % to 0.3 %, while the extrapolated band's coverage holds
    (0.734 / 0.916).
  - The dev session is the least fast-heavy of the four (23 % extrapolated). On the fast-heavy folds (A1) the plain
    loss fails outright on 4 of 6 seeds, so the dev fold understates the difference.
- **Pitch is mixed, and it is the cost.**
  - The moving median error is +0.06° (0.508° → 0.568°), and the 1 s sum +0.63°.
  - Direction is better (0.859 → 0.887).
  - **The extrapolated band's 1σ coverage drops** from 0.734 to 0.604: the stated pitch std is now too tight at
    speed.
  - This matches A2: pitch non-inferior on the mean, but not free.
- **The edges are an unplanned side effect, reported, not claimed.** At 0.5, jump's F1 nearly doubles (0.128 →
  0.239, AUC 0.890 → 0.940), web_cluster goes from 0 to 0.165, and abstained onsets fall.
  - A plausible mechanism: β-NLL rescales the camera loss relative to the press loss, which changes the shared
    trunk's balance.
  - One seed, one small session. It needs its own test before anyone counts it.
- **Summary across A1-A4:**
  - yaw is learned 6/6 and better at Gate 1;
  - pitch passes the pre-registered non-inferiority margin, with a measurable cost (error +0.06° here; extrapolated
    pitch coverage too tight);
  - the calibration improves overall and the bounds hold 6/6.
  - **If the pitch cost is acceptable, the evidence supports default-on. If not, β-NLL on yaw only** (the next test
    A2 named) is the targeted alternative.

## Hashes (checked across the wire)

| File | sha256 |
|---|---|
| `a4-beta/idm-seed0.pt` | `90aa4befa489e9a8385d9d40445be2d17efafb32395375aecedb0f488fb7da0a` |
| `a4-beta/report.json` | `43c2f8bbf1afc64508e51f5cb024de0ac13e9bd238512fe09c2fe1190bfc1c8e` |
| `a4-plain-rescore/gate1.json` (re-scoring checkpoint `676369216b608910…`) | `e15a2770aeb41d6f32ccfeb4402ed35d5f0bb0529f9e819d6095ca993b0454c4` |
| Mac `a4.zsh` | `0f86e3b73d8ed37c9c387c7c4c223e7bae25ff1c444c8e33f3cf8a2abb9ae54b` |
| Mac `rescore_gate1.py` | `7df5c4456762311ad51a9ae13db95a1f8de7f350bc3a7650849010ed96e38fe1` |
| PC `judge_a4.py` | `68b0ecb70f47a308be12055a750020145218403431df20a5951a05f22ef8a541` |
| PC `judge_a4-out.md` | `58831b0681d8e11e6222cd4864adb9513f2f574c2feef135600612d40a83cd4f` |

**Locations:**
- the runs: `C:\Users\volpe\repos\rivals-agent\data\idm\runs\a4-beta\` and `…\a4-plain-rescore\` (gitignored), with
  `a4.log` and `a4.exit`;
- the judge: `scratchpad\idm-diag\`.

**Next on the Mac:** edge-input-2 has been running since A4 ended; it hands back as `idm-edge-input-2.md`.
