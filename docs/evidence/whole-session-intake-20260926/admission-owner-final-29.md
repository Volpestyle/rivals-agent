# admission-owner final 29: the late take admitted (train, 30.15 min); train 180.57 of 180; the second landing list; the seven-session sweep

## The late take admitted

`20260926T035932-508Z-63684-14` (`2026-09-25 22-59-32.mkv`, James's main account) was assembled on 2026-09-26 at
05:48, as train, from **`code-snapshot-6bbb276`** (manifest `33b4c6f8…`). That snapshot is the landed intake code, as
committed blobs with no overlay.
- **Independent record:** `88afc54b…` (review-session-035932.md `78b22e91…`), which matches all 35 owner verdicts and
  bounds.
- **Freeze:** `check_freeze` is clean; 25 folder files, 9 external.
- **Accepted:** 8 segments (483.667 / 646.008 / 55.033 / 8.375 / 3.708 / 233.242 / 155.883 / 223.217 s); **30.1522
  counted min** (8 runs).
- **Trainable:** 30.1500 min.
- **Step table:** 55,017 rows, 54,270 accepted and gap-free.
- **Import:** 221,760 frames; 2 unwritten tail packets.
- **Header:** settings identity `a8dea3ba…`, the lead-authorized equivalent profile (review N2). The per-session motor
  text states the equivalence; see F2.

**The review's fix-forwards.**
- **F2 (done before assembly):** `MOTOR_STATEMENTS["2026-09-25"]["sessions"]` for this session now states, for each
  speed, the measured gain against 0.0330738: slow (1,702 counts/s) +0.159 %, medium (2,862) −0.023 %, fast (5,284)
  +0.057 %, mean +0.064 %.
  - It says the slow turn **did not meet** the scripted ±0.08 % check (`within` false, `all_within` false).
  - It says "equal" is **the lead's decision of 2026-09-26** under 030045's ±0.25 % slow-class tolerance, which all three
    speeds meet.
  - It says the main account has acceleration off.

  The motor record was regenerated with `--supersedes`:
  - `motor-settings.json` is now `9e6d2682…`;
  - `motor-settings.v1.json` is `4d2bc5e6…`, named in `supersedes` and pinned by the freeze;
  - `segments-evidence.json` (`b753ac38…`, the reviewed evidence) still points at the `.v1` record it was built from.
    That is the 025230/232304 precedent: no re-emission and no re-decode.

  The assembled `settings.json` carries the new text.
- **F1 (narrative):** my final-25 said the take had no duplicated composition time. There is **one equal adjacent pair**,
  f221161/f221162 at 1,843.102 s, after the final focus loss (1,843.090 s) and the last accepted endpoint (1,843.010 s).
  There is no reversal, and the bounds and minutes are unaffected. It is corrected in the lane doc.

## The tally: **180.57 counted minutes**

- **Normal, train: 180.5690 admitted** (180.5578 trainable), **10 sessions**; 0 of 180 to go.
- **Normal, val:** 15.5846 (212646), beside the headline.
- **The fit's reader** loads **11 step tables** as one cohort: 10 train, 1 val.

## The seven-session sweep (report only): clean

This is the 1 fps native banner sweep for TIMED PRACTICE (`…/arrivals-0925/sweep/banner_sweep.py` `89afa2dd…`), run
at below-normal priority, two at a time, about 131 MB per ffmpeg; no game or OBS ran.

| Session | Frames | PRACTICE RANGE | TIMED | Neither | Max TIMED score | TIMED in accepted | Result sha256 |
|---|---|---|---|---|---|---|---|
| 051828 | 422 | 421 | 0 | 1 | 0.4619 | 0 | `7c8c2263…` |
| 171533 | 170 | 162 | 0 | 8 | 0.4596 | 0 | `8e49fe52…` |
| 200129 | 1,610 | 1,604 | 0 | 6 | 0.4669 | 0 | `a845f81b…` |
| 205528 | 667 | 667 | 0 | 0 | 0.4648 | 0 | `e8adfc5a…` |
| 232304 | 531 | 528 | 0 | 3 | 0.4675 | 0 | `baf2eea4…` |
| 021320 | 2,195 | 2,187 | 0 | 8 | 0.4631 | 0 | `34ca73ac…` |
| 025230 | 225 | 224 | 0 | 1 | 0.4644 | 0 | `94792764…` |

- **No Timed Practice round** in any earlier session.
- **With final-28's addendum,** every admitted session is swept: none has a TIMED PRACTICE frame in accepted footage.
- **The only rounds** are 203745's and the late take's, both cut.

## Second landing list

**Session folder** `data/human/sessions/20260926T035932-508Z-63684-14/`, the standard file set:
- `artifact-hashes.json`, `candidates-pass1.json`, `independent-review.md`, `independent-review.verdicts.json`;
- `input-profile.json`, `minutes.json`, `motor-settings.json`, `owner-verdicts.json`, `provenance.json`;
- `recorder-verification.json`, `recording-log.6bbb276.md`, `regime-timeline.json`, `registry.26d55f3d1bba.json`;
- `review.json`, `sampling.json`, `segments-evidence.json`, `settings.json`, `slot-mapping.json`;
- plus `settings-change.json`, `timed-practice.json`, `motor-settings.v1.json`, `candidates-pass1.v1.json` and
  `segments-evidence.v1.json`.

The step table, import, HUD samples and both review-frame folders stay out, pinned by the freeze.

| File | Bytes | sha256 |
|---|---|---|
| `20260926T035932-508Z-63684-14.steps.jsonl` (out; pinned) | 37,404,523 | `1a98150a122f316b9bd975e82ef8453d714466454a25a2d186c341b8baf2bdc2` |
| `artifact-hashes.json` | 5,601 | `2184320220d387095a6237209d80167d93a50339589ed9fe946f7c7f0a4b8f2d` |
| `settings.json` | 5,915 | `0f274c8d7b83ee0b7d8596eb133759129591ca41497f50b17ae46f16cf2b2d31` |
| `review.json` | 25,919 | `62c83412db0137a661ea80bad4bd7f38fcc6a5db307dfd18523a1b6f9010e7e2` |
| `sampling.json` | 641 | `db5959b9089d10ae9ca2d45bbd3474ef4837c72a17265d034f98fc578fcaee81` |
| `minutes.json` | 1,008 | `c22af277af5c81a98be0ee977aca5ec87d06a94aeb5c94e3116c2b3acfadcf33` |
| `motor-settings.json` | 7,563 | `9e6d26825c3eefe7c26ff67f4c6d9d84182c0e9413a770abd6d7661621381e34` |
| `motor-settings.v1.json` | 6,785 | `4d2bc5e6ade520de4c9838143c00beb2d945465dd843348ca8ce2af9f1fdbeae` |
| `independent-review.verdicts.json` | 624,000 | `88afc54b6534bf3a37d3ad570c42acd6616f083aac388b276878e2ca9b05a03e` |
| `independent-review.md` | 22,570 | `78b22e91b932116bd2f79e3419f560d217b7a5c88aa08386087197f86b9f69b7` |
| `recording-log.6bbb276.md` | 13,206 | `dbf4c3236f3e62f668e055d29f921429930ed4c17c101d825f2ab7fa4ba9b26a` |
| `registry.26d55f3d1bba.json` | 20,304 | `26d55f3d1bba686eaea1af82e5e02fa6fc6b93ef57737c5c9fff168a24d8da71` |
| intake files | | as in final-25 (updated) |

**The main-account calibration folder** `data/human/calibration/20260926T060921-977Z-60612-1/` (never a split):
- `calibration.json` `df5107c1…`;
- `turncal.json` `4ab87a55…`, `turncal.py` `a3dbf412…`, `plan.json` `cb98f350…`;
- `reproduction-030045.turncal.json` `6d91a908…` and `reproduction-030045.plan.json` `78b04b97…`.

The media hash `becf4c8c…` is in its registry row.

**Snapshots:**

| Snapshot | `manifest.json` sha256 | Role |
|---|---|---|
| `code-snapshot-83c05f1` | `070a2882…` | the late take's provenance and verify |
| `code-snapshot-6bbb276` | `33b4c6f8…` | the late take's assembly |

The late take's other steps ran from `3936f94` and `3936f94-4c9638d1`, both landed.

**Code, data and docs:**

| File | LF sha256 | Change |
|---|---|---|
| `data/human/sessions/assemble_session.py` (LF) | `f96bd7492b3956bf936652fa4d2731567c28c2d53c78b2f48280ace8ab8635a7` | only the late take's `MOTOR_STATEMENTS` entry (the F2 text), since `6bbb276` |
| `data/human/sessions/tally.py` (CRLF) | `c5926668542ce3c7d53e538dcec0adbdb8c674a2d45ccc2be5c28eb532b12a98` | the late take moved to `ADMITTED` |
| `data/human/session-splits.corpus.json` | `d5f0f7d7f6ffb9b8aa94adae56a5ae9adf01619174902a1691741ad9ae5a57a9` | the late take's `note` only (admitted, with the basis). The freeze pins the landed revision `26d55f3d` that it was assembled against |
| `data/human/sessions/tally.json` | `7e9b86697a352ac686ddff3d48351e70708ce2bb554d6784929fd79c26983363` | regenerated from that registry |
| `docs/evidence/corpus-tally.md` | `b1e8e275eadc520f0f666b34cf09c6491601773895b90fa248c558e91d901e25` | regenerated |
| `docs/lanes/human-admission.md` (CRLF) | `c460a82010a2c313e65dd23c0ff7cf8d180d178307273bd9cb427107b7e55012` | the late take admitted, F1/F2, the sweep |

- **Tests:** `tests/test_human_intake.py`, 66 passed, 2 skipped, with the new statement text.

**Review and evidence** to add to `docs/evidence/whole-session-intake-20260926/`:
- `review-session-035932.md` (`78b22e91…`) and `.verdicts.json` (`88afc54b…`), with its work folder if any;
- my `admission-owner-final-25.md` (updated), `admission-owner-final-25.held.md` and this `final-29`;
- `arrivals-0925/late/`: `bindings_equivalence.py` and `.json`, `presscheck/`, `perpair*` (the superseded estimate);
- `arrivals-0925/sweep/`: the script and all ten results.

**Not mine:** `docs/lanes/inverse-dynamics.md`, `docs/lanes/idm-gate2-anchors*.md`, the `perception/` gate-2 readers and
their tests and fixtures.

No commits, no Linear, nothing on the Mac.
