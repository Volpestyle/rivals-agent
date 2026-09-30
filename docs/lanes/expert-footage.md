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
| Necros | Well-known Spider-Man main; own channel claims rank 1 and documents tournament gameplay | [Tournament upload](https://www.youtube.com/watch?v=Wx-ncoUWmXg) and [broadcast channel](https://www.twitch.tv/necros); current rank unverified |
| Simii_exe | Well-known Spider-Man main; current broadcast titles claim rank 1 Spider-Man | [Creator archives](https://www.twitch.tv/simii_exe/videos); leaderboard claim unverified |
| Jit (jitnoward) | Candidate elite flex player; titles claim rank 1 world and two MRC championships | [Creator archives](https://www.twitch.tv/jitnoward/videos); claims unverified independently. Inspected sources mostly contain other heroes/watchparty footage; none admitted |

Twitch exposes 1080p60 for the admitted creators. YouTube metadata discovery
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

### Source checks and scaling

Eight distributed frames from `2876184005` showed a Wolverine game, including
cutscenes, rather than Marvel Rivals. Req `2873352801` switches Spider-Man/Jeff
and includes menus/killcams; the readers accepted the two inspected Spider-Man
frames and rejected the other six. Day `2886339556` switches heroes later in
the broadcast, including Gambit, Deadpool, Daredevil and Jeff. Native source
hours therefore remain distinct from screened Spider-Man hours.

Necros `2879205768` supplied a fragmented MP4 that was slow to seek locally.
It was remuxed with stream copy to `.normalized.mp4`, with the original retained.
Its review's `media_path_override` points the catalogue/consumer at that indexed
copy. Eight distributed frames include Spider-Man, other heroes and menus;
the avatar/drops overlay covers part of the lower-left HUD. A later retained-span
check found an occasional facecam at normalized `[.76,.38,1,.72]`; the review
now records it, also inside the conservative right-side chat mask.

To compensate for mixed-hero streams, acquisition was expanded to current-patch
Spider-Man-titled Simii archives and Jit archives, excluding explicitly labelled
reruns and unrelated game titles. Two ephemeral cloud cohorts use four CPU
containers each; the PC only downloads/remuxes and inspects a few frames. The
lead's notice that the game was reopening arrived after the owner had already
stopped local NVDEC. All bulk decode stays in Modal.

Cloud results can be adopted with:

```powershell
uv run python scripts/footage_corpus.py import-cloud D:/rivals-expert-footage/cloud-results
```

The importer checks source identity, geometry and nonoverlapping bounded
timestamps against local media. Span IDs include timestamps, so a later dense
pass cannot reuse a sparse span ID for different footage. Results remain private
metadata; publishing a milestone sends the lead counts and paths, never frames.

### First usable milestone (2026-09-30, 05:34 CDT)

The private export held 669 spans / 3.265 candidate gameplay hours against
33.479 downloaded hours across six completed sources. Req `2873352801` supplied
2.329 hours and Necros `2879205768` 0.898 hours; the balance was the earlier
Day sparse sample. Twelve distributed retained-span midpoints from each dense
source were inspected: 24/24 showed Spider-Man player POV with HUD. This is
sampled validation, not a claim that every frame is labelled correctly. The
lead and IDM received the export paths and limitations; Linear owns acceptance.

Day `2883793845` was withheld after its retained-span audit found multiple other
heroes. The old one-class portrait matcher scored Gorr, Daredevil and Captain
America around 0.34, inside its weak Spider-Man band. The footage classifier now
requires independent ability evidence for a weak portrait match and never
overrides an explicit known-other-hero match. Six inspected failure frames are
rejected and both inspected Spider-Man controls pass. New cloud screenings retain
numeric reads for later tuning without another decode. Existing accepted Req and
Necros results retain their sampled-v2 provenance; new results name v3.

The first diversity batch stopped on Twitch's changing HLS initialization
fragments. The retry uses FFmpeg's HLS demuxer for that specific format error;
an individual unavailable source now returns an error record and cannot abort
the rest of the batch. No authentication or access-control workaround is used.
The failed batch was confirmed stopped with zero containers. V3 Day and
diversity runs remain bounded by 7,200-second function timeouts and ephemeral
CLI lifetimes. No PC GPU or game input is used.

Further distributed samples show that Day `2882124665` changes to Fortnite and
a bomb-defusal game, and `2879354299` ends with Fortnite and an esports
watchparty. The latter's tail from 25,000 seconds is conservatively withheld by
the review's `exclude_intervals`, even if a broadcast hero HUD passes a reader.
Refresh applies these exclusions to both consumer formats and computes hours
from the exported intervals. Withholding a source also removes its own generated
manifest, preventing a stale manifest from bypassing the current review.

Simii `2879380353` has an upper-left facecam and chat beneath it; distributed
samples show multiple heroes and menus. Its indexed, lossless remux is used for
local seeking. Retained-span checks are still required before that source is
exported. The catalogue deduplicates retry metadata by video ID while retaining
failed downloader files for diagnosis. A Windows FFmpeg process created at
BelowNormal stalled; the identical single-thread native-frame command at normal
priority completed in 0.36 seconds. Normal-priority local work is limited to
brief frame checks and stream copies while the game is confirmed closed.

Two cloud preemptions restarted longer scans. Subsequent targeted CPU calls use
`nonpreemptible=True` (client 1.5.5), retaining the 7,200-second timeout and
ephemeral lifetime. [Modal documents the 3x CPU/memory multiplier](https://modal.com/docs/guide/preemption).
This avoids another full-video restart; no persistent volume was added.
Jit `2887910767` proved to be an ongoing live stream (`is_live=true`), despite
appearing in the archive listing. Its partial download is withheld and the owner
stopped that download. New cloud code skips live/unfinished sources before media
acquisition; the older running image does not yet contain that correction.

### Native portrait profiles

The generic portrait/ability geometry missed every retained second in the first
full Simii scan. A native portrait profile compares the fixed HUD crop against
a human-inspected Spider-Man frame from the same video, retaining the existing
HUD, death, banner, scoreboard and replay exclusions. Two independent ability
icons can still corroborate Spider-Man under colour effects. Reference IDs and
timestamps live in `scripts/footage_modal.py`; no third-party raster is committed
or returned by the cloud worker. The reference frame is extracted privately from
the downloaded public source. A same-channel reference is available for other
Simii videos and is recorded in each result.

On 64 human-inspected native development controls, excluding each fitted
reference frame, v3 kept 5/10 Spider-Man positives and admitted 1/54 exclusions;
v4 kept 10/10 positives and admitted 0/54 exclusions. The private working table
is `D:/rivals-expert-footage/audit/profile-validation.json`. These are small-sample
checks, not whole-corpus accuracy or a sealed evaluation. Bulk v4 results still
require retained-span inspection. Per-video profiles are needed because HUD
geometry and portrait framing differ even across Day broadcasts.

The observed scoreboard tap in Day `2882124665` was shorter than the sample
interval: native 1594.0 seconds is a scoreboard, whereas 1593.75 and 1594.25
are gameplay, and the latter's HP matches the cloud read. This demonstrates the
documented sub-500ms limitation rather than a broken scoreboard reader. Its
touching span remains explicitly excluded. Review intervals are applied after
screening, so later classifications cannot restore that known bad span or the
unrelated-game/watchparty tails.

Network seeking for a one-second Twitch reference clip stalled or returned an
empty fragment. Subsequent reference extraction uses a full temporary public
download and local seek, the same path that already decoded successfully. The
completed v3 sources remain usable while v4 is checked; a rescreen is not
automatically promoted over an inspected result.

### Consumer delivery and admission safeguards

The completed 20-hour target is recorded in
`D:/rivals-expert-footage/README.md` and `totals.json`; the consumer reads
`idm-spans.jsonl` through the existing junction. Source grouping remains by
whole video. The retained source mix includes Day, Req, Necros and Simii;
Jit's inspected mixed-hero/watchparty sources remain withheld. The only
publishable visual is the counts-only `metrics/corpus-progress.png`; private
native review sheets and all third-party clips stay local.

Each classifier generation needs its own approval. Refresh withholds a
rescreen whose version differs from `approved_classifier_version`, and removes
its generated manifest to prevent a stale consumer bypass. An integration test
exercises that path without opening the corpus. A media-path override must name
its own video ID, preventing copied review fields from pointing at another
broadcast. Mask fields are copied explicitly, never the entire review.

Native checks found brief scoreboard taps in three new sources. Their whole
touching spans are removed by review intervals; twelve additional retained
midpoints per affected source then showed Spider-Man player POV with HUD.
Simii `2887257689` also admitted a Phoenix killcam: its portrait and ability
checks produced a false positive, and the existing banner reader did not
recognize the current banner placement. That entire source remains withheld,
rather than treating its candidate hours as delivered. This is a demonstrated
limitation of v4, alongside the known sub-500ms sampling limit. Spot checks do
not establish every-frame purity; downstream IDM should preserve these
limitations and treat uncertain transitions conservatively.

All footage Modal apps were observed stopped with zero tasks after the final
cohorts completed. They used ephemeral CPU containers only, with bounded
timeouts and no persistent volume. A local `metrics/cloud-usage.json` records
the app IDs and resource estimates for the lead's spend ledger; exact billed
usage is not exposed by the CLI used here. No PC GPU was used for this corpus.

### Expansion: current-patch diversity and v5 exclusion

The next requested consumer volume is about 50 admitted hours. New discovery
prioritizes Luckyzeal (broadcast title: top 2 global / number 1 NA Spider-Man),
RekRiot (broadcast title: top 3 Spider-Man / Season 10), and 6ftHumbleArab
(Spider-Man-specific broadcasts; a same-name Season 10 player appears as
Celestial 2 on the [third-party hero leaderboard](https://rivalsdata.com/heroes/spider-man/leaderboard)).
Their primary archive URLs and claim limits are stored in the external
`experts.json`; a matching display name is not authenticated leaderboard identity.
Keyboard prompts must be inspected before admission. Humble's source stream is
1664x936 at 60 fps, below the preferred 1080p; retain the true native geometry
and prioritize the other creators' 1080p sources rather than upscaling metadata.

V5 adds a conservative current-patch yellow exclusion detector: yellow ink must
occupy more than 8% of both the measured respawn-counter region and its adjacent
status-heading region. This catches the moved PAST LIVES/SPECTATING banners
that the older word template missed. On 330 retained/distributed native working
frames it detected eight exclusions: four hero-select screens, two spectating
frames and two killcams, all inspected; it did not flag the inspected retained
gameplay controls. The numeric table is private
`D:/rivals-expert-footage/audit/banner-controls.json`. This is development
evidence, not full-video or sealed accuracy. Known scoreboard-tap limitations
remain. Each new source still needs its twelve retained-midpoint checks.

Cloud profile times can now be supplied as a JSON mapping to the local entry
point, avoiding a code change for each inspected public source. Bulk processing
retains native function timeouts and ephemeral CPU containers. Source batches
are reported to IDM as soon as their reviews pass.

The Mac's installed CLI does expose `modal billing`. Its hourly report returned
the first session's actual app usage, recorded in the requested
[spend ledger](../steering/spend-ledger-20260927.md); the earlier availability
assumption and configured estimate are superseded by that report.

Luckyzeal's bottom-left avatar covers the hero portrait across multiple heroes.
Native portrait profiles are therefore explicitly refused for that channel.
V6 can resegment retained numeric reads without decoding again: an unknown
hero read needs a named Spider-Man ability plus independently read 250 maximum
HP, or 250 current HP with a measured full health bar. Known exclusions and
explicit foreign-hero readings remain rejected. On 72 private development
controls this recovered two additional positives and introduced no additional
false positives; the generic baseline's existing one false positive remains.
The table is `audit/masked-validation.json` in external storage. An offline
regression check specifically prevents a killcam or foreign HP reading from
being restored. New v6 candidates still need the twelve native retained checks.

RekRiot's first inspected broadcast includes watching DayMR's gameplay. Its
tail from 2,900 seconds is conservatively withheld, including later own-play
sections; a fresh retained sample of the earlier own-play prefix passed. This
is why player HUD alone does not establish source provenance. Later broadcasts
need their own distributed and retained checks. Humble's music card is at right
centre and Twitch chat can overlap the bottom-right ability prompts; native
inspection corrected its masks before further consumer use.

Additional diversity discovery includes rdpaco, whose primary Season 10 archive
titles claim One Above All / rank 1 Spider-Man peak. That is a creator claim,
not independent rank verification. Tephrite's explicitly controller-titled day
is excluded from acquisition; other available titles emphasize different heroes
or tournaments. Source metadata and claim links remain in external `experts.json`.

The expansion uses creator diversity before more Day/Simii volume. Rdpaco's
first generic retained sample exposed an other-hero false positive and a
scoreboard. A native portrait rescan, explicit exclusion of those intervals
and a fresh twelve-frame retained sample passed; the generic result was never
admitted. Rdpaco has both facecam and camera-free broadcasts, so masks are
reviewed per video rather than copied across the channel blindly. RekRiot's
French UI and own gameplay are checked against explicit playback controls;
conservative brackets remove observed secondary-video intervals. Luckyzeal's
mixed broadcasts have low admitted yield: Fortnite duration and other heroes
are withheld even when their archive titles claim Spider-Man-only play.

The external export check verifies unique timestamp IDs, ordered nonoverlapping
spans, complete local media, native geometry/FPS, keyboard/mouse-only admission,
classifier/review agreement, normalized rectangles, interval exclusions and
manifest/video membership. `agent.demos` loaded all milestone manifests with
unknown patch/cooldown provenance and one-video groups preserved. The current
consumer catalogue and counts live only in the external README/JSONL, reached
through the repository's ignored junction. Milestone PNGs use our aggregate
counts only; private frame sheets remain under external `audit/`.

A known Simii retry file is about ten seconds shorter than the cloud/provider
video (27,740.028665 versus 27,750 seconds). Its native retained frames disagree
with the cloud reads at the purported timestamps. The entire source remains
withheld; it was never admitted. Cloud import now refuses local/provider duration
differences above two seconds, allowing provider rounding but rejecting this
observed discontinuity loss. The offline regression check covers refusal before
writing spans and a valid rounded-duration control. All currently admitted
sources differ by less than one second in the same audit. Nine offline checks
and Ruff passed. This catches the demonstrated mismatch; matching duration alone
is not a proof that independently downloaded streams are byte-identical.

Twitch game-category changes can lag the actual switch to another game.
Rdpaco's Wolverine tails are therefore bracketed from native frames, using
category chapters only as supplementary evidence. Humble's later broadcasts
include VOD reviews with top team rosters and playback controls; conservative
tail brackets remove those reviews before another twelve retained native checks.
These are source-provenance exclusions, separate from the hero/HUD classifier.

The 50-hour export uses the same twelve retained native midpoint checks per
source, followed by the external export validator and the repository manifest
loader. New batches are sent to IDM immediately after the atomic refresh. The
counts-only milestone chart and measured totals live in external
`metrics/corpus-progress-50h.png` and `metrics/milestone-50h.json`; subsequent
completed sources appear in the current README/export without rewriting that
milestone snapshot. Source masks are measured separately: the final white-shirt
Rdpaco broadcast places its facecam lower than the black-shirt broadcast.


## Read-only IDM labelling page

`scripts/idm_board.py` projects published metadata for `/idm-labelling` on the
Mac training board; the main page links it. A separate 30-second background SSH
fetch runs its stdlib collector on the PC, with a 15-second timeout. Page
requests never wait for SSH. It opens only the external catalogue/spans,
explicit `idm-*` job receipts, and the first bounded line of each v2-a/v2-cd
label file. No action rows, frames, checkpoints, supervisor internals or GPU
work are read. A malformed header cannot fall through to action rows.

IDM owns the optional `C:/Users/volpe/jobs/idm-labelling.json` receipt: supervisor
state/reason, per-video state/count/hours/update, throughput/ETA, and published
per-creator expert-check accuracy. Missing values remain unknown; an aggregate
`done` job receipt never means all corpus spans were labelled. Partial span
counts cannot establish partial duration without knowing which spans were
labelled. Fully labelled videos can use admitted durations from the catalogue
export. Cached counts survive a failed fetch with a visible warning and an
unconfirmed supervisor state. Backups beside the Mac scripts use `.bak`.


The IDM receipt publishes `pending|partial|labelled|exported` per video. The
page maps these to queued/labelling/done and applies the published supervisor
pause/hold to unfinished rows. The superseded v2-a set is held. An exported
video may have refused spans, so the displayed count stays below its denominator;
processing completion is not invented label coverage. The expert-check value
is a yaw/image-shift slope relative to James, not classification accuracy; the
page retains its metric, sample count, source, DayMR uncertainty flag and the
separate press spot-check precision. Throughput/ETA remain owner-reported.
The metadata sidecar refreshes roughly every two minutes; the page/fetch refresh
is 30 seconds. Thirty-two synthetic tests and Ruff passed, and live Mac HTTP
checks confirmed both sets, forty videos per set and eight creator/check rows.

## Private span and actual-label review (2026-09-30)

James authorized bounded action-row reads and third-party review clips on the
private tailnet board. The metadata collector above retains its header-only
contract; `/idm-review/` adds video timelines, per-span label availability,
actual yaw/pitch traces and separate held/press strips. Per-step camera deltas
are divided by the header step duration for deg/s; positive pitch points down.
Unknown action labels stay unknown. Availability comes from exported segment
rows, so refused spans are not presented as labelled.

`scripts/idm_clip_renderer.py` owns the PC queue under
`D:/rivals-expert-footage/private-review`; `worker --sync` serves requests and
copies explicit projections and clips to `/Users/james/dev/idm-review` on the
Mac. Indexing streams at most 1 GiB/120 seconds per changed label file; a selected
span reads at most 32 MiB/10,000 rows. Video availability refreshes every ten
minutes. Requests show queued/rendering/paused status and refresh every five
seconds; ready playback is uninterrupted. Rendering uses software decode,
two FFmpeg threads, BelowNormal priority, and a 180-second deadline. A process
check before and throughout rendering yields to Marvel-Win64 or obs64, including
tray OBS. Sealed paths, symlinks and Windows reparse points are refused.

Sixteen 10-second, 960x540 samples cover all eight creators. A seventeenth clip
verified the complete tailnet POST-to-PC-queue-to-Mac-playback path for v2-a;
v2-cd playback and the 358-span ReqMR timeline also passed browser checks.
The focused board/viewer suite passes 51 tests and Ruff passes. The Mac helper
backup is `scripts/idm_board.py.pre-span.bak`; explore-policy performed the single
coordinated service restart. Local/cloud spend for this viewer is $0.

Playing-clip/strip screenshots are private at
`D:/rivals-expert-footage/private-review/span-view-private.png` and
`on-demand-private.png`, mirrored under the Mac review directory. They contain
third-party footage and must not be attached to Linear or the blog. No media or
label projections enter git. Restart the persistent PC queue worker with
`uv run python scripts/idm_clip_renderer.py worker --sync` if it exits; its
singleton lock prevents two workers from rendering concurrently.
