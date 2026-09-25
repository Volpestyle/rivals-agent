# scoreboard-fix: edge-input-2, the HUD-after-the-interval input across seeds and folds (VUH-1353)

2026-09-25.
- **Pre-registration:** lane doc "**Addendum: edge-input-2**" under the part B section, LF sha256
  `61e47c57e249a641f5d64561c045d2d58471aa59fc5da8037e2bbaf5d749508d`. It was sent before the runs; the lead
  confirmed the readings and committed it.
- **Queue:** one niced MPS queue; exit 0 after 145 min.
- **Not done:** no commits to main, no Linear, no game input.

## Result: the lag arm does not help (pre-registered reading)

| Component (all three required) | Result | Met? |
|---|---|---|
| (1) amazing_combo clears chance (ΔF1 ≥ 0.05, ≥ 30 onsets) on ≥ 2 of 3 seeds **in each fold** | lag: 051828 **1 of 3** (seed 0 only, part B's run); 205528 **0 of 3**. (Today: 1 of 3 on each fold) | **no** |
| (2) Get Over Here! or team_up clears on ≥ 2 of 3 seeds on 205528 | lag: Get Over Here! 0 of 3, team_up 0 of 3 (today: 0 and 0) | **no** |
| (3) jump's pooled F1: lag ≥ today − 0.05 | today 0.174, lag 0.184 (+0.010) | yes |

**Part B's single-seed "helps" does not replicate.**
- The amazing_combo gain it showed (+0.030 → +0.089) appears on seed 0 of 051828 only.
- On 051828 seeds 1 and 2, the lag arm clears less than or about the same as today.
- On all three seeds of 205528 it clears less than today (+0.045 / −0.009 / +0.002, against +0.070 / +0.019 / +0.033).

## Per fold and seed (F1 / ΔF1 over chance / AUC)

| Fold | Seed | Action | Onsets | Today | Lag |
|---|---|---|---|---|---|
| 051828 | 0 | amazing_combo | 60 | 0.039 / +0.030 / 0.797 | 0.108 / **+0.091** / 0.877 |
| 051828 | 1 | amazing_combo | 60 | 0.069 / **+0.057** / 0.818 | 0.039 / +0.027 / 0.765 |
| 051828 | 2 | amazing_combo | 60 | 0.017 / +0.004 / 0.802 | 0.033 / +0.012 / 0.796 |
| 205528 | 0 | amazing_combo | 82 | 0.082 / **+0.070** / 0.828 | 0.059 / +0.045 / 0.821 |
| 205528 | 1 | amazing_combo | 82 | 0.035 / +0.019 / 0.808 | 0.000 / −0.009 / 0.788 |
| 205528 | 2 | amazing_combo | 82 | 0.048 / +0.033 / 0.767 | 0.012 / +0.002 / 0.785 |
| 205528 | 0 / 1 / 2 | get_over_here | 35 | ΔF1 −0.002 / −0.005 / −0.004 | ΔF1 +0.020 / −0.004 / −0.002 |
| 205528 | 0 / 1 / 2 | team_up | 42 | ΔF1 −0.005 / −0.001 / −0.004 | ΔF1 +0.000 / +0.016 / −0.006 |
| 051828 | 0 / 1 / 2 | jump | 361 | F1 0.104 / 0.218 / 0.054 | F1 0.069 / 0.180 / 0.186 |
| 205528 | 0 / 1 / 2 | jump | 487 | F1 0.278 / 0.190 / 0.200 | F1 0.241 / 0.235 / 0.194 |
| 051828 | 0 / 1 / 2 | web_swing (reported only) | 83 | ΔF1 +0.058 / +0.049 / +0.068 | ΔF1 +0.001 / +0.041 / +0.059 |
| 205528 | 0 / 1 / 2 | web_swing (reported only) | 135 | ΔF1 +0.022 / +0.018 / +0.077 | ΔF1 +0.018 / +0.039 / +0.028 |

- **Get Over Here! and team_up** stay at chance in every run of both arms, with AUC 0.57–0.73.
- **Movement keys, spider_power and AUC** for every action are in `judge_e2-out.md`.

## What this says

- **The HUD crops at +67 and +133 ms do not make the HUD-visible abilities detectable at the rate-matched threshold.**
  Their HUD evidence mostly lags further (combo 0.3–0.5 s, Get Over Here! 1–1.9 s), beyond what the stored ±16-frame
  window can offer. That was the design's known limit.
- **Seed variance in the edge head is large enough that single-seed edge comparisons mislead.** Today's arm alone
  moves amazing_combo's ΔF1 from +0.004 to +0.070 across seeds, and jump's F1 from 0.054 to 0.218 on one fold. Part
  B's "helps" was inside that spread.
- **For future edge tests: at least three seeds per arm.** Two folds is what caught this.
- **A later-HUD input (0.3–2 s after the press) would need new stores:** the current ones hold only ±16 video
  frames. That's a design decision, not something I'm proposing to run now.

**A note on the numbers:** the seed-0 pair on 051828 reproduces part B's F1 values exactly. Its chance baseline uses
this judge's own seeded draws, so the ΔF1 differs from `idm-edge-input.md` by ≤ 0.004 (for example +0.091 against
+0.089).

## Hashes (all 50 run files checked across the wire)

**Lag-arm runs** (code `b3112fc` clean, `hud_offsets: [8, 16]`, plain loss, 3 epochs; in
`C:\Users\volpe\repos\rivals-agent\data\idm\runs\`, gitignored, with `e2.log` and `e2.exit`):

| Run | Fit | Checkpoint | report.json |
|---|---|---|---|
| e2-lag-051828-s1 | 1,211 s | `03aa0e1aaecacb61bf50b84d26c5a294eab330d2700c81f9d5341120d4c66435` | `b63273e4f76277259bbb153788cf05d638ab05ef90027ebed0f47f3c89b1a91d` |
| e2-lag-051828-s2 | 1,211 s | `da9cf01e1ccc5b323bbf53c42c473bff4c551e85ac4327b5e0a19a0dc2e38f44` | `13aa748cab3d84c59e8b09a6f13cda75e91cda24eb1e635949c4f83eb5162943` |
| e2-lag-205528-s0 | 1,122 s | `a6d4a5c4785a039ee88fb60099cf74d15f80c87d2d666560d5f9001e7f6518b3` | `7fdcf4420c1fd4f6592ee2562d156ed730533fd8f3d28a63ebb04bdbdbc27d11` |
| e2-lag-205528-s1 | 1,095 s | `67587c920675df0978bb69bdfd1b18feb79caec32020d718967643c1bb9ebf93` | `0bfe3a89d7ad50d47cd51815b9c735b78a8ac949154c4425db0f335311891b49` |
| e2-lag-205528-s2 | 1,104 s | `ee0ecd57788fab9e1ae8c4c7c96d436e3e5cd611b1d6bc9d5ff68783a8e3dac0` | `de8ebd30cb76de190c8e67ccd37fa9a70fdd30eaf67563aa98bdfe75ca88ec89` |

**The 40 probability files** (`scratchpad\idm-diag\press\e2-{today,lag}-<fold>-s<seed>-on-<session>.jsonl`):
- The full hashes are in `data\idm\runs\e2.log`.
- Today's 205528 seed-0 files hash identically to part C's `205528-on-*` (`a528f5d2…`, `14298fab…`, `f0933616…`,
  `9ae95e01…`). That is consistent with `a1-plain-s0`'s weights being bit-identical to `loso-205528`'s.

**Scripts and outputs:**

| File | sha256 |
|---|---|
| `judge_e2.py` | `dd2d8539320a460873866db5f8079e4ed5da8f55bf8ab169728fa555f9053103` |
| `judge_e2-out.md` | `e9ab45cb52b0d32a10ede5f387c53bbecc25880c7962c3f94a99dfdf32746f97` |
| `judge_e2-results.json` | `9394e265d9bbebc0d663d03cab947ef4092480f855e686467e4d15941dde6da3` |
| Mac `e2.zsh` | `0fcccbe869a6f54d9a04915d64c94830f824b28e419408489973c91b421d7b06` |
| Mac `chain2.zsh` | `1487324bc6b1f81a189880ee54e60d0f34a35bc392da1034275e8c8142bc00e3` |

**The branch** `idm/edge-hud-lag-20260925` (`b3112fc`) stays off main. With this result there is no case to land it.

**Next on the Mac:** the yaw-only β-NLL test (Y1–Y3) has been running since this queue ended. It hands back as
`idm-beta-yaw-only.md`.
