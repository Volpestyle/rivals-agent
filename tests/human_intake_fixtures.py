"""Synthetic recorder sessions for whole-session intake tests, importable by other lanes' contract tests.

    from tests.human_intake_fixtures import session_payload, steps_payload, build_dataset, key_event, mouse_event

Everything here is generated in memory or under a caller's `tmp_path`; nothing opens the corpus. A payload is the
importer's own `{metadata, events, packets, decoded}` shape (100 fps, one frame per 10 ms), and `build_dataset`
turns it plus review segments into an `agent.human_demos.HumanDataset` with the importer's `_build`, exactly as
`load_dataset` would after hashing real files.
"""
from agent import human_demos as hd

BASE = 10**17 + 7   # beyond float-exact integers
MS = 1_000_000
STEP = 10 * MS      # the synthetic frame period


def key_event(ms, vk, scan, down, device=12, flags=None):
    return dict(type="key", t_ns=BASE + ms * MS, device=device, vk=vk, scan=scan,
                flags=(0 if down else 1) if flags is None else flags, down=down)


def mouse_event(ms, device=22, **kw):
    row = dict(type="mouse", t_ns=BASE + ms * MS, device=device, dx=0, dy=0, motion_flags=0, button_flags=0,
               wheel_data=0, relative=True, buttons_down=[], buttons_up=[], wheel_vertical=0, wheel_horizontal=0)
    row.update(kw)
    return row


def session_payload(tmp_path, esc_at_ms, total_ms=3000):
    """A focused session with steady mouse motion every 20 ms and one Esc press at `esc_at_ms`."""
    video = tmp_path / "original.mkv"
    video.write_bytes(b"synthetic")
    ev = [dict(type="raw_input_status", t_ns=BASE, ok=True), dict(type="focus", t_ns=BASE, active=True, held_vk=[])]
    for ms in range(20, total_ms - 20, 20):
        ev.append(mouse_event(ms, dx=3, dy=-1))
    ev += [dict(key_event(esc_at_ms, 27, 1, True), t_ns=BASE + esc_at_ms * MS + 1),
           dict(key_event(esc_at_ms, 27, 1, False), t_ns=BASE + esc_at_ms * MS + 5 * MS + 1)]
    ev.sort(key=lambda e: e["t_ns"])
    for i, row in enumerate(ev):
        row["seq"] = i
    n = total_ms // 10
    packets = []
    for i in range(n):
        row = dict.fromkeys(hd.FRAME_COLUMNS, 0)
        row.update(event_seq=len(ev) + i, packet_index=i, pts=i * 10, dts=i * 10, timebase_num=1, timebase_den=1000,
                   composition_ns=BASE + i * STEP)
        packets.append(row)
    meta = dict(schema_version=1, control_type="keyboard_mouse", status="complete", complete=True, clean_stop=True,
                writer_failed=False, queue_dropped_events=0, raw_input_errors=0, first_queue_drop_ns=0,
                last_queue_drop_ns=0, frames_without_composition_timestamp=0, events_attempted=len(ev) + n,
                video_packets=n, input_events=sum(e["type"] in ("key", "mouse") for e in ev), start_ns=BASE,
                end_ns=BASE + n * STEP, width=640, height=360, fps_num=100, fps_den=1, capture_latency_calibrated=False,
                session_id="s1", video_path=str(video.resolve()), target_executable="Marvel-Win64-Shipping.exe")
    return dict(metadata=meta, events=ev, packets=packets,
                decoded=dict(timebase_num=1, timebase_den=1000, pts=[21 + i * 10 for i in range(n)], width=640, height=360))


def rebuild(data, events):
    """Replace a payload's events, renumbering sequences and the metadata counts consistently."""
    for i, row in enumerate(events):
        row["seq"] = i
    n = len(data["packets"])
    for i, p in enumerate(data["packets"]):
        p["event_seq"] = len(events) + i
    data["events"] = events
    data["metadata"].update(events_attempted=len(events) + n,
                            input_events=sum(e["type"] in ("key", "mouse") for e in events))
    return data


def steps_payload(tmp_path):
    """A session exercising the step tables: W held with a repeated make, an RMB press, C (team-up, bound to no fit
    action), mouse X1, and the Esc at 2.9 s."""
    data = session_payload(tmp_path, esc_at_ms=2900)
    extra = [key_event(100, 87, 17, True), key_event(150, 87, 17, True), key_event(400, 87, 17, False),
             mouse_event(500, button_flags=4, buttons_down=[2]), mouse_event(600, button_flags=8, buttons_up=[2]),
             key_event(700, 67, 46, True), key_event(720, 67, 46, False),
             mouse_event(800, button_flags=64, buttons_down=[4]), mouse_event(810, button_flags=128, buttons_up=[4])]
    return rebuild(data, sorted(data["events"] + extra, key=lambda e: e["t_ns"]))


SETTINGS = dict(dpi=800, horizontal_sensitivity=1.89, vertical_sensitivity=1.89,
                swing_mode={"automatic_swing": False, "hold_to_swing": True}, mouse_acceleration=True,
                mouse_smoothing=True)
BINDINGS = {"move_forward": ["key:17:0"], "move_left": ["key:30:0"], "move_back": ["key:31:0"],
            "move_right": ["key:32:0"], "jump": ["key:57:0"], "web_swing": ["key:42:0"], "get_over_here": ["key:33:0"],
            "amazing_combo": ["key:18:0"], "ultimate": ["key:16:0"], "melee": ["key:47:0", "mouse:5"],
            "spider_power": ["mouse:1"], "web_cluster": ["mouse:2"], "team_up": ["key:46:0"],
            "goh_targeting": ["mouse:4"]}
ALIASES = {"mouse:5": "melee"}
PATCH = "1.1/build"
DENYLIST = dict(schema_version=1, sessions=[dict(session_id="sealed-1", media_path="C:/v/sealed.mkv",
                                                 media_sha256="d" * 64)])


def review_for(data, segments, *, settings=None, bindings=None, aliases=None, patch=PATCH, regime="normal"):
    """A minimal importer review over the given segments, with provenance in the shape assembly writes."""
    cite = [{"path": "synthetic", "sha256": "0" * 64}]
    prov = {"hero": "Spider-Man",
            "settings": {"value": settings or SETTINGS, "source": "s", "evidence": cite},
            "bindings": {"value": bindings or BINDINGS, "aliases": ALIASES if aliases is None else aliases,
                         "source": "s", "evidence": cite},
            "game_patch": {"value": patch, "source": "s", "evidence": cite},
            "cooldown_regime": {"value": regime, "source": "s", "evidence": cite}}
    return dict(schema_version=1, session_id=data["metadata"]["session_id"], reviewer="r", reviewed_at="now",
                device_scope={"kind": "single_keyboard_mouse", "source": "synthetic"},
                pts_anchor={"kind": "independent_muxer_offset", "offset_num": 21, "offset_den": 1000,
                            "source": "synthetic"},
                provenance=prov,
                alignment={"kind": "assumption", "statement": "CTS clock", "source": "synthetic"}, segments=segments)


def build_dataset(data, segments, *, group="g", split="train", **review):
    """The importer's HumanDataset for a payload and review segments (`review` overrides the provenance)."""
    data["review"] = review_for(data, segments, **review)
    meta = data["metadata"]
    return hd._build(data, hd.Placement(meta["session_id"], group, split, meta["video_path"]), "a" * 64)
