"""Read a run's outcome off the screen, and be explicit about what is not there.

  uv run --no-project --with opencv-python-headless --with numpy \
      python -m perception.evalread <run_dir> [--limit N]

**Damage dealt and eliminations are not on screen in the practice range.**
That is a finding, not a gap in this file. Checked across the 6360 frames of
run1 and the 347 of trial1:

- No scoreboard. The practice range draws the player's own HUD and the bots'
  nameplates, nothing else. A scoreboard would need TAB held down, which means
  sending input, which this lane does not do.
- No kill feed. The top-right corner carries the FPS/ping overlay and nothing
  else.
- No damage counter, and floating damage numbers drift from the hit and fade,
  so no fixed region holds them (see docs/evidence/l2).
- An enemy nameplate vanishing is not an elimination: it happens 511 times in
  run1's 636 seconds, because the camera turns away.
- The enemy health bar's red length shrinks both with damage and with distance,
  and its empty half is not separable from the background at 720p, so it yields
  no health fraction to difference into damage.

So `damage_dealt` and `eliminations` come back `None` on these recordings, every
frame, by construction rather than by failure. What the screen does carry is
below; `summarise()` turns a run into the numbers an eval can actually stand on.

To get real damage and elimination numbers, someone has to record frames with
the scoreboard open. That is an input-sending lane's job, and this reader can be
pointed at those frames when they exist.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `agent`

from perception.hud import read as read_hud  # noqa: E402
from perception.outline import detect as find_enemies  # noqa: E402


@dataclass(frozen=True)
class EvalRead:
    """One frame's worth of outcome signal. None means "not readable here"."""

    enemies_visible: int | None = None  # hostiles the game is marking with a nameplate
    ult_charge: float | None = None     # 0..1 of the ult diamond; see the caveat below
    hp: int | None = None
    damage_dealt: int | None = None     # never readable in the practice range
    eliminations: int | None = None     # never readable in the practice range


def read(frame) -> EvalRead:
    hud = read_hud(frame)
    if hud.hp is None and hud.bar_fill is None:
        return EvalRead()  # menu or loading screen: nothing here is about a run
    return EvalRead(enemies_visible=len(find_enemies(frame)),
                    ult_charge=hud.ult_charge, hp=hud.hp)


def summarise(reads, seconds=None):
    """A run's worth of reads, rolled up.

    `ult_gained` is the one damage-shaped number available, and it is a proxy,
    not a measurement: the ult meter fills with damage dealt but the conversion
    rate is the game's and is not calibrated here. Report it as ult charge, and
    never as damage.
    """
    live = [r for r in reads if r.enemies_visible is not None]
    if not live:
        return {"frames": len(reads), "frames_in_play": 0}
    charges = [r.ult_charge for r in live if r.ult_charge is not None]
    gained = 0.0
    for a, b in zip(charges, charges[1:]):
        if b > a:
            gained += b - a          # rises only; a use resets the meter to zero
    hps = [r.hp for r in live if r.hp is not None]
    return {
        "frames": len(reads),
        "frames_in_play": len(live),
        "seconds": None if seconds is None else round(seconds, 1),
        "enemy_visible_frac": round(sum(r.enemies_visible > 0 for r in live) / len(live), 3),
        "max_enemies_at_once": max(r.enemies_visible for r in live),
        "ult_charge_gained": round(gained, 2),
        "ult_full_frac": round(sum(c >= 1.0 for c in charges) / len(charges), 3) if charges else None,
        "hp_min": min(hps) if hps else None,
        "hp_unreadable_frac": round(1 - len(hps) / len(live), 3),
        "damage_dealt": None,
        "eliminations": None,
        "why_none": "no scoreboard, kill feed or damage counter is drawn in the practice range",
    }


def walk(run_dir, limit=None):
    index = Path(run_dir) / "frames.jsonl"
    if not index.exists():
        sys.exit(f"{index}: not found (is {run_dir} an L1 run directory?)")
    rows = [json.loads(line) for line in index.read_text().splitlines() if line.strip()]
    if limit:
        rows = rows[:limit]
    reads, seconds = [], (rows[-1]["t"] - rows[0]["t"]) if rows else None
    for row in rows:
        frame = cv2.imread(str(Path(run_dir) / row["file"]))
        if frame is not None:
            reads.append(read(frame))
    return reads, seconds


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run_dir")
    p.add_argument("--limit", type=int)
    p.add_argument("--per-frame", action="store_true", help="also print one JSON line per frame")
    a = p.parse_args(argv)
    reads, seconds = walk(a.run_dir, a.limit)
    if a.per_frame:
        for r in reads:
            print(json.dumps(asdict(r)))
    print(json.dumps(summarise(reads, seconds), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
