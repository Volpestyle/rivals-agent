"""Track ids (VUH-1314): one identity per enemy, assigned once, between the finder and State.

The finder returns boxes with no memory, so the brain re-picked "the enemy nearest where the last one was" every tick while the controller
kept its own private Track, and the two could disagree about who the target was. Here every detection gets a `track` id at the one place
detections become a State (agent.loop calls `update` for the controller's per-frame boxes and for the brain's whole-frame search, on one
instance). The brain's memory and Jev's re-association follow the id. The controller does not read it: its `_follow` still re-associates
its own Track by bearing (docs/lanes/tracker.md).

An id survives the four ways the green finder loses a bot (docs/lanes/l3-detector.md, "Where the 13 misses come from"):

  hit flash      the outline washes out for a few frames after our own hit (~0.35 s)
  small, far     the box is at the size floor and flickers in and out
  point blank    the outline runs off the frame edge and fails the fill test (the controller holds a close box 1.5 s)
  occluded       the bot passes behind Spider-Man's own body as the camera turns onto it (~0.5 s)

by holding the track, coasting it on its last velocity, for a while after its last sighting (MAX_AGE_S, longer for a close or a small box),
and by matching the bot when it comes back to where the track says it should be, not to whichever box is nearest the crosshair. While a
confirmed track is held but unseen its id is in `coasting`, so the brain knows the target is briefly missing and not gone.

Stdlib only. `update(dets, t, frame)`: `t` in seconds, `frame` (w, h) of the frame the boxes are in (only the height is used, to tell a close
or a small box). Ids are never reused.
"""
import math
from dataclasses import dataclass, replace

MAX_AGE_S = 0.8      # a confirmed track is held this long unseen: a hit flash (~0.35 s), a pass behind the hero (~0.5 s), with margin
CLOSE_AGE_S = 1.5    # ...and this long once its box is close: the controller's own CLOSE_LOST_S for a point-blank outline off the edge
SMALL_AGE_S = 1.2    # ...and this long once it is small: a far bot at the size floor flickers, and a small box barely moves on screen
NEW_AGE_S = 0.3      # a track seen fewer than CONFIRM times is a maybe (a lit panel, a lamp): it is dropped fast, and never "coasting"
CONFIRM = 3
CLOSE_H = 0.20       # box height / frame height from which a box is close (0.6 * brain.RANGES.near_h, the controller's own threshold)
SMALL_H = 0.05
GATE = 1.3           # a detection may sit this many box sizes from where its track is predicted. Measured on tagrun0 (docs/lanes/tracker.md):
                     # the bot's own re-associations jump up to 1.12 sizes (688 px at point blank). A fresh bot within 1.3 of a hit-flashed
                     # target still takes its id: the residual risk in docs/lanes/tracker.md
SIZE_RATIO = 2.5     # ...and its height may differ from the track's by at most this factor: a lamp's box is not a bot's, whatever is near it
CLOSE_RATIO = 4.5    # ...except when either box is close: a point-blank outline is cut by the frame edge, so its size means little
IOU_MIN = 0.1
SPLIT_X = 0.6        # two boxes of one frame are one body drawn in pieces (the finder's split at close range) if they overlap this share of the
SPLIT_GAP = 0.25     # narrower one's width, are STACKED (apart or overlapping vertically by at most this share of the shorter one's height; a bot
SPLIT_RATIO = 2.5    # standing behind another overlaps it over its whole height), comparable in size, and their union is body-shaped
BODY_ASPECT = (1.2, 4.5)   # the union's height / width: a bot's box is ~2.4
PIECE_INSIDE = 0.7   # a box that would start a NEW id is instead a piece of a confirmed body if this share of it lies inside that body's box
EDGE_PX = 3          # a box within this of the edge of the region it was found in (the aim crop) is cut by it
PIECE_PAD = 0.10     # (padded by this share of its size): the finder draws a close bot as 2-5 pieces that change every frame, and the aim
                     # crop's edges cut it; on postfreeze30 that made 14 of the engaged bot's new ids (docs/lanes/tracker.md)
HIST_S = 1.0         # a track remembers the heights it had this long, so one small stray box does not make its real size unrecognisable
STEADY = 1.6         # a velocity is only learned between boxes of similar height: a box cut by the frame edge jumps in size and centre
SMOOTH = 0.5         # weight kept from the old velocity
PREDICT_S = 0.3      # a velocity is trusted for this long: coasting further than that stands still (a stale velocity walks off the bot)


@dataclass
class _Track:
    id: int
    cls: str
    box: tuple
    seen_t: float
    hits: int = 1
    vx: float = 0.0      # centre velocity, px/s, in the frame the boxes are in
    vy: float = 0.0
    hs: list = None      # (t, height) over the last HIST_S
    cam: tuple = None    # (yaw, pitch) degrees of the camera the box was last placed in; None = not known

    def __post_init__(self):
        self.hs = [(self.seen_t, self.box[3] - self.box[1])]

    @property
    def size(self):
        return max(self.box[2] - self.box[0], self.box[3] - self.box[1])


def _same_body(a, b):
    """Are boxes a and b one body split in two? Same width band, stacked one above the other with a small gap or seam, comparable in size,
    and body-shaped together. Two bots in a line overlap over their whole height, so they stay two."""
    ah, bh = a[3] - a[1], b[3] - b[1]
    if min(ah, bh) <= 0 or max(ah, bh) / min(ah, bh) > SPLIT_RATIO:
        return False
    x = min(a[2], b[2]) - max(a[0], b[0])
    gap = max(a[1], b[1]) - min(a[3], b[3])          # negative when they overlap vertically
    u = _union((a, b))
    return (x >= SPLIT_X * min(a[2] - a[0], b[2] - b[0]) and abs(gap) <= SPLIT_GAP * min(ah, bh)
            and BODY_ASPECT[0] <= (u[3] - u[1]) / max(u[2] - u[0], 1e-9) <= BODY_ASPECT[1])


def _turned(box, was, now, frame):
    """`box` as the camera `now` (yaw, pitch, focal px) sees what the camera `was` (yaw, pitch) saw there: a still point's bearing is the
    camera's plus atan(offset / focal), so turning right moves it left on screen, pitching up moves it down."""
    (w, h), f = frame, now[2]
    dyaw, dpitch = (now[0] - was[0] + 180.0) % 360.0 - 180.0, now[1] - was[1]      # a whole turn brings a still point back

    def along(v, half, d):
        a = math.atan2(v - half, f) + math.radians(d)
        return half + f * math.tan(max(-1.5, min(1.5, a)))
    return (along(box[0], w / 2, -dyaw), along(box[1], h / 2, dpitch), along(box[2], w / 2, -dyaw), along(box[3], h / 2, dpitch))


def _union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _iou(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    i = w * h
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)


class Tracker:
    def __init__(self):
        self.tracks, self._next = [], 1
        self.coasting = ()   # ids of confirmed tracks held but not matched by the last update

    def _predicted(self, tr, t):
        dt = min(max(t - tr.seen_t, 0.0), PREDICT_S)
        x1, y1, x2, y2 = tr.box
        dx, dy = tr.vx * dt, tr.vy * dt
        far = math.hypot(dx, dy) / max(tr.size, 1.0)
        if far > 1.0:                                # never predict further than a box size: a wild velocity walks off the bot
            dx, dy = dx / far, dy / far
        return (x1 + dx, y1 + dy, x2 + dx, y2 + dy)

    def _cost(self, tr, box, t, frame=None):
        """Lower is a better match; None if the box cannot be this track. Close and overlapping is best."""
        dh = box[3] - box[1]
        heights = [tr.box[3] - tr.box[1]] + [h for tt, h in tr.hs if t - tt <= HIST_S]     # its last height, and those it has had lately
        th = min(heights, key=lambda h: max(h, dh) / max(min(h, dh), 1e-9))              # the one nearest this box's height
        close = frame is not None and max(th, dh) >= CLOSE_H * frame[1]
        if min(th, dh) <= 0 or max(th, dh) / min(th, dh) > (CLOSE_RATIO if close else SIZE_RATIO):
            return None
        pb = self._predicted(tr, t)
        pcx, pcy = (pb[0] + pb[2]) / 2, (pb[1] + pb[3]) / 2
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        size = max(tr.size, box[2] - box[0], box[3] - box[1], 1.0)
        near, overlap = math.hypot(cx - pcx, cy - pcy) / size, _iou(pb, box)
        return near - overlap if near <= GATE or overlap >= IOU_MIN else None

    @staticmethod
    def _bodies(dets):
        """Indices of `dets` grouped by body: boxes that are one body drawn in pieces share a group."""
        groups = []
        for i, d in enumerate(dets):
            hit = [g for g in groups if any(dets[k].cls == d.cls and _same_body(dets[k].bbox, d.bbox) for k in g)]
            merged = [i] + [k for g in hit for k in g]
            groups = [g for g in groups if g not in hit] + [merged]
        return sorted(groups, key=min)

    @staticmethod
    def _body_of(box, cls, got, boxes):
        """The confirmed track whose body `box` is a piece of, or None. Only a body matched in this same update can take pieces (a lone
        small box where a body is merely predicted is not that body: a lamp at a coasting bot's place stays a lamp). Most of the box must
        lie inside the body's box (last update's and the one it matched now), padded, and the box be no taller than the body."""
        best, share = None, PIECE_INSIDE
        for gi, tr in got.items():
            if tr.cls != cls or tr.hits < CONFIRM:
                continue
            body, pad = _union([tr.box, boxes[gi]]), PIECE_PAD * max(tr.size, 1.0)   # where it was, and the box it matched now
            if box[3] - box[1] > body[3] - body[1] + pad:
                continue
            w = max(0.0, min(box[2], body[2] + pad) - max(box[0], body[0] - pad))
            h = max(0.0, min(box[3], body[3] + pad) - max(box[1], body[1] - pad))
            inside = w * h / max((box[2] - box[0]) * (box[3] - box[1]), 1e-9)
            if inside >= share:
                best, share = tr, inside
        return best

    def _entering(self, box, cls, clip, used, t):
        """Index of the held, confirmed track whose body a box cut by `clip`'s edge is the visible part of, or None. A bot turned into the
        aim crop enters it as a sliver at the crop's edge (stall30: a 24 x 30 px box, of a bot the whole-frame search saw as 693 x 504),
        which no size or distance gate matches. It is that bot if the track's predicted body (where the camera turn put it) reaches the same
        edge of the crop and the box lies inside that body, unpadded: padding alone once let a body wholly inside the crop claim a box
        outside it (input-path review)."""
        cut = (abs(box[0] - clip[0]) <= EDGE_PX or abs(box[1] - clip[1]) <= EDGE_PX
               or abs(box[2] - clip[2]) <= EDGE_PX or abs(box[3] - clip[3]) <= EDGE_PX)
        if not cut:
            return None
        best, share = None, PIECE_INSIDE
        for k, tr in enumerate(self.tracks):
            if k in used or tr.cls != cls or tr.hits < CONFIRM:
                continue
            pb = self._predicted(tr, t)
            # The body itself must reach the edge that cut the box: a body wholly inside the crop has no part out there to show.
            reaches = ((abs(box[0] - clip[0]) <= EDGE_PX and pb[0] <= clip[0] + EDGE_PX) or (abs(box[1] - clip[1]) <= EDGE_PX and pb[1] <= clip[1] + EDGE_PX)
                       or (abs(box[2] - clip[2]) <= EDGE_PX and pb[2] >= clip[2] - EDGE_PX) or (abs(box[3] - clip[3]) <= EDGE_PX and pb[3] >= clip[3] - EDGE_PX))
            if not reaches:
                continue
            w = max(0.0, min(box[2], pb[2]) - max(box[0], pb[0]))            # and the box lie in the body itself, not in a margin round it
            h = max(0.0, min(box[3], pb[3]) - max(box[1], pb[1]))
            inside = w * h / max((box[2] - box[0]) * (box[3] - box[1]), 1e-9)
            if inside >= share:
                best, share = k, inside
        return best

    def _age(self, tr, frame):
        if tr.hits < CONFIRM:
            return NEW_AGE_S
        h = (tr.box[3] - tr.box[1]) / frame[1] if frame else None
        return CLOSE_AGE_S if h is not None and h >= CLOSE_H else SMALL_AGE_S if h is not None and h <= SMALL_H else MAX_AGE_S

    def update(self, dets, t, frame=None, cam=None, clip=None):
        """The same detections with `track` set, in order. Tracks not matched are held (see the module docstring) or dropped. None is [].

        `cam`: (yaw, pitch, focal px) of the camera this frame shows, from the controller's commanded-camera model. Held tracks are moved
        into it before anything is matched, so a camera turn does not carry a bot past its gate: on stall30 the re-aim turned 19 degrees
        between a bot's last whole-frame box and its first aim-crop box, 1.5 track sizes on screen, and it got a new id both times.
        `clip`: (x1, y1, x2, y2) of the region the boxes were found in when it is not the whole frame (the aim crop)."""
        dets = dets or []
        stored = {}                              # each track's own box and camera, put back unless a newer measurement replaces them
        if cam is not None and frame is not None:
            for tr in self.tracks:
                stored[id(tr)] = (tr.box, tr.cam)
                if tr.cam is not None:           # matched against a VIEW of the track in this frame's camera: the projection can clamp
                    tr.box = _turned(tr.box, tr.cam, cam, frame)   # (a box behind an older camera), so it is never written back
        moved = set()
        self.tracks = [tr for tr in self.tracks if t - tr.seen_t <= self._age(tr, frame)]   # an expired track cannot claim a box
        groups = self._bodies(dets)
        boxes = [_union([tuple(dets[i].bbox) for i in g]) for g in groups]
        pairs = sorted(((c, gi, k) for gi, g in enumerate(groups) for k, tr in enumerate(self.tracks)
                        if tr.cls == dets[g[0]].cls and (c := self._cost(tr, boxes[gi], t, frame)) is not None), key=lambda p: p[0])
        got, used = {}, set()
        for _, gi, k in pairs:
            if gi in got or k in used:
                continue
            got[gi] = self.tracks[k]
            used.add(k)
        direct = dict(got)                       # the bodies matched on their own: the only witnesses (an absorbed piece is never one,
        for gi, g in enumerate(groups):          # or the footprint chains outward piece by piece and the result depends on the order)
            if gi not in direct and (tr := self._body_of(boxes[gi], dets[g[0]].cls, direct, boxes)) is not None:
                got[gi] = tr
        if clip is not None:                     # a box cut by the aim crop's edge: the part of a bot that has come in so far
            for gi, g in enumerate(groups):
                if gi not in got and (k := self._entering(boxes[gi], dets[g[0]].cls, clip, used, t)) is not None:
                    got[gi] = self.tracks[k]
                    used.add(k)
        parts = {}                               # one update per track: the union of every group it got
        for gi, tr in got.items():
            parts.setdefault(tr.id, []).append(gi)
        ids = {}
        for gi, g in enumerate(groups):
            tr = got.get(gi)
            if tr is not None and parts[tr.id][0] != gi:
                ids.update({i: tr.id for i in g})    # a further piece: labelled, the track updated once below with the union
                continue
            box = boxes[gi] if tr is None else _union([boxes[k] for k in parts[tr.id]])
            if tr is not None and t < tr.seen_t:
                # A measurement older than the track's last sighting (the decision worker's whole-frame search lands after newer aim-crop
                # updates) names the box but does not move the track: on stall30 a 60 ms older box, taken before a turn, replaced the
                # crop's box of the same bot, and the next frame's box fell outside the gate.
                ids.update({i: tr.id for i in g})
                continue
            if tr is None:
                tr = _Track(self._next, dets[g[0]].cls, box, t, cam=cam[:2] if cam is not None else None)
                self._next += 1
                self.tracks.append(tr)
            else:
                dt = t - tr.seen_t
                cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                ox, oy = (tr.box[0] + tr.box[2]) / 2, (tr.box[1] + tr.box[3]) / 2
                oh, nh = tr.box[3] - tr.box[1], box[3] - box[1]
                if 0 < dt <= PREDICT_S and max(oh, nh) <= STEADY * max(min(oh, nh), 1.0):
                    tr.vx, tr.vy = SMOOTH * tr.vx + (1 - SMOOTH) * (cx - ox) / dt, SMOOTH * tr.vy + (1 - SMOOTH) * (cy - oy) / dt
                else:
                    tr.vx = tr.vy = 0.0          # a long gap, or a box that changed size: the old velocity says nothing about where it went
                tr.box, tr.seen_t, tr.hits = box, max(tr.seen_t, t), tr.hits + 1
                tr.cam = cam[:2] if cam is not None else tr.cam
                moved.add(id(tr))
                tr.hs = [(tt, h) for tt, h in tr.hs if t - tt <= HIST_S] + [(t, box[3] - box[1])]
            ids.update({i: tr.id for i in g})
        for tr in self.tracks:
            if id(tr) in stored and id(tr) not in moved:
                tr.box, tr.cam = stored[id(tr)]
            elif tr.cam is None and cam is not None and id(tr) not in stored:
                tr.cam = cam[:2]                 # a track born in this update is in this frame's camera
        out = [replace(d, track=ids[i]) for i, d in enumerate(dets)]
        seen = {tr.id for tr in got.values()} | {tr.id for tr in self.tracks if tr.seen_t >= t}
        self.coasting = tuple(tr.id for tr in self.tracks if tr.id not in seen and tr.hits >= CONFIRM)
        return out
