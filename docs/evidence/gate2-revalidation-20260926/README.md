# Gate 2 readers: the one re-validation (seed 20260927), 2026-09-26 (VUH-1353)

This folder records the re-validation of the two Gate 2 readers pre-registered in `docs/lanes/inverse-dynamics.md`,
"Gate 2 step 1": section `3fc13f3b`, amendments 3 (`9d8ad8f2`) and 4 (`51a2733c`), and the addendum to amendment 3
(`94e1f61a`). Owner: scoreboard-fix. Reviewer: fit-review (`review-gate2-revalidation-20260926.md`).

## Results

| Reader | Result |
|---|---|
| **Kill feed** | **FAILS** (live K1 0.18, K2 0.78). Named cause: the layout recognition read a competitive live HUD's team-box clock as the replay viewer. Rejected by the review. |
| **Match timer** | **T1 passes** (1 wrong in 750). T2 / T3' are information only (69 of 100 changes). The replay half is undecided. |

**What landed:** `perception/match_timer.py` (LF `945b3634`) and `perception/match_timer_glyphs.json` (`1f5ce476`)
land as a value reader only, with `tests/test_match_timer.py`. The review does not validate `second_changes` as a Gate
2 anchor source, and the original T3 failure stays on record.

**The rejected kill-feed reader** is kept here, unchanged, as a failed experiment: `code/killfeed.py` and
`code/spectator_prompt.json` are byte-identical to the frozen amendment-4 files (`c5147271`, `5aeab850`). The
original combined test file and its fixtures are in `code/`. They are not collected by the test suite.

The details are in `RESULTS.md`: the verdict, the blind re-label agreement, the deviations and disclosures, and the
scorer limitations.

## Files

**Truth:** `truth/feed_truth.json` is v2, the version scored. v1 (`8842a476`) differs only in the seven adjudicated
arrivals; the review reconstructs it exactly. `truth/truth-sha256.txt` lists the LF hashes at freezing.

**Hashes:** raw-byte sha256; `.gitattributes` keeps these files byte-exact.

| File | sha256 |
|---|---|
| `RESULTS.md` | `92946a7f1a816f8e7e15e65a27fa4295ba707968524cb27ad87d6daa0490fedd` |
| `code/fixtures_gate2_readers/centre_blurred.png` | `7d6e3a7690168e7f9ba871558bd4dfb756f9837d43c3add19deafbd57dc3ef8c` |
| `code/fixtures_gate2_readers/centre_decimal.png` | `6015241f5988e131d07669ee2f63fd50f178208965155819fd504b835d2ff796` |
| `code/fixtures_gate2_readers/centre_decimal_19_1.png` | `6015241f5988e131d07669ee2f63fd50f178208965155819fd504b835d2ff796` |
| `code/fixtures_gate2_readers/centre_lilac.png` | `06acb20646f6e6eca4fa0b7ba29546f1abe244cac238ccf04f2d4a2dfda22cde` |
| `code/fixtures_gate2_readers/centre_none.png` | `59937854b8ed7efd92d718774e0fbb1227179ebc3e8515d6ed75b00c90571710` |
| `code/fixtures_gate2_readers/centre_pop.png` | `1ff04017262664ef555cf1955a6bf333ba37acbbfc5d455886e98041c1ae1b58` |
| `code/fixtures_gate2_readers/centre_pop_18_9.png` | `814f01a5e368324c3b3c5a907932e346c52efffa55a8a22300eb76d978e4765e` |
| `code/fixtures_gate2_readers/centre_white_00_24.png` | `3dc349c66f571d22a521b327a95ad977fecf6f21ee3ba72754bd4cab0f4d4126` |
| `code/fixtures_gate2_readers/centre_white_mmss.png` | `3dc349c66f571d22a521b327a95ad977fecf6f21ee3ba72754bd4cab0f4d4126` |
| `code/fixtures_gate2_readers/centre_yellow_mmss.png` | `169f25754dc33de022f56733cd78424d54c6828d04e5965b3842cc4bcd99869f` |
| `code/fixtures_gate2_readers/kf_live_dark.png` | `f02c89402492bb513f0c5ffa0c83fad43fcbe43473dddf1c36ccc2e52499b3aa` |
| `code/fixtures_gate2_readers/kf_live_empty.png` | `db6772ae10683ee3d82b420682342762a1d1968d7af875fc875909ff47b9dc43` |
| `code/fixtures_gate2_readers/kf_live_light.png` | `feb289bb2ccc510b1aa243ecceacd5ad840dc9799ca875ae2f6f12ef0309f546` |
| `code/fixtures_gate2_readers/kf_spec_empty.png` | `42955c51725caec94842d9a6f0573f4f89bd836925e3786b232e3f64e6ae8f2e` |
| `code/fixtures_gate2_readers/kf_spec_entry.png` | `c266450e4375fbf74be33f71a2107fb1afc1bee2b82ee9043d6b65f082555764` |
| `code/fixtures_gate2_readers/prompt_live.png` | `2cd59db4d946e3dfd387344906f92fdb188e829872e69146c5e277b3c0f2c228` |
| `code/fixtures_gate2_readers/prompt_viewer.png` | `11be632169bdc43aa0bd02c771c3024629992ce389df9308dd727860541bcbde` |
| `code/fixtures_gate2_readers/team_a.png` | `d7a4fb9cabad03c08cce9abaf3717d34ad28f538b92c307cede713775273c9c9` |
| `code/fixtures_gate2_readers/team_b.png` | `b5b95cab73ce3426fca08e0a2460420d56ee23f05e06d7c5437ee2251d0b976a` |
| `code/killfeed.py` | `c514727180493fcdf774c2730221e406a013368e44696e326f10d15dfd6fe377` |
| `code/spectator_prompt.json` | `5aeab85063424bea29b538d4adc699989e85d77941b3e4ef5b2cfb709df88e2b` |
| `code/test_gate2_readers.py` | `41877ed7d048af7a4abae374d7eb5bc0dc9bc48f9e14901cdd84e1e0a7b7e3ab` |
| `fit-review-labels.json` | `2b4868b4f03ecc2b1468e89703b0fb8c6cbc223edab0eaf5c8212d96edac5f26` |
| `review-gate2-revalidation-20260926.md` | `0c204fdb219b25775ffd5c67c61620b61236ec019659fbe526b80433a6cac116` |
| `score_feed.json` | `8be58102cb0dc2262f80972171ac6dce436b875addaa419b18390fb802197142` |
| `score_timer.json` | `665128073a74be9335bc4db5446ff311b8904c1fc94a7eddfe0ce190db1e9534` |
| `scorers/draw_sample_2.py` | `68cd14e29cda211e541af6debe160ca090b8a7aecc7bbc4305166f7dc17c888b` |
| `scorers/draw_sample_3.py` | `b12682c5228f1ebd8b41c798c47fca7a083c8839f7135dde41fe2d9426a9d7d1` |
| `scorers/jumpaid.py` | `827503585bfe4ae22100ae98164149bec79d2224a0584515a208acfd95c3e19a` |
| `scorers/r2_blind_packet.py` | `c91bb48d7d86c7044d1922533fd973f316a1a52da5d55ec36a6916da495760ff` |
| `scorers/r2_score_feed.py` | `eda9a938d513b937547028a310d5cdee9e91e2ae2b53bbb9e2b061b40fac18fd` |
| `scorers/r2_score_timer.py` | `79eb59f248d54ef5bb4276c0a5b4ce05b182178098b63e314bc77d684593e2c1` |
| `scorers/sample-2.json` | `d7e738e2ab6360ee4029ab3d1bd645d7daa5be14a92b77dd84fcb6aaf3d013d8` |
| `scorers/sample-3.json` | `852c78f3fe6f08e0022b2630731d17b0f44e423c4102fc0c21058a235b3c4169` |
| `truth/blind_adjudication.json` | `67fe5f6fd94eb926677799f62de32ef7266869dfa5f704816b6864ae34832944` |
| `truth/feed_coarse.json` | `c4c68e3a24f88bf11c06e42d69cf30c863e9956bf4dba094d7a71efbc61cac9a` |
| `truth/feed_truth.json` | `3e1cf70153ff16e6d4ab830d97ea8ee1536811fb00330c50060ee1f6db6865c0` |
| `truth/timer_changes.json` | `c73008731eed14bf3d73f251c06572fc086618289b88df02af4e3ef730cdd6bf` |
| `truth/timer_coarse.json` | `d9b4bef5f4382926b1270c28668110f2fae92db5e6aaab39029e416e553d2a56` |
| `truth/timer_values.json` | `642a0c6c0f4d4f1e81dfcc183a0d48d4d49e7d029bcad2d3c8733107349d67c0` |
| `truth/truth-sha256.txt` | `e717ca754419e1ced811be78f10d20013b37531eac0cc93a3d1f9bac6b0b260c` |
