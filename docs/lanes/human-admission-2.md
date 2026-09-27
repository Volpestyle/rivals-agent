# human-admission, continued (admission-owner)

`docs/lanes/human-admission.md` is frozen. Its bytes at a0e9a79 (LF `333b872b…`) are pinned by
`docs/evidence/idm-train-release-20260926/`, which admission-review reviewed, so it is not edited. This note continues
it. The allocation `idm-reader-validation-20260927T030000Z` is defined there, in its section "Allocation
idm-reader-validation-20260927T030000Z", and its selected ids are recorded here.

## Allocation idm-reader-validation-20260927T030000Z: selected ids

Every selection is recorded here before anything of it is inspected. The inputs are logger folder names, video
filenames, sizes and mtimes, James's declarations and the lead's recording-log rows. No logger folder content, video
frame or media hash is read.

| Slot | Family | Original live recording (START ≥ 2026-09-27T03:00:00Z) | Linked files | Declaration | Recorded at |
|---|---|---|---|---|---|
| **V-C**, `reader_validation` | the 23:13 Competitive match (Platinum, alt account) | `20260927T041331-992Z-150600-1` (`2026-09-26 23-13-31.mkv`, 14,639,289,304 B, mtime 23:31:56) | its replay of self, `20260927T043214-589Z-150600-2` (`2026-09-26 23-32-14.mkv`, 14,368,464,487 B, mtime 23:48:13) | James, chat, 23:49 CDT: "1 new competitive match in plat on my alt and the full replay" (the lead's rows, da92739) | 2026-09-26 23:52 CDT (PC clock) |
| **V-Q**, `reader_validation` | the 23:59 Quick Match (Museum of Contemplation, alt account, party with a friend) | `20260927T045943-301Z-150600-3` (`2026-09-26 23-59-43.mkv`) | none (no replay recorded) | James, chat, 01:37 CDT, with his match-history screenshot (the lead's rows, 8392576) | 2026-09-27 01:41 CDT (PC clock) |

**Why this family.**
- As of 23:51 CDT, only two logger sessions start on or after the boundary, `-150600-1` (04:13:31Z) and `-150600-2`
  (04:32:14Z).
- `-1` is the first original live recording in UTC-start order, and James declares it Competitive.
- `-2` is its replay, also by James's declaration. A replay is part of the same indivisible family, not a separate
  identity.
- No earlier unknown-mode recording exists to resolve first. So V-C is filled and V-Q stays open.
- **V-Q (01:41 CDT):** in UTC-start order after the V-C family, the next logger session is `-150600-3`
  (04:59:43Z). James declares it a Quick Match, so it is the first Quick Match family. Every earlier identity since
  the boundary is resolved: `-1` Competitive and `-2` its replay. **Both slots are now filled.** The allocation is
  complete, and every later match is IDM-train.

**Hashes (2026-09-27 01:50:52-01:52:19 CDT).**
- All eleven registered files and -9 were streamed while neither `obs64` nor `Marvel*` ran. The lead verified both
  closed from 01:50:09, and I rechecked before launch and after every file.
- Each file's size and mtime were unchanged across its hash. The sha256 values are in the registry.

## 2026-09-27: the night's Quick Matches (lead's rows 8392576)

Registered at 01:41 CDT (PC clock) from names, sizes, ids, James's declaration and the lead's rows only. Nothing was
inspected. James's declaration covers all of them: alt account, keyboard settings unchanged (DPI, sensitivity 1.89,
binds), played in a party with a friend.

- **V-Q:** `20260927T045943-301Z-150600-3` goes to `evaluation_sessions` as `reader_validation`, slot V-Q.
- **`idm_train`, the default for matches (8):** each is its own `session_group`.
  - `-150600-4` Thebes, `-5` Celestial Husk, `-6` Yggdrasill Path, `-7` Krakoa, `-8` Museum of Contemplation.
  - `-10` Royal Palace, `-11` Central Park, `-12` Celestial Husk.
  - `recorded_video_path` and `expected_media_sha256` are added together once the files are hashed; the importer
    requires the pair.
- **Not registered:** `-150600-9` (`2026-09-27 00-58-41.mkv`, ~42 s) is a practice-range fragment and not a match.
  - The lead decided at 01:5x CDT to leave it unregistered as a fragment. The tally lists it as not_range.
  - Its media sha256 (for the record) is `e851e9fe72542ba400bb68bc70b29fd1b327c30862597e225d67411987366ae7`, 456,011,652 B.
- **Registry:** 36 split rows (idm_train 16, train 12, gate2 4, test 3, val 1), plus the three V-C/V-Q evaluation rows.
  It validates with denylist v2.
- **Hashed (01:52 CDT):** `expected_media_sha256` and `recorded_video_path` are filled for all eleven files (V-C 2,
  V-Q 1, idm_train 8). The tally is regenerated, and the headline is unchanged at 180.57 / 15.58.
