# intake-motor-2: M1–M3 and the zone fixed; 025230's and 232304's motor records regenerated deliberately

This answers `review-intake-motor.md`. The identity fix (from final-14) is unchanged. The per-date statements now quote
the committed recording log, and the 2026-09-23 wording is the admitted sessions' exact text.

## The fixes

**M1: the 2026-09-23 wording.**
- `MOTOR_STATEMENTS["2026-09-23"]` now carries the two admitted strings separately:
  - settings: "James's dated statements of 2026-09-23, applied by the lead to every existing session";
  - bindings: "James's dated statements of 2026-09-23 (docs/recording-log.md)".
- A corpus test (`--corpus`) re-derives all four admitted sessions' `settings.json` per-session sources byte-identical
  from their own recording times. **It passes.**

**M2: the 2026-09-24 entry cites the committed line.**
- The entry quotes the `57d1f3d` recording-log line verbatim: "2026-09-24: **DPI, in-game sensitivity and bindings
  unchanged** for the four 2026-09-24 takes (James, chat via the lead, 2026-09-24 ~22:40 CDT, …)".
- Its per-session source text: "James's dated statement for the 2026-09-24 takes (docs/recording-log.md, Motor settings,
  committed 57d1f3d): DPI, in-game sensitivity and bindings unchanged (chat via the lead, 2026-09-24 ~22:40 CDT)".
- The ~22:10 brief is no longer cited anywhere.

**M3: each record quotes its own date's line.**
- Every `MOTOR_STATEMENTS` entry now carries `log_quotes`, the exact recording-log text it rests on.
- `motor_statement(meta, hi, log_text)` refuses when that text is missing from the log. The assembly checks it before
  writing anything, and the log must equal its last commit.
- `step_motor` quotes the recording date's own lines (`statement.date`, `statement.text`, verbatim), not the 09-23 text.
  It still checks that the 09-23 lines exist, because they are where the values come from.
- The bindings record now also cites the log as evidence.

**Minor: the zone.**
- The recording date is taken in America/Chicago by `chicago_date` in `assemble_session.py`, whatever zone the machine
  is set to.
- `zoneinfo` can't do it here: it finds no tz database on this PC (`ZoneInfoNotFoundError` in both Python environments),
  and the stdlib suite takes no `tzdata`. So the US rule since 2007 is written out:
  - CDT from the second Sunday of March 08:00 UTC;
  - to the first Sunday of November 07:00 UTC;
  - CST otherwise.
- Tested at both 2026 transitions, and on your example: 02:30Z on 09-24 reads 09-23.

**The old admitted motor records.** They carry `e55453d6…`, against `a8dea3ba…` in their `settings.json`. That is now
recorded in the lane doc's new 2026-09-25 section. The frozen files are not touched.

## Regenerated on purpose: 025230 and 232304

Both ran the motor step before `57d1f3d`. 232304 has the same M2/M3 defect as 025230, because it ran on the same code
before this fix.
- **How:** a new `--supersedes REASON` flag on the motor step regenerates the record deliberately. It works only with an
  existing record and only for the motor step. The first record is kept as `motor-settings.v1.json` and named, by sha256,
  in the new record's `supersedes`.
- **Why keep `.v1`:** each session's `segments-evidence.json` records the motor input it was built from (`8955d5b8…`,
  `14334d6b…`), which is now that `.v1` file. So the evidence, the owner verdicts and the review frames stay exactly as
  sent for review.
- **Result:** the new records quote the `57d1f3d` line, with identity `a8dea3ba…`.
- **021320:** it hasn't reached its motor step yet, so it will run this fixed code directly.

| File | Bytes | sha256 |
|---|---|---|
| 025230 `motor-settings.json` (new) | 6,143 | `2a6e604e460f8f8ecdc8f3e7ddaf4332652e49b8d4b16a19566fe3eb78ea7099` |
| 025230 `motor-settings.v1.json` (kept) | 5,708 | `8955d5b83fd0e8d4480d9cd3fd5be4498bc67892d789713568cc0a7c6c01e84d` |
| 232304 `motor-settings.json` (new) | 6,146 | `46e82b4f110d514996625c5824dce7105e076863b4763e3e534b1554577201eb` |
| 232304 `motor-settings.v1.json` (kept) | 5,711 | `14334d6bcea838140f58f0710ee7e94559c8c17d1e3d16661700c02ffa63761d` |

## Tests

The intake suite has **59 passed, 1 skipped (the corpus test)**. With `--corpus` that test passes too. The new tests:
- `chicago_date` at 8 cases: both of tonight's takes, your 09-23 evening example, the 05:00Z day boundary, and both 2026
  transitions.
- `motor_statement` on the real `docs/recording-log.md`:
  - 09-23 gives the two admitted strings;
  - 09-24 names `57d1f3d` and ~22:40, not ~22:10;
  - 09-22 and 09-25 are refused;
  - a log whose 09-24 line was altered is refused.
- `step_motor` in a temporary folder:
  - a 09-24 record quotes the 09-24 line, with identity `a8dea3ba…`;
  - a second run without `--supersedes` is refused (write-once);
  - with `--supersedes`, `.v1` is kept and named by sha256;
  - a 09-23 record quotes the 09-23 lines.
- The corpus test described under M1.

Full stdlib suite: **1961 passed, 71 skipped**. The run also covers other lanes' uncommitted work in the tree.

## Bytes

| File | Working tree | LF (the git blob) |
|---|---|---|
| `data/human/sessions/assemble_session.py` | 24,233 `d786de1e…` | 23,880 `1edf130277d2ff17013dc118e60a905389f86a1196187469dbc85a20b94f4461` |
| `data/human/sessions/intake_session.py` | 35,487 `8360e7e8…` | 34,897 `2ad9908ba4c21eac1b74cd7bc876751cbbab483aa55c5a3ccfcfcfc5a2ed371f` |
| `tests/test_human_intake.py` | 55,670 `6e6887f6…` | 54,739 `32228519cf306778c0d4810fe040cfd7c6e1998d7605efb5e7489abcd0730ee9` |
| `docs/lanes/human-admission.md` (appended section) | 83,100 `cfeeae29…` | 82,886 `a0b95952d6f96506623fe1057bb24a5de540a30013b08b483c5b9cb1de2cb0d7` |

Still uncommitted from before: `data/human/session-splits.corpus.json` (the registration, `f36e9e3b…`).

No commits, no Linear, nothing on the Mac. 021320's intake is still running (frame-level verify).
