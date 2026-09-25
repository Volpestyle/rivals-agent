# admission-owner final 17: 021320 ready for independent review (34.52 provisional min)

**021320** (`2026-09-24 21-13-20.mkv`, train, sitting 2026-09-24-late-evening, 36.6 min).
- **Steps provenance through propose** ran from `code-snapshot-2ad0992`, with the motor step on the fixed driver.
- **The evidence step** ran from **`code-snapshot-dfbb4dd-98e52781`** (the edge rule and E1):
  - the scheduled run on 2ad0992 was refused by the new E1 guard, as intended, and wrote nothing;
  - `earlier_steps` records 2ad0992.
- **Owner verdicts are written.** It needs the independent review. Nothing is assembled.

## Session

- **Recorder:** check clean, 263,435 decoded = matched frames, 2 unwritten tail packets, the +21 ms anchor (residual 0.33 ms).
- **Provenance:** the anchor matches.
- **Build:** `1.1.3892207/build25501035`.
- **Saved settings:** equal the 09-22 receipt.
- **Motor:** identity `a8dea3ba…`; the statement quotes the 2026-09-24 log line.
- **Devices:** one keyboard and one mouse, 0 injected control packets, 44 zero-effect handle-0 packets. One UI key (the
  closing Alt at 2,192.89 s). The two AFK spans, 54.9 s and 56.1 s, are James stepping away, as you said. **No duplicated
  composition time** in this file, and no capture gap.
- **Regime:** normal (`normal_depletion_observed` 413, `no_evidence` 26, `no_hud` 1).
- **Edge reads (the new rule):** every gameplay edge sits on a frame both proofs hold.
  - seg-002's start bracket held 15 unproven frames: the hero select, then the spawn-in, f745–f759, where the HUD reads
    present but `in_range` is False. The edge landed on f760.
  - Every review frame of the five gameplay segments passes `in_range`.

| Segment | Reason | Owner | Seconds | Frames |
|---|---|---|---|---|
| seg-000/001 | focus_transition, no_range_hud | rejected | 0.25, 3.58 | 3, 3 |
| **seg-002** | range_hud_present | **accepted** | 361.942 | 38 |
| seg-003/004/005 | unsampled edge, **afk** (54.9 s), unsampled edge | rejected | | 0, 7, 0 |
| **seg-006** | range_hud_present | **accepted** | 850.225 | 87 |
| seg-007/008 | **dead** (1,273.55 s), unsampled edge | rejected | 2.2 | 3, 0 |
| **seg-009** | range_hud_present | **accepted** | 127.567 | 14 |
| seg-010/011/012 | unsampled edge, **afk** (56.1 s), unsampled edge | rejected | | 0, 7, 0 |
| **seg-013** | range_hud_present | **accepted** | 451.725 | 47 |
| seg-014/015 | **dead** (1,911.15 s), unsampled edge | rejected | 2.2 | 3, 0 |
| **seg-016** | range_hud_present | **accepted** | 279.525 | 29 |
| seg-017/018 | unsampled edge, ui_key (Alt) | rejected | | 0, 3 |

**Provisional counted minutes (owner verdicts only): 34.52** (5 runs, all counted).

**For the independent review:**
1. **seg-002's first frame, f760.**
   - f760 passes the live guard: the range banner and HP bar are drawn. The hero model itself only appears on f761.
   - f759 is the spawn-in frame (no hero, HP bar incomplete) and fails the guard.
   - James presses nothing until W at f804 (logger 6.855 s).
   - Under your rule f760 is a valid edge. If the rule should also require the hero to be drawn, that is a rule change,
     not mine to make. Native frames f759–f762 with the guard's verdicts are in my scratchpad, `edge/f021320/`.
2. **The deaths.**
   - 1,273.55 s: a fall into the sea, 0 HP, then SPECTATING.
   - 1,911.15 s: a fall off the map edge against the sky, then the 1 s respawn ghost.
   - Both were cut by the dead rule, and both resume from the spawn room after the respawn settle.
3. **The second AFK span** has a Windows "Output device has changed, please confirm audio settings" banner over the game
   on frames 170625 and 171747. It is inside the rejected span.
4. **The hero select opens on Elsa Bloodstone** before James switches to Spider-Man. It is inside rejected seg-000/001.

## Bytes (`data/human/sessions/20260925T021320-371Z-7804-1/`, all LF)

| File | Bytes | sha256 |
|---|---|---|
| `provenance.json` | 48,972 | `9caa9ef22344ae4494d26c31bd1a9235f3c545491af9eda690b94718f954be94` |
| `recorder-verification.json` | 1,212 | `bd0e65cd4ffac8d8c2c942d2f7f44ab4ec0a9840b2ff85ae115859e5393bc986` |
| `input-profile.json` | 1,802 | `b52b17d180226f7a96ebefe18fbd95c7bcc0f0ab2dc9643edb6b1a7f78590033` |
| `slot-mapping.json` | 259 | `1a4677df7972e94e94ae500d6e15a617655213f54fd52f33d5bd0d3f5ce3587d` |
| `hud-scan-samples.jsonl` | 8,322,129 | `461f8ac174816770ca4b4942601530ba686d57fae5e9ed799917d88c98c551a1` |
| `regime-timeline.json` | 96,496 | `058265e2362162d1f3fd5aeca0b38484530f68f97d6f1690923e43f6b8577c01` |
| `motor-settings.json` | 5,799 | `dbf5245551ee4af7a7d206ce66f7dfb30648cd07280c828bb4f69f13be550fe3` |
| `candidates-pass1.json` | 4,765 | `7c921d594ae7491192660a3148cc31830ba99fcaa1a2dedda775093cc1b21daa` |
| `segments-evidence.json` | 136,712 | `75e34751156ff813cfcbf69613eda598433c02d387ea0f0ac5feca49ddcdcf34` |
| `owner-verdicts.json` | 51,179 | `e492b2c443e7a8e94d557353fb33b03126b57fdd41323d980c4aeae4f1ea6bd4` |
| `review-frames/` | 244 files, 50,926,514 | per-frame hashes in `segments-evidence.json` |

No commits, no Linear, nothing on the Mac.
