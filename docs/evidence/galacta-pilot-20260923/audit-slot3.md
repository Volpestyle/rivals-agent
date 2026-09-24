# Slot 3 audit: the designated KO (VUH-1319)

The audit was independent of the operator. It was offline, with no game input. The decode was low priority, 4 threads, 320×180 thumbnails plus one 0.4 s native strip.

## Verdict: CONFIRMED, with two corrections to the record

The right/stair Galacta, the designated bot, took the whole combo and was KO'd at loop t ≈ 11.68 s (frame `000027`). That is about 3.0 s after the first phase frame, or 3.1 s into the phase by `meta.seconds`. The left bot was untouched: it is visible and bar-less up to `000012`, and the damage total rules out any hit after that. The boards read KOs 0 → 1 and damage 0 → 250 with the landed reader (`7f18ba4`). The `frames.jsonl` timeline agrees with the frames and the native video.

The two corrections, detailed below:
1. The archive manifest's hash of `scripted-native.mp4` is of a partial file.
2. Track id 1 was *coasting*, not measured, for the last 0.8 s of the combo.

Neither changes the verdict.

## Evidence

**Provenance.**
- All 45 run files in `data/l1/galacta-pilot-20260923-03-scripted/` match `archive-manifest.json` `run_files`: frames, `frames.jsonl`, both boards and `meta.json`.
- The native video was aligned to the loop by thumbnail matching. All 28 loop frames match monotonically increasing video frames at a steady offset: **video t = loop t + 1.02 s** (±0.03). Most matches have error ≤ 60 against a 4th-best in the hundreds or thousands. The recorder itself says `video_loop_mapping_known: false`, so this mapping is mine.

**Which bot took the combo**, from `frames.jsonl` pad records and the frames. Button meanings are from `docs/spiderman-kit.md`.

| Loop t | Frame | Input | What the pixels show |
|---|---|---|---|
| 8.65 | `000000` | idle | Both bots at rest; the right bot at `1223,509,1351,642` (id 1). The left bot shows its name plate only (no bar = undamaged) |
| 9.02–9.14 | `000003`–`000004` | LT, two press edges (Web Cluster) | Aimed at the right bot; webs 5 → 4 by `000005` |
| 9.44 | `000007` | RB (Get Over Here!) | Spider-Man is pulled *to* the bot (`000008`–`000011`). That is the tagged web-strike form, so the Web Cluster tag was on the right bot |
| 10.01 | `000012` | camera pitch | Spider-Man at the right bot, now showing a green bar. **The left bot is still at its spot, name plate only, no bar** (checked on a native crop) |
| 10.20 | between `000013`/`000014` | X (Amazing Combo) | Native 60 fps strip, video 10.9–11.3 s: one continuous engagement on one bot, no cut, no swap; bot launched up |
| 10.78–11.74 | `000019`–`000027` | RT held (Spider-Power chain) | Same bot at the stair base; `000027` shows the KO burst over it |
| 11.76 | (feed) | stop `candidate_feed` | `executor_release` at 11.774; feed candidate at 11.76 |
| 11.92 | `scoreboard-end.png` | BACK | Terminal board |

After the kill, the video (v760–v1800, 12.8–30 s) shows the KO burst and the scoreboard. From about 18 s it shows a full-health Galacta bot beside Spider-Man, presumably the respawn. The left bot is never back in view after `000012`.

**The left bot was untouched.** It shows no damage bar through `000012`, after both Web Cluster shots and the RB strike. After `000012` there is no pixel view of it, so that stretch rests on damage accounting. The terminal board's damage is **250**, one bot's full life, and a kill needs all of it on the KO'd bot, so nothing was credited to the left bot.

The "bot HP = 250" figure is inferred, not documented: two independent one-KO boards (09-22-03 end and this one) read exactly 250, and slot 1's +90 left the bot at about 65 %.

The finder saw the left bot as id 4 at `000009`–`000011` and `000016`, clipped at x=800. It then coasted; it was never the target.

**Boards**, re-read now with `perception.scoreboard` at `7f18ba4`:
- `scoreboard-baseline.png` (sha `56ad5c21…`, matches the manifest): KOs 0, deaths 0, assists 0, damage 0, all zero.
- `scoreboard-end.png` (sha `e52b25b7…`, matches): KOs 1, deaths 0, assists 0, damage 250, web_cluster_accuracy 33.
- Both equal the `parsed` values recorded live in `meta.json`.

## Corrections for the record

1. **The video hash in the archive manifest is of a partial file.**
   - The manifest was `written_utc` 18:46:18, while the 60 s recorder (launched 18:46:02) finished at 18:47:03.
   - The manifest records `scripted-native.mp4` as 91,226,160 bytes, sha `f18f5a7f…`. On disk it is 311,440,981 bytes, sha `97d7633d…`.
   - `scripted-record.log` shows the same thing, and there the proof is exact: the first 4,384 bytes of today's log hash to the manifest's `609c262f…`.
   - The mp4 prefix does not reproduce the manifest hash. A finalized mp4 rewrites its header; I tried the obvious `mdat`-size placeholders and none reproduced it, and I stopped there.
   - No file in the repo records the final video's hash. The video's identity rests on its content matching all 28 hash-pinned loop frames at a constant offset.
   - Suggested fix (not mine to make): archive after the recorder exits, or re-hash once it does.
2. **"The selector held id 1 for the whole combo" is true only of the `target` field.**
   - From `000020` to `000027`, id 1 is in `coasting` with `target_px` frozen at 193.9.
   - During that stretch the bot was measured as ids 7, 9, 10 and 12, fragments of the launched and falling bot. The pixels show one physical bot throughout.
   - So the physical claim stands, but the tracker did not re-associate its measurement to id 1 for about 0.8 s. That is worth a line in the tracker lane, and it bears on the VUH-1314 fragment accounting.

## Open detail (not contradicting)

`web_cluster_accuracy` 33 % against two logged LT press edges. It is unexplained whether one press fires more than one counted shot. A miss adds no damage, and a hit on the left bot would have pushed damage past 250, so this does not affect the verdict.
