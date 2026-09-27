"""Step 3: the learned chooser behind the loop's existing brain seam.

`LearnedBrain` has `brain.decide`'s signature, so `agent/loop.py --brain learned` reads nothing
special of it. **The scripted gate runs first, exactly as the Jev path does** — retreat, a
playing hold and a flickering target never wait on a model — and the head only replaces
`brain.policy`, the choice. Every answer is then put through `jev.legal`, the same preconditions
`brain.policy` enforces, and adopted with `jev.adopt`, the same hold and mode bookkeeping. None
of that is rewritten here; it is imported.

  uv run --group policy python -m policy.train --save weights/policy-off   # make a head
  uv run --group policy python -m policy.live --bench                      # latency on this Mac
  python -m agent.loop --dry data/l1/baseline1 --brain learned             # offline, fake pad

**Nothing here runs live.** The controller lane owns the desktop.

The head reads pixels, which the `decide(state, memory)` seam does not carry, so this object also
exposes `see(frame, t)`: the loop's decision worker hands it the frame the `State` was built from,
just before deciding. That is the one change in `agent/loop.py` besides the flag, it is
duck-typed like the loop's other seams (`.source`, the tracker), and a brain without `see` is
called exactly as before.

An answer is dropped, and the tick falls to `brain.policy`, when the head names something no
target can execute, when the frame history is too short to be a window, or when the pixels have
not arrived. Each reason is counted, so a run says how often the head actually chose.
"""
import argparse
import json
import sys
import time
from collections import Counter, deque
from pathlib import Path

import mlx.core as mx
import numpy as np

from agent import brain, jev
from agent.brain import Memory
from agent.intents import BURST
from .encode import DEFAULT, Encoder
from .frames import SIZE, mask
from .train import Head, _state_features, emb_dim_of, layout

ROOT = Path(__file__).resolve().parent.parent

# Our recorders' note vocabulary -> the intent names jev.legal and jev.build speak.
# `combo` is the BURST macro; `stand` and `idle` are both "choose nothing this tick", which is
# what the scripted policy is for, so they are never adopted as an answer.
TO_JEV = {"engage": "engage", "pull": "pull", "webstrike": "web_strike", "combo": BURST,
          "swingto": "swing_to", "search": "search", "disengage": "disengage"}
PASS = ("idle", "stand", "none")   # answers that mean "nothing to adopt": the scripted policy fills the tick


class LearnedBrain:
    """decide(state, memory) -> Intent, with the scripted gate in front and the kit checks behind."""

    source = "learned"

    def __init__(self, head=None, encoder=None, max_age_s=1.0):
        head = Path(head or ROOT / "weights" / "policy-off")
        self.spec = json.loads(head.with_suffix(".json").read_text())
        self.classes = self.spec["classes"]
        self.model = Head(self.spec["width"], len(self.classes))
        self.model.load_weights(str(head.with_suffix(".safetensors")))
        self.model.eval()
        self.encoder = encoder or Encoder(self.spec.get("encoder", DEFAULT), batch=1)
        self.steps = self.spec["steps"]
        self.dim = self.spec.get("emb_dim") or emb_dim_of(self.spec["width"])
        self.at_col = layout(self.dim)          # the trainer's own layout, never a second copy
        self.period = 1.0 / self.spec["frame_hz"]
        self.max_age_s = max_age_s          # pixels older than this are not a window we may decide on
        self.seen = deque(maxlen=self.steps)     # (t, embedding)
        self.states = deque(maxlen=self.steps)   # (t, State)
        self.stats = Counter()
        self.trace = []

    # --- pixels -------------------------------------------------------------------------
    def see(self, frame, t):
        """The frame the State was built from. Encoded at the head's own rate, never faster."""
        if self.seen and t - self.seen[-1][0] < self.period - 1e-9:
            return
        self.seen.append((t, self.encoder(self._prepare(frame))[0]))

    def _prepare(self, frame):
        """Native BGR capture -> the recorded normalization: RGB, SIZE x SIZE, our own masks."""
        import cv2  # noqa: PLC0415 - the loop's own dependency, absent from the policy group
        small = cv2.resize(frame, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        return mask(rgb[None, ...].copy(), "us")

    # --- the window ---------------------------------------------------------------------
    def window(self, state):
        """[1, steps, width], oldest first, or None when the pixels are missing or stale.

        Absent steps stay zero with their present bits clear: a short history is a masked window,
        never invented frames.
        """
        if not self.seen or state.t - self.seen[-1][0] > self.max_age_s:
            return None
        block = np.zeros((self.steps, self.spec["width"]), np.float32)
        for k, (_, emb) in enumerate(self.seen):
            at = self.steps - len(self.seen) + k
            block[at, :self.dim], block[at, self.at_col["emb_present"]] = emb, 1.0
        for k, (_, st) in enumerate(self.states):
            at = self.steps - len(self.states) + k
            feat, present = _state_features(st.to_dict() if hasattr(st, "to_dict") else st)
            o = self.at_col["state"]
            block[at, o:o + self.spec["state_f"]], block[at, self.at_col["state_present"]] = feat, float(present)
        # The event channel and the scene-mask bit stay zero: no live event stream feeds this seam
        # yet, and nothing live proves a hidden scene. A zero with its bit clear is exactly what the
        # head was trained to read for "not available".
        return block[None, ...]

    def ranked(self, block):
        """Class names, most probable first."""
        logits = self.model(mx.array(block))
        mx.eval(logits)
        return [self.classes[i] for i in np.asarray(logits)[0].argsort()[::-1]]

    # --- the seam -----------------------------------------------------------------------
    def __call__(self, state, memory: Memory):
        self.states.append((state.t, state))
        early, target = brain.gate(state, memory)
        if early is not None:
            return self._done("gate", early)

        block = self.window(state)
        if block is None:
            self.stats["no_pixels"] += 1
            return self._done("scripted", brain.policy(state, memory, target))

        hostile = jev.hostiles(state, target)
        for name in self.ranked(block):
            if name in PASS:
                self.stats["passed"] += 1
                break
            wanted = TO_JEV.get(name)
            if wanted is None:
                self.stats["vocab"] += 1
                continue
            det = next((d for d in hostile if jev.legal(wanted, state, d)), None) if wanted in jev.TARGETED else None
            if wanted in jev.TARGETED and det is None:
                self.stats["illegal"] += 1
                continue
            if wanted not in jev.TARGETED and not jev.legal(wanted, state, None):
                self.stats["illegal"] += 1
                continue
            return self._done("learned", jev.adopt(state, memory, target, wanted, det))
        self.stats["fell_back"] += 1
        return self._done("scripted", brain.policy(state, memory, target))

    def _done(self, source, intent):
        self.stats[source] += 1
        self.source = source            # the loop logs this per tick, as it does for Jev
        self.trace.append((round(getattr(intent, "t", 0.0) or 0.0, 3), source))
        return intent


def bench(head=None, n=200):
    """See + decide latency on this Mac, at batch 1, on a real frame."""
    from agent.state import Detection, State
    learned = LearnedBrain(head)
    frame = np.random.randint(0, 255, (1440, 2560, 3), dtype=np.uint8)
    state = State(t=0.0, frame=(2560, 1440), hp=250, max_hp=250, webs=5,
                  detections=[Detection("enemy", (1200, 600, 1300, 800), 0.9, tagged=False)], on_target=True)
    memory = Memory()
    see_ms, decide_ms = [], []
    for i in range(n):
        state.t = i * 0.1
        t0 = time.perf_counter()
        learned.see(frame, state.t)
        t1 = time.perf_counter()
        learned(state, memory)
        t2 = time.perf_counter()
        if i > 10:
            see_ms.append((t1 - t0) * 1000)
            decide_ms.append((t2 - t1) * 1000)

    def spread(xs):
        xs = sorted(xs)
        return f"p50 {xs[len(xs)//2]:.1f} / p95 {xs[int(len(xs)*0.95)]:.1f} / max {xs[-1]:.1f} ms"

    print(f"see (resize, mask, encode) {spread(see_ms)}")
    print(f"decide (window, head, gate, legality) {spread(decide_ms)}")
    print(f"total per decision tick {spread([a + b for a, b in zip(see_ms, decide_ms)])}")
    print(f"sources {dict(learned.stats)}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bench", action="store_true")
    ap.add_argument("--head", help="path without suffix (default weights/policy-off)")
    a = ap.parse_args(argv)
    if a.bench:
        return bench(a.head)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
