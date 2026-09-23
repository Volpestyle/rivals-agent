"""The State struct: what perception knows about one frame, and nothing more.

Perception lanes (L2 HUD, L3 detector) fill it; the brain and eval read it.
Every field a reader can fail on is Optional, and None means "could not read
this frame". None is never "zero" or "not ready"; readers must not guess.

`frame` is required and has no default: it is the (width, height) of the frame
that was actually processed, and every bbox is in those pixels. Whoever builds
the State from a frame sets it; a wrong default would put every box off by the
capture/processing scale.

One State per line of JSONL: json.dumps(state.to_dict()) / State.from_dict(json.loads(line)).
"""
from dataclasses import asdict, dataclass, field

# Detection classes (L3 trains these).
ENEMY = "enemy"    # bots / AI heroes that move and may shoot back
TARGET = "target"  # static range dummies
ANCHOR = "anchor"  # surfaces worth swinging to

# Ability names (L2 reads these from the HUD slots; primitives are in docs/spiderman-kit.md).
# Web Cluster (LT, 5 charges) is ammo, see State.webs.
SWING = "swing"        # Web-Swing (LB): 3 charges
PULL = "pull"          # Get Over Here! (RB): one 8 s cooldown shared by the pull and the web strike
UPPERCUT = "uppercut"  # Amazing Combo (X): 2 charges
ULT = "ult"            # Spectacular Spin


@dataclass(frozen=True)
class Detection:
    cls: str
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels of the State.frame it sits in
    conf: float
    distance: float | None = None  # metres, estimated; None = no estimate
    tagged: bool | None = None  # Spider-Tracer icon over this enemy; None = not read (icon absent from view is not "untagged")
    track: int | None = None  # identity, assigned once by agent.tracker between the finder and State; None = not tracked. Never reused
    plate: bool | None = None  # the game's name-and-health bar was seen belonging to this box; None = its place was out of view or not read

    @property
    def center(self):
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def height(self):
        return self.bbox[3] - self.bbox[1]


@dataclass(frozen=True)
class Ability:
    ready: bool | None = None   # None = icon unreadable this frame
    charges: int | None = None  # None = unreadable, or the ability has no charges


@dataclass
class State:
    t: float  # seconds, monotonic within a run (capture timestamp, not wall clock)
    frame: tuple[int, int]  # (width, height) of the processed frame; bboxes are in these pixels. Required, so it sits before the defaults
    hp: float | None = None
    max_hp: float | None = None
    abilities: dict[str, Ability] = field(default_factory=dict)  # missing key = unknown
    webs: int | None = None  # Web-Cluster ammo
    detections: list[Detection] | None = None  # None = detector did not run; [] = ran, saw nothing
    on_target: bool | None = None  # crosshair over a hostile
    coasting: tuple[int, ...] = ()  # track ids the tracker still holds but did not see this frame (hit flash, occlusion, off the edge)
    kill_feed: bool | None = None  # a kill-feed line is on screen (perception.scoreboard.is_killfeed); None = not read. Names no victim

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        dets = d.get("detections")
        w, h = d["frame"]  # strict: a State without its frame size cannot be interpreted
        return cls(
            t=d["t"],
            frame=(w, h),
            hp=d.get("hp"),
            max_hp=d.get("max_hp"),
            abilities={k: Ability(**v) for k, v in (d.get("abilities") or {}).items()},
            webs=d.get("webs"),
            detections=None if dets is None else [Detection(**{**x, "bbox": tuple(x["bbox"])}) for x in dets],
            on_target=d.get("on_target"),
            coasting=tuple(d.get("coasting") or ()),
            kill_feed=d.get("kill_feed"),
        )
