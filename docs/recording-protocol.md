# Recording protocol: whole-session Spider-Man data (from 2026-09-23)

Goal: about 3 to 5 hours of logged practice-range play, then a first end-to-end
behaviour-cloning fit (frames in, keys and mouse out) on the Mac. The pilot of the
web-start timing head (`docs/evidence/galacta-pilot-20260923/`) stopped at 3 of 20
slots on 2026-09-23 because the between-slot placement needed a human; the head
proved the pipe (3 accepted starts, 3 hits) and is not the product. This protocol
replaces event-only recording (VUH-1351) with whole-session recording.

## What James does per session

1. OBS with the Rivals Input Logger enabled (`C:\Users\volpe\obs-input-logger\README.md`),
   Tools > Rivals Input Logger - Status says enabled and waiting. Same OBS profile as
   before (2560x1440, 120 fps, MKV). Nothing else changes.
2. Same game settings as the September 23 sessions: normal cooldowns (No Ability
   Cooldown OFF), Friendly Fire OFF, 240 FPS cap, same DPI, sensitivity and bindings.
   If any of these change, say so with the recording. Once per campaign, and again after any
   change: a 5-second look at the Controls settings screen (mouse sensitivity, DPI if shown,
   swing mode, key bindings) inside a recording, so the motor settings that the mouse counts
   depend on are pinned from pixels and not from memory. Keyboard and mouse only; the logger
   cannot see a controller, so say if one was ever plugged in.
3. Start recording, tab into the game once, play 20 to 30 minutes, tab out once, stop.
   One recording is one session. Do not pause OBS. If you must stop early, stop the
   recording and start a new one later; do not resume.
4. Play the range as yourself, not as a demo. Wanted, in roughly this mix:
   - both Galacta bots, from near, mid and far starts;
   - approaches on foot, by swing, and from above; leave and come back;
   - full combos with real cooldown waits, and also interrupted or wasted ones;
   - misses, whiffed pulls, bad angles, falling off the terrace and climbing back;
   - other bots and areas of the range too, once the Galacta pair is well covered;
   - resource variety: sometimes web-empty, sometimes ult ready, sometimes nothing.
   Do not stand still for more than about a minute; the game's idle kick ends the session.
   Cooldowns on for most sessions: that is where the decisions live (two webs left, wait
   for uppercut or commit). No Ability Cooldown ON sessions are welcome as extra
   mechanics reps (aim, combo execution) if you say so when you drop the path; the
   regime scan separates them from normal-regime rows automatically. Roughly two hours
   on to one hour off.
5. Afterwards, drop the video path in chat. The logger folder is matched by time in
   `C:\Users\volpe\Videos\RivalsInput\`. Nothing else is needed from you.

Mistakes are wanted. A model that only sees clean combos never learns a recovery.

## Real games

If you are playing matches anyway (quick play, versus AI), record them the same way, as
Spider-Man. They do not train the range agent yet: the range perception is tuned to
the practice-range bots, and no agent input goes near a live lobby. They feed the later
stages (inverse dynamics for replay imitation, VUH-1353; match behaviour, VUH-1323) and
cost nothing extra to capture now. Range sessions come first until the 3-hour mark.

## What breaks a session

- Alt-Tab or focus loss mid-play: the logger discards inputs outside the game, and the
  gap becomes an excluded interval. Once in and once out is fine.
- OBS pause/resume: excluded interval; avoid.
- Changing sensitivity, DPI, bindings, or the cooldown setting inside a session: the
  session cannot be admitted as one identity. Change between sessions and say so.
- Idle kick to the lobby: the rest of the recording is lobby footage; stop there.
- A game patch: still record; the patch is a first-class fact on every source (VUH-1324).

## What the swarm does with it

- Whole-session intake (VUH-1309 extension): every focused gameplay frame and its
  input history become training rows, not only web-start events. Keeps the recorder
  verification, muxer-offset anchor, regime scan and split registry already used for
  admission; adds per-interval imitation suitability at session granularity.
- Tally: a running table of admitted minutes per session and per scenario mix, so the
  3-hour mark is a fact and not a feeling.
- First fit when admitted minutes cross about 3 hours: a small causal frame/input
  policy on the Mac, held-out session evaluation per the learning plan's
  [step 4](learning-plan.md#paired-human-execution-current-work), then
  a live range pilot with reset-based placement (no human between trials).
