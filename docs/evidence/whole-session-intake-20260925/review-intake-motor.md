# Review: the intake motor-step fix (admission-owner final 14)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-25. The review is read-only: `step_motor` ran only into scratch
copies, and nothing under `data/` was written.

**Bytes:**

- `data/human/sessions/intake_session.py`: LF `b13c7e9e`
- `data/human/sessions/assemble_session.py`: LF `822bd4b9`
- `human_intake` from `code-snapshot-2ad0992`
- main at `57d1f3d`

The review aid is `motorfix.py` in my scratchpad.

## Verdict: the identity fix is right. Three wording and source defects to fix before 025230 is assembled

**What is right:**

- `step_motor` now takes `MOTOR`/`BINDINGS` from the assembly. On every admitted session and on 025230, the
  re-derived motor record carries identity **`a8dea3ba…`**, equal to each `settings.json` and to the step-table
  headers' `settings_hash`. The old records carry `e55453d6…` (from before I1).
- The per-date refusal works.

**What is wrong:** the admitted sessions' records do **not** re-derive byte-identical, and the 09-24 source text
doesn't match the committed log line.

| Check | Result |
|---|---|
| Identity of the re-derived motor records (4 admitted + 025230) | **a8dea3ba**, equal to `settings.json` |
| A date without a statement | **Refused**: 2026-09-22 and 2026-09-25 each give "no per-session motor statement … refused" |
| Admitted `motor-settings.json` re-derive byte-identical | **No, by design**: `settings`, `bindings`, `calibration_takes` and the identity all change |
| Admitted `settings.json` re-derive byte-identical | **No**: M1 |
| The 2026-09-24 statement maps to the committed log line | **No**: M2 |

## M1 (fix): the 2026-09-23 wording is not the old wording

The hand-back says "2026-09-23 keeps the old wording". It does not.

| Field in the admitted `settings.json` | Stored text | New text |
|---|---|---|
| `settings.per_session_source` | "James's dated statements of 2026-09-23, applied by the lead to every existing session" | "James's dated statements of 2026-09-23 (docs/recording-log.md, Motor settings), applied by the lead to every session up to that day" |
| `bindings.per_session_source` | "James's dated statements of 2026-09-23 (docs/recording-log.md)" | the same new text |

- **The consequence:** on all four admitted sessions, a re-assembly writes a different `settings.json`.
- **That file is pinned:** its sha256 is in each session's `artifact-hashes.json` (checked on 205528), so
  `freeze.py --check` would fail after a re-assembly.
- **Not affected:** the identity and the step tables.
- **Fix:** keep the two old strings for 2026-09-23, separately for settings and bindings. Or accept that admitted
  sessions are never re-assembled, and say so.

## M2 (fix): the 2026-09-24 entry doesn't cite the line the lead committed

**The table says:** `MOTOR_STATEMENTS["2026-09-24"]` = "James, relayed by the lead on 2026-09-24 (addendum to
brief-admission-owner-arrivals-0924, **~22:10 CDT**): DPI and sensitivity unchanged; …".

**The log says:** `docs/recording-log.md` at `57d1f3d`, Motor settings, reads "2026-09-24: **DPI, in-game
sensitivity and bindings unchanged** for the four 2026-09-24 takes (James, chat via the lead, 2026-09-24
**~22:40 CDT**, …)".

- **The time disagrees** (22:10 against 22:40).
- **The source is wrong:** the entry cites a brief in a temp folder, when it should cite the repo line.

**Fix:** make the entry name the recording-log line: its date, "~22:40 CDT", and the section, as the 09-23 entry does.

## M3 (fix): a 09-24 motor record quotes the 09-23 log line

- **The problem:** `step_motor`'s `statement` block is hard-coded to the 2026-09-23 text ("2026-09-23: mouse DPI 800
  … unchanged since the 2026-09-21 sessions"). Every session therefore quotes that line, including 025230 and 232304.
  Its `need(...)` guard checks for the 09-23 phrases only.
- **Fix:** give each `MOTOR_STATEMENTS` entry the exact log text it rests on. Then `step_motor` can quote it, and check
  that the text occurs in the committed log.

## 025230's existing motor record

- **What I compared:** I re-derived the 025230 record at main `57d1f3d` against the owner's `motor-settings.json`
  (`8955d5b8`).
- **The differences:** only `settings.statement` (the log sha, and the commit `14f2a145` → `57d1f3df`) and the
  matching `evidence` entry. The identity and the bindings are equal.
- **What that means:** the stored record predates the log line it now depends on. It is `write_once`, so it has to be
  regenerated deliberately, after M2 and M3. Delete it and re-run the step, and don't expect the assembly to replace
  it.

## Minor

- **The date comes from the machine's local timezone.** `motor_statement` takes it with
  `datetime.astimezone()` and no zone. That is CDT on this PC, but UTC on a machine set to UTC.
  - For 09-24 evening takes this fails safe (refused as 09-25).
  - A 09-23 evening take would map to the 09-24 statement **silently**, because both dates exist. For example,
    02:30Z on 09-24 is correctly 09-23 here, but would read as 09-24 on a UTC machine.
  - **Fix:** pin `zoneinfo.ZoneInfo("America/Chicago")`, the PC's zone.
- **The old admitted motor records remain inconsistent:** they carry `e55453d6`, their `settings.json` carries
  `a8dea3ba`.
  - As the owner says, they are evidence records, and the assembly and fit used `a8dea3ba`.
  - Record that in the lane doc; don't rewrite the frozen files.

## Addendum, 2026-09-25: re-check of the fix-forward (`intake-motor-2.md`)

**Bytes:**

- `assemble_session.py` LF `1edf1302`
- `intake_session.py` LF `2ad9908b`
- `tests/test_human_intake.py` LF `32228519`

**Tests:** `tests/test_human_intake.py --corpus`, run in my own environment: **60 passed**.

**My re-derivation** (`motorfix2.py` in my scratchpad; `step_motor` into scratch copies only):

| Item | Status | My evidence |
|---|---|---|
| **M1** 2026-09-23 wording | **Fixed** | all four admitted sessions: `motor_statement` from their own start times gives the stored `settings` and `bindings` per-session sources, **both byte-equal** |
| **M2** 2026-09-24 source | **Fixed** | the entry quotes the `57d1f3d` log line verbatim (~22:40 CDT); a log with "~22:10" in its place is **refused** |
| **M3** a record quotes its own date's line | **Fixed** | 025230 and 232304 records: `statement.date` 2026-09-24, and `statement.text` equal to that entry's `log_quotes`, at commit `57d1f3df` |
| Refusal for a date without a statement | **Holds** | 2026-09-22 and 2026-09-25 are refused |
| Zone | **Fixed** | `chicago_date` agrees with this PC's own Central clock at **all 52,560 instants** (every 20 min through 2026-2027, both transitions each year) |

**Are the regenerated records what the sessions should assemble with? Yes.**

- **They are reproducible:** my own `step_motor` run at `2ad9908b` reproduces both new records exactly (all fields
  except `supersedes`):
  - 025230 `2a6e604e`
  - 232304 `46e82b4f`
- **They agree with the assembly:** each record's identity equals `settings_identity(MOTOR, BINDINGS)` of the
  assembly (`a8dea3ba`). Its settings and bindings per-session sources equal what `assemble_session.py` will write
  from the same `motor_statement`.
- **Strictly, the assembly doesn't read `motor-settings.json` at all.** It derives `settings.json` from its own
  `MOTOR`, `BINDINGS` and statement. So the record and `settings.json` now agree by construction, not by copying.
- **The old records are kept as `.v1`,** each named by sha256 in the new record's `supersedes`:
  - 025230 `8955d5b8`
  - 232304 `14334d6b`

**One audit-trail note: fix at the freeze, not before assembly.**

- **The problem:** each session's `segments-evidence.json` still says
  `motor: {path: "motor-settings.json", sha256: <v1>}`. That path now hashes to the *new* record, so anyone resolving
  the pointer by path finds a mismatch.
- **Why it doesn't block:** no code checks that pointer. The chain can be followed: the evidence's sha256 → the `.v1`
  named in the new record's `supersedes`.
- **The fix:** when these sessions are frozen, pin both `motor-settings.json` and `motor-settings.v1.json`. Say in the
  session's lane record that the evidence's motor sha256 names the `.v1` file.
