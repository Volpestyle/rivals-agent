"""One recorded normalization, the same for expert footage and for our own runs.

The policy sees the scene, not the chrome. Every frame from either domain goes through the
same path: decode at the source's own frame rate, scale the whole 16:9 frame to SIZE x SIZE,
then paint the HUD and the known permanent overlays with the encoder's mean colour. The
version stamp `NORM` goes into every cache entry, so an embedding can never be read as
having come through a different normalization than it did.

What is masked, and why (bounds read off inspected frames from both creators and one of our
own runs; the streamer regions were confirmed by a temporal-std map over 120 frames spread
across each 15-minute VOD, where a permanent graphic is a pixel that never changes):

  game chrome   the objective banner, the score/timer, the kill feed and the whole bottom HUD
                band. Present in both domains at the same fractions (perception/hud.py reads its
                fields at 0.87-0.95 of the height), and the HUD lane reads those pixels at native
                resolution before this ever runs. A policy must not re-read hp off a 224 px thumbnail.
  per creator   the FPS/ping counter, and each streamer's permanent furniture: DayMR's avatar,
                music widget and sponsor panel. These are painted on every frame of that
                creator's video and nothing else's, so unmasked they are a source fingerprint.

Chat is **not** masked. The std map shows it scrolling, so it is not a permanent graphic, and
its panel sits over live play (the learning plan's warning about blanket-masking the chat
column). The risk that is accepted instead: a model may key on "chat text is present" as a
creator cue. Held-out-session metrics are what would expose it, and re-encoding the corpus
under a changed mask costs a few minutes.

Times are **decoded** presentation timestamps, never a nominal grid: frames are picked by
source frame index (`select`) and their real PTS is read back from ffmpeg's `showinfo`, because
the sample clips are variable frame rate (the demos lane measured Req at 4082 frames in 60.08 s
against a reported 60/1). A cache row is keyed by its source and that timestamp.
"""
import re
import subprocess
import threading
from pathlib import Path

import numpy as np

NORM = "n1"     # normalization version; bump on any change to SIZE, the fill or the rects below
SIZE = 224
FILL = (124, 116, 104)   # ImageNet mean in 8-bit: a masked region normalizes to ~0, the least-activating input
BLEED_PX = 2             # the scale mixes ~5 source pixels into one output pixel; grow every rect by this

# (x0, y0, x1, y1) as fractions of the frame.
GAME_CHROME = (
    (0.00, 0.000, 0.32, 0.160),   # top-left: objective lines, or the PRACTICE RANGE panel in our runs
    (0.31, 0.000, 0.69, 0.110),   # top-centre: score and round timer
    (0.76, 0.000, 1.00, 0.100),   # top-right: kill feed
    (0.00, 0.855, 1.00, 1.000),   # bottom band: portrait, ammo, hp, ability slots, the UID line
)
FPS_COUNTER = (0.91, 0.130, 1.00, 0.300)   # the same green FPS/ping block on both creators and our PC

OVERLAYS = {
    "us": (FPS_COUNTER,),
    "reqmr": (FPS_COUNTER,),
    "req": (FPS_COUNTER,),
    "daymr": (FPS_COUNTER,
              (0.00, 0.590, 0.13, 0.830),   # music widget, lower left
              (0.79, 0.690, 1.00, 0.820),   # sponsor panel, lower right
              (0.57, 0.650, 0.77, 0.870)),  # the Spider-Man avatar: person-like, painted on every frame
    "day": (FPS_COUNTER,
            (0.00, 0.590, 0.13, 0.830),
            (0.79, 0.690, 1.00, 0.820),
            (0.57, 0.650, 0.77, 0.870)),
}
DEFAULT_OVERLAYS = (FPS_COUNTER,)   # a creator with no inspected sample gets the chrome and nothing invented

_PTS = re.compile(rb"pts_time:([0-9.]+)")


def thin(times, hz):
    """Indices of the frames at most 1/hz apart: a run saves at its own rate, not the cache's."""
    step, out, last = 1.0 / hz, [], -1e9
    for i, t in enumerate(times):
        if t - last >= step - 1e-9:
            out.append(i)
            last = t
    return out


def rects(creator):
    """The mask rectangles for a source, as fractions. Unknown creators get chrome only."""
    return GAME_CHROME + OVERLAYS.get(creator, DEFAULT_OVERLAYS)


def mask(batch, creator, size=SIZE):
    """Paint the rects over a [n, size, size, 3] uint8 batch, in place. Returns it."""
    for x0, y0, x1, y1 in rects(creator):
        a = max(0, int(x0 * size) - BLEED_PX)
        b = max(0, int(y0 * size) - BLEED_PX)
        c = min(size, int(round(x1 * size)) + BLEED_PX)
        d = min(size, int(round(y1 * size)) + BLEED_PX)
        batch[:, b:d, a:c] = FILL
    return batch


def visible_fraction(creator, size=SIZE):
    """How much of the frame survives the mask: what the policy is actually given."""
    kept = mask(np.ones((1, size, size, 3), np.uint8), creator, size)[..., 0]
    return float((kept == 1).mean())


class Decoded:
    """Frames out of one media file at `hz`, with the timestamp each frame really carries.

    Iterating yields [n, SIZE, SIZE, 3] uint8 batches, masked. `times` fills as they are read
    and is complete when iteration ends; `check()` refuses a run whose frame and PTS counts
    disagree, so a row can never be given a time that is not its own.
    """

    def __init__(self, path, creator, hz, src_fps, size=SIZE, batch=64):
        self.path, self.creator, self.hz, self.size, self.batch = Path(path), creator, hz, size, batch
        self.every = max(1, round((src_fps or 60.0) / hz))   # keep one source frame in `every`
        self.times, self.frames = [], 0

    def _cmd(self):
        return ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(self.path),
                # showinfo goes AFTER the scale: it checksums every plane it sees, and doing that on
                # full 1080p frames costs ~20% of the whole pass. scale does not touch PTS.
                "-vf", f"select='not(mod(n,{self.every}))',scale={self.size}:{self.size}:flags=area,showinfo",
                "-fps_mode", "passthrough", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]

    def __iter__(self):
        proc = subprocess.Popen(self._cmd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        reader = threading.Thread(target=self._read_pts, args=(proc.stderr,), daemon=True)
        reader.start()
        n = self.size * self.size * 3
        try:
            while True:
                buf = proc.stdout.read(n * self.batch)
                if not buf:
                    break
                k = len(buf) // n
                self.frames += k
                yield mask(np.frombuffer(buf[: k * n], np.uint8).reshape(k, self.size, self.size, 3).copy(),
                           self.creator, self.size)
        finally:
            proc.stdout.close()
            proc.wait()
            reader.join(timeout=10)

    def _read_pts(self, stderr):
        for line in stderr:
            found = _PTS.search(line)
            if found:
                self.times.append(float(found.group(1)))
        stderr.close()

    def check(self):
        if len(self.times) != self.frames:
            raise ValueError(f"{self.path.name}: {self.frames} frames decoded but {len(self.times)} timestamps read; "
                             "a frame would be given a time that is not its own")
        return np.asarray(self.times, np.float64)


class DecodedJpegs(Decoded):
    """The same path for a run's saved jpgs, read as an image sequence in filename order.

    A run's timestamps come from its frames.jsonl, not from the media, so the caller supplies
    them; the constructor refuses a directory whose jpgs are not exactly the files the index
    names, in that order, because then row i would not be frame i.
    """

    def __init__(self, directory, files, creator, size=SIZE, batch=64):
        super().__init__(directory, creator, hz=1, src_fps=1, size=size, batch=batch)
        on_disk = sorted(p.name for p in self.path.glob("*.jpg"))
        if on_disk != sorted(files) or list(files) != sorted(files):
            raise ValueError(f"{self.path}: the jpgs on disk are not the {len(files)} the index names in order; "
                             "row i would not be frame i")
        self.files = list(files)

    def _cmd(self):
        return ["ffmpeg", "-hide_banner", "-nostdin", "-f", "image2", "-pattern_type", "glob",
                "-i", str(self.path / "*.jpg"),
                "-vf", f"scale={self.size}:{self.size}:flags=area", "-fps_mode", "passthrough",
                "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]

    def check(self):
        if self.frames != len(self.files):
            raise ValueError(f"{self.path.name}: {self.frames} frames decoded from {len(self.files)} jpgs")
        return self.frames
