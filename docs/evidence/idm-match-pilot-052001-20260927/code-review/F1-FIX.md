# F1 fix: delta-only review (admission-owner, 2026-09-27 11:02:46 CDT)

Answers fit-review's FIX verdict (review-matchmode-20260927.md, 77d5ca80...). All other files keep their FROZEN.md pins;
only these two changed:

| File | LF sha256 | Frozen pin |
|---|---|---|
| agent/human_intake.py | 8f06dc19ecb1a5c4664700e4fce89a4420a85a3f9df2bfb3b86c4b84308376bb | b67dcb1a |
| tests/test_intake_match_mode.py | ee959c99787e1972b773764b3066e28ce8624de55b7d5d57f706dca2e4ce01a5 | 52e8bfb2 |

Diffs against the frozen copies: F1-fix.human_intake.diff, F1-fix.test.diff (both in this folder).

**The fix.** `move_presses` now counts a movement-key make only outside every input-consuming UI span. It tracks those
spans from the same events, by ui_cuts' rules, on makes only:
- open chat (Enter until Enter or Esc; keys typed there are text);
- a toggled overlay (F1, B, H; Esc closes it);
- a held Tab or T;
- everything after a settings-menu Esc (R3).

With no real movement make, the emote cut keeps its conservative end, the focus interval's end.

**Test** (`test_movement_typed_in_chat_never_ends_the_emote_cut`):
- Your sequence: T down 1 s, up 2 s, Enter 3 s, W 4 s, Enter 5 s. `move_presses` returns [], and the emote cut is
  [1 s, focus end).
- A real W at 6 s gives a cut of [1 s, 6 s + settle).
- Also covered: an F1 overlay, a held Tab, the settings menu, and Esc closing F1.

Suite: 367 passed, 4 skipped.

**Pilot -5** (the lead's question: is it affected?). No.
- The whole session has no Enter, Esc, F1, B or H key-down. Its only UI-key downs are the T hold and its auto-repeats,
  281.4-282.7 s.
- Recomputed on -5's real input log, the emote cut is [281.414, 307.124) under both the frozen and the fixed rule.
- The fix drops exactly one movement press, at 435.628 s: a W made while Tab was held, inside both the third death cut
  (425.7-435.9 s) and the Tab cut. No segment changes, so -5's evidence, verdicts and assembly stand.

**The other seven.** Their propose and evidence steps run on the fixed snapshot `code-snapshot-f8fd92c-08c36e68`
(manifest raw sha256 b1300a2a451886f8f59dbaef79f648c7a18e0b5e3a4c78b6df79b1d771c2cac5). Provenance through motor run on `code-snapshot-f8fd92c-6046514b`, which those steps
don't use `move_presses` in, recorded as `--earlier-snapshot`.
