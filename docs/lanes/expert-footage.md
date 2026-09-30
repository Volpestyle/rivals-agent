# Expert Spider-Man footage (footage)

Owner: footage. Delivery issue: [VUH-1466](https://linear.app/vuhlp/issue/VUH-1466).
Consumer: IDM / VUH-1353. Scope and sealed-source rules remain in
[the plan](../plan.md); this is offline public video, with no game input.

## Storage and consumer interface

Media and local review artifacts live at `D:/rivals-expert-footage/`, exposed
through the ignored junction `data/demos/expert-footage/`. `path-config.json`
names the catalogue, spans and manifests. Media and third-party frames are
never committed or posted. Review sheets are private local working files.

- `catalogue.jsonl`: one video per line, keyed by `video_id` / `source_id`.
  URL, channel, title, upload date, estimated season, duration, native resolution
  and FPS, bitrate, input-device evidence, normalized overlay/facecam rectangles.
  `null` rectangles mean unreviewed; `[]` means inspected and absent.
- `idm-spans.jsonl`: one span per line, using the IDM worker's agreed fields:
  `span_id`, `video_id`, `local_path`, `sha256` (initially null), `width`, `height`,
  `fps`, `start_s`, `end_s`, `hero=spider_man`, `pov=player`, `input`, `hud`,
  `overlays`, `notes`. Additional fields identify screening confidence and
  whether a 2-Hz pass was performed. Times are on the local video's playback
  clock, excluding its container PTS origin. Keep each video in one split group.
- `reviews/<id>.json`: input evidence, masks and the owner's inspected sample.
- `screening/`, `spans/`, `dense-spans/`: reader verdicts and interval results.
- `manifests/`: compatible `agent.demos` JSONL. Sources remain
  `inspection_only`, `splittable=false`, patch/cooldowns unknown until their
  independent provenance and split decisions are established. The consumer
  should not treat the new corpus as a new validation/test split.
- `totals.json`: completed download hours, reviewed screened hours and span count.

Existing media in `data/demos/vods` and `data/demos/youtube/reqmr` is on the Mac,
not this PC. Its formats and source groupings are reused; public full VODs are
downloaded afresh rather than waiting for a large Mac-to-PC transfer. The old
Req train broadcast `2873352801` keeps its existing source group. Sources
`2871472478`, `2877719252`, `d0C8RMBnFfA`, `yjc51uOjKEQ` are refused by the scripts;
sealed sessions and existing frozen evidence are never opened or modified.

## Source selection

The kit reference currently reflects Season 10 / Version 20260911. A September
upload or S10 title estimates season; it does not independently prove an exact
balance patch. Do not silently promote that estimate into manifest provenance.

| Creator | Why selected | Evidence limits |
|---|---|---|
| DayMR | James's pick; channel describes rank 1 Spider-Man, One Above All and top-500 lobbies | [Channel upload](https://www.youtube.com/watch?v=wypnTJ3MqrE) explicitly contains promotional claims; leaderboard identity unverified |
| ReqMR | James's pick; longstanding Spider-Man main with rank-1 upload claims | [Rank-1 upload](https://www.youtube.com/watch?v=ruW9Dr_1waQ); not independent leaderboard verification |
| Necros | Well-known Spider-Man main, rank-1 one-trick and tournament gameplay titles; additional creator diversity | [Creator channel](https://www.youtube.com/@necrosow) and [Spider-Man-titled broadcast channel](https://www.twitch.tv/necros); current rank unverified |

Twitch exposes 1080p60 for all three selected sources. YouTube metadata discovery
works, but the first media probe returned a sign-in/bot check; Twitch supplied
full broadcasts without browser or account changes. No bypass was attempted.

## Screening and measured limitations

`scripts/footage_corpus.py` uses existing `perception.events` hero portraits and
killcam/spectating banners, `perception.hud` health/bar and ability icons,
`perception.scoreboard`, and the replay roster detector in `replay_hud`.
Menus, deaths, foreign heroes, spectating, killcams, scoreboards and detected
replays break spans. Unknown readings are retained as unknown. Two distinct
Spider-Man ability icons can establish the hero when the portrait abstains or
mistakes colour-graded Spider-Man for another portrait.

Sparse keyframes are candidates only. Dense screening samples at 2 Hz, trims
each edge inward by 0.5 seconds and requires at least four seconds. Up to two
unknown samples may have temporal support from positive samples on both sides;
known exclusions and missing frames are never bridged. `weak_samples` records
that support. Sub-500ms overlays/transitions can escape sampling. A spot-check
is required before export, and sampling is not a claim of perfect segmentation.

Day's inspected sample shows keyboard HUD binds and a mouse settings page,
no facecam, an animated avatar partly over the ability HUD, chat, music cards,
sponsors and follower alerts. Masks conservatively cover their possible areas;
they do not imply those rectangles are occupied on every frame.

### 2026-09-30 first smoke delivery

12.59 raw hours downloaded and finalized across Day and Necros at the first delivery
(17.05 hours after a second Day broadcast finalized). First Day export:
11 sparse spans / 140 seconds, from a two-hour screened prefix. All 12 inspected
positive frames showed Spider-Man player POV with visible HUD. Twelve rejection
controls covered lobby/hero select, starting screen and spectating, plus valid
gameplay false negatives. The ability-icon extension recovered three of those
false negatives while keeping the inspected exclusion controls rejected.
This is smoke data for IDM, **not the requested two-hour gameplay milestone**.

Sparse recall was poor: 1,006 accepted keyframes out of 3,683, fragmented into
only 140 retained seconds after trims. This prompted the dense pass and added
icon evidence rather than presenting candidate duration as delivered gameplay.

Windows lessons: consumers must wait until yt-dlp finalization finishes. Reading
the raw download early held its filename open and blocked the remux rename;
the owner stopped that reader, retained original bytes as `.source.ts` and moved
the completed remux to the final path. Future catalogue entries require both
the `.part` and `.temp` files to be absent. A failed native probe falls back to
explicitly identified provider metadata; it does not block every other source.

## Commands and cloud work

```powershell
uv tool install yt-dlp
uv run python scripts/footage_corpus.py summary
uv run python scripts/footage_corpus.py screen <final-media> <source-id>
uv run python scripts/footage_corpus.py dense <source-id> --duration 7200
uv run python -m unittest scripts.footage_corpus_test
```

ffmpeg was already installed. Local decode uses bounded frames and at most two
threads. Optional `--cuda` checks that the game is absent before and throughout
NVDEC use, and stops its own decode if the game starts. No desktop input exists.

`scripts/footage_modal.py` downloads explicit public sources inside temporary
cloud containers, screens them and returns JSON metadata/spans only. It mounts
only six named source modules; no credentials, James recordings, sealed data,
or review frames are uploaded. Profile `rivals`, workspace `volpestyle` were
verified on the Mac. Functions use `timeout=7200`, `retries=0`, four maximum
containers, and ephemeral apps; no volume or persistent deployment. A 60-second
pilot completed and its app stopped before the bulk launch. Actual spend belongs
in the lead's existing spend ledger after teardown.

The first cloud pilot caught an unnecessary disk-size override below Modal's
minimum; removing it allowed the pilot to finish. Local CPU decode was slow
amid concurrent transcodes; a short NVDEC probe measured 13x realtime at roughly
630 MB. Cloud CPU screening initially measured about 11x realtime per source.
Raw Windows frame pipes were replaced by bounded JPEG analysis transport;
consumer media stays native and unreencoded.

The finalized Day file has a nominal 60-Hz Twitch profile but ffprobe average
rate of about 59.983 Hz. Catalogue/manifests retain the measured average; IDM
should decode by presentation timestamp rather than assuming frame index / 60
is the exact clock over a whole broadcast.
