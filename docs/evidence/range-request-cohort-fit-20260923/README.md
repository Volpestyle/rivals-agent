# Admitted two-session request cohort fit

The admitted `web-cluster-request-v1` cohort trained on Mac MPS and reloaded on Windows CPU. It holds 37 received
Web-Cluster requests and 39 no-new-request controls from two of James's sessions. The model reproduced 74 of 76
training labels. The ammo-positive rule reproduced 36, and never-start reproduced 39. This is a train-only numerical
result on two same-owner sessions, not validation, generalization or learned gameplay. No human-trained model has
controlled the game.

| Check | Observed result |
|---|---|
| Mac and Windows code | `45530720c10274680afe138f06f4b2f8689f77f7` |
| Training | PyTorch 2.14.0, `mps:0`, 9.29 seconds (3,800 optimizer steps), one fit |
| Configuration | GRU hidden 8, five causal observations at 10 Hz, 100 epochs, batch 2, learning rate 0.01, seed 7; confidence threshold 0.7. Unchanged from the 2026-09-22 request fit |
| Full grid | 4,288 coordinates (108 + 4,180): 76 known, 4,212 masked, 37 unique requests |
| Model training confusion | 38/39 no-new, 36/37 start; one extra start |
| Ammo-positive baseline | 1/39 no-new, 35/37 start; 38 extra starts. Two starts have unknown ammo and are unscored |
| Never-start baseline | 39/39 no-new, 0/37 start |
| Confidence ≥ 0.7 | 70/76 scored, all correct (37 no-new, 33 start); six below threshold |
| MPS to Mac CPU | Same predictions; max probability delta 5.960e-7 |
| Mac CPU to Windows CPU | Same predictions and event metrics; max delta 4.172e-7 |
| Independent validation / deployment binding | None |

## Labels, thresholds and sessions

The two argmax errors are both in session 051828 and both have ammo 4:
- **Missed start at grid 51:** `p_start` 0.411; its request id ends `rmb-down:808`.
- **Extra start at control grid 591:** `p_start` 0.642.

The mean anchor-to-received-request lead on matched starts is 0.050 s. That is an offline forecast distance on training
rows, not input latency or reaction time.

**Six rows fall below the 0.7 confidence threshold**, all in 051828. They include both errors:

| Grid | Label | Max probability |
|---|---|---|
| 48 | no-new | 0.690 |
| 51 | start | 0.589 |
| 591 | no-new | 0.642 |
| 764 | start | 0.697 |
| 3835 | start | 0.676 |
| 4032 | start | 0.523 |

The confidence filter gives precision 1.0 and recall 0.892.

| Session (group) | Known | Model | Ammo-positive | Never-start |
|---|---|---|---|---|
| 032454 (`james-2026-09-21-evening`) | 5: [4 no-new, 1 start] | 5/5. 141 start at 0.947; no-new 137 / 144 / 200 / 206 at 0.008 / 0.042 / 0.071 / 0.001 | 1/4 + 1/1, 3 extra starts | 4/4 + 0/1 |
| 051828 (`james-2026-09-23-session`) | 71: [35, 36] | 69/71: controls 34/35, starts 35/36 | controls 0/35, starts 34/36 (2 unscored) | 35/35 + 0/36 |

**Same-ammo contrast groups** (known rows with identical five-step ammo histories and both labels):

| Ammo history | No-new | Start |
|---|---|---|
| `[3,3,3,3,3]` | 032454:137; 051828: 134, 1714, 1788, 1859, 3266 | 032454:141; 051828: 137, 404, 764, 1791, 2349, 3010, 3987 |
| `[4,4,4,4,4]` | 051828: 48, 591, 1655, 1663, 1665, 3255 | 051828: 51, 126, 594, 652, 1047, 1658, 1668, 2730, 3113, 3258, 3401, 3434, 4032 |
| `[4,3,3,3,3]` | 051828: 56, 131, 599, 657, 667, 1867, 3263, 3439, 4037 | 051828: 1092, 2069 |
| `[1,1,1,1,1]` | 051828: 1184, 1514, 3832 | 051828: 1177, 1187, 1517, 3752, 3835 |
| `[5,5,5,5,5]` | 051828:36 (`p_start` 0.026) | 051828:39 (0.925) |
| `[0,0,1,1,1]` | 032454:206 | 051828:3730 |

- Inside these groups the model labels every row correctly except 051828:51 and 051828:591, so its output is not
  ammo alone.
- Both errors fall in the largest mixed group, `[4,4,4,4,4]`.
- The only full-ammo support is the Luna pair 36/39.

## Inputs and admission

The manifest is `data/human/skill-event-candidates/james-request-cohort-ae648b33/cohort-manifest.json`, SHA-256
`bcaa1cf46eb0a86fc587c0cb3d66a8be682d5915a14da3ca36165aec20fb8794`, status `admitted`. It was checked against the
hash the lead handed over before anything read it.

| Member | Examples artifact | Rows / known / [no-new, start] | Evidence digest | Receipt |
|---|---|---|---|---|
| 032454: accepted labels re-measured under `ae648b33` | `032454-request-diagnostic-v1-ae648b33/examples.json` `c1a39ea72bc0f835…` | 108 / 5 / [4, 1] | `e66b6fec…` | 2026-09-22 decision `52423a3c…` |
| 051828: v5 admitted 2026-09-23 | `james-request-cohort-ae648b33/051828-v5-admitted-examples.json` `ffec16330a22211…` | 4,180 / 71 / [35, 36] | `a6f8d629…` | `admission-decision.json` `6d9fbe2d…` |

- **Joint evidence digest:** `86e5894b12d9a6bf665524aad89ef29589b63dd05f070bd67052c6659d2a96c9`.
- **Hashes checked:** the driver hash-checked 27 inputs; the Mac report's `input_artifacts` lists each with its
  SHA-256. They include:
  - v5's admitted `candidate-rows.json` `bc605bf9…` and `coverage.json` `c6e701b4…`;
  - the 032454 re-measurement report `37c813f3…`;
  - the shared source profile `c5528cf7…`;
  - the `ae648b33` code-snapshot manifest `11f2e88d…`.
- **Admission was read from the frozen artifacts,** not only the manifest:
  - each packet's own status, its hash-pinned receipt, and the receipt's binding to the packet and session;
  - for v5, row-for-row equality with the lead-admitted rows and coverage;
  - for 032454, row-for-row equality with the accepted original on everything except re-measured features.
- **Code:** the seven modules the policy import runs equal the pinned `ae648b33` snapshot's git blobs.
- **Rules:** see [fit readiness](../fit-readiness-20260923/README.md).

The shared `SourceIdentity`:

| Field | Value |
|---|---|
| Patch | `1.1.3870120/build25364676` |
| Regime | `normal` |
| Source profile | `c5528cf7…` |
| Perception | `a30b3cae3024641a1a235a99f6297114ec7cbc5d79398a3712e8fe06d8854e2c` |
| Selector | `00fd672e388faa0743bec098fc4bb0b6d8dfd35425fe7517bdfd67b846d4ed5f` |
| Revisions | `web-cluster-request-v1`, `masked-state-grid-causal-v1` |

**Identity check.** At `4553072`, those perception and selector digests are reproduced from the CRLF byte form of
the files (`source_identity_matches: ["crlf"]`). The LF form gives `75912d7f…` / `9e024bc1…`. A runtime binding must
use the CRLF recipe or re-issue the identities.

## Driver and the F8 decision

| Driver | SHA-256 |
|---|---|
| At launch | `f9f158fcc9abaa8fefe09d48c3fde2a85d80fa6573f69b4df777a82e30a7b653` |
| After F8 | `80c118d5c30cd05e6d16321f4c3fa2fad6aff099fc7e6b22397e442d9d5eb917` |

- **At launch.** The Mac report records `f9f158fc…`. Its exact bytes are kept beside the run on both machines, at
  `data/diagnostics/range-request-cohort-fit-20260923/fit_cohort_20260923.py`.
- **After F8.** [`fit_cohort_20260923.py`](../range-request-human-fit-20260922/fit_cohort_20260923.py) now hashes
  `80c118d5…`. F8 changed only the re-measured branch of `admission()`. The training path is unchanged.
- **Verifier.** [`verify_windows_cohort_20260923.py`](../range-request-human-fit-20260922/verify_windows_cohort_20260923.py),
  `f01efa194f7de3cd…`. It is also copied into the run directory next to the launch driver, because it requires the
  driver beside it to be the bytes the Mac ran.

**Review history:**
- The [independent driver review](../fit-readiness-20260923/driver-review.md) approved with required fixes F1-F4,
  then F7.
- Its second delta check required F8: bind the re-measured 032454 histories to the pinned
  `remeasure/ae648b3/report.json`.

**Lead decision, 2026-09-23.** This fit ran without F8, because the reviewer had independently verified that the real
packet's histories equal that pinned report. F8 is required before any later fit. After the fit:
- F8 was implemented;
- the `80c118d5…` driver's `--check` passes on this same manifest, with output byte-identical to the launch driver's;
- so the 032454 histories this fit trained on equal the pinned re-measurement report.

## Exact artifacts and reproduction

Checkpoint on both machines: `data/diagnostics/range-request-cohort-fit-20260923/run-1/model.pt`

SHA-256: `698d8831a6740d1d060ed3691dc2102fc1a39987ad4c7a03ad4c96a49df9ce1b`.

[Mac report](mac-report.json) SHA-256: `d67507a00a1f302311f55d63fa7e36e344d26856ae0b23c19d235ce228a8bc61`.
[Windows report](windows-report.json) SHA-256: `b38defa3c42c59cd5bc261dabdd14e8bfab1486deface43885e58a85037752b8`.
Both are exact copies of the run's reports.

**Code checks in the Windows report:**
- `range_skill_policy.py` (`d6b62274…`) and `range_policy.py` (`c46e7d8a…`) are byte-identical to the Mac commit's
  blobs.
- `agent/state.py` differs only by CRLF checkout conversion.

The run followed the "Next fit" sequence in [fit readiness](../fit-readiness-20260923/README.md) verbatim:
- `$MS` was the manifest hash above, with no `--dry-run`;
- one `nohup nice -n 10` job on the Mac, `run-1` created exclusively, exit status 0;
- all 28 transferred hashes matched on the Mac before the fit.

```text
# Mac, human-execution worktree at 4553072; niced durable job
uv run --offline --locked --group execution python -B data/diagnostics/range-request-cohort-fit-20260923/fit_cohort_20260923.py \
    --manifest data/human/skill-event-candidates/james-request-cohort-ae648b33/cohort-manifest.json \
    --manifest-sha256 bcaa1cf46eb0a86fc587c0cb3d66a8be682d5915a14da3ca36165aec20fb8794 \
    --out data/diagnostics/range-request-cohort-fit-20260923/run-1
# Windows, shared checkout with LF policy files; torch pinned to the Mac's version
uv run --offline --no-project --with torch==2.14.0 python -B docs/evidence/range-request-human-fit-20260922/verify_windows_cohort_20260923.py \
    --run data/diagnostics/range-request-cohort-fit-20260923/run-1 \
    --mac-report-sha256 d67507a00a1f302311f55d63fa7e36e344d26856ae0b23c19d235ce228a8bc61
```

**Reproducing now:**
- Use the launch driver and the verifier kept in the run directory.
- The docs verifier sits beside the F8 driver and refuses this report by design.
- The fit and the verifier both write exclusively, so run them on a separate checkout or on a copy of `run-1`.

## Limits

- **Train only.** There is no validation split and no held-out session. The sealed 053616 validation take is
  excluded and was never opened.
- **Small support.** 37 unique events across two sessions from one player, in groups `james-2026-09-21-evening` and
  `james-2026-09-23-session`. Only 76 of 4,288 coordinates are known; unknowns stay masked.
- **Full ammo:** one Luna pair (051828:36 no-new, 051828:39 start).
- **Recipients.** In 051828 they are mostly the designated Galacta: 32 starts / 29 controls, Galacta bot ultra 2 / 2,
  Luna Snow 2 / 4. The one 032454 start is Luna, a named visual source, not a Galacta benchmark substitute.
- **Request timing.** Labels are received RMB points associated with reviewed casts, not physical press or delivery
  timestamps. Motor settings and pad equivalence are unknown.
- **Selector.** Histories come from the window-reset selector. That is not proven equivalent to continuous live
  selection.
- **Report limits are member-specific.** The Mac report's `limits` array carries the 032454 packet's own
  limitations verbatim, which describe that member alone ("One target-agreed received request, four … controls",
  "`james-2026-09-21-evening` TRAIN only"). The v5 packet declares none. This section states the joint limits.
- **No live authority.** No deployment binding exists; see "What the binding needs" in fit readiness. Returning the
  weights to Windows does not authorize live use.
