"""agent/tracker.py on RECORDED frames: the green finder's real output over tagrun0 (the Luna Snow bot from ~8 m to point blank, hit, lost, found),
with the brain choosing a target from the tracked detections. Needs the perception group and data/l1/tagrun0 (gitignored)."""
import json
import math
from pathlib import Path

import cv2
import pytest

from agent.brain import Memory, decide
from agent.state import State
from agent.tracker import CLOSE_AGE_S, Tracker
from perception.outline import find_enemies

RUN = Path(__file__).resolve().parent.parent / "data" / "l1" / "tagrun0"
pytestmark = pytest.mark.skipif(not (RUN / "frames.jsonl").is_file(), reason="data/l1/tagrun0 is not on this machine")
FRAME = (2560, 1440)
N = 216


@pytest.fixture(scope="module")
def recorded():
    """[(t, [Detection])] for the first N recorded frames: what the finder really returned, native pixels."""
    rows = [r for r in map(json.loads, (RUN / "frames.jsonl").read_text().splitlines()) if "file" in r][:N]
    out = []
    for r in rows:
        f = cv2.imread(str(RUN / r["file"]))
        out.append((r["t"], find_enemies(f, scale=f.shape[1] / 1280.0)))
    return out


def track(recorded):
    tr, out = Tracker(), []
    for t, dets in recorded:
        got = tr.update(dets, t, FRAME)
        out.append((got, tr.coasting))
    return out


def biggest(dets):
    return max(dets, key=lambda d: d.height, default=None)


def test_the_bot_keeps_one_id_from_first_sight_through_a_split_body_a_dropout_and_the_point_blank_boxes(recorded):
    tracked = track(recorded)
    big = {i: [d for d in got if d.height / FRAME[1] >= 0.15] for i, (got, _) in enumerate(tracked) if 4 <= i <= 27}
    ids = {d.track for ds in big.values() for d in ds}
    assert len(ids) == 1, ids                         # frames 4-27: one bot, one id (the finder splits it in two at 19; loses it at 24; cuts it at 26-27)
    bot = ids.pop()
    assert bot in tracked[24][1]                       # frame 24: nothing found, and the tracker says the bot is held, not gone
    assert biggest(tracked[26][0]).track == bot        # frame 26: a point-blank box 0.67 of the frame high is still it


def test_the_same_id_follows_the_bot_for_fifteen_seconds_including_the_fight_and_the_crowd(recorded):
    tracked = track(recorded)
    ids = {biggest(got).track for got, _ in tracked[71:197] if got}
    assert len(ids) == 1, ids                           # frames 71-196: the standing bot, through the combo, the hits and the loss of sight


def test_other_bots_get_their_own_ids_and_an_id_never_comes_back_after_it_was_let_go(recorded):
    tracked = track(recorded)
    times = {}
    for (t, _), (got, _) in zip(recorded, tracked):
        for d in got:
            times.setdefault(d.track, []).append(t)
    assert all(b - a <= CLOSE_AGE_S for ts in times.values() for a, b in zip(ts, ts[1:]))     # a gap longer than the tracker's memory would be a reused id
    assert len({d.track for d in tracked[200][0]}) >= 2                                        # several bots in view at 22 s: several ids
    assert len(times) > 10                                                                     # and a great many boxes were tracked


def test_the_brain_holds_its_target_by_id_through_the_recorded_fight(recorded):
    def target_seq(with_ids):
        m, tr, seq = Memory(), Tracker(), []
        for t, dets in recorded:
            got = tr.update(dets, t, FRAME) if with_ids else dets
            decide(State(t=t, frame=FRAME, hp=250, max_hp=250, detections=got, coasting=tr.coasting if with_ids else ()), m)
            seq.append(m.target)
        return seq

    seq, plain = target_seq(True), target_seq(False)
    bot = biggest(track(recorded)[10][0]).track
    assert all(d is not None and d.track == bot for d in seq[8:28])                    # locked on from frame 8 to 27
    assert len({d.track for d in seq[71:197] if d is not None}) == 1                   # and on ONE bot from 71 to 196, whatever else came into view

    def jumps(s):      # frame to frame, a target whose centre moved by more than its own size: the brain re-picking, or a bot crossing the screen
        return sum(1 for a, b in zip(s, s[1:]) if a is not None and b is not None and a is not b
                   and math.dist(a.center, b.center) > max(a.height, b.height))
    assert jumps(seq) < jumps(plain)                                                   # the id rule jumps less than "nearest to where it was"
