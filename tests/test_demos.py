"""agent/demos.py: format validation, segment boundaries, leakage, missing modalities, split integrity. Stdlib only, offline.

Synthetic clips are built in tmp_path; the real-data tests at the end skip only when data/ is absent, never on a format mismatch.
"""
import dataclasses
import json
import os
import random
from pathlib import Path

import pytest

from agent import demos
from agent.demos import (AlignmentError, Demos, FormatError, LeakageError, Mask, Observation, ProvenanceError, RegimeError, SplitError,
                         FrameRef, Event, Input)

ROOT = Path(__file__).resolve().parent.parent


# --- builders --------------------------------------------------------------------------------------------------------
def header(**kw):
    h = dict(id="vodA", kind="vod", source_url="https://example.invalid/videos/111", run=None, vod_id="111", creator="someone",
             retrieved="2026-09-20", source_start_s=1000.0, source_end_s=1060.0, resolution=[1920, 1080], fps=60, hero="spider-man",
             overlays=["chat"], split=None, media={"kind": "video", "path": "vodA.mp4"}, inputs=None, events=None,
             annotations=None, segments_from="segmenter", duration_s=60.0, cooldowns="normal", patch="Season 10, Version 20260911",
             patch_from="broadcast_date", splittable=True, edited_upload=False)
    h.update(kw)
    h.setdefault("cooldowns_from", "none" if h["cooldowns"] == "unknown" else "broadcast_date")
    return h


SEGS = [dict(start_t=0.0, end_t=20.0, started_by="run_start", ended_by="death"),
        dict(start_t=30.0, end_t=50.0, started_by="respawn", ended_by="no_hud"),
        dict(start_t=55.0, end_t=60.0, started_by="hud_returned", ended_by="run_end")]
EVENTS = [dict(kind="hp_lost", t_from=4.0, t_to=4.2, slot=None, amount=75, before=250, after=175),
          dict(kind="ability_cast", t_from=10.0, t_to=10.4, slot="get_over_here", amount=8, before="off", after=8),
          dict(kind="hp_lost", t_from=12.9, t_to=13.3, amount=25, before=175, after=150),      # still pending at t=13.0
          dict(kind="slot_available", t_from=18.0, t_to=18.2, slot="get_over_here", before=False, after=True),
          dict(kind="slot_unavailable", t_from=36.0, t_to=36.2, slot="swing", before=True, after=False),
          dict(kind="charges_spent", t_from=44.9, t_to=45.1, slot="swing", amount=1, before=3, after=2)]


MAPPING = {s: s for s in ("teamup", "swing", "get_over_here", "uppercut")}
META = dict(type="meta", format=4, source="x", layout="mk", frames=601, fps=10.0, t_origin="first frame of the media", pts_origin_s=0.0,
            cuts=0, slot_mapping=MAPPING, slot_mapping_from="ability icon matched by shape, voted over sampled frames",
            observed={"get_over_here": {"casts": 2, "countdown_mode": 8}})


def with_pos(e):
    """An event as the format 4 extractor writes it: a named slot has the layout position it fired in (identity mapping here)."""
    return {**e, "slot_pos": e["slot"]} if e.get("slot") and "slot_pos" not in e else e


def jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def make_vod(tmp, name="vodA", segs=SEGS, events=None, annotations=None, **kw):
    """Writes <name>.manifest.jsonl (and the events/annotation files it names). Returns the manifest path."""
    h = header(id=name, media={"kind": "video", "path": f"{name}.mp4"}, **kw)
    if events is not None:
        jsonl(tmp / f"{name}.events.jsonl", [META] + [with_pos(e) for e in events])
        h["events"] = f"{name}.events.jsonl"
    if annotations is not None:
        jsonl(tmp / f"{name}.annotations.jsonl", annotations)
        h["annotations"] = f"{name}.annotations.jsonl"
    path = tmp / f"{name}.manifest.jsonl"
    demos.write_manifest(path, h, segs)
    return path


def write_jpeg_header(path, w, h):
    path.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xE0, 0, 4, 0, 0, 0xFF, 0xC0, 0, 11, 8]) + h.to_bytes(2, "big") + w.to_bytes(2, "big")
                     + bytes([1, 1, 0x11, 0, 0xFF, 0xD9]))


PAD = dict(lx=0.0, ly=1.0, rx=0.25, ry=0.0, lt=0.0, rt=0.0, buttons=[])


def make_l4_run(tmp, name="tagrunX", seconds=30.0, hz=20, every=2, pad=True):
    """A recorder run in L4's shape: a row per control tick, `file`/`i` on every `every`-th."""
    d = tmp / name
    d.mkdir()
    rows = []
    for k in range(int(seconds * hz)):
        t = round(k / hz, 4)
        row = {"t": t, "note": f"n{t:.3f}", "dets": []}
        if pad:
            row["pad"] = {**PAD, "lx": round((k % 7) / 7, 3)}
        if k % every == 0:
            row.update(file=f"{k // every:06d}.jpg", i=k // every)
        rows.append(row)
    jsonl(d / "frames.jsonl", rows)
    write_jpeg_header(d / "000000.jpg", 2560, 1440)
    return d


def make_l1_run(tmp, name="run1X", frames=100, fps=10):
    """A recorder run in record.py's shape: one row per saved frame, pad state on it."""
    d = tmp / name
    d.mkdir()
    jsonl(d / "frames.jsonl", [{"i": i, "t": round(i / fps, 4), "file": f"{i:06d}.jpg", "step": "approach", "pad": {**PAD},
                                "pad_age": 0.001, "idle_warning": False} for i in range(frames)])
    write_jpeg_header(d / "000000.jpg", 1280, 720)
    return d


def walk(obj):
    """Every object reachable from obj through dataclass fields, tuples, lists and dicts."""
    seen, stack = set(), [obj]
    while stack:
        o = stack.pop()
        if id(o) in seen:
            continue
        seen.add(id(o))
        yield o
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            stack.extend(getattr(o, f.name) for f in dataclasses.fields(o))
        elif isinstance(o, (tuple, list)):
            stack.extend(o)
        elif isinstance(o, dict):
            stack.extend(o.values())


# --- the format ------------------------------------------------------------------------------------------------------
def test_a_header_must_carry_every_required_field(tmp_path):
    h = header()
    del h["hero"]
    with pytest.raises(FormatError, match=r"lacks \['hero'\]"):
        demos.write_manifest(tmp_path / "x.manifest.jsonl", h, SEGS)


def test_unknown_kinds_splits_reasons_and_shapes_are_refused(tmp_path):
    bad = [(dict(kind="podcast"), SEGS, "kind"), (dict(split="dev"), SEGS, "split"),
           (dict(segments_from="guess"), SEGS, "segments_from"), (dict(resolution=[1920]), SEGS, "resolution"),
           (dict(inputs="keyboard"), SEGS, "inputs"), (dict(media={"kind": "zip"}), SEGS, "media kind"),
           ({}, [{**SEGS[0], "ended_by": "lunch"}], "ended_by"), ({}, [{**SEGS[0], "started_by": "boredom"}], "started_by"),
           ({}, [{**SEGS[0], "end_t": -1.0}], "ends before it starts"),
           ({}, [SEGS[1], SEGS[0]], "overlaps or precedes"), ({}, [SEGS[0], {**SEGS[1], "start_t": 19.0}], "overlaps or precedes"),
           ({}, [{**SEGS[2], "end_t": 99.0}], "after the clip does"), ({}, [{**SEGS[0], "start_t": "0"}], "expected a number")]
    for extra, segs, why in bad:
        with pytest.raises(FormatError, match=why):
            demos.write_manifest(tmp_path / "x.manifest.jsonl", header(**extra), segs)


def test_the_reasons_the_hud_segmenter_writes_are_all_accepted():
    """docs/lanes/l2-hud.md, Event stream format: every started_by and ended_by the segmenter can write."""
    started = ("run_start", "respawn", "killcam_over", "spectating_over", "scoreboard_closed", "hero_returned", "hud_returned", "after_cut")
    ended = ("run_end", "death", "killcam", "spectating", "scoreboard", "not_our_hero", "no_hud", "hard_cut")
    for a in started:
        for b in ended:
            demos.Clip(header(), [dict(start_t=0.0, end_t=1.0, started_by=a, ended_by=b)], ".")


def test_an_event_that_crosses_a_boundary_or_lies_in_a_gap_is_refused(tmp_path):
    for e in (dict(kind="hp_lost", t_from=19.5, t_to=30.5),       # spans the gap between two segments
              dict(kind="hp_lost", t_from=22.0, t_to=23.0),       # entirely in a gap
              dict(kind="hp_lost", t_from=5.0, t_to=4.0)):        # backwards
        with pytest.raises(FormatError, match="outside every segment or crosses a boundary"):
            make_vod(tmp_path, events=[e])


def test_events_are_assigned_to_segments_by_time_not_by_the_files_index(tmp_path):
    e = dict(EVENTS[3], segment=7)  # the file's own index is only a hint
    clip = demos.read_manifest(make_vod(tmp_path, events=[e]))
    assert clip.events[0].segment == 0


def test_a_manifest_must_start_with_its_header_and_hold_only_segments_after_it(tmp_path):
    p = tmp_path / "a.manifest.jsonl"
    jsonl(p, [dict(type="segment", **SEGS[0])])
    with pytest.raises(FormatError, match="first line must be the clip header"):
        demos.read_manifest(p)
    jsonl(p, [dict(type="clip", **header()), dict(type="event", kind="x")])
    with pytest.raises(FormatError, match="only segment lines"):
        demos.read_manifest(p)
    p.write_text('{"type": "clip"\n')
    with pytest.raises(FormatError, match="not JSON"):
        demos.read_manifest(p)


def test_segment_lines_inside_an_events_file_are_ignored_by_the_loader(tmp_path):
    seg_line = dict(type="segment", start_t=0.0, end_t=20.0, started_by="run_start", ended_by="death", n=0)
    clip = demos.read_manifest(make_vod(tmp_path, events=[seg_line, dict(type="event", **EVENTS[0])]))
    assert len(clip.events) == 1


def test_a_per_clip_events_file_that_carries_its_segments_becomes_a_manifest(tmp_path):
    lines = [META] + [dict(type="segment", n=n, start_i=0, end_i=9, **s) for n, s in enumerate(SEGS)] + [dict(type="event", **with_pos(e)) for e in EVENTS]
    jsonl(tmp_path / "vodC.events.jsonl", lines)
    segs = demos.events_file_segments(tmp_path / "vodC.events.jsonl")
    assert segs == SEGS
    clip = demos.write_manifest(tmp_path / "vodC.manifest.jsonl", header(id="vodC", events="vodC.events.jsonl"), segs)
    assert len(clip.segments) == 3 and len(clip.events) == len(EVENTS)      # events checked against those segments, by time


def test_the_hud_lanes_event_file_shape_loads_as_written(tmp_path):
    """meta line, then segment lines, then events without a type: the format in docs/lanes/l2-hud.md, verbatim."""
    lines = [dict(META, source="vodC", duration_s=60.0, segments=3, events=2)]
    lines += [dict(type="segment", start_i=int(s["start_t"] * 10), end_i=int(s["end_t"] * 10), **s) for s in SEGS]
    lines += [dict(kind="hp_lost", i_from=40, t_from=4.0, i_to=42, t_to=4.2, slot=None, amount=75, before=250, after=175, segment=0),
              dict(kind="ability_cast", i_from=100, t_from=10.0, i_to=104, t_to=10.4, slot="get_over_here", slot_pos="get_over_here",
                   amount=8, before="off", after=8, segment=0)]
    jsonl(tmp_path / "vodC.events.jsonl", lines)
    segs = demos.events_file_segments(tmp_path / "vodC.events.jsonl")
    clip = demos.write_manifest(tmp_path / "vodC.manifest.jsonl", header(id="vodC", events="vodC.events.jsonl"), segs)
    assert len(clip.segments) == 3 and [e.kind for e in clip.events] == ["hp_lost", "ability_cast"]


def test_slivers_between_scoreboard_openings_yield_no_windows(tmp_path):
    segs = [dict(start_t=0.0, end_t=10.0, started_by="run_start", ended_by="scoreboard"),
            dict(start_t=10.4, end_t=10.9, started_by="scoreboard_closed", ended_by="scoreboard"),      # a few frames of play
            dict(start_t=12.0, end_t=20.0, started_by="scoreboard_closed", ended_by="run_end")]
    sliver_event = dict(kind="ability_cast", t_from=10.5, t_to=10.7, slot="get_over_here", amount=8, before="off", after=8)
    path = make_vod(tmp_path, segs=segs, events=[sliver_event], duration_s=20.0, split="train", decisions=[5.0, 10.5, 15.0])
    d = Demos.load(path)
    clip, = d.clips.values()
    assert len(clip.segments) == 3 and [e.kind for e in clip.events] == ["ability_cast"]     # the sliver is kept: it is what was proven
    obs = list(d.observations("train"))
    assert obs and all(o.segment != 1 for o in obs) and not any(10.4 - 1e-6 <= o.t <= 10.9 + 1e-6 for o in obs)
    assert [(k.t, k.reason) for k in d.skipped] == [(10.4, "segment_too_short")]
    got = [round(s.observation.t, 3) for s in d.samples("train", decisions="manifest", hindsight=True)]
    assert got == [5.0, 15.0]                                                               # the explicit one inside it is not cut
    assert (10.5, "segment_too_short") in [(k.t, k.reason) for k in d.skipped]
    assert not any(e.kind == "ability_cast" for o in obs for e in o.events)                 # and its event reaches no window
    assert "(short: 1)" in demos.summary(d)[0]


def test_the_minimum_segment_length_is_named_and_a_segment_of_exactly_that_length_is_kept(tmp_path):
    assert demos.MIN_SEGMENT_S == 1.0
    segs = [dict(start_t=0.0, end_t=1.0, started_by="run_start", ended_by="scoreboard"),
            dict(start_t=2.0, end_t=2.99, started_by="scoreboard_closed", ended_by="run_end")]
    path = make_vod(tmp_path, segs=segs, duration_s=3.0, split="train")
    d = Demos.load(path)
    assert {o.segment for o in d.observations("train")} == {0}                              # 1.0 s stays, 0.99 s goes
    assert {o.segment for o in Demos.load(path, min_segment_s=0.0).observations("train")} == {0, 1}   # the knob
    assert {o.segment for o in Demos.load(path, min_segment_s=2.0).observations("train")} == set()


def test_every_events_format_but_4_is_refused_naming_the_file_and_both_versions(tmp_path):
    """Format 1 claimed casts that never happened; 2 and 3 name abilities by layout position and know no cut: refuse, do not read."""
    old = [dict(kind="hp_lost", t_from=4.0, t_to=4.2, amount=75, before=250, after=175)]
    for n, (lines, fmt) in enumerate([(old, 1),                                                     # no meta line at all
                                      ([dict(type="meta", source="x", fps=10.0)] + old, 1),         # a meta line without a format
                                      ([dict(META, format=1)] + old, 1), ([dict(META, format=2)] + old, 2),
                                      ([dict(META, format=3)] + old, 3),                            # every file the HUD lane wrote before 4
                                      ([dict(META, format=5)] + old, 5)]):                          # a newer one the loader does not know
        d = fresh(tmp_path, f"f{n}")
        jsonl(d / "v.events.jsonl", lines)
        with pytest.raises(FormatError, match=rf"v\.events\.jsonl: event stream format {fmt}, this loader reads format 4"):
            demos.write_manifest(d / "v.manifest.jsonl", header(events="v.events.jsonl"), SEGS)
        with pytest.raises(FormatError, match="format"):
            demos.events_file_segments(d / "v.events.jsonl")


def test_a_format_4_meta_line_must_say_how_its_slots_were_named(tmp_path):
    for k in demos.META_KEYS:
        d = fresh(tmp_path, f"m{k}")
        jsonl(d / "v.events.jsonl", [{x: v for x, v in META.items() if x != k}])
        with pytest.raises(FormatError, match=rf"meta line lacks \['{k}'\]"):
            demos.events_file_segments(d / "v.events.jsonl")


def test_format_1_vocabulary_inside_a_format_4_file_is_refused(tmp_path):
    for e in (dict(kind="ability_used", t_from=4.0, t_to=4.2, slot="swing", before=True, after=False),
              dict(kind="ability_ready", t_from=4.0, t_to=4.2, slot="swing", before=False, after=True),
              dict(kind="ability_cast", t_from=4.0, t_to=4.2, slot="pull", amount=8, before="off", after=8)):
        with pytest.raises(FormatError, match="format 1 vocabulary inside a format 4 file"):
            make_vod(fresh(tmp_path, f"v{e['kind']}{e['slot']}"), events=[e])


def test_hud_segments_keeps_only_the_fields_that_matter():
    row = dict(start_i=0, start_t=0.0, end_i=38, end_t=7.6, started_by="run_start", ended_by="death")
    assert demos.hud_segments([row]) == [dict(start_t=0.0, end_t=7.6, started_by="run_start", ended_by="death")]


# --- source timestamps survive trimming ----------------------------------------------------------------------------------
def test_source_time_survives_trimming(tmp_path):
    clip = demos.read_manifest(make_vod(tmp_path, source_start_s=1920.0, source_end_s=1980.0))
    assert clip.source_time(5.0) == 1925.0
    rows = [dict(clip.header)] + [dict(type="segment", **s) for s in SEGS]  # the header already carries type: clip
    cut = demos.trim(rows, 10.0, 40.0, "vodA-10-40", media_path="vodA-10-40.mp4")
    head = {**cut[0], "events": None}
    assert (head["source_start_s"], head["source_end_s"], head["duration_s"], head["id"]) == (1930.0, 1960.0, 30.0, "vodA-10-40")
    assert head["media"]["path"] == "vodA-10-40.mp4"
    assert [(s["start_t"], s["end_t"], s["started_by"], s["ended_by"]) for s in cut[1:]] == [
        (0.0, 10.0, "run_start", "death"),      # cut at the new start: it starts with the clip, ends as before
        (20.0, 30.0, "respawn", "run_end")]     # cut at the new end
    new = demos.write_manifest(tmp_path / "vodA-10-40.manifest.jsonl", head, cut[1:])
    for t in (0.0, 4.5, 12.25, 30.0):
        assert new.source_time(t) == clip.source_time(t + 10.0)  # the same moment of the VOD
    # a trim that keeps a whole segment keeps its own reasons; one that misses a segment drops it
    keep = demos.trim(rows, 25.0, 52.0, "k")
    assert [(s["started_by"], s["ended_by"]) for s in keep[1:]] == [("respawn", "no_hud")]
    assert demos.trim([dict(type="clip", **header(source_start_s=None, source_end_s=None))] + [dict(SEGS[0])], 0.0, 5.0, "r")[0]["source_start_s"] is None


# --- nothing crosses a segment boundary --------------------------------------------------------------------------------
def gap_of(t):
    return 20.0 < t < 30.0 or 50.0 < t < 55.0


def test_nothing_crosses_a_segment_boundary(tmp_path):
    d = Demos.load(make_vod(tmp_path, events=EVENTS, split="train"))
    clip = d.clips["vodA"]
    n = 0
    for s in d.samples("train", hindsight=True):
        o, out = s.observation, s.hindsight.outcome
        seg = clip.segments[o.segment]
        assert seg.start_t - 1e-6 <= o.context_start <= o.t <= seg.end_t + 1e-6
        assert all(seg.start_t - 1e-6 <= f.t <= o.t for f in o.frames)
        assert all(e.segment == seg.n and seg.start_t - 1e-6 <= e.t_from and e.t_to <= o.t for e in o.events)
        assert o.t < out.t_end + 1e-9 and out.t_end <= seg.end_t + 1e-6
        assert all(o.t < f.t <= seg.end_t + 1e-6 for f in out.frames)
        assert all(e.segment == seg.n and o.t < e.t_to <= seg.end_t + 1e-6 for e in out.events)
        assert not gap_of(o.t) and not any(gap_of(f.t) for f in o.frames + out.frames)
        n += 1
    assert n > 100


def test_a_window_cut_by_a_boundary_says_why_and_a_short_context_is_flagged(tmp_path):
    d = Demos.load(make_vod(tmp_path, events=EVENTS, split="train"))
    by_t = {round(s.observation.t, 3): s for s in d.samples("train", hindsight=True)}
    early, mid, late = by_t[2.0], by_t[12.0], by_t[18.0]
    assert early.observation.truncated_context and early.observation.context_start == 0.0
    assert not mid.observation.truncated_context and mid.observation.context_start == 7.0
    assert not mid.hindsight.outcome.truncated and mid.hindsight.outcome.ended_by is None and mid.hindsight.outcome.t_end == 17.0
    assert late.hindsight.outcome.truncated and late.hindsight.outcome.ended_by == "death"   # death is an outcome
    assert late.hindsight.outcome.t_end == 20.0
    first_in_segment = by_t[30.0]
    assert [f.t for f in first_in_segment.observation.frames] == [30.0]   # nothing from before the gap
    assert by_t[55.0].hindsight.outcome.ended_by is None and not by_t[55.0].hindsight.outcome.truncated   # fits exactly: not cut
    assert by_t[57.0].hindsight.outcome.ended_by == "run_end" and by_t[57.0].hindsight.outcome.t_end == 60.0  # the clip's end cuts it


def test_a_decision_never_snaps_to_a_frame_outside_its_segment(tmp_path):
    """Sparse frames (one a second): the grid time 10.6 is inside a segment that starts at 10.5, but the newest frame at or
    before it is at 10.0, on the far side of the boundary. That decision must not exist."""
    d = tmp_path / "sparse"
    d.mkdir()
    jsonl(d / "frames.jsonl", [{"t": float(k), "file": f"{k:06d}.jpg", "i": k, "pad": PAD} for k in range(30)])
    jsonl(d / "manifest.jsonl", [dict(type="clip", **header(id="run:sparse", kind="run", run="sparse", vod_id=None, inputs="pad",
                                                           segments_from="annotator", fps=1, source_start_s=None, source_end_s=None,
                                                           duration_s=29.0, resolution=None, split="train",
                                                           media={"kind": "frames", "dir": ".", "index": "frames.jsonl"})),
                                 dict(type="segment", start_t=10.5, end_t=25.0, started_by="hud_returned", ended_by="run_end")])
    demos_ = Demos.load(d)
    obs = list(demos_.observations("train", hz=5.0))
    assert obs and min(o.t for o in obs) == 11.0                       # the first decision is on a frame inside the segment
    assert all(f.t >= 10.5 for o in obs for f in o.frames) and all(i.t >= 10.5 for o in obs for i in o.inputs)
    assert all(o.segment == 0 and o.truncated_context for o in obs if o.t < 15.5)


def test_explicit_decisions_outside_every_segment_are_skipped_and_reported(tmp_path):
    d = Demos.load(make_vod(tmp_path, decisions=[5.0, 15.0, 25.0, 45.0], split="train"))
    got = [round(s.observation.t, 3) for s in d.samples("train", decisions="manifest")]
    assert got == [5.0, 15.0, 45.0] and [(x.t, x.reason) for x in d.skipped] == [(25.0, "outside_segments")]


# --- a scoreboard gap is soft: a window may span it, masked; every other gap is hard -----------------------------------------
SB = [dict(start_t=0.0, end_t=20.0, started_by="run_start", ended_by="scoreboard"),
      dict(start_t=22.0, end_t=40.0, started_by="scoreboard_closed", ended_by="death"),       # 20-22 soft, 40-45 hard
      dict(start_t=45.0, end_t=60.0, started_by="respawn", ended_by="run_end")]
SB_EVENTS = [dict(kind="ability_cast", t_from=19.0, t_to=19.2, slot="get_over_here", amount=8, before="off", after=8),        # before the gap
             dict(kind="slot_available", t_from=22.5, t_to=22.7, slot="get_over_here", before=False, after=True),      # after it
             dict(kind="hp_lost", t_from=22.9, t_to=23.3, amount=25, before=250, after=225)]                # pending at 23.0
MASK = Mask(("scoreboard",))


def fresh(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    return d


def sb_demos(tmp_path, annotations=None, segs=SB, bridge=2.0, **kw):
    """SB's scoreboard tap is 2.0 s wide: bridged here by raising the maximum to 2.0 (the default 1.0 would make it hard)."""
    return Demos.load(make_vod(tmp_path, segs=segs, events=SB_EVENTS, annotations=annotations, split="train", **kw), max_bridge_s=bridge)


def test_only_a_scoreboard_closing_after_a_scoreboard_is_a_soft_gap():
    started = ("run_start", "respawn", "killcam_over", "spectating_over", "scoreboard_closed", "hero_returned", "hud_returned")
    ended = ("run_end", "death", "killcam", "spectating", "scoreboard", "not_our_hero", "no_hud", "hero_swap", "menu", "brb")
    for e in ended:
        for st in started:
            clip = demos.Clip(header(), [dict(start_t=0.0, end_t=10.0, started_by="run_start", ended_by=e),
                                         dict(start_t=12.0, end_t=20.0, started_by=st, ended_by="run_end")], ".")
            assert bool(clip.soft_gap(0, 2.0)) == (e == "scoreboard" and st == "scoreboard_closed"), (e, st)
    clip = demos.Clip(header(), SB, ".")
    a, b, c = clip.segments
    assert clip.stretch(a, 2.0) == clip.stretch(b, 2.0) == (a, b) and clip.stretch(c, 2.0) == (c, c)
    assert clip.mask_at(21.0, 2.0) == MASK and clip.mask_at(20.0, 2.0) is None and clip.mask_at(22.0, 2.0) is None
    assert MASK.hidden == ("hud", "scene")


def test_a_scoreboard_tap_wider_than_the_named_maximum_is_a_hard_boundary():
    assert demos.MAX_BRIDGE_S == 1.0
    tap = lambda gap: demos.Clip(header(), [dict(start_t=0.0, end_t=10.0, started_by="run_start", ended_by="scoreboard"),
                                            dict(start_t=10.0 + gap, end_t=20.0, started_by="scoreboard_closed", ended_by="run_end")], ".")
    assert tap(0.6).soft_gap(0) and tap(1.0).soft_gap(0) and not tap(1.1).soft_gap(0)
    assert tap(1.1).stretch(tap(1.1).segments[1]) == (tap(1.1).segments[1],) * 2 and tap(1.1).mask_at(10.5) is None
    assert tap(1.1).soft_gap(0, 2.0)                                                           # the knob
    d = Demos([demos.Clip(header(split="train", decisions=[12.0]), [dict(start_t=0.0, end_t=10.0, started_by="run_start", ended_by="scoreboard"),
                                                                   dict(start_t=11.5, end_t=20.0, started_by="scoreboard_closed",
                                                                        ended_by="run_end")], ".")])
    o, = d.observations("train", decisions="manifest")
    assert o.context_start == 11.5 and o.truncated_context and not o.masked_context             # default window: not bridged
    o, = Demos(list(d.clips.values()), max_bridge_s=2.0).observations("train", decisions="manifest")
    assert o.context_start == 7.0 and o.masked_context


def test_a_window_stops_at_a_scoreboard_when_told_not_to_bridge_it(tmp_path):
    obs, = sb_demos(tmp_path, decisions=[23.0]).observations("train", decisions="manifest", across_overlays=False)
    assert obs.context_start == 22.0 and obs.truncated_context and not obs.masked_context and obs.frames[0].t == 22.0
    assert [e.kind for e in obs.events] == ["slot_available"]                                   # the event before the gap is not seen


def test_a_window_spans_a_scoreboard_gap_when_asked_and_the_gap_frames_are_masked(tmp_path):
    d = sb_demos(tmp_path, decisions=[23.0, 18.0, 38.0])
    o18, o23, o38 = d.observations("train", decisions="manifest", across_overlays=True)   # decisions run in time order
    assert (o23.segment, o23.context_start, o23.truncated_context, o23.masked_context) == (1, 18.0, False, True)
    got = [f.t for f in o23.frames if f.masked]
    assert got == pytest.approx([20.2, 20.4, 20.6, 20.8, 21.0, 21.2, 21.4, 21.6, 21.8])          # strictly inside the gap
    assert all(f.masked == MASK for f in o23.frames if f.masked)
    assert not any(f.masked for f in o23.frames if f.t <= 20.0 or f.t >= 22.0)                # the frames the segmenter proved
    assert [e.kind for e in o23.events] == ["ability_cast", "slot_available"]                    # both sides of the gap; hp_lost pending
    s18, s23, s38 = d.samples("train", decisions="manifest", hindsight=True, across_overlays=True)
    assert s18.hindsight.outcome.ended_by is None and not s18.hindsight.outcome.truncated       # 18 -> 23 spans the gap
    assert [f.t for f in s18.hindsight.outcome.frames if f.masked] == got
    assert s38.hindsight.outcome.ended_by == "death" and s38.hindsight.outcome.t_end == 40.0    # the hard boundary still ends it
    assert [e.kind for e in s23.hindsight.outcome.events] == ["hp_lost"]                        # pending at 23.0 is hindsight
    far, = [x for x in d.samples("train", decisions="manifest", hindsight=True, across_overlays=True, outcome_s=25.0)][:1]
    assert (far.hindsight.outcome.t_end, far.hindsight.outcome.ended_by) == (40.0, "death")      # from the FIRST segment: the stretch's end
    s, = sb_demos(fresh(tmp_path, "d"), decisions=[18.0]).samples("train", decisions="manifest", hindsight=True, across_overlays=False)
    assert (s.hindsight.outcome.t_end, s.hindsight.outcome.ended_by, s.hindsight.outcome.truncated) == (20.0, "scoreboard", True)


HARD_STARTED = ("respawn", "killcam_over", "spectating_over", "hero_returned", "hud_returned", "scoreboard_closed", "run_start", "after_cut")
HARD_ENDED = ("death", "killcam", "spectating", "not_our_hero", "no_hud", "scoreboard", "hero_swap", "menu", "brb", "unreadable_hud",
              "hard_cut")


def test_no_hard_boundary_is_ever_spanned_even_when_asked_to_span_overlays():
    for e in HARD_ENDED:
        for st in HARD_STARTED:
            if (e, st) == ("scoreboard", "scoreboard_closed"):
                continue
            segs = [dict(start_t=0.0, end_t=20.0, started_by="run_start", ended_by=e),
                    dict(start_t=22.0, end_t=40.0, started_by=st, ended_by="run_end")]
            d = Demos([demos.Clip(header(split="train", decisions=[23.0, 18.0]), segs, ".")], max_bridge_s=2.0)   # width is no excuse
            before, after = d.samples("train", decisions="manifest", hindsight=True, across_overlays=True)
            assert after.observation.context_start == 22.0 and after.observation.truncated_context, (e, st)
            assert not after.observation.masked_context and before.hindsight.outcome.t_end == 20.0, (e, st)
            assert before.hindsight.outcome.ended_by == e and not any(f.masked for f in before.hindsight.outcome.frames), (e, st)


def test_spanning_a_soft_gap_never_lets_the_future_into_a_window(tmp_path):
    d = sb_demos(tmp_path, decisions=[19.0, 22.0, 23.0, 27.0, 50.0])
    for o in d.observations("train", decisions="manifest", across_overlays=True):
        assert all(f.t <= o.t + 1e-6 for f in o.frames) and all(e.t_to <= o.t + 1e-6 for e in o.events)
    at = {o.t: o for o in d.observations("train", decisions="manifest", across_overlays=True)}
    assert "hp_lost" not in [e.kind for e in at[23.0].events] and "hp_lost" in [e.kind for e in at[27.0].events]
    assert "slot_available" not in [e.kind for e in at[19.0].events]                       # a later segment's event, not yet happened


def annotation(t, **kw):
    return dict(type="annotation", t=t, by=kw.pop("by", "codex"), assisted=True, actions=["engage"], target="unknown", evidence=[t], **kw)


def test_an_annotation_over_a_scoreboard_is_refused_until_the_window_matches_what_was_judged(tmp_path):
    d = sb_demos(tmp_path, annotations=[annotation(23.0, context_start=18.0, masked_context=True)])
    with pytest.raises(AlignmentError, match=r"judged context from 18.0 but this window starts at 22.0.*across_overlays=True"):
        list(d.samples("train", decisions="manifest", across_overlays=False))                # a window stopped at the scoreboard
    s, = d.samples("train", decisions="manifest", across_overlays=True)
    assert s.labels[0].by == "codex" and s.observation.masked_context and s.observation.context_start == 18.0
    assert (s.labels[0].context_start, s.labels[0].masked_context) == (18.0, True)


def test_an_annotation_is_refused_when_the_masked_claim_or_the_history_disagrees(tmp_path):
    cases = [(annotation(23.0, context_start=18.0, masked_context=False), {}, "masked_context=False"),     # saw none, the window has some
             (annotation(15.0, context_start=10.0, masked_context=True), {}, "masked_context=True"),        # saw some, the window has none
             (annotation(23.0, context_start=15.0, masked_context=True), {}, "judged context from 15.0"),   # history_s 5 < what was judged
             (annotation(47.0, context_start=42.0), {}, "hard boundary")]                                    # death -> respawn in the context
    for n, (row, kw, why) in enumerate(cases):
        d = sb_demos(fresh(tmp_path, f"c{n}"), annotations=[row])
        with pytest.raises(AlignmentError, match=why):
            list(d.samples("train", decisions="manifest", across_overlays=True, **kw))
    d = sb_demos(fresh(tmp_path, "ok"), annotations=[annotation(23.0, context_start=15.0, masked_context=True)])
    s, = d.samples("train", decisions="manifest", across_overlays=True, history_s=8.0)                       # matching history: fine
    assert s.observation.context_start == 15.0


def test_annotation_rows_that_declare_no_context_load_as_before_and_a_bad_flag_is_a_format_error(tmp_path):
    d = sb_demos(tmp_path, annotations=[annotation(23.0)])
    for across in (False, True):
        s, = d.samples("train", decisions="manifest", across_overlays=across)
        assert s.labels[0].context_start is None and s.labels[0].masked_context is None
    with pytest.raises(FormatError, match="masked_context must be true, false or absent"):
        sb_demos(fresh(tmp_path, "bad"), annotations=[annotation(23.0, masked_context="yes")])


# --- resource regimes: cooldowns off | normal | unknown are never mixed by accident -----------------------------------------
def regime_fleet(tmp_path, regimes=("off", "normal", "unknown"), split="train"):
    for n, r in enumerate(regimes):
        make_vod(tmp_path, name=f"v{n}", vod_id=f"9{n}", split=split, cooldowns=r)
    return Demos.load(tmp_path)


def test_cooldowns_is_required_and_must_be_one_of_off_normal_unknown(tmp_path):
    h = header()
    del h["cooldowns"]
    with pytest.raises(FormatError, match="lacks .*cooldowns"):
        demos.write_manifest(tmp_path / "x.manifest.jsonl", h, SEGS)
    for bad in (None, "on", "Off", True, ""):
        with pytest.raises(FormatError, match="cooldowns .* is not one of"):
            demos.write_manifest(tmp_path / "x.manifest.jsonl", header(cooldowns=bad), SEGS)
    assert demos.COOLDOWNS == ("off", "normal", "unknown")


def test_a_split_that_mixes_regimes_is_refused_unless_asked(tmp_path):
    d = regime_fleet(tmp_path)
    assert d.regimes("train") == ["normal", "off", "unknown"]
    for call in (d.observations, d.samples):
        with pytest.raises(demos.RegimeError, match=r"mixes resource regimes \['normal', 'off', 'unknown'\]"):
            list(call("train"))
    assert {o.clip for o in d.observations("train", mix_regimes=True)} == {"v0", "v1", "v2"}
    assert {s.observation.clip for s in d.samples("train", mix_regimes=True)} == {"v0", "v1", "v2"}


def test_a_regime_can_be_picked_and_two_of_three_is_still_a_mix(tmp_path):
    d = regime_fleet(tmp_path)
    for regime, clip in (("off", "v0"), ("normal", "v1"), ("unknown", "v2")):
        assert {o.clip for o in d.observations("train", cooldowns=regime)} == {clip}
        assert {s.observation.clip for s in d.samples("train", cooldowns=(regime,))} == {clip}
    with pytest.raises(demos.RegimeError):
        list(d.observations("train", cooldowns=("off", "normal")))
    assert {o.clip for o in d.observations("train", cooldowns=("off", "normal"), mix_regimes=True)} == {"v0", "v1"}
    for bad in ("on", (), ("off", "maybe")):
        with pytest.raises(ValueError, match="cooldowns must be"):
            list(d.observations("train", cooldowns=bad))


def test_regimes_only_conflict_inside_a_split(tmp_path):
    for n, (r, split) in enumerate((("off", "train"), ("normal", "val"), ("unknown", "test"))):
        make_vod(tmp_path, name=f"v{n}", vod_id=f"9{n}", split=split, cooldowns=r)
    d = Demos.load(tmp_path)
    for split in ("train", "val", "test"):
        assert list(d.observations(split)) and len(d.regimes(split)) == 1
    assert d.regimes("inspection_only") == []


def test_a_run_directory_takes_its_regime_from_its_meta_json_and_is_unknown_without_one(tmp_path):
    d = make_l4_run(tmp_path, "tagrunR")
    assert demos.clip_from_run(d).cooldowns == "unknown"                         # never assumed from the date
    (d / "meta.json").write_text(json.dumps({"stop": "completed", "cooldowns": "off"}))
    assert demos.clip_from_run(d).cooldowns == "off" and demos.clip_from_run(d).header["cooldowns"] == "off"
    (d / "meta.json").write_text(json.dumps({"cooldowns": "normal"}))
    assert Demos.load(d).clips["run:tagrunR"].cooldowns == "normal"
    (d / "meta.json").write_text(json.dumps({"cooldowns": "yes"}))
    with pytest.raises(FormatError, match="cooldowns 'yes'"):
        demos.clip_from_run(d)
    (d / "meta.json").write_text(json.dumps({"seconds": 3}))                      # a recorder that says nothing about it
    assert demos.clip_from_run(d).cooldowns == "unknown"


def test_a_manifest_in_a_run_directory_can_state_the_regime_for_old_runs(tmp_path):
    d = make_l4_run(tmp_path, "tagrunOld")
    head = {k: v for k, v in demos.clip_from_run(d).header.items() if k != "type"}
    demos.write_manifest(d / "manifest.jsonl", dict(head, cooldowns="off", cooldowns_from="run_metadata"),
                         [dict(start_t=0.0, end_t=25.0, started_by="run_start", ended_by="run_end")])
    assert Demos.load(d).clips["run:tagrunOld"].cooldowns == "off"


def test_the_summary_says_the_regime(tmp_path):
    lines = demos.summary(regime_fleet(tmp_path))
    assert all(any(f"cooldowns={r}" in l for l in lines) for r in ("off", "normal", "unknown"))


# --- events are weak intervals -------------------------------------------------------------------------------------------
def test_events_are_intervals_and_a_pending_one_is_hindsight(tmp_path):
    assert {"t_from", "t_to"} <= {f.name for f in dataclasses.fields(Event)} and "t" not in {f.name for f in dataclasses.fields(Event)}
    d = Demos.load(make_vod(tmp_path, events=EVENTS, split="train"))
    by_t = {round(s.observation.t, 3): s for s in d.samples("train", hindsight=True)}
    at_13, at_13_4 = by_t[13.0], by_t[13.4]
    pending = lambda evs: [e for e in evs if e.t_from == 12.9]
    assert pending(at_13.observation.events) == []                       # its confirming frame (13.3) is after t
    assert len(pending(at_13.hindsight.outcome.events)) == 1             # known only in hindsight
    assert len(pending(at_13_4.observation.events)) == 1                 # confirmed by 13.4
    assert pending(at_13_4.hindsight.outcome.events) == []
    for s in by_t.values():
        assert all(e.t_to <= s.observation.t for e in s.observation.events)
        assert all(e.t_to > s.observation.t for e in s.hindsight.outcome.events)


# --- leakage ---------------------------------------------------------------------------------------------------------------
def canary_run(tmp_path):
    """A recorder run whose rows and events carry their own time, so a leak names itself."""
    d = make_l4_run(tmp_path, "canary", seconds=30.0)
    jsonl(d / "events.jsonl", [META] + [dict(kind="hp_lost", t_from=round(t, 2), t_to=round(t + 0.2, 2), before=250, after=f"after@{t + 0.2:.2f}")
                                        for t in (2.0, 9.0, 14.9, 20.0, 27.0)])
    return d


def test_no_future_datum_is_reachable_from_an_observation(tmp_path):
    d = Demos.load(canary_run(tmp_path))
    split = d.splits["run:canary"]
    seen = 0
    for o in d.observations(split, hz=10.0):
        for x in walk(o):
            assert not isinstance(x, (demos.Clip, Demos, demos.Sample, demos.Hindsight, demos.Outcome, demos.Label)), type(x)
            if isinstance(x, FrameRef):
                assert x.t <= o.t + 1e-6
            if isinstance(x, Input):
                assert x.t <= o.t + 1e-6 and float(x.note[1:]) <= o.t + 1e-6      # the note says when it was written
            if isinstance(x, Event):
                assert x.t_to <= o.t + 1e-6 and float(str(x.after).split("@")[1]) <= o.t + 1e-6
            if isinstance(x, str):
                assert not x.startswith("after@") or float(x.split("@")[1]) <= o.t + 1e-6
        assert o.frames[-1].t == pytest.approx(o.t)
        seen += 1
    assert seen > 100


def test_an_observation_refuses_to_hold_anything_later_than_t():
    f = lambda t: FrameRef("c", t, "image", "x.jpg")
    ok = dict(clip="c", segment=0, t=5.0, frames=(f(4.0), f(5.0)), events=(), inputs=(), context_start=0.0, truncated_context=False)
    Observation(**ok)
    for bad in (dict(frames=(f(4.0), f(5.5))),
                dict(events=(Event("hp_lost", 4.9, 5.5),)),           # confirmed after t
                dict(inputs=(Input(5.2, {}),)),
                dict(frames=())):
        with pytest.raises(LeakageError):
            Observation(**{**ok, **bad})
    Observation(**{**ok, "events": (Event("hp_lost", 4.0, 5.0),)})    # confirmed exactly at t: fine


def test_the_policy_facing_types_have_no_route_to_labels_or_outcomes(tmp_path):
    names = {f.name for f in dataclasses.fields(Observation)}
    assert not names & {"label", "labels", "outcome", "hindsight", "outcome_reviews", "clip_obj"}
    d = Demos.load(make_vod(tmp_path, events=EVENTS, split="train"))
    obs = list(d.observations("train"))
    assert obs and all(type(o) is Observation for o in obs)
    assert not hasattr(d.observations, "hindsight") and "hindsight" not in d.observations.__code__.co_varnames
    plain = list(d.samples("train"))
    assert all(s.hindsight is None for s in plain)                    # the outcome is opt-in
    withh = list(d.samples("train", hindsight=True))
    assert all(s.hindsight is not None for s in withh)
    assert [s.observation for s in plain] == obs == [s.observation for s in withh]   # asking for hindsight changes nothing else


def test_the_outcome_is_strictly_after_t(tmp_path):
    d = Demos.load(canary_run(tmp_path))
    for s in d.samples(d.splits["run:canary"], hindsight=True, hz=5.0):
        assert all(f.t > s.observation.t for f in s.hindsight.outcome.frames)
        assert all(e.t_to > s.observation.t for e in s.hindsight.outcome.events)


# --- missing modalities are explicit -------------------------------------------------------------------------------------
def test_a_vod_has_no_inputs_and_no_events_unless_a_stream_exists(tmp_path):
    d = Demos.load(make_vod(tmp_path, split="train"))
    for s in d.samples("train", hindsight=True):
        assert s.observation.inputs is None and s.observation.events is None and s.hindsight.outcome.events is None
        assert s.labels == ()                                          # no annotations: not labelled, not invented


def test_no_events_in_a_window_is_an_empty_tuple_not_none(tmp_path):
    d = Demos.load(make_vod(tmp_path, events=EVENTS, split="train"))
    by_t = {round(s.observation.t, 3): s.observation for s in d.samples("train")}
    assert by_t[1.0].events == () and by_t[1.0].inputs is None        # the stream exists and is empty here; inputs do not exist


def test_a_run_has_pad_inputs_and_no_events_unless_it_has_an_events_file(tmp_path):
    run = make_l4_run(tmp_path)
    d = Demos.load(run)
    split = d.splits["run:tagrunX"]
    o = next(d.observations(split))
    assert o.events is None and isinstance(o.inputs, tuple)
    s = list(d.samples(split))[10]
    assert [l.kind for l in s.labels] == ["recorded_inputs"] and s.labels[0].inputs and all(i.t > s.observation.t for i in s.labels[0].inputs)


def test_pad_rows_are_ignored_when_the_manifest_says_there_are_no_inputs(tmp_path):
    run = make_l4_run(tmp_path)
    jsonl(run / "manifest.jsonl", [dict(type="clip", **header(id="run:tagrunX", kind="run", run="tagrunX", vod_id=None, inputs=None,
                                                             segments_from="assumed_whole_run", fps=10, source_start_s=None,
                                                             source_end_s=None, duration_s=29.95, resolution=None,
                                                             media={"kind": "frames", "dir": ".", "index": "frames.jsonl"})),
                                   dict(type="segment", **SEGS[0])])
    d = Demos.load(run)
    o = next(d.observations(d.splits["run:tagrunX"]))
    assert o.inputs is None                                            # explicit, though the rows carry pad states
    assert all(s.labels == () for s in d.samples(d.splits["run:tagrunX"]))


def test_a_run_recorded_without_a_pad_has_inputs_null(tmp_path):
    run = make_l4_run(tmp_path, pad=False)
    d = Demos.load(run)
    assert d.clips["run:tagrunX"].header["inputs"] is None and next(d.observations(d.splits["run:tagrunX"])).inputs is None


def test_annotations_carry_an_explicit_unknown_and_keep_the_outcome_review_apart(tmp_path):
    ann = [dict(type="annotation", t=5.0, by="a1", situation="closing on a bot", actions=["engage"],
                target={"bbox": [900, 400, 940, 470], "frame_t": 5.0}, evidence=[4.6, 5.0], uncertainty="low",
                outcome_review="the attack landed"),
           dict(type="annotation", t=5.0, by="model-x", assisted=True, actions=["engage", "pull"], target="unknown"),
           dict(type="annotation", t=30.0, by="a1", unusable="chat covers the ability row", actions=None)]
    d = Demos.load(make_vod(tmp_path, annotations=ann, decisions=[5.0], split="train"))
    got = {round(s.observation.t, 3): s for s in d.samples("train", decisions="manifest", hindsight=True)}
    five = got[5.0]
    assert [(l.by, l.assisted, l.target if l.target == "unknown" else "box") for l in five.labels] == [("a1", False, "box"), ("model-x", True, "unknown")]
    assert five.labels[0].evidence == (4.6, 5.0) and five.labels[0].actions == ("engage",)
    assert five.hindsight.outcome_reviews == (("a1", "the attack landed"),)   # only in hindsight, never on a label
    only_review = Demos.load(make_vod(tmp_path, "vodR", vod_id="333", decisions=[5.0], split="train", annotations=[
        dict(type="annotation", t=5.0, by="a3", outcome_review="it died")]))
    rev = next(only_review.samples("train", decisions="manifest", hindsight=True))
    assert rev.labels[0].actions is None and rev.labels[0].situation is None and rev.labels[0].target is None   # the review is not a label
    assert not any("it died" in repr(x) for x in walk(rev.labels)) and rev.hindsight.outcome_reviews == (("a3", "it died"),)
    assert not any("outcome_review" in f.name for f in dataclasses.fields(demos.Label))
    assert got[30.0].labels[0].unusable == "chat covers the ability row" and got[30.0].labels[0].actions is None
    assert next(iter(Demos.load(make_vod(tmp_path, "vodB", vod_id="222", annotations=ann, decisions=[5.0], split="train")).observations(
        "train", decisions="manifest"))).events is None


def test_the_spectator_negative_is_skipped_but_its_annotation_survives(tmp_path):
    segs = [dict(SEGS[0], end_t=12.0), dict(SEGS[1], start_t=16.0, started_by="hero_returned")]
    ann = [dict(type="annotation", t=15.0, by="a1", unusable="spectating another hero")]
    d = Demos.load(make_vod(tmp_path, segs=segs, annotations=ann, decisions=[5.0, 15.0], split="train"))
    assert [round(s.observation.t, 3) for s in d.samples("train", decisions="manifest")] == [5.0]
    assert [(x.t, x.reason) for x in d.skipped] == [(15.0, "outside_segments")]
    assert d.clips["vodA"].annotations[15.0][0].unusable == "spectating another hero"


# --- splits: whole recordings, before windows are cut ----------------------------------------------------------------------
def fleet(tmp_path, vods=20, per_vod=2, runs=6, mirrors=0):
    for v in range(vods):
        for c in range(per_vod):
            make_vod(tmp_path, f"v{v}c{c}", vod_id=f"vod{v}", source_start_s=100.0 * c)
    for r in range(runs):
        make_l4_run(tmp_path, f"run{r}", seconds=6.0)
    return tmp_path


def test_a_recording_is_never_on_both_sides(tmp_path):
    d = Demos.load(fleet(tmp_path))
    demos.check_splits(list(d.clips.values()), d.splits)
    by_group = {}
    for c in d.clips.values():
        by_group.setdefault(c.group, set()).add(d.splits[c.id])
    assert all(len(v) == 1 for v in by_group.values())
    assert {d.splits[f"v{v}c0"] for v in range(20)} <= set(demos.SPLITS[:3])
    for v in range(20):
        assert d.splits[f"v{v}c0"] == d.splits[f"v{v}c1"]                     # two cuts of one VOD stay together
    assert len({s for s in d.splits.values()}) >= 2                            # and the assignment does split things


def test_windows_are_cut_only_from_the_requested_side(tmp_path):
    d = Demos.load(fleet(tmp_path, vods=12, runs=4))
    sides = {}
    for split in demos.SPLITS[:3]:
        ids = {o.clip for o in d.observations(split)}
        assert ids == {c.id for c in d.clips_in(split) if d.clips[c.id].segments and any(True for _ in d.observations(split))} or ids <= {c.id for c in d.clips_in(split)}
        assert ids <= {c.id for c in d.clips_in(split)}
        sides[split] = ids
    assert not (sides["train"] & sides["val"]) and not (sides["train"] & sides["test"]) and not (sides["val"] & sides["test"])
    assert sum(len(v) for v in sides.values()) > 10


def test_no_clip_and_no_group_appears_on_two_sides_over_many_random_fleets():
    rng = random.Random(7)
    for trial in range(30):
        clips = []
        for i in range(rng.randint(5, 60)):
            g = f"g{rng.randint(0, 20)}"
            clips.append(demos.Clip(header(id=f"c{i}", vod_id=g, group=None), SEGS, "."))
        splits = demos.assign_splits(clips, seed=trial)
        demos.check_splits(clips, splits)
        sides = {}
        for c in clips:
            sides.setdefault(splits[c.id], set()).add(c.group)
        for a in sides:
            for b in sides:
                assert a == b or not (sides[a] & sides[b])


def test_the_assignment_depends_only_on_the_group_and_the_seed():
    def clip(name, vod):
        return demos.Clip(header(id=name, vod_id=vod), SEGS, ".")
    a = [clip(f"a{i}", f"vod{i}") for i in range(40)]
    first = demos.assign_splits(a, seed=3)
    shuffled = a[:]
    random.Random(1).shuffle(shuffled)
    more = shuffled + [clip(f"z{i}", f"other{i}") for i in range(25)]
    again = demos.assign_splits(more, seed=3)
    assert all(again[c.id] == first[c.id] for c in a)                          # adding clips or reordering moves nothing
    assert any(demos.assign_splits(a, seed=4)[c.id] != first[c.id] for c in a)  # the seed does matter


def test_mirrors_and_reuploads_share_a_group_and_so_a_side():
    for i in range(40):
        pair = [demos.Clip(header(id=f"m{i}-{k}", vod_id=f"up{i}-{k}", group=f"mirror{i}"), SEGS, ".") for k in (0, 1)]
        s = demos.assign_splits(pair)
        assert s[pair[0].id] == s[pair[1].id]


def test_conflicting_splits_and_a_vod_in_two_groups_are_refused():
    mk = lambda n, **kw: demos.Clip(header(id=n, **kw), SEGS, ".")
    with pytest.raises(SplitError, match="two splits"):
        demos.assign_splits([mk("a", split="train"), mk("b", split="test")])            # same VOD, different explicit sides
    with pytest.raises(SplitError, match="two groups"):
        demos.assign_splits([mk("a", group="g1"), mk("b", group="g2")])                 # same VOD, different groups
    ok = demos.assign_splits([mk("a", split="test"), mk("b")])
    assert ok == {"a": "test", "b": "test"}                                             # an unassigned clip inherits its group's side
    with pytest.raises(SplitError, match="two sides"):
        demos.check_splits([mk("a"), mk("b", vod_id="222", group="111")], {"a": "train", "b": "val"})


def test_the_split_must_be_named_and_an_explicit_one_wins(tmp_path):
    d = Demos.load(make_vod(tmp_path, split="inspection_only"))
    assert d.splits == {"vodA": "inspection_only"} and list(d.observations("train")) == [] and list(d.observations("inspection_only"))
    with pytest.raises(TypeError):
        d.samples()
    with pytest.raises(ValueError, match="split must be"):
        list(d.samples("dev"))


def test_duplicate_clip_ids_are_refused(tmp_path):
    (tmp_path / "a").mkdir(), (tmp_path / "b").mkdir()
    make_vod(tmp_path / "a")
    make_vod(tmp_path / "b")
    with pytest.raises(FormatError, match="duplicate clip ids"):
        Demos.load(tmp_path)


# --- the existing range recordings load unchanged ----------------------------------------------------------------------------
def snapshot(d):
    return {str(p.relative_to(d)): (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(d.rglob("*")) if p.is_file()}


def test_range_recordings_load_unchanged_with_their_pad_state_as_the_input_modality(tmp_path):
    l4, l1 = make_l4_run(tmp_path), make_l1_run(tmp_path)
    before = {p: snapshot(p) for p in (l4, l1)}
    d = Demos.load(l4, l1)
    n = 0
    for split in demos.SPLITS:
        for s in d.samples(split, hindsight=True):
            n += 1
    assert n > 50
    assert {p: snapshot(p) for p in (l4, l1)} == before                                      # not one byte or mtime changed
    a, b = d.clips["run:tagrunX"], d.clips["run:run1X"]
    assert (a.kind, a.header["segments_from"], a.hero, a.header["inputs"], a.group) == ("run", "assumed_whole_run", "spider-man", "pad", "tagrunX")
    assert a.resolution == [2560, 1440] and b.resolution == [1280, 720]                      # from the JPEG headers
    assert a.fps == pytest.approx(10.0, abs=0.1) and b.fps == pytest.approx(10.0, abs=0.1)
    assert [(s.start_t, s.end_t) for s in a.segments] == [(0.0, 29.95)] and [(s.start_t, s.end_t) for s in b.segments] == [(0.0, 9.9)]
    assert len(a.inputs) == 600 and len(b.inputs) == 100                                     # L4: a pad row per tick; L1: per frame
    assert a.inputs[3].pad == {**PAD, "lx": round(3 / 7, 3)} and a.inputs[3].note == "n0.150"
    assert b.inputs[0].note == "approach" and b.inputs[0].extra["idle_warning"] is False    # `step` becomes the note; the rest is kept
    assert a.frames.refs[1].path.endswith("000001.jpg") and a.frames.refs[1].i == 1 and a.frames.refs[1].t == 0.1


def test_the_two_recorders_frame_and_pad_streams_are_kept_apart(tmp_path):
    d = Demos.load(make_l4_run(tmp_path))
    c = d.clips["run:tagrunX"]
    assert len(c.frames.refs) == 300 and len(c.inputs) == 600                                # frames at 10 Hz, pad at 20 Hz


def test_a_directory_without_frames_or_a_manifest_is_refused(tmp_path):
    (tmp_path / "empty").mkdir()
    (tmp_path / "jpgs_only").mkdir()
    (tmp_path / "jpgs_only" / "000000.jpg").write_bytes(b"x")
    with pytest.raises(FormatError):
        Demos.load(tmp_path / "empty")
    with pytest.raises(FormatError, match="no manifest and no frames.jsonl"):
        Demos.load(tmp_path / "jpgs_only")
    with pytest.raises(FormatError, match="not found"):
        Demos.load(tmp_path / "nope")


def test_a_manifest_inside_a_run_directory_replaces_the_synthesized_one(tmp_path):
    run = make_l4_run(tmp_path)
    jsonl(run / "manifest.jsonl", [dict(type="clip", **header(id="run:tagrunX", kind="run", run="tagrunX", vod_id=None, inputs="pad",
                                                             segments_from="annotator", fps=10, source_start_s=None, source_end_s=None,
                                                             duration_s=29.95, resolution=None, split="val",
                                                             media={"kind": "frames", "dir": ".", "index": "frames.jsonl"})),
                                   dict(type="segment", start_t=0.0, end_t=9.0, started_by="run_start", ended_by="menu"),
                                   dict(type="segment", start_t=12.0, end_t=29.0, started_by="hud_returned", ended_by="run_end")])
    d = Demos.load(run)
    c = d.clips["run:tagrunX"]
    assert len(c.segments) == 2 and d.splits["run:tagrunX"] == "val"
    assert all(not (9.0 < o.t < 12.0) for o in d.observations("val"))


def test_summary_and_the_command_line_run(tmp_path, capsys):
    make_vod(tmp_path, events=EVENTS, split="train")
    demos.main([str(tmp_path)])
    out = capsys.readouterr().out
    assert "vodA: vod split=train" in out and "segments=3" in out and "has=frames+events" in out


# --- format 4: an ability is named only when its icon was identified -------------------------------------------------------
def test_a_cast_at_an_unidentified_position_stays_null_through_every_window(tmp_path):
    """VUH-1326 finding 7: with no icon mapping for a position, the layout position must never become the ability's name."""
    cast = dict(kind="ability_cast", t_from=10.0, t_to=10.4, slot=None, slot_pos="teamup", amount=15, before="off", after=15)
    d = fresh(tmp_path, "null")
    jsonl(d / "v.events.jsonl", [dict(META, slot_mapping={"swing": "swing"})] + [cast])
    got = Demos.load(demos.write_manifest(d / "v.manifest.jsonl", header(events="v.events.jsonl", split="train"), SEGS).path)
    seen = [e for o in got.observations("train") for e in o.events if e.kind == "ability_cast"]
    assert seen and all(e.slot is None and e.slot_pos == "teamup" for e in seen)


def test_a_guessed_ability_name_is_refused(tmp_path):
    cast = dict(kind="ability_cast", t_from=10.0, t_to=10.4, amount=8, before="off", after=8)
    for n, (mapping, extra, why) in enumerate([
            ({"swing": "swing"}, dict(slot="teamup", slot_pos="teamup"), "position 'teamup', where the icon mapping says None"),
            (None, dict(slot="swing", slot_pos="swing"), "position 'swing', where the icon mapping says None"),     # nothing identified
            ({}, dict(slot="swing", slot_pos="swing"), "where the icon mapping says None"),                          # icons read, none found
            ({"swing": "get_over_here"}, dict(slot="swing", slot_pos="swing"), "says 'get_over_here'"),               # rebound keys
            (MAPPING, dict(slot="swing"), "with no slot_pos")]):
        d = fresh(tmp_path, f"g{n}")
        jsonl(d / "v.events.jsonl", [dict(META, slot_mapping=mapping), dict(cast, **extra)])
        with pytest.raises(FormatError, match=f"names a guessed ability: .*{why}"):
            demos.write_manifest(d / "v.manifest.jsonl", header(events="v.events.jsonl"), SEGS)
    d = fresh(tmp_path, "ult")                                                         # the ult's position is fixed by the layout
    jsonl(d / "v.events.jsonl", [dict(META, slot_mapping=None), dict(kind="ult_ready", t_from=5.0, t_to=5.1, slot="ult", slot_pos="ult")])
    assert demos.write_manifest(d / "v.manifest.jsonl", header(events="v.events.jsonl"), SEGS).events[0].slot == "ult"


def test_a_window_never_crosses_a_hard_cut(tmp_path):
    segs = [dict(start_t=0.0, end_t=20.0, started_by="run_start", ended_by="hard_cut"),
            dict(start_t=20.1, end_t=40.0, started_by="after_cut", ended_by="run_end")]    # a cut is instantaneous: no width excuses it
    ev = [dict(kind="hp_lost", t_from=19.0, t_to=19.2, amount=25, before=250, after=225)]
    d = Demos.load(make_vod(tmp_path, segs=segs, events=ev, duration_s=40.0, split="train"), max_bridge_s=60.0)
    for s in d.samples("train", hindsight=True):
        o, out = s.observation, s.hindsight.outcome
        side = (0.0, 20.0) if o.t <= 20.0 else (20.1, 40.0)
        assert all(side[0] - 1e-6 <= f.t <= side[1] + 1e-6 for f in o.frames + out.frames)
        assert not any(f.masked for f in o.frames + out.frames)
        assert o.t <= 20.0 or not o.events                                             # the hp_lost before the cut never reaches after
    late = [s for s in d.samples("train", hindsight=True) if 15.0 < s.observation.t <= 20.0]
    assert late[-1].hindsight.outcome.ended_by == "hard_cut"


# --- bridged windows carry masked frames, and nothing is read off them -----------------------------------------------------------
def visibility(ts, **fields):
    base = dict(scene="partial", player="visible", hp="visible", ammo="visible", swing="visible", get_over_here="visible",
                uppercut="visible", ult="visible")
    return [dict(t=t, pts=t, segment=0, reasons=["normal_world_and_own_hero_occlusion"], **{**base, **fields}) for t in ts]


def test_a_bridged_window_carries_masked_frames_and_no_hud_feature_from_them(tmp_path):
    segs = [dict(start_t=0.0, end_t=20.0, started_by="run_start", ended_by="scoreboard"),
            dict(start_t=20.6, end_t=40.0, started_by="scoreboard_closed", ended_by="run_end")]          # a 0.6 s tap: bridged by default
    ev = [dict(kind="web_cluster_fired", t_from=19.8, t_to=20.0, before=4, after=3),     # read off 20.0, which an annotator masked
          dict(kind="hp_lost", t_from=19.8, t_to=20.0, amount=25, before=250, after=225),    # hp stayed visible there: kept
          dict(kind="charges_spent", t_from=21.0, t_to=21.2, slot="swing", amount=1, before=2, after=1)]
    d = fresh(tmp_path, "b")
    (d / "ctx.json").write_text(json.dumps(visibility([20.0], ammo="unavailable") + visibility([21.2], swing="partial_chat_overlay")
                                           + visibility([30.0], scene="partial")))
    make_vod(d, segs=segs, events=ev, duration_s=40.0, split="train", annotations=[annotation(22.0, context_mask="ctx.json")])
    got = Demos.load(d)
    o, = [o for o in got.observations("train", frame_hz=10.0) if o.t == pytest.approx(22.0)]
    masked = {round(f.t, 1): f.masked for f in o.frames if f.masked}
    assert [t for t, m in masked.items() if "scoreboard" in m.reasons] == [20.1, 20.2, 20.3, 20.4, 20.5]   # the tap, kept, masked
    assert all(masked[t].hidden == ("hud", "scene") for t in (20.1, 20.5))
    assert masked[20.0].hidden == ("ammo",) and masked[21.2].hidden == ("swing",)                          # the annotator's extra masks
    assert "partial_chat_overlay" in masked[21.2].reasons and 30.0 not in masked                            # partial is not hidden
    assert [e.kind for e in o.events] == ["hp_lost"]                     # ammo read off a masked frame and swing under chat: dropped
    assert o.masked_context and not o.truncated_context and o.context_start == 17.0
    stop, = [o for o in got.observations("train", frame_hz=10.0, across_overlays=False) if o.t == pytest.approx(22.0)]
    assert stop.context_start == 20.6 and not any(f.masked and "scoreboard" in f.masked.reasons for f in stop.frames)


def test_two_annotators_masks_of_one_frame_are_unioned(tmp_path):
    d = fresh(tmp_path, "u")
    (d / "a.json").write_text(json.dumps(visibility([5.0], player="unavailable")))
    (d / "b.json").write_text(json.dumps(visibility([5.0], uppercut="partial_chat_overlay")))
    make_vod(d, split="train", annotations=[annotation(6.0, context_mask="a.json"), annotation(6.0, by="claude", outcome_mask="b.json")])
    m = demos.read_manifest(d / "vodA.manifest.jsonl").frame_masks[5.0]
    assert set(m.hidden) == {"player", "uppercut"}
    (d / "a.json").write_text("not json")
    with pytest.raises(FormatError, match="context_mask: cannot read"):
        demos.read_manifest(d / "vodA.manifest.jsonl")


# --- provenance: one authority, never mixed, never guessed -------------------------------------------------------------------------
def test_every_provenance_field_is_required_and_a_claim_needs_a_basis(tmp_path):
    p = tmp_path / "x.manifest.jsonl"
    for k in ("cooldowns_from", "patch", "patch_from", "splittable", "edited_upload"):
        h = header()
        del h[k]
        with pytest.raises(FormatError, match=f"lacks .*{k}"):
            demos.write_manifest(p, h, SEGS)
    for extra, err, why in [(dict(patch_from="vibes"), FormatError, "patch_from 'vibes' is not one of"),
                            (dict(patch=""), FormatError, "patch must be"), (dict(splittable="yes"), FormatError, "splittable must be"),
                            (dict(patch="unknown", patch_from="upload_date"), ProvenanceError, "unknown has none"),
                            (dict(patch_from="none"), ProvenanceError, "a known value needs a basis"),
                            (dict(cooldowns="off", cooldowns_from="none"), ProvenanceError, "a known value needs a basis"),
                            (dict(cooldowns_from="observed_cooldowns"), ProvenanceError, "countdowns for \\[\\]"),   # no events file
                            (dict(splittable=False, split="train"), ProvenanceError, "may only be inspection_only")]:
        with pytest.raises(err, match=why):
            demos.write_manifest(p, header(**extra), SEGS)
    assert demos.read_manifest(make_vod(fresh(tmp_path, "o"), events=EVENTS, cooldowns_from="observed_cooldowns")).cooldowns == "normal"
    d = fresh(tmp_path, "off")                                                     # countdowns seen cannot back a claim of `off`
    jsonl(d / "v.events.jsonl", [META])
    with pytest.raises(ProvenanceError, match="running countdowns prove normal"):
        demos.write_manifest(d / "v.manifest.jsonl", header(events="v.events.jsonl", cooldowns="off", cooldowns_from="observed_cooldowns"), SEGS)


def test_a_split_that_mixes_patches_is_refused_unless_asked(tmp_path):
    for n, p in enumerate(("Season 10, Version 20260911", "Season 9", "unknown")):
        make_vod(tmp_path, name=f"v{n}", vod_id=f"9{n}", split="train", patch=p, **({"patch_from": "none"} if p == "unknown" else {}))
    d = Demos.load(tmp_path)
    assert d.patches("train") == ["Season 10, Version 20260911", "Season 9", "unknown"]
    for call in (d.observations, d.samples):
        with pytest.raises(RegimeError, match=r"mixes patches \['Season 10, Version 20260911', 'Season 9', 'unknown'\].*mix_patches=True"):
            list(call("train"))
    assert {o.clip for o in d.observations("train", patch="Season 9")} == {"v1"}
    assert {o.clip for o in d.observations("train", mix_patches=True)} == {"v0", "v1", "v2"}
    with pytest.raises(RegimeError, match="mixes patches"):
        list(d.observations("train", patch=("Season 9", "unknown")))
    assert any("usable minutes: patch=Season 9 cooldowns=normal split=train: 0.8" in l for l in demos.summary(d))


def test_a_source_not_shown_independent_is_never_trained_or_scored_on(tmp_path):
    """VUH-1326 finding 3: inspection_only and non-splittable sources never reach a train/val/test iterator."""
    for n in range(40):
        make_vod(tmp_path, name=f"u{n}", vod_id=f"8{n}", splittable=False, edited_upload=True)
    make_vod(tmp_path, name="kin", vod_id="99", group="g", split="train")
    make_vod(tmp_path, name="kin2", vod_id="98", group="g", splittable=False)     # a group with one unsplittable clip: whole group out
    with pytest.raises(SplitError, match="two splits"):
        Demos.load(tmp_path)
    (tmp_path / "kin.manifest.jsonl").unlink()
    d = Demos.load(tmp_path)
    assert set(d.splits.values()) == {"inspection_only"}
    for split in ("train", "val", "test"):
        assert d.clips_in(split) == [] and list(d.observations(split)) == []
    assert len(list(d.observations("inspection_only", hz=0.2))) > 0


def test_a_run_directorys_manifest_and_meta_json_must_agree(tmp_path):
    d = make_l4_run(tmp_path, "tagrunP")
    (d / "meta.json").write_text(json.dumps({"cooldowns": "normal", "patch": "Season 10, Version 20260911"}))
    c = demos.clip_from_run(d)
    assert (c.cooldowns, c.header["cooldowns_from"], c.patch, c.header["patch_from"]) == ("normal", "run_metadata",
                                                                                           "Season 10, Version 20260911", "run_metadata")
    head = {k: v for k, v in c.header.items() if k != "type"}
    seg = [dict(start_t=0.0, end_t=25.0, started_by="run_start", ended_by="run_end")]
    demos.write_manifest(d / "manifest.jsonl", dict(head, cooldowns="off"), seg)
    with pytest.raises(ProvenanceError, match=r"disagree on \{'cooldowns': \('off', 'normal'\)\}"):
        Demos.load(d)
    demos.write_manifest(d / "manifest.jsonl", dict(head, patch="Season 9"), seg)
    with pytest.raises(ProvenanceError, match="disagree on .*patch"):
        Demos.load(d)
    demos.write_manifest(d / "manifest.jsonl", head, seg)
    assert Demos.load(d).clips["run:tagrunP"].patch == "Season 10, Version 20260911"
    (d / "meta.json").unlink()
    c = demos.clip_from_run(d)
    assert (c.cooldowns, c.patch, c.header["patch_from"]) == ("unknown", "unknown", "none")    # never from a table, never from the date


# --- real data: skipped only where data/ is absent, never on a format mismatch --------------------------------------------------
DEMOS = ROOT / "data" / "demos"
REAL_RUN = ROOT / "data" / "l1" / "tagrun0"
REAL_REQ = DEMOS / "samples" / "reqmr-2873352801-1920.manifest.jsonl"
REAL_DAY = DEMOS / "samples" / "daymr-2879354299-21600-60s.manifest.jsonl"
REAL_SECTION = DEMOS / "vods" / "reqmr-2871472478-5400-900s.manifest.jsonl"      # a retained Twitch section, with scoreboard taps
REAL_UPLOAD = DEMOS / "youtube" / "reqmr" / "Cf_2goe1snQ.manifest.jsonl"          # an edited upload: hard cuts, an unmapped teamup
REAL_RERUN = DEMOS / "annotations" / "codex-rerun" / "reqmr-2873352801-1920.jsonl"
NO_DATA = pytest.mark.skipif(not DEMOS.is_dir(), reason="data/demos is not on this machine")


def hard_gaps(clip, bridge=demos.MAX_BRIDGE_S):
    return [(a.end_t, b.start_t) for n, (a, b) in enumerate(zip(clip.segments, clip.segments[1:])) if not clip.soft_gap(n, bridge)]


def assert_windows_hold(d, clip, split="inspection_only", **kw):
    """No window crosses a hard boundary, and no event in a window was read off a frame masked for it."""
    gaps, n = hard_gaps(clip, d.max_bridge_s), 0
    for s in d.samples(split, hindsight=True, **kw):
        o, out = s.observation, s.hindsight.outcome
        lo, hi = min(f.t for f in o.frames), max([f.t for f in out.frames] or [o.t])
        assert not any(lo < b and a < hi for a, b in gaps), (o.t, lo, hi)
        for e in (o.events or ()) + (out.events or ()):
            assert d._readable(clip, e), e
        n += 1
    return n


@NO_DATA
def test_both_sample_clips_load_under_format_4():
    for path in (REAL_REQ, REAL_DAY):
        clip = demos.read_manifest(path)                             # a format 3 events file fails here, naming both versions
        assert clip.events_meta["format"] == 4 and clip.cooldowns == "normal" and clip.header["cooldowns_from"] == "observed_cooldowns"
        assert clip.patch == "Season 10, Version 20260911" and clip.header["patch_from"] == "broadcast_date"


@NO_DATA
def test_the_req_sample_manifest_iterates():
    d = Demos.load(REAL_REQ)
    clip = d.clips["reqmr-2873352801-1920"]
    assert (clip.kind, clip.header["vod_id"], clip.header["creator"], clip.header["source_start_s"]) == ("vod", "2873352801", "reqmr", 1920)
    assert clip.source_time(5.0) == 1925.0 and d.splits[clip.id] == "inspection_only"
    got = list(d.samples("inspection_only", hindsight=True))
    assert len(got) > 150 and all(s.observation.inputs is None and s.observation.events is not None and s.labels == () for s in got)
    assert assert_windows_hold(d, clip) == len(got)
    pilot = [round(s.observation.t, 3) for s in d.samples("inspection_only", decisions="manifest")]
    assert pilot == [5.0, 30.0, 45.0] and (15.0, "outside_segments") in [(x.t, x.reason) for x in d.skipped]


@NO_DATA
def test_the_codex_rerun_rows_load_bridged_with_the_annotators_own_masks(tmp_path):
    real = demos.read_manifest(REAL_REQ)
    head = {k: v for k, v in real.header.items() if k != "type"}
    head.update(media={"kind": "video", "path": str(REAL_REQ.parent / real.header["media"]["path"])},
                events=str(real._resolve(real.header["events"])), annotations=str(REAL_RERUN))
    mani = tmp_path / "req.manifest.jsonl"
    demos.write_manifest(mani, head, [dict(start_t=s.start_t, end_t=s.end_t, started_by=s.started_by, ended_by=s.ended_by)
                                      for s in real.segments])
    d = Demos.load(mani)
    kw = dict(decisions="manifest", history_s=5.0, frame_hz=10.0)
    with pytest.raises(AlignmentError, match="judged context from 40.0 but this window starts at 43.8"):
        list(d.samples("inspection_only", across_overlays=False, **kw))                     # +45: an unbridged window stops at the tap
    got = {s.observation.t: s for s in d.samples("inspection_only", **kw)}                # bridged by default
    assert sorted(got) == [5.0, 30.0, 45.0]
    s30, s45 = got[30.0], got[45.0]
    assert len(s30.observation.frames) == len(s45.observation.frames) == 51
    m45 = {round(f.t, 1): f.masked for f in s45.observation.frames if f.masked}
    assert all({"hud", "scene"} <= set(m45[t].hidden) and "scoreboard" in m45[t].reasons for t in (43.3, 43.7))   # the bridged tap
    # 43.2 is the segment's last proven frame to the segmenter, but the annotator saw the scoreboard there: every field hidden
    assert {"scene", "hp", "ammo", "swing", "get_over_here", "uppercut", "ult"} <= set(m45[43.2].hidden) and "scoreboard" in m45[43.2].reasons
    assert "player" in m45[40.6].hidden and "camera_clips_geometry" in m45[40.6].reasons                               # camera in geometry
    m30 = [f.masked for f in s30.observation.frames if f.masked]
    assert m30 and all({"uppercut", "ult"} <= set(m.hidden) and "partial_chat_overlay" in m.reasons for m in m30)       # chat over abilities
    assert not any(e.slot in ("uppercut", "ult") for e in s30.observation.events)
    assert s45.labels[0].by == "codex" and not s45.observation.truncated_context and s45.observation.context_start == 40.0
    assert assert_windows_hold(d, d.clips[real.id], decisions="manifest") == 3


@NO_DATA
def test_a_retained_section_loads_and_bridges_its_scoreboard_taps():
    d = Demos.load(REAL_SECTION)
    clip, = d.clips.values()
    assert clip.events_meta["format"] == 4 and clip.events_meta["cuts"] == 4 and clip.header["edited_upload"] is False
    assert (clip.cooldowns, clip.patch, clip.splittable, d.splits[clip.id]) == ("normal", "Season 10, Version 20260911", True, "inspection_only")
    taps = [n for n in range(len(clip.segments) - 1) if clip.soft_gap(n)]
    assert taps                                                                             # scoreboard taps under the maximum
    obs = list(d.observations("inspection_only", hz=1.0))
    bridged = [o for o in obs if any(f.masked and "scoreboard" in f.masked.reasons for f in o.frames)]
    assert bridged and all(not o.truncated_context or o.context_start > o.t - 5.0 for o in bridged)
    assert assert_windows_hold(d, clip, hz=1.0) == len(obs)
    for split in ("train", "val", "test"):
        assert list(d.observations(split)) == []


@NO_DATA
def test_an_edited_upload_loads_never_splittable_and_never_crosses_a_cut():
    d = Demos.load(REAL_UPLOAD)
    clip, = d.clips.values()
    assert (clip.edited_upload, clip.splittable, d.splits[clip.id], clip.patch) == (True, False, "inspection_only", "unknown")
    assert clip.events_meta["cuts"] == 55 and any(s.ended_by == "hard_cut" for s in clip.segments)
    null = [e for e in clip.events if e.kind == "ability_cast" and e.slot is None]
    assert null and all(e.slot_pos == "teamup" for e in null) and "teamup" not in clip.events_meta["slot_mapping"]
    # Its one null cast sits in a 0.5 s sliver between spectating and another hero: kept, named nothing, and no window is cut from it
    # (the synthetic test_a_cast_at_an_unidentified_position_stays_null_through_every_window covers a null cast inside a window).
    assert all(clip.segments[e.segment].length < demos.MIN_SEGMENT_S for e in null)
    assert not [e for o in d.observations("inspection_only", hz=1.0) for e in o.events if e in null]
    assert assert_windows_hold(d, clip, hz=1.0) > 500


@pytest.mark.skipif(not (REAL_RUN / "frames.jsonl").is_file(), reason="data/l1/tagrun0 is not on this machine")
def test_tagrun0_iterates():
    d = Demos.load(REAL_RUN)
    clip = d.clips["run:tagrun0"]
    split = d.splits[clip.id]
    assert clip.cooldowns in demos.COOLDOWNS                                              # "unknown" until its meta.json or manifest says
    obs = list(d.observations(split))
    assert len(obs) > 300 and clip.resolution == [2560, 1440] and clip.header["inputs"] == "pad"
    assert all(o.events is None and o.inputs and o.frames[-1].t == pytest.approx(o.t) for o in obs)   # inputs present, events missing
    assert all(all(f.t <= o.t + 1e-6 for f in o.frames) and all(i.t <= o.t + 1e-6 for i in o.inputs) for o in obs)
    ts = [o.t for o in obs]
    assert ts == sorted(ts) and len(set(ts)) == len(ts) and ts[0] >= 0.0 and ts[-1] <= 70.0
    assert os.path.exists(obs[0].frames[0].path) and os.path.exists(obs[-1].frames[-1].path)
    samples = list(d.samples(split, hindsight=True))
    labelled = [s for s in samples if s.labels]
    assert len(labelled) > 0.9 * len(samples) and all(l.kind == "recorded_inputs" for s in labelled for l in s.labels)
    assert all(s.hindsight.outcome.t_end <= clip.segments[0].end_t + 1e-6 for s in samples)
    assert samples[-1].hindsight.outcome.ended_by == "run_end"                                   # the run's own end cuts the window


# --- a dataset split, by name -------------------------------------------------------------------------------------------------
def split_fleet(tmp_path, status="proposed", **clip_kw):
    for n, g in enumerate(("gA", "gB", "gC")):
        make_vod(tmp_path, name=f"v{n}", vod_id=f"7{n}", group=g, **clip_kw)
    spec = dict(name="s", status=status, patch="Season 10, Version 20260911", cooldowns="normal",
                sources=[f"v{n}.manifest.jsonl" for n in range(3)], sides={"train": ["gA"], "val": ["gB"], "test": ["gC"]}, sealed=["test"])
    (tmp_path / "splits").mkdir(exist_ok=True)
    (tmp_path / "splits" / "s.json").write_text(json.dumps(spec))
    return spec


def rewrite(tmp_path, spec, **kw):
    (tmp_path / "splits" / "s.json").write_text(json.dumps(dict(spec, **kw)))


def test_a_proposed_split_loads_by_name_and_promotes_nothing(tmp_path):
    split_fleet(tmp_path, split="inspection_only")
    d = Demos.load_split("s", root=tmp_path)
    assert d.proposed == {"v0": "train", "v1": "val", "v2": "test"} and set(d.splits.values()) == {"inspection_only"}
    for side in ("train", "val", "test"):
        assert list(d.observations(side)) == []                        # a proposal yields nothing to a training iterator


def test_an_accepted_split_takes_effect_only_where_each_source_allows_it(tmp_path):
    spec = split_fleet(tmp_path, split="inspection_only", status="accepted")
    with pytest.raises(ProvenanceError, match=r"not splittable or their manifests keep another split"):
        Demos.load_split("s", root=tmp_path)                           # the split file never overrides a manifest
    d = fresh(tmp_path, "ok")
    split_fleet(d, status="accepted")                                   # manifests with split null: promotion was made in them
    got = Demos.load_split("s", root=d)
    assert got.splits == {"v0": "train", "v1": "val", "v2": "test"} and {o.clip for o in got.observations("train")} == {"v0"}
    d = fresh(tmp_path, "unsplit")
    split_fleet(d, status="accepted", splittable=False)
    with pytest.raises(ProvenanceError, match="not splittable"):
        Demos.load_split("s", root=d)


def test_a_split_refuses_a_mixed_patch_a_straddling_group_and_an_orphan(tmp_path):
    spec = split_fleet(tmp_path)
    for kw, err, why in [(dict(patch="Season 9"), RegimeError, "the split is 'Season 9'"),
                         (dict(cooldowns="off"), RegimeError, "cooldowns 'normal'"),
                         (dict(sides={"train": ["gA", "gB"], "val": ["gB"], "test": ["gC"]}), SplitError, "on 'train' and 'val'"),
                         (dict(sides={"train": ["gA"], "val": ["gB"]}), SplitError, "gC' is on no side"),
                         (dict(sides={"train": ["gA", "gZ"], "val": ["gB"], "test": ["gC"]}), SplitError, "no source: \\['gZ'\\]"),
                         (dict(sides={"dev": ["gA"], "val": ["gB"], "test": ["gC"]}), FormatError, "side 'dev'"),
                         (dict(status="final"), FormatError, "status 'final'")]:
        rewrite(tmp_path, spec, **kw)
        with pytest.raises(err, match=why):
            Demos.load_split("s", root=tmp_path)


@NO_DATA
def test_the_first_season_10_split_is_a_proposal_with_the_reserved_sessions_sealed_as_test():
    d = Demos.load_split("s10-normal-v0")
    assert d.split_spec["status"] == "proposed" and set(d.splits.values()) == {"inspection_only"}
    groups = {s: {d.clips[c].group for c, x in d.proposed.items() if x == s} for s in ("train", "val", "test")}
    assert groups["test"] == {"twitch:2877719252", "twitch:2871472478"} and d.split_spec["sealed"] == ["test"]
    assert all(d.clips[c].patch == "Season 10, Version 20260911" and d.clips[c].cooldowns == "normal" for c in d.proposed)
    assert not any(d.clips[c].edited_upload for c, s in d.proposed.items() if s != "val")
