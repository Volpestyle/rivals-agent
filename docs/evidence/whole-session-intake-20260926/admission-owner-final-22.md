# admission-owner final 22: 212646 admitted as val (15.5846 val min, beside train); tally regenerated

**Assembly.** `20260925T212646-322Z-49728-6` was assembled on 2026-09-25 from **`code-snapshot-b7d4592`** (manifest
`1927686c…`), with the independent record `7c47d6af…` (review-session-212646.md `fcc71973…`). The record agrees with
the owner verdicts on all 28 segments and all their bounds.
- **Freeze:** `check_freeze` is clean; 20 folder files, 9 external.
- **The freeze and `minutes.json` carry `split: val`,** sitting 2026-09-25-afternoon, settings identity `a8dea3ba…`,
  calibration v2.
- **The recording log** is pinned at `fbe6693` (the motor line at ~16:50 CDT). The registry is pinned at `cbae5149…`.

**What it holds.**
- **Accepted:** six segments (126.050 / 224.550 / 141.400 / 172.267 / 206.175 / 64.633 s); **15.5846 counted min**
  (6 runs, all counted).
- **Trainable:** 15.5822 min at the 33.3 ms stride.
- **Step table:** 28,325 rows, 28,048 accepted and gap-free.
- **Header:** `split: val`, patch `1.1.3892207/build25501035`, sitting 2026-09-25-afternoon.
- **Import:** 114,301 decoded = referenced frames; 3 unwritten tail packets; no `unknown_composition`.
- **The fit's reader:** `steps.load_cohort` over all eight step tables, with the patch-equivalence file, loads them as
  one cohort. 212646 comes back as `val`, the other seven as `train`. A train fit must still select `splits=("train",)`
  or leave this table out; `load_cohort`'s default is train and val.

## The tally

- **Normal, train (the headline): 94.18 admitted / 94.17 trainable of 180, 7 sessions.** It is unchanged; val adds
  nothing to it.
- **Normal, val: 15.58 admitted / 15.58 trainable,** reported beside the headline (`val_by_regime`).
- **`tally.py`:**
  - `ADMITTED` gains 212646;
  - `ROWS` gains the four 2026-09-25 OBS false starts as `not_range`, so every logged folder has a row;
  - 203745 joins at its admission.

| File | Bytes | sha256 |
|---|---|---|
| `data/human/sessions/tally.json` | | `fd30dee052eb09e82a085575739aae80764af2b89285b2a1f3d0e738e8211c7f` |
| `docs/evidence/corpus-tally.md` | | `aad11f0c71cccd1d384cf63101cb3322a3aa5fb7250a88928548a9dd731bc333` |
| `data/human/sessions/tally.py` | | LF `529327502f5b0a9146d6fc748462e3b2b31fa701af445934a467e5665f91773e` (the working file is CRLF, as it was) |

## Corrections carried forward from the review (not into pinned artifacts)

- **F1, the scoreboard.** All three Tab presses open the scoreboard. In seg-013 it is drawn at 498.505–499.105 s
  (f59807–f59879). My final-21 said seg-013's frames showed "ordinary play with no scoreboard drawn". That was wrong: my
  three samples straddled the display and missed it. No verdict or bound changes.
- **F2, focus.** The three brief focus losses are 354.32–356.62 s (2.30 s), 673.64–674.95 s (1.31 s) and
  883.51–885.40 s (1.89 s). The closing loss is at 950.50 s.
  - **Where I went wrong:** my arrivals-0925 and final-21 gave the third loss as 950.3, and said only one Alt press was
    logged. There are four Alt-down transitions.
  - **The cause:** my press counter kept a key "down" across focus loss. A key released while the game is unfocused
    never logs its up, so later presses were not counted.
  - Re-counted with every key reset at each focus event, I get Alt ×4 (354.22, 673.55, 883.21, 950.29 s). The train
    take's counts are unchanged by the fix (Alt ×1, Tab ×2, G ×1).
- **F3, capture gap.** "No capture gap" holds inside accepted footage. There is a 25 ms step at 952.605–952.630 s,
  after the closing focus loss.
- **The review's notes:**
  - **N1:** validation scope. This is not validation from an independent sitting: the take was named after recording
    and recorded second in the same sitting.
  - **N2:** the saved settings are corroboration, not a measurement.
  - **N3:** the one wheel-up tick at 599.22 s follows a Web Cluster click, with no Simple Swing.

  These go into my lane-doc entry, which I write once 203745 is done.

## Bytes (`data/human/sessions/20260925T212646-322Z-49728-6/`, all LF; the intake files are as in final-21)

| File | Bytes | sha256 |
|---|---|---|
| `20260925T212646-322Z-49728-6.steps.jsonl` | 19,222,046 | `19d75c2a0bd6e84467c56b6ecb3064c0503177e94ca4b72fa7a6c2f579196646` |
| `artifact-hashes.json` | 4,840 | `415b1b8bc95a682ea0acfb1252a68272540063b894243f2b485a10519883e984` |
| `review.json` | 22,441 | `168eaa1fc93cbd5f91879d0d939d694d194b8f7874ff175188665f39b4cddb6d` |
| `settings.json` | 5,086 | `ee4478f171b49d1c9fca99d1893156ddd854e189b69e75920f66ff590bee52c2` |
| `imported-demo.jsonl` | 58,627,616 | `fae920c5d6205862b2e19493edbcc240e6a2e4329388d18a317f40c688fee165` |
| `sampling.json` | 639 | `799100972efa8f5cd3b1c5745c7a8e022fd99eefedb8a40cb52475f0f14f1860` |
| `minutes.json` | 917 | `055461cc937210a31e140f1d2c35ed194bccbf58bf1ab9e00354bf04ec1cf310` |
| `recording-log.fbe6693.md` | 9,727 | `f7ef32b2c9c3b099abd5c5f043cbd77d8d17782cb521be3b813e3bb9a712b4b0` |
| `registry.cbae5149ab17.json` | 10,320 | `cbae5149ab179ebfab7912dbbb6c2a0b5d60f4eb715246ed90f76ed4b0927222` |
| `independent-review.verdicts.json` | 229,134 | `7c47d6afac6c439298ff64ff755877ce2ebfccabef52021bdae84d12e34fb9bf` |
| `independent-review.md` | 16,345 | `fcc7197343571ce0a28916d26513dc6d4e5b4148860df0594496f8e0832d3012` |
| `segments-evidence.json` | 90,572 | `1f7b819485452efedb6892ba2f46dc36419c50510161d2512983f43ed89d2248` |
| `owner-verdicts.json` | 34,765 | `a05aedf83b2536b328f4572684047060c8aeed1305b02f81db76cac6fd822bc2` |
| `motor-settings.json` | 5,870 | `766a635c8024fdd15d0e125f1d6c12491b745a19a5fe1e42a66f1497fc274adf` |
| `provenance.json` | 47,088 | `69143ff2f96e941b7040aef199987141416d92bf3cf4f0fb34dd51dd9cf75601` |
| `recorder-verification.json` | 1,211 | `ceee836eecc1edd58983aa886dd8d431a463c9abef3ec6ab88c5ba535b5ffc2b` |
| `input-profile.json` | 5,971 | `4fe53a8646b94b7f02210351540cdfdf5da826c2341605cd5710ff1af08dce5f` |
| `slot-mapping.json` | 260 | `21d0e0b8539eba0cb5c381c9208b3f66b8f880586be08768eea760e768a83d43` |
| `hud-scan-samples.jsonl` | 3,591,848 | `f05f0d8a5fe1a85970f674cf3abb3fe859edee13780d07a8ee1b9f69599e5bcd` |
| `regime-timeline.json` | 42,113 | `af7c4fd581c172dda834afcf6f42f8f47e1a4b260c363daa8f6b2dd959d6ec3f` |
| `candidates-pass1.json` | 6,611 | `0ecfb24ddaed2bef7ca1de95f1401887fc61be33a5c110f0abe4e20dc36343aa` |

`review-frames/` (136 files) is not pinned by the freeze, as for the admitted sessions; its hashes are in
`segments-evidence.json`.

**Next:** 203745 (train) is in its HUD scan (48 min of video at 5 fps). REVIEW-READY follows once its evidence and
owner verdicts are written. The landing list comes with the final hand-back.

No commits, no Linear, nothing on the Mac.
