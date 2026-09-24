# admission-owner final 13: 200129 and take 2 admitted; four sessions, 47.23 counted minutes

**The plumbing fit's input.** Four step files, all in `rivals-range-steps-v1` with the 15-action vocabulary. The fit
lane's reader loads them as **one cohort: 85,016 accepted rows**, normal regime, train.
- **Header:** calibration v2 (yaw 0.0330738 slow-turn gain, pitch derived equal, `accel_on: true`); settings identity
  `a8dea3ba...`.
- **Checks:** 36 intake tests pass; every session freeze checks clean.
- **Scope:** offline, four decoder threads, below-normal priority. Nothing committed.
- **A correction to the Caps Lock note:** the 13 presses are in **take 2 (205528)**, not 200129; 200129 has 3.

## Tally: normal, train: 47.23 counted / 47.23 trainable of 180 minutes

| Session | Accepted | Counted min | Rows (accepted) | Freeze | Notes |
|---|---|---|---|---|---|
| 171533 (v3) | seg-007 | 2.57 | 4,800 (4,630) | `eb61a5ac...` | re-stepped for 15 actions |
| 051828 (v2) | seg-002 | 6.97 | 12,558 (12,550) | `f428cc64...` | re-stepped for 15 actions |
| 200129 | seg-007, seg-010 | 26.62 | 48,195 (47,910; 2 runs) | `93e24521...` | two death cuts; review `70e77f63...` |
| 205528 take 2 (HEVC) | seg-002 | 11.07 | 19,935 (19,926) | `c0687e0f...` | review `e526a4f3...` |

**Accepted presses across the cohort:**

| Action | Presses | Action | Presses |
|---|---|---|---|
| jump | 2,186 | amazing_combo | 368 |
| move_left | 1,244 | team_up | 168 |
| web_cluster | 1,322 | get_over_here | 159 |
| move_forward | 997 | goh_targeting | 51 |
| move_right | 977 | melee | 23 |
| move_back | 778 | simple_swing | 16 |
| spider_power | 635 | ultimate | 9 |
| web_swing | 573 | | |

Unsupported presses: one Alt in 171533, one LCtrl (slow walk) and one Alt in 200129.

## Bytes and sha256

| Session | File | Bytes | sha256 |
|---|---|---|---|
| 200129 | `20260923T200129-346Z-33696-6.steps.jsonl` | 32,759,007 | `fcc9b0443e720648b899453ea3f04f82c0a6dd1735f30a420a36b3675549ba8e` |
| 200129 | `artifact-hashes.json` | 5,143 | `93e2452130b267ba39e59b39c3ef3b0f7c7bcbe7307bdc337a58a1eb7850f48f` |
| 200129 | `review.json` | 13,726 | `4dd80ec3cfb71a3658b137b99341643fc5386f125997a16963aa889795697c1b` |
| 200129 | `settings.json` | 4,818 | `524f89aefd1409e00e9c479e50102e65bf33adcc21db02656fb2d4ff113dc210` |
| 200129 | `sampling.json` | 639 | `53de74d86904534ec7d04950e80345563b4883c9fcc90eec64df68eb3b73be43` |
| 200129 | `minutes.json` | 978 | `feb4ebf1620fb91de25881aa128eac82a305dc21ea423ad6623b6212e05db9dd` |
| 200129 | `imported-demo.jsonl` | 100,729,519 | `e8c4fde71f106241a3a192a6f2dd0fae21725191083a89a319036702e7aca07d` |
| 205528 | `20260923T205528-900Z-45572-3.steps.jsonl` | 13,522,361 | `941950f16edef6a88b14d6bc536e33a66a0e779867fa145c78e7142164e1fd98` |
| 205528 | `artifact-hashes.json` | 5,138 | `c0687e0fe8e9ed1e05a49ebb98757dbf3321ea40f26be291f4eaad82fd9aba53` |
| 205528 | `review.json` | 9,739 | `bb092a8a9e016e199e57ba6b30903a7cc0c3a9ef43f5fdf43878971d200c7ab9` |
| 205528 | `settings.json` | 4,819 | `5f80279e8e472591ebade1843a8fc405dc881db032d840068d98608f1a4dd265` |
| 205528 | `sampling.json` | 639 | `692f3a7ef59ddc046fa357963d31d3413ca4a0dfc87cfcd023bdf2549bbca8db` |
| 205528 | `minutes.json` | 894 | `1ac3886fd35b06b891198a6568ed43441aa01eedb0ef0b76084642a14a5deee3` |
| 205528 | `imported-demo.jsonl` | 41,098,528 | `0906e7e0bf9298d697631f7c6802fc0e282334234c1069d9c6f93897f1a669e1` |
| 171533 | `20260923T171533-187Z-33696-5.steps.jsonl` (v3) | 3,247,674 | `dc28b0c1511f7847c8dde08c3e04addce8b57bc6c32cc2873405962d3235559e` |
| 171533 | `artifact-hashes.json` | 7,441 | `eb61a5ac010ed82dc20d72b152bfbb4efc129068252df871a7a6ac4576d8f0b4` |
| 171533 | `sampling.json` | 701 | `770d462907e0a949c682a6eb58a11d0abcb9f10622fde3e22b1de1c52bc8a3fa` |
| 051828 | `20260923T051828-422Z-33696-1.steps.jsonl` (v2) | 8,515,125 | `d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb` |
| 051828 | `artifact-hashes.json` | 6,255 | `f428cc64d9efd5e894d79dd6a29f146be323e780919d9332e6a60a11b99590cf` |
| 051828 | `sampling.json` | 704 | `8d1d042a648372cad5c79eb955c089efecdaa3a6f8f91892a0bc9c2cc916c4d4` |

171533's and 051828's `review.json`, `settings.json`, `minutes.json` and `imported-demo.jsonl` are unchanged from their
earlier assembly.

**Code: diffs on top of the landing (`86a1912`)**

| File | Bytes | sha256 | Change |
|---|---|---|---|
| `agent/human_intake.py` | 72,561 | `83a18a42a00a14500fade79d9a079bca940571f50eef34b47a5022285f8996ff` | `FIT_ACTIONS` gains `simple_swing` |
| `tests/human_intake_fixtures.py` | 7,053 | `f30458dd6763e44ee791fd172b9a120d1c484a062d81dc5c0ed237cad219d351` | fixture binding table gains Caps Lock |
| `data/human/sessions/restep_session.py` (new) | 4,685 | `fab95c379c4154fc8f0730ad21f8b6c4391b4903f36858e6f83b77d14c46f2bb` | versioned step-file rewrite |
| `data/human/sessions/tally.py` | 5,627 | `f32adfbd6169c58496901f9d54b262cc5e8d1193221426da171ff33632ee6f6a` | four admitted sessions |
| `data/human/sessions/assemble_session.py` | 18,993 | `5a14b4cbed9ecc1d2288e7b6294fa9f587d65993541feb3c6c7f1087b674da92` | adds `--sessions-dir`, used for the rehearsal |
| `docs/evidence/corpus-tally.md` | 3,277 | `1e6ec8be8513c5752ad93244e50236c4091c77b4ef61bbc55c7bb2c15e6b62a5` | regenerated |
| `data/human/sessions/tally.json` | 5,963 | `af6833e986b9168b69a4b2a0bd4a99c871ed427d9b228810b915c19a60556ea7` | regenerated |

`docs/lanes/human-admission.md` has two appended sections: the dead-rule amendment with the two frames, and this
admission.

**Before the reviews arrived,** I rehearsed both assemblies into scratch with stand-in verdicts. Take 2 passed end to
end; 200129 was stopped at its import when the reviews came in. The real runs then followed the same path.
