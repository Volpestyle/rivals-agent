# Demonstrations: dataset format and loader (VUH-1308)

**Built and tested offline.** `agent/demos.py` is one on-disk format and one loader for three kinds of source:
expert VOD clips (no inputs), the agent's own range recordings (pad state as the input modality), and later human
annotations. It reads the design in [learning-plan.md](../learning-plan.md) and the "Direction" section of
[plan.md](../plan.md); it adds no competing schema. Stdlib only: 41 tests in `tests/test_demos.py`, plus two that read the
real `data/l1/tagrun0` and the Req sample manifest when they are on the machine. Nothing is committed.

```sh
uv run python -m agent.demos data/demos/samples data/l1/tagrun0     # one summary line per clip
uv run pytest tests/test_demos.py
```

```python
from agent.demos import Demos
demos = Demos.load("data/demos/samples", "data/l1/tagrun0")
for obs in demos.observations("train"):                 # what a policy may see: nothing after obs.t
    ...
for s in demos.samples("val", hindsight=True):          # + labels, and the outcome window after t
    ...
```

Media is never copied or re-encoded, and there is no database: a clip is one JSONL manifest beside the media where it
already lives (`data/demos/samples/<clip>.manifest.jsonl`), and the loader hands back frame references, not pixels.

## Shape of the data

```mermaid
flowchart LR
  V["VOD clip: mp4 + manifest.jsonl<br/>no inputs"] --> L[Demos.load]
  R["range run: frames.jsonl + jpgs<br/>loaded as it is, no manifest"] --> L
  E["events JSONL<br/>(HUD lane, perception/events.py)"] --> V
  A["annotations JSONL<br/>(later)"] --> V
  L --> S["splits by group<br/>before any window is cut"]
  S --> O["observations(split)<br/>past only"]
  S --> H["samples(split, hindsight=True)<br/>labels + outcome window"]
```

One decision, on the clip's own clock (every `t` is seconds from the start of the media):

```
clip time   0 ---- 7.6 | gap | 18.0 ------------------------------ 43.0 | gap | 43.8 ---- 59.8
segments    [ seg 0    ]      [ seg 1                                  ]      [ seg 2       ]
                              started_by=hero_returned          ended_by=no_hud
decision                                     t=30.0
observation                        [25.0 .......... 30.0]   frames, events with t_to <= 30.0, inputs
hindsight                                            (30.0 .......... 35.0]   outcome window, still inside seg 1
```

Nothing crosses a boundary: history is clipped to the segment's start, the outcome window to its end, and a window cut by
the segment says why (`ended_by`, `truncated`). A decision needs a frame proven inside a segment.

## The manifest

A manifest is JSONL: one `{"type": "clip", ...}` header, then zero or more `{"type": "segment", ...}` lines. Every header
key below except the last group must be present; a value that does not apply is `null`, never omitted, so absence is never
silent. Unknown extra keys are kept and ignored.

| Key | Meaning |
|---|---|
| `id` | unique clip id (`reqmr-2873352801-1920`; runs are `run:<dir name>`) |
| `kind` | `vod` \| `run` \| `human` |
| `source_url`, `vod_id`, `creator`, `retrieved` | where a VOD came from and when it was fetched (`null` for a run) |
| `run` | the recorder's run name (`null` for a VOD) |
| `source_start_s`, `source_end_s` | the clip's start and end on the source's own clock (a VOD's seconds); `source_time(t) = source_start_s + t` |
| `resolution` | `[width, height]` of the media (`null` if unknown) |
| `fps` | nominal frame rate (a video clip needs it: frame times snap to its grid) |
| `hero` | who is played |
| `overlays` | what covers the screen (list of strings; `[]` for none) |
| `split` | `train` \| `val` \| `test` \| `inspection_only` \| `null` (assign by group) |
| `media` | `{"kind": "video", "path": ...}` or `{"kind": "frames", "dir": ..., "index": "frames.jsonl"}`; paths are relative to the manifest |
| `inputs` | `"pad"` or `null`: the input modality this clip has |
| `events`, `annotations` | relative path of the companion JSONL, or `null` |
| `segments_from` | who drew the segments: `segmenter` \| `annotator` \| `assumed_whole_run` |
| optional | `group` (split unit, default the VOD id or run name), `duration_s`, `alignment`, `licence`, `notes`, `decisions` (clip times to sample instead of a grid) |

**Segments** are the stretches proven usable: `start_t` (first frame proven inside), `end_t` (last frame proven inside),
`started_by`, `ended_by`. What lies between two segments is unproven, and its width is the boundary's uncertainty: an
unreadable interval is a gap, never bridged. The reasons are the HUD segmenter's own, plus refinements an annotator may use:

| Ended by | Meaning |
|---|---|
| `run_end` | end of the clip or recording |
| `death` | hp reached zero |
| `not_our_hero` | the hero played is known not to be ours (refines to `spectating`, `hero_swap`) |
| `no_hud` | the HUD is gone (refines to `menu`, `brb`, `unreadable_hud`) |

Started by: `run_start`, `respawn`, `hero_returned`, `hud_returned`. Any other value is refused when the manifest loads, as
are overlapping or out-of-order segments and a segment that outlives the clip.

## Events: consumed as the HUD lane writes them

`perception/events.py` emits one JSON object per transition, `asdict(Event)`: `kind`, `i_from`, `t_from`, `i_to`, `t_to`,
`slot`, `amount`, `before`, `after`, `segment`. It is read unchanged. Two things matter to the loader:

- **An event is an interval, never an instant.** `t_from` is the last frame showing the old value, `t_to` the first showing
  the new one. There is no press time, and an unreadable stretch simply widens the interval. At decision time `t` an event
  is *known* only if `t_to <= t`; one with `t_from <= t < t_to` is still pending and belongs to hindsight.
- **An event lies inside one segment.** The loader assigns it to a segment by time (the file's own `segment` index is only
  a hint, so editing segments cannot silently mis-assign events) and refuses the file if an event crosses a boundary or
  sits in a gap. `type` is optional on an event line; `{"type": "segment", ...}` lines may share the file and are ignored
  by the loader (`events_file_segments` turns them into manifest segments).

`t_*` must be clip time, seconds from the first frame of the media. The two sample clips were sampled at 5 fps, so `t = n / 5`.

## Annotations (the pilot's fields, one line each)

```json
{"type": "annotation", "t": 30.0, "by": "annotator-1", "assisted": false, "situation": "closing on a bot",
 "actions": ["engage"], "target": {"bbox": [900, 400, 940, 470], "frame_t": 30.0}, "evidence": [29.6, 30.0],
 "uncertainty": "low", "unusable": null, "outcome_review": "the attack landed"}
```

`actions` are candidate actions (several are allowed; `["none"]` is a no-engage decision), `target` is a box in the original
pixels of a stated frame, the string `"unknown"`, or `null` (not stated), and `unusable` carries the reason a window cannot
be labelled. Several annotators give several labels for one decision; `assisted` marks a model's proposal, which is not
human ground truth. `outcome_review` is a separate field: it is returned only inside hindsight and never becomes part of a
label. Codex's annotation specification owns the vocabulary; this is the representation it lands in.

## Range recordings load unchanged

A recorder's run directory needs no manifest: `Demos.load("data/l1/tagrun0")` synthesizes one in memory and writes nothing
(a test snapshots every byte and mtime before and after). Both recorders' `frames.jsonl` shapes load:

| Recorder | Rows | Inputs |
|---|---|---|
| L4's trials (`tagrun*`) | a row per control tick (about 30 Hz), `file` and `i` on every third | every row with a `pad`; `note` is the intent it logged |
| L1's `record.py` (`data/run1`) | a row per saved frame | the pad on each frame row; `step` becomes the note; `pad_age`, `idle_warning` are kept in `extra` |

The synthesized clip is one segment start to end (`assumed_whole_run`: the recorders refuse to send input off the range HUD),
hero `spider-man` by convention, resolution read from the first JPEG's header, fps from the median frame gap. A
`manifest.jsonl` inside a run directory replaces the synthesized one, which is how a run gets real segments or an events
file. Directories that hold only jpgs (`data/l1/run1`, `full`, `trial1`) have no index and are refused.

## Samples, and why the future cannot leak

| Guarantee | Enforced by | Pinned by |
|---|---|---|
| An `Observation` holds nothing later than `t` | every source is cut off at `t` before it is read, and `Observation` refuses to be constructed with a later frame, event or input (`LeakageError`) | `test_an_observation_refuses_to_hold_anything_later_than_t`, `test_no_future_datum_is_reachable_from_an_observation` (rows and events carry their own time, and the whole object graph is walked) |
| No route from an observation to labels or the outcome | `Observation` has no such field and no reference to the clip; `observations()` never builds hindsight | `test_the_policy_facing_types_have_no_route_to_labels_or_outcomes` |
| Hindsight is opt-in | `samples(..., hindsight=True)`; the default returns `hindsight=None`, and asking for it changes nothing else | same test, `test_the_outcome_is_strictly_after_t` |
| An event still pending at `t` is not known at `t` | events filter on `t_to <= t` | `test_events_are_intervals_and_a_pending_one_is_hindsight` |
| Nothing crosses a segment | history starts at the segment's start, the outcome ends at its end, a decision needs a frame inside the segment | `test_nothing_crosses_a_segment_boundary`, `test_a_decision_never_snaps_to_a_frame_outside_its_segment` |
| A label is a target, not an input | recorded-input labels take pad states strictly after `t`; annotation labels are separate objects | `test_a_run_has_pad_inputs_...`, `test_annotations_carry_an_explicit_unknown...` |
| The split is named and whole recordings stay together | `samples(split)` requires the split; assignment is by group | the split tests below |

What this does not stop: code that asks for hindsight and then feeds `sample.hindsight` to a policy. The type is named for
what it is and the policy-facing path (`observations()`) has no way to reach it.

**Missing modalities are explicit, never filled.** `inputs` is `None` for a VOD (and for a run whose manifest says `null`
even though its rows carry pad states); `events` is `None` when there is no event stream, and `()` only when a stream exists
and nothing happened in the window; `labels` is `()` when a decision is unlabelled. Frames are always present.

**Splits.** `split` is assigned per *group*, never per window: a group is the VOD id by default, so cuts of one VOD stay
together; mirrors and re-uploads are given the same `group`. An explicit `split` wins and the rest of its group inherits it;
an unassigned group is hashed (`sha256(seed:group)`), so the assignment depends only on the group and the seed and does not
move when other clips are added. `SplitError` refuses a group with two explicit sides or one VOD in two groups, and
`check_splits` proves no group is on two sides. Windows are cut only after that, from the requested side.

## Trimming keeps source timestamps

`trim(rows, start_t, end_t, new_id, media_path)` returns the manifest rows for a sub-clip: times are re-based,
`source_start_s` moves forward by `start_t` so `source_time` still names the same moment of the VOD, and a segment cut at the
new edge starts as `run_start` or ends as `run_end`. Events and annotations are not rewritten here; whoever cuts the media
re-cuts them, and the loader refuses events that no longer fit the segments.

## Worked example: the Req sample clip

`data/demos/samples/reqmr-2873352801-1920.manifest.jsonl` (built from the HUD segmenter's real output; header abridged):

```json
{"type": "clip", "id": "reqmr-2873352801-1920", "kind": "vod", "source_url": "https://www.twitch.tv/videos/2873352801",
 "vod_id": "2873352801", "creator": "reqmr", "retrieved": "2026-09-20", "run": null, "source_start_s": 1920, "source_end_s": 1980,
 "resolution": [1920, 1080], "fps": 60, "hero": "spider-man", "overlays": ["chat intermittently covers the rightmost abilities and the ult"],
 "split": "inspection_only", "media": {"kind": "video", "path": "reqmr-2873352801-1920.mp4"}, "inputs": null,
 "events": "reqmr-2873352801-1920.events.jsonl", "annotations": null, "segments_from": "segmenter", "alignment": "requested",
 "licence": "unverified", "duration_s": 60.083, "decisions": [5, 15, 30, 45], "notes": "..."}
{"type": "segment", "start_t": 0.0, "end_t": 7.6, "started_by": "run_start", "ended_by": "death"}
{"type": "segment", "start_t": 18.0, "end_t": 43.0, "started_by": "hero_returned", "ended_by": "no_hud"}
{"type": "segment", "start_t": 43.8, "end_t": 59.8, "started_by": "hud_returned", "ended_by": "run_end"}
```

An event line beside it (`reqmr-2873352801-1920.events.jsonl`, 30 lines, events only; the one the decision below meets):

```json
{"kind": "hp_lost", "i_from": 150, "t_from": 30.0, "i_to": 152, "t_to": 30.4, "slot": null, "amount": 45, "before": 250, "after": 205, "segment": 1}
```

What the loader returns for the decision at clip time 30.0 (`samples("inspection_only", hindsight=True)`):

```
observation  clip reqmr-2873352801-1920, segment 1, t 30.0, context_start 25.0, truncated_context False
             26 frames: video refs (path + clip time, no pixels) every 0.2 s from t=25.0 to t=30.0, the last at 30.0
             events []   (the hp_lost [30.0, 30.4] is pending at 30.0: its confirming frame is after the decision)
             inputs None (a VOD)
labels       ()          (nothing annotated)
outcome      t_end 35.0, 25 frames, events hp_lost [30.0, 30.4], ability_used swing [33.6, 34.0], ability_ready swing [34.0, 34.4]
             ended_by None, truncated False
source_time(30.0) = 1950.0
```

The pilot's decisions are `[5, 15, 30, 45]`. `samples("inspection_only", decisions="manifest")` yields 5, 30 and 45 and skips
15: it lies in the gap (7.6, 18.0), where the portrait check says the hero is not ours. That is the deliberate spectator
negative. The skip is reported in `demos.skipped` as `(clip, 15.0, "outside_segments")`, and an annotation saying why
(`unusable: "spectating another hero"`) is kept on the clip.

## What the real data showed

- **Req.** The HUD segmenter (`perception.events`, run over the clip at 5 fps) gives three segments, 48.6 s usable, 246
  decision times at 5 Hz, 30 events. +15 s is outside every segment and its hp read 663, the value the segmenter's
  docstring warns about. +5, +30 and +45 s are inside.
- **Day** (`daymr-2879354299-21600-60s`). Nine segments, several three or four frames long, 44.0 s usable, 229 decision
  times, 24 events. hp at +5/+30/+45 reads 250/242/99, as the inspection notes say. The fragmentation is probably the
  avatar, sponsor and chat overlays read as HUD dropouts; that is an honest gap, not something the format should bridge.
  Ten frames read hp 0 (a `death` segment end at 45.4 s) and the stretch to 56.2 s is outside every segment; nothing in the
  notes explains it, so it is recorded, not resolved.
- **The ammo channel reads nothing** on either VOD (`webs` is `None` on 299 of 300 frames), so there are no
  `web_cluster_fired` events. That is the HUD lane's, not the format's.
- **The clips are variable frame rate.** Req has 4082 frames counted in 60.08 s while ffprobe reports 60/1; sampling at 5 fps
  aligns to the source only to about one source frame (16-50 ms). Manifests carry `alignment: "requested"`: the requested
  start is not frame-verified, and a video frame reference is a time on the nominal grid, to be decoded by timestamp.
- **`tagrun0`.** 2070 rows, 609 with frames, 70.0 s, native 2560x1440, 9.21 fps, pad at about 30 Hz, notes Search / stand /
  Engage / Combo. It loads as one segment and yields 349 decision times at 5 Hz. All five real clips (three runs, two VODs)
  load in 0.05 s and iterate 1,320 samples with hindsight in 0.09 s.
- **Two recorders, two row shapes** (above), and three run directories that are jpgs only.

## Asks for the HUD lane (through the lead)

The event stream needs nothing new for the interval semantics: `i_from/t_from`/`i_to/t_to`, the reason vocabulary and the
segment index all fit. Three small things would remove hand steps:

1. **Write the segments down.** `python -m perception.events` prints segments but writes only events. If the per-clip file
   carries `{"type": "segment", ...asdict(Segment)}` lines (and optionally `"type": "event"` on events), a manifest is one call:
   `write_manifest(path, header, events_file_segments(events_file))`. Today the manifest is built from a run of the
   segmenter's Python API.
2. **Say what `t` is.** In the format section: `t_*` is clip time (seconds from the first frame of the media), the sampling
   fps used, and that `i_*` indexes that sampling.
3. **Location.** `data/demos/events/<clip-stem>.jsonl` works as is: the manifest's `events` is any path relative to the
   manifest, e.g. `../events/<stem>.jsonl`. The two current manifests point at `<stem>.events.jsonl` beside them and can be
   repointed when the files move.

## Decisions and what was not built

- **Segments are the proven-usable intervals, not a partition.** The HUD segmenter records the last frame proven inside
  and the first frame proven inside the next; the frames between are unproven. Keeping that gap, rather than inventing a
  boundary time, is what "never bridge an unreadable interval" means in a file format.
- **Events belong to segments by time.** The alternative (trusting the file's segment index) breaks silently the first time
  a person edits a segment.
- **No decoder, no pixels.** A frame is a reference (a jpg path, or a time in a video). Decoding, resizing, masking
  overlays and the class balance the plan asks for belong to the training side; this keeps the loader standard-library only.
- **Run manifests are not written to disk.** The recordings belong to other lanes and are still being appended to; a
  manifest inside a run directory is opt-in.
- **`hero: spider-man` for runs is a convention, not a measurement.** The range recorders switch to Spider-Man first and
  refuse to act off the range HUD.
- **The spectator negative is a skipped decision, not a sample.** If annotators need the preceding context of a negative
  presented, an `unusable_context()` view can be added; today its annotation is kept and reported.
- **Not built:** video decoding, an annotation tool, event and annotation re-cutting on `trim`, verification of `alignment`,
  any training or sampling-weight code.

Mutation checks: 19 hand-made breakages of `agent/demos.py` (a guard removed, a pending event counted as known, history or
outcome crossing a boundary, a filled-in missing modality, a split per clip instead of per group, a lost source clock, an
outcome review folded into a label, ...) each fail at least one test; two escaped at first and now have tests.
