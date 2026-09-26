# admission-owner final 25: the late take (22:59, main account) is held; its record

**Session:** `20260926T035932-508Z-63684-14` (`2026-09-25 22-59-32.mkv`, 30.8 min).
- Registered train at 23:32:36 CDT, before inspection.
- **Held** under the lead's option B (2026-09-26): the pre-registered relative per-pair gain check is not consistent.
- The footage is kept. Revisit with a main-account calibration take.

## The checks, as they stand

| Condition (option B) | Result | Evidence |
|---|---|---|
| (1) effective bindings equal for every pressed key | **pass**: no semantic difference; LeftShift default-dependent | `arrivals-0925/late/bindings_equivalence.py` (`6fc8b2fd…`) → `bindings-equivalence.json` (`9f2adb9b…`) |
| (2) Shift web-swings, Caps Lock simple-swings (frames) | not run | stopped at the hold |
| (3) regime normal across accepted spans | not run | the intake stopped at `vote` |
| (4) yaw gain: main-account calibration (none recorded), then the relative per-pair check at about 1 % | **fail** | see below |
| (5) cut up to the second Esc + 2 s | done: 0–7.438 s | `settings-change.json` (`6f671e74…`) |

## The per-pair check

The check was pre-registered, and its windows were fixed before any decode:
- `perpair.py` (`f633e58e…`);
- `perpair-windows.json` (`42b33712…`): 60 one-second steady-yaw windows per take, from 258 qualifying in the late take
  and 407 in 203745.

It compares the late take against 203745 (campaign account, same day, same range), with the snapshot per-pair
estimator on both. The rule: consistent only if the 95 % bootstrap interval of R (late ratio over reference ratio)
contains 1 with half-width ≤ 2 %.

- **The first output was invalid.** `perpair-result.json` (`dee7cc13…`) has R 1.906, with an interval of −11.5 to 11.9.
  - The script summed signed yaw over signed counts across windows. Left and right turns cancel: the late take's signed
    dx sum is −16,805 against an absolute sum of 199,595.
- **The correction:** `perpair_signfix.py` (`adc0e826…`) computes the intended sign-normalized ratio per window,
  Σ(yaw·sign dx)/Σ|dx|.
  - It uses the same saved per-window measurements and does not re-decode.
  - The windows, the bootstrap (2,000 resamples, seed 7) and the rule are unchanged.
  - Result: `perpair-result-signfix.json` (`dc7e3c5b…`).
- **Result:**
  - late ratio 0.02789 deg/count; reference 0.02980;
  - **R = 0.936**, 95 % interval **0.841–1.041**, half-width **10.0 %**;
  - the interval contains 1 but is five times too wide, so **not consistent**.
  - The per-window medians (0.02946 against 0.03171) point the same way, about 7 % lower.
- **Interpretation (inference).** The estimate points to a gain about 6 % lower on the main account. That is roughly the
  gap a sensitivity near 1.77 would give, or the acceleration-off profile. The interval cannot exclude equal gains.
  - 60 windows are about 25 times too few for ±2 %, and the take has only 258 qualifying windows.
  - A still-to-still calibration take on the main account (the 030045 protocol) would settle it.

## Other findings

- **Main account's saved Spider-Man profile** (folder `1859995554`, written 23:35, after the take): sensitivity 1.89/1.89,
  mouse acceleration off, 29 differences from the 09-22 receipt.
- **The campaign account's file** (`1295996384`), which the intake reads: still equal to the receipt.
- **Motor statement:** `MOTOR_STATEMENTS["2026-09-25"]["sessions"]` holds this take's own entry, quoting `83c05f1`,
  with option B's conditions written in. It is kept for a later revisit and used by nothing now.

## Bytes (`data/human/sessions/20260926T035932-508Z-63684-14/`, all LF; steps provenance to vote only)

| File | Bytes | sha256 |
|---|---|---|
| `settings-change.json` | 925 | `6f671e74b4c6274a07406188926078c4d7aa8920414ac5f2257b2dafc7c376cf` |
| `provenance.json` | 47,291 | `e816be1da9838e921db7f02547393633785ab6d2b99ad501ef6d9ac1733d00e6` |
| `recorder-verification.json` | 1,216 | `69cb642ffc89bec337fa5c9cda894eea24b1611db3a0940f9d907a1cfb989bed` |
| `input-profile.json` | 6,031 | `6f21995fc425865df5ae35fde2bf4cce703cd8ee4cd4a976c18fa77c62aa5690` |
| `slot-mapping.json` | 261 | `4f7123888abe7835a07e7f02b50160d1e4fbba42d3cb2e17c3fbbab4c24789ac` |

- **Snapshots:** provenance and verify ran from `code-snapshot-83c05f1`; profile and vote from `code-snapshot-3936f94`.
  The two differ only in the importer's sealed-split list and its tests. The first runner stopped at the `gate2`
  registry change, as expected.
- **The recorder check is clean:** `integrity_ok`, all decoded frames matched.
- **Not landed with the first landing:** these partial folder files, like the step tables, stay out until the take is
  revisited. Your call.

No commits, no Linear, nothing on the Mac.
