# arrivals-0925-late: the 22:59 range take registered and inventoried; 22-48-05 looks like a match; one decision (Esc)

**Summary**

- **Registered train, before inspection.** `2026-09-25 22-59-32.mkv` is session `20260926T035932-508Z-63684-14`
  (started 03:59:32 UTC). I registered it at **23:32:36 CDT**, from its file name, size and session id alone.
  - **Registry** `data/human/session-splits.corpus.json`: `cbae5149…` → `85db5429…` (row added) → **`636547d01065885521f5e419fb25f93f2a90e300b072356b93b36ece32c28c81`**
    (media hash and focused minutes added; 11,044 B, LF). `check_registry` passes: 13 rows.
  - **Sitting** `2026-09-25-late`; OBS process 63684.
- **Motor:** `MOTOR_STATEMENTS["2026-09-25"]["log_quotes"]` now holds both lines: the `fbe6693` line first, unchanged, then the
  `0072df5` "(late)" line verbatim. `motor_statement` resolves both 212646 and the late take against the committed log.
  Intake, timed and importer tests: **158 passed, 3 skipped**.
- **The take is complete and clean,** and the +21 ms anchor holds, read from packet headers only. Build
  `1.1.3892207/build25501035`, which is equivalent. Controls equal the 09-22 receipt.
- **22-48-05 looks like a match, not range play,** from its input log alone (below). Not registered; the video is never
  opened.
- **One decision for you:** the range take opens with **two Esc presses at 4.1 s and 5.4 s**. Under R3, the proposer
  holds everything after the first Esc as `after_settings_menu`, unresolved, and the session is held by default. That
  would hold the whole take, unless you decide otherwise (below).
- **The hold is kept:** no decode or heavy step while the game and OBS run. Hashing ran at background priority. The
  match recordings (19-21-09 through 21-13-21) and tonight's other logger folders were not opened.

## The range take (`20260926T035932-508Z-63684-14`)

| Video | Duration (frames.csv) | Focused | Packets | Bytes | Original sha256 |
|---|---|---|---|---|---|
| `2026-09-25 22-59-32.mkv` | 1,848.025 s (30.80 min) | 1,834.46 s (30.57 min) | 221,762 | 26,996,242,485 | `7ab6b6083ac9aa38ad5b3ccde866ccb684d79332be42696ab36c2c7030f22494` |

- **Logger files:**
  - `inputs.jsonl` `efe410e9…` (42,636,918 B);
  - `frames.csv` `6d4ad194…` (28,659,611 B);
  - `metadata.json` `661a18c2…` (1,125 B).

  Full hashes are in `inventory-late.json` (`8066fba8…`).
- **Completeness:** complete, clean stop, `integrity_ok`, 0 drops, 0 raw-input errors, contiguous packet indices.
  - There are two one-frame steps: 16.7 ms at 1,843.0 s (at the closing Alt) and at the tail.
  - **Anchor** `[21, 46, 29, …, 121]` / `[0, 21, 42, 64, 85]`, equal to the prediction.
- **OBS:** process 63684, log `2026-09-25 18-43-05.txt`, lines 582–609.
- **Build:** `1.1.3892207/build25501035`, inside the pinned equivalence. Steam shows no update since 2026-09-24; the game
  restarted at 21:17:56 and 21:18:45.
- **Saved settings** `28aec189…`: rewritten at 21:17 CDT (the restart), before the take. Hero 0 and 1036 controls equal
  the 09-22 receipt; `NoCDSaved` is 0.
- **Devices:** one keyboard and one mouse, 0 injected control packets, 37 zero-effect handle-0 packets.
  - **The keyboard handle changed again,** to `305729567` (09-24: `1043402031`; this afternoon: `661785265`). Handles are
    reassigned on reconnect; the device-scope check passes.
- **Focus:** five intervals, 0.41–1,145.96, 1,147.50–1,202.82, 1,207.30–1,216.02, 1,217.15–1,222.25 and 1,223.31–1,843.09 s.
  - There are four brief Alt+Tab losses of 1.5, 4.5, 1.1 and 1.1 s, around 19–20 min.
  - There are six Alt presses, counted with key state reset at each focus event.
- **Presses:**

  | Key | Presses |
  |---|---|
  | Space | 1,367 |
  | A | 897 |
  | D | 602 |
  | W | 567 |
  | Shift | 401 |
  | S | 345 |
  | E | 235 |
  | C | 150 |
  | F | 111 |
  | Alt | 6 |
  | Q | 4 |
  | Tab | 3 |
  | Esc | 2 |
  | V | 1 |
  | Caps Lock | 1 |
  | LWin | 1 |

  - Mouse button downs: 2 ×875, 1 ×338, 5 ×23, 4 ×18.
  - No AFK span of 20 s or more.
- **UI keys** (the proposer's cuts):
  - Esc at 4.1 and 5.4 s;
  - Tab at 1,221.1, 1,457.5 and 1,616.1 s;
  - the Alts;
  - V at 216.1 s (unbound in `BINDINGS` and not a UI key: noted, like 203745's G).

## Decision: the two opening Esc presses

- **The rule.** R3 treats any Esc that does not close chat or an overlay as a settings-menu opening (`ui_cuts`). Every
  span after it is proposed `after_settings_menu`, unresolved and never acceptable, and the session is flagged
  `settings_menu_opened` and held.
- **Why the rule exists:** 032454 turned No Ability Cooldown ON in the practice settings.
- **In this take:** the first Esc is at 4.1 s, 3.7 s after focus. So, as the rule stands, **none of the 30.6 min can be
  admitted.**
- **What the log shows:** Esc at 4.1 s, then Esc 1.3 s later (5.4 s). In the range, Esc opens PRACTICE SETTINGS (the
  banner's "ESC PRACTICE SETTINGS" line), and a second Esc closes it. 1.3 s is time to open and close the menu, not to
  navigate it. That is inferred from timing only; no frame has been read.
- **Options:**
  - **A. Keep R3 as it is.** The take is held (0 counted min). No code change.
  - **B. A narrow exception** (recommended if you want the minutes; about 30 min at stake):
    - an Esc that is closed by the next Esc within 2 s, with nothing but mouse motion between them, becomes a `ui_key`
      cut from the first Esc to the second plus the 2 s settle;
    - it is admitted only if the regime scan stays `normal` across the whole take and the frames either side of the pair
      show the same practice settings (the HUD's cooldowns and ammo behave normally after it);
    - a small change to `ui_cuts` with tests, reviewed with the session, like the timed cut;
    - any other Esc keeps R3.
  - **C. Ask James** what he did at 4.1 s. His answer would settle it, but he may not remember.
- **When:** the evidence (the regime scan and the frames at 4–8 s) needs a decode, so it waits for the game and OBS to
  close either way. If you choose B, I implement the rule while the hold lasts and run the scan when the processes are
  gone.

## 22-48-05: input log only; it looks like a Quick Play match

`20260926T034805-307Z-63684-13` (`2026-09-25 22-48-05.mkv`, 22:48:05, 685.1 s / 11.41 min, 82,181 packets, 5.46 GB).
- **Logger:** complete, clean, 0 drops, `integrity_ok`. Build `1.1.3892207`. One keyboard (305729567) and one mouse, 0
  injected.
- **What the input log shows** (no frame or packet header read):
  - **About 2.5 min before sustained play:** idle spans of 22.6, 24.1 and 26.0 s in the first 100 s, then an Alt+Tab
    away from 110.6 to 154.9 s (44 s). Range takes start moving within seconds of focus. This looks like hero select,
    the countdown or matchmaking.
  - **Tab ×56,** in bursts (240–288 s, 373–463 s, 570–633 s). Range takes have 0–3 Tab presses. The pattern is a player
    checking the scoreboard repeatedly.
  - **Enter ×8** (478.8 and 481.2 s among them), which opens chat. H ×2, Esc ×1 (157.3 s, right after focus returns),
    G ×1, Caps Lock ×4, key 78 (N) ×1, Mouse 3 ×1.
  - **Movement and abilities** (Space 314, A 194, D 180, W 146, Shift 64, E 31) are about half the density of range
    play.
  - **Focus ends at 682.4 s** with the third Alt.
- **Verdict (inference):** the input log is **consistent with a short match** (a pre-game wait, heavy scoreboard use,
  chat) and unlike any range take so far. Only the frames can confirm it, and I haven't opened them.
- **Not registered.** It is grouped with tonight's unnamed matches.

## Tonight's other logger folders (named only; not opened)

The matches you named map to logger folders `20260926T002109-428Z-63684-2` through `…T021321-378Z-63684-9`.

Four more folders have **no matching video** in `Videos`. I have read nothing inside them, only their names:

| Folder | Time (CDT) |
|---|---|
| `20260925T234952-361Z-63684-1` | 18:49 |
| `20260926T022734-732Z-63684-10` | 21:27 |
| `20260926T031019-828Z-63684-11` | 22:10 |
| `20260926T033121-111Z-63684-12` | 22:31 |

They are probably false starts or deleted takes, like this afternoon's. I'll inventory them from metadata when you say
so.

## Ledger rows (for you to append)

```
| 2026-09-25 22-59-32.mkv | 20260926T035932-508Z-63684-14 | 30.8 min | range, whole-session training take (James: usual skin, same settings; input log: 1,834 s focused in five intervals, four brief Alt+Tab losses around 19-20 min, Tab ×3, two Esc at 4.1 and 5.4 s) | not yet read (HUD scan after the game closes); saved NoCDSaved 0 | logger complete, clean stop, 0 drops, 0 raw-input errors; anchor holds (+21 ms); game build 1.1.3892207 (kit-equivalent); registered train 2026-09-25 23:32 CDT; the opening Esc pair needs a decision under R3 before intake can count any of it |
| 2026-09-25 22-48-05.mkv | 20260926T034805-307Z-63684-13 | 11.4 min | probably a short Quick Play match (James: "probably nothing"; input log: ~2.5 min pre-play wait, Tab ×56 in bursts, Enter ×8) | n/a | logger complete, clean stop, 0 drops; inventoried from metadata and the input log only; not registered (grouped with tonight's unnamed matches) |
```

## Artefacts (my scratchpad, `…/51f6344f-…/scratchpad/arrivals-0925/`)

| File | sha256 |
|---|---|
| `inventory-late.py` (inventory.py with the two sessions; 22-48-05 metadata/input-only) | in folder |
| `inventory-late.json` | `8066fba843ad294616324ce65b5398608c2b6fce418695bb452b2dd76f0134cb` |
| `inventory-late.log` | in folder |

**Uncommitted repo changes of mine now:**
- the registry;
- `assemble_session.py` (the second quote);
- the intake code and tests from final-23.

Final-23's code hashes still hold, except `assemble_session.py`.

No commits, no Linear, no game input, nothing on the Mac.
