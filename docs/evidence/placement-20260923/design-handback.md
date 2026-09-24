# pilot-prep: placement design written (VUH-1359, VUH-1299)

Offline, no game input, no commit. The deliverable is `docs/lanes/placement.md` (new lane; I am its single writer).

## Answer

**Don't reset; home on the Galacta pair.**

**No reset exists in the range:**
- The pause menu and Practice Settings have no reset or respawn row.
- Re-picking the hero doesn't respawn the player.
- Re-entry costs:
  - an idle drop of about 10 min, because `l4_menu` has no confirmable Leave Game by design;
  - `cooldowns-off` every time;
  - a new binding per entry;
  - a lobby where X is Quick Match.
- "Suicide" is unknown: bots don't attack and Friendly Fire is off.

**The pair signature.** The two courtyard bots, as the existing finder boxes them, form a geometric signature:
- same floor (Δy1 ≤ 12 px), same size (≤ 12 %);
- **separation / height ∈ [3.3, 4.3]**, measured at 3.6-4.0 at every distance on the lane;
- box top in the on-lane band (on-lane 475-545 at 1440p; below the terrace, 975);
- midpoint near screen centre.

**Checked on 17 pilot-2 frames:**
- On-lane frames pass, and every off-lane frame fails: under-terrace, below the ledge, the other lane, and point blank.
- `scene-03`, James's 25 m park, shows the finder missing one bot on a single frame. So the rule takes up to 3 fresh
  frames.
- Distance comes from the target's `h`: 25 m ≈ .038, mid target .085-.11, near .33-.37.

## Procedure

1. **P0 classify** the fresh frame.
2. **P1 reacquire (LOST):** camera-only 60° sweeps; never walk while the pair is out of view.
3. **P2 back away from point blank,** in 0.4 s pulses, keeping the target centred and requiring `h` to fall and `y1` to
   stay in band after every pulse. This replaces the blind 2.5 s back-walk that fell off the terrace.
4. **P3 distance servo:** keep the pair's midpoint centred until `h` is in the bin band.
5. **P4 readiness.**
6. **Limits:** one retry, 90 s / 40 pulses, then hand back with the slot unconsumed.

The numbers are measured from my runs, not guessed:
- yaw 172°/s at 0.45 (0.35 s ≈ 60°, 1.05 s ≈ 180°);
- 25 m → mid ≈ 3.7 s of walk; 15 m → near ≈ 3.9 s;
- web refill 2 s per charge;
- respawn ≤ ~4 s.

**Slot endings:**
- **KO ending:** wait 5 s, then P0-P3, then wait for swing charges.
- **Timeout ending:** the accepted Web Cluster KO reset first (the bot is damaged), then the same.
- **Setup failure:** P0 only.

## James once vs offline

**Offline now:**
- the rules as a pure function over finder output, tested on the pilot-2 frames and the first pilot's scouts;
- a simulated-lane planner test;
- James's logged sessions, for more PAIR frames and true walk rates.

**One supervised look:**
- whether falling into the courtyard water respawns;
- one live P1-P3 run from the three real failure states: after a KO, the under-terrace nook, and the lower plaza;
- the spawn-to-courtyard route in a logged session, only if re-entry is ever the last resort.

No reset menu needs looking at, because there is none.

## Caveats

- The signature's thresholds come from 17 frames of one day, one camera pitch and one pair of bots. The logged
  sessions should widen them before the rule gates a pilot.
- The lane's unrailed right side is known only from the fall. The limits in P2 guard it by the `y1` band, not by a map.
