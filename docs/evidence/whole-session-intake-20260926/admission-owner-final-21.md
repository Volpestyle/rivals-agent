# admission-owner final 21: 212646 (val) ready for independent review (15.58 provisional min)

**212646** (`2026-09-25 16-26-46.mkv`, **split val**, sitting 2026-09-25-afternoon, 15.9 min). It was registered to val
at 16:47:16 CDT, before any inspection (arrivals-0925.md).
- **Every step** (provenance through evidence) ran from **`code-snapshot-b7d4592`** (manifest `1927686c…`). That is the
  reviewed intake code the 2026-09-24 batch was assembled from, and its intake files equal HEAD's.
- **The motor step** used the new `MOTOR_STATEMENTS["2026-09-25"]` entry, which quotes the `fbe6693` recording-log line
  verbatim.
- **Owner verdicts are written.** The take needs the independent review. Nothing is assembled.

## Session

- **Recorder:** check clean. 114,301 decoded frames = matched frames, 3 unwritten tail packets, the +21 ms anchor
  (residual 0.33 ms).
- **No duplicated composition time** (0 reversals, 0 shared values in `frames.csv`), and no capture gap.
- **Provenance:** the anchor matches; media sha256 `02e6375b…` equals the registry.
- **Build:** `1.1.3892207/build25501035`, the same as the 2026-09-24 takes (kit-equivalent).
- **Saved settings:** equal the 09-22 receipt.
- **Motor:** identity `a8dea3ba…`. The statement is the 2026-09-25 line, "yep all the same".
- **Devices:** one keyboard (new handle `661785265`; see arrivals-0925) and one mouse, with 0 injected control packets.
- **Regime:** normal (`normal_depletion_observed` 188, `no_evidence` 3).
- **HUD:** present in 4,753 of 4,763 scan samples.
- **Slot mapping:** equal to 051828/032454.
- **Edges (edge rule, E1):** every gameplay edge sits on a frame where both proofs hold. The evidence step wrote
  `flags: []`.
- **UI keys:**
  - three Tab presses at 127.26, 498.29 and 881.38 s;
  - three Alt+Tab focus losses at 354.2, 673.6 and 950.3 s (Alt down, focus lost, Tab released on return).

  Each is cut by the UI-key or focus rule. Tab stays a UI key (lead, 2026-09-25).

| Segment | Reason | Owner | Seconds | Frames |
|---|---|---|---|---|
| seg-000/001 | focus_transition, unsampled edge | rejected | 0.25, 0.005 | 3, 0 |
| **seg-002** | range_hud_present | **accepted** | 126.050 | 14 |
| seg-003 | **dead** (fall off the map edge, then SPECTATING) | rejected | 0.546 | 3 |
| seg-004/005 | ui_key (Tab, pressed while spectating), unsampled edge | rejected | 2.40 | 3, 0 |
| **seg-006** | range_hud_present | **accepted** | 224.550 | 24 |
| seg-007/008/009/010 | unsampled edge, ui_key (Alt), focus_transition, unsampled edge | rejected | | 0, 3, 3, 0 |
| **seg-011** | range_hud_present | **accepted** | 141.400 | 16 |
| seg-012/013/014 | unsampled edge, ui_key (Tab, held ~1 s), unsampled edge | rejected | 2.98 | 0, 3, 0 |
| **seg-015** | range_hud_present | **accepted** | 172.267 | 19 |
| seg-016/017/018/019 | unsampled edge, ui_key (Alt), focus_transition, unsampled edge | rejected | | 0, 3, 3, 0 |
| **seg-020** | range_hud_present | **accepted** | 206.175 | 22 |
| seg-021/022/023/024 | unsampled edge, ui_key (Tab), focus_transition, unsampled edge | rejected | | 0, 3, 3, 0 |
| **seg-025** | range_hud_present | **accepted** | 64.633 | 8 |
| seg-026/027 | unsampled edge, ui_key (closing Alt) | rejected | | 0, 4 |

**Provisional counted minutes (owner verdicts only): 15.5846** (6 runs). They are val minutes, reported beside the train
headline and never added to it.

**For the independent review:**
1. **The end of seg-002, and the death.**
   - seg-002's last frame, f15192 (126.6 s), shows Spider-Man falling past the map edge against the sky. HP reads
     250/250, and the frame passes the guard.
   - seg-003's frames show the fall, then "1s SPECTATING" with 0 HP.
   - The respawn falls inside seg-004, the Tab cut. seg-006 opens in the spawn room.
   - This is the same shape as 021320's second death (1,911.15 s), which your review accepted: the fall up to the last
     alive, guarded frame counts as play.
   - If the fall itself should be cut, that is a rule change for the lead.
2. **The Alt+Tab returns.** The focus-transition frames f42782 and f106235 carry the Windows taskbar. Each is inside a
   rejected segment, and the gameplay edges after them (f42812, f106265) have no taskbar.
3. **Tab while alive** (seg-013, 498.3–501.3 s): the frames show ordinary play with no scoreboard drawn. The cut is by
   rule, as instructed.
4. **Val-specific:** the split is James's decision (recorded in the registry row); please don't re-derive it. The code
   already keeps val apart; I checked it by reading the code, not by running it:
   - `assemble_session.py` accepts `train` or `val` and writes `split` into `minutes.json` and the freeze;
   - the step header carries `split`, and `policy/range_bc/steps.py` reads it;
   - `human_intake.tally` (`render_tally`) puts only train in `headline_train_by_regime` and reports val in
     `val_by_regime`.

## Bytes (`data/human/sessions/20260925T212646-322Z-49728-6/`, all LF)

| File | Bytes | sha256 |
|---|---|---|
| `provenance.json` | 47,088 | `69143ff2f96e941b7040aef199987141416d92bf3cf4f0fb34dd51dd9cf75601` |
| `recorder-verification.json` | 1,211 | `ceee836eecc1edd58983aa886dd8d431a463c9abef3ec6ab88c5ba535b5ffc2b` |
| `input-profile.json` | 5,971 | `4fe53a8646b94b7f02210351540cdfdf5da826c2341605cd5710ff1af08dce5f` |
| `slot-mapping.json` | 260 | `21d0e0b8539eba0cb5c381c9208b3f66b8f880586be08768eea760e768a83d43` |
| `hud-scan-samples.jsonl` | 3,591,848 | `f05f0d8a5fe1a85970f674cf3abb3fe859edee13780d07a8ee1b9f69599e5bcd` |
| `regime-timeline.json` | 42,113 | `af7c4fd581c172dda834afcf6f42f8f47e1a4b260c363daa8f6b2dd959d6ec3f` |
| `motor-settings.json` | 5,870 | `766a635c8024fdd15d0e125f1d6c12491b745a19a5fe1e42a66f1497fc274adf` |
| `candidates-pass1.json` | 6,611 | `0ecfb24ddaed2bef7ca1de95f1401887fc61be33a5c110f0abe4e20dc36343aa` |
| `segments-evidence.json` | 90,572 | `1f7b819485452efedb6892ba2f46dc36419c50510161d2512983f43ed89d2248` |
| `owner-verdicts.json` | 34,765 | `a05aedf83b2536b328f4572684047060c8aeed1305b02f81db76cac6fd822bc2` |
| `review-frames/` | 136 files, 27,939,189 | per-frame hashes in `segments-evidence.json` |

**Contact sheets** (12 per sheet): my scratchpad, `…/51f6344f-…/scratchpad/arrivals-0925/sheets-212646/`. My verdict
input is `verdicts-212646.json`, beside it.

**Uncommitted repo changes of mine:**
- `data/human/session-splits.corpus.json` (`cbae5149…`);
- `data/human/sessions/assemble_session.py`: the 2026-09-25 motor entry, citing `fbe6693`. The file is now LF, which
  equals the committed blob; it was CRLF before;
- `tests/test_human_intake.py`: the 09-25 assertions.

The train take 203745 is still in its recorder verify.

No commits, no Linear, nothing on the Mac.
