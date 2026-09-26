# arrivals-0925: registration and inventory of the 2026-09-25 afternoon takes (admission-owner, step 1)

**Summary**

- **Registered, val first.** `20260925T212646-322Z-49728-6` went to split **`val`** at **16:47:16 CDT**, before anything
  about it was read beyond its file name, size and session id. The train take `20260925T203745-207Z-49728-2` was
  registered after it. The rows got their media hashes and focused minutes once the inventory had them.
  - Registry `data/human/session-splits.corpus.json`: `f36e9e3b…` → **`cbae5149ab179ebfab7912dbbb6c2a0b5d60f4eb715246ed90f76ed4b0927222`**
    (10,320 B, LF, same `indent=1` form). `check_registry` passes with the sealed denylist, and the importer's
    `read_splits` holds: 12 rows.
  - The val row's `split_basis` gives James's words verbatim ("the 15 min validation take"). It also says the take was
    named after recording and was recorded after the 48-min take in the same sitting, not at a sitting's start as the
    protocol asks. It says the split is James's decision, made before anyone inspected the take. Its minutes are
    reported beside train and it never enters train.
  - **The clock is off from the brief.** The val file was last written at 16:42:39 CDT and I registered it at 16:47:16
    by the PC clock. The brief puts James's message at ~16:50 and the brief itself at 16:55. So the 16:50 is either
    approximate or not PC time. The row gives both.
- **Both takes are complete and clean:** clean stop, 0 queue drops, 0 raw-input errors, contiguous packet indices, and
  no composition gap except one tail step. The **+21 ms anchor holds** on both, read from the first 16 packet headers.
- **Build `1.1.3892207/build25501035`,** from `recorded_build` over the Steam evidence. It is the same build as the
  2026-09-24 takes and falls **inside the pinned equivalence** ("Season 10, Version 20260911"). Steam logged no update
  after 2026-09-24 06:15. The game ran from 14:50:12 to 16:44:39 CDT.
- **The saved controls equal the 09-22 receipt** (hero 0 and 1036), and `NoCDSaved` is 0. The file was rewritten at
  16:43:51 CDT, after the val take, so this is later local state, not a recording-time attestation.
- **The four short sessions are false starts.** Each has a logger folder and an OBS start/stop of 4–15 s. James sent all
  four videos to the Recycle Bin. None is registered.
- **Intake has started** on both takes: provenance, verify, profile, vote, scan, regime and propose, from
  `code-snapshot-b7d4592`. Motor and evidence wait for the 2026-09-25 motor statement (step 2).

## The takes

| Video (`Videos/`) | Logger session | Split | Duration (frames.csv) | Focused | Packets | Bytes | Original sha256 |
|---|---|---|---|---|---|---|---|
| `2026-09-25 16-26-46.mkv` | `20260925T212646-322Z-49728-6` | **val** | 952.550 s (15.88 min) | 944.6 s (15.74 min) | 114,304 | 13,713,417,259 | `02e6375bc861154ef0999a94e000ec180e15644ebfaf955d9641e17a7b10bb28` |
| `2026-09-25 15-37-45.mkv` | `20260925T203745-207Z-49728-2` | train | 2,879.358 s (47.99 min) | 2,862.4 s (47.71 min) | 345,523 | 42,276,178,384 | `666c626d4c285e20b3444081b9a1813d743aec8ab6cb538f134c5b61a265125c` |

Duration runs from the first to the last composition time, plus one frame period (8.3333 ms, 120 fps). The provenance
step re-hashed the val original independently and got the same value.

**Logger files (sha256, bytes):**

| Session | `inputs.jsonl` | `frames.csv` | `metadata.json` |
|---|---|---|---|
| 212646 (val) | `7e310977…` 21,405,860 | `4f2c13dc…` 14,581,312 | `b841172e…` 1,123 |
| 203745 (train) | `c2beba39…` 65,501,434 | `5620adc3…` 44,870,296 | `7c82ed27…` 1,124 |

The full hashes are in `inventory.json` (path at the end).

**Logger completeness** (`check_session.check` without video, plus `frames.csv`):
- Both takes: `complete`, `clean_stop`, `integrity_ok`, 0 queue drops, 0 raw-input errors, 0 frames without a composition
  time, and `writer_failed` false.
- Packet indices are contiguous. The only composition step above 1.5 periods is val's 25 ms tail step at 952.5 s; train
  has none.
- **Anchor:** video `[21, 46, 29, 38, 71, 54, 63, 96, 79, 88, 121]` ms, audio `[0, 21, 42, 64, 85]` ms on both, equal to the
  forward prediction. 205528 was re-read as a control and matched.
- **Recorder frame-level verification** (`--verify-video`) is the intake's verify step, now running.

**Encoder and OBS:** one OBS process, 49728, with log `2026-09-25 15-08-33.txt` (sha256 `473c763d…`). It wrote the
train take at lines 260–285 and val at 374–399. The encoder is NVENC HEVC 2560×1440 at 120 fps with a 2.083 s keyframe
interval, as before. OBS 32.0.1, logger 1.0.0.

**Settings:**
- **Recorded by the logger:** nothing. `dpi`, `game_sensitivity`, `hero`, `game_patch` and `bindings` are null, as for
  every earlier take.
- **The saved settings file** `MarvelUserSetting.json` (sha256 `f564f1dd…`): the hero 0 and 1036 controls equal the 09-22
  receipt and 205528's receipt, with no differences.
- **The bindings identity** the step file will carry is `a8dea3ba…`, from `assemble_session`'s `MOTOR`/`BINDINGS`. That is
  code, not a recording fact, and it waits on the motor statement.
- **Devices:** each take has one keyboard and one mouse, 0 injected control packets, and only zero-effect handle-0
  packets (19 val, 58 train).
  - **The keyboard's handle changed**: `661785265` today, against `1043402031` on 2026-09-24. The mouse handle, `614403941`,
    is unchanged.
  - A raw-input handle is reassigned on reconnect or reboot, so this is not a second device. The device-scope check
    passes.

## Content from metadata and input logs only (no frame has been opened)

Presses count up→down transitions, not raw key-down packets (which include auto-repeat).

- **212646, val** (15.9 min, 16:26)
  - **Focus:** four focused intervals, 0.41–354.32, 356.62–673.64, 674.95–883.51 and 885.40–950.50 s. Focus is lost three
    times, for 2.3, 1.3 and 1.9 s. Only one Alt press is logged, so what took focus away is not visible in the input log.
    The intake's focus cuts take these spans out.
  - **Presses:**

    | Key | Presses |
    |---|---|
    | Space | 670 |
    | A | 386 |
    | D | 290 |
    | W | 274 |
    | S | 204 |
    | Shift | 201 |
    | E | 130 |
    | C | 75 |
    | F | 63 |
    | Tab | 3 |
    | Q | 3 |
    | Ctrl | 2 |
    | Alt | 1 |

  - **Mouse button downs:** 2 ×435, 1 ×156, 4 ×21, 5 ×2.
  - **Tab ×3** (127.3 s, 498.3 s and 881.4 s, held 0.4–1.0 s). The third comes 2 s before the third focus loss. Tab is a UI
    key to the intake, so each press gets a UI-key cut with the 2 s settle. **The earlier admitted takes have no Tab.**
  - No AFK span, no Esc, Enter, B, H or F1, and no Caps Lock.
- **203745, train** (48.0 min, 15:37)
  - **Focus:** one interval, 13.88–2,876.32 s. The first 13.9 s are unfocused.
  - **Presses:**

    | Key | Presses |
    |---|---|
    | Space | 2,055 |
    | A | 1,282 |
    | D | 925 |
    | W | 890 |
    | Shift | 595 |
    | S | 589 |
    | E | 349 |
    | C | 167 |
    | F | 146 |
    | Q | 10 |
    | Caps Lock | 6 |
    | Tab | 2 |
    | G | 1 |
    | Alt | 1 |

  - **Mouse button downs:** 2 ×1,210, 1 ×563, 4 ×76, 5 ×16.
  - **Tab ×2** (2,092.9 s, held 0.66 s; 2,873.9 s, held 1.68 s, just before the closing Alt). Both are UI-key cuts.
  - **G ×1** at 2,245.7 s, held 0.14 s. G is neither in `BINDINGS` nor a UI key, so the step table carries no action for
    it. It is noted here for the review.
  - No AFK span of 20 s or more, which is unlike 021320.
- **Neither take has a mouse-only turn run,** so neither contains a calibration window.

## The four sessions without a video

| Logger session | OBS file (in the Recycle Bin) | Recording | Focused | Content hint (inputs) |
|---|---|---|---|---|
| `20260925T200851-935Z-49728-1` | `2026-09-25 15-08-51.mkv` | 15:08:51, 7.7 s | 0 s | no input at all: OBS started with the game out of focus |
| `20260925T212548-665Z-49728-3` | `2026-09-25 16-25-48.mkv` | 16:25:48, 10.1 s | 7.7 s | 51 key and 786 mouse events; ends with Alt |
| `20260925T212615-212Z-49728-4` | `2026-09-25 16-26-15.mkv` | 16:26:15, 6.6 s | 4.2 s | 28 key and 327 mouse events; ends with Alt |
| `20260925T212626-543Z-49728-5` | `2026-09-25 16-26-26.mkv` | 16:26:26, 14.9 s | 11.6 s | 63 key and 985 mouse events; two Alt presses |

- **All four are logger-complete and clean.** The first three stop 3–20 s before the next recording starts (the last
  stops 5 s before val).
- **They are false starts** before the train take and the val take. James deleted each video within a minute, and they
  are in the Recycle Bin, not in `Videos`.
- Not registered, not restored. Their logger hashes are in `inventory.json`.

## Ledger rows (the recording log's column format; for you to append with the motor line)

```
| 2026-09-25 15-37-45.mkv | 20260925T203745-207Z-49728-2 | 48.0 min | range, whole-session training take (James: "a 40 ish minute take", ordinary range play; input log: 2,862 s focused in one interval, Tab ×2, no AFK span) | not yet read (HUD scan running); saved NoCDSaved 0 | logger complete, clean stop, 0 drops, 0 raw-input errors; anchor holds (+21 ms); game build 1.1.3892207 (kit-equivalent); registered train 2026-09-25 (after the val take); intake running |
| 2026-09-25 16-26-46.mkv | 20260925T212646-322Z-49728-6 | 15.9 min | range, **validation** take (James: "the 15 min validation take", named after recording, in chat; recorded after the 48-min take in the same sitting, not at a sitting's start; input log: 944.6 s focused in four intervals, Tab ×3) | not yet read (HUD scan running); saved NoCDSaved 0 | logger complete, clean stop, 0 drops, 0 raw-input errors; anchor holds (+21 ms); game build 1.1.3892207 (kit-equivalent); **registered val** 2026-09-25 16:47 CDT before any inspection; minutes reported beside train, never added; intake running |
```

The four false starts need no rows, unless you want the ledger to list every logger folder. If so, a single line will
do: "15:08, 16:25, 16:26, 16:26: four OBS false starts of 7–15 s, videos deleted by James, not sessions".

## For you

1. **Motor statement (step 2): done.** `assemble_session.MOTOR_STATEMENTS["2026-09-25"]` quotes the `73ecce3` line
   verbatim and cites `73ecce3`. `motor_statement` resolves both takes to 2026-09-25 against the committed log.
   - One test assumed 2026-09-25 had no statement:
     `test_motor_statements_quote_the_committed_log_and_keep_the_admitted_wording`. Its refusal case now uses
     2026-09-26, and it now also asserts the 09-25 quote.
   - `tests/test_human_intake.py` and `tests/test_human_demos.py`: **154 passed, 3 skipped**.
   - Uncommitted in the tree: the registry, `data/human/sessions/assemble_session.py` and `tests/test_human_intake.py`.
   - **Clock:** the PC read 16:52 CDT when your message citing James at "~17:05 CDT" arrived. Your times run about
     15 min ahead of the PC's (file mtimes and logger UTC agree with the PC). The log line's "~17:05" is yours, and I
     left it.
2. **Tab.** Both takes have Tab presses; no earlier admitted take does. The UI-key rule cuts each one with a 2 s settle.
   That costs a few seconds each, not a content problem, unless James has Tab bound to something in play. I leave the
   rule as it is.
3. **Val's three focus losses** (1.3–2.3 s, only one Alt press) are cut by the focus rule. That is not a decision, just
   something to know before the review.

## Artefacts (my scratchpad, `…/51f6344f-…/scratchpad/arrivals-0925/`)

| File | sha256 |
|---|---|
| `inventory.py` (decode-free; adapted from arrivals-0924, with the build via `recorded_build` and the 09-22 receipt) | in folder |
| `inventory.json` (six sessions, common Steam/settings facts, the 205528 control) | `b2155408b9724ceff60bd3eb7a8244e42b52784a85511f4b99453e32b9a72084` |
| `inventory.log` | in folder |
| `run_intake.sh`, `intake-212646.log`, `intake-203745.log` | running |

Constraints kept: no commits, no Linear, no game input, nothing on the Mac. The only repo write is the registry.
