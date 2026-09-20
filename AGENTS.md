# rivals-agent

A vision-based agent that plays Spider-Man in the Marvel Rivals **practice range** on a
virtual Xbox 360 pad. The game runs on the Windows PC `supedupsilly`; development runs
from this Mac, usually as a Herdr swarm. `CLAUDE.md` is a symlink to this file.

## Read before doing anything

1. `docs/plan.md`: scope boundary, gate results, architecture, perception decisions. The
   scope boundary is binding: pixels only, no anti-cheat evasion, no matchmade modes, and
   a path the game rejects stays closed. Stop and report instead of working around it.
2. The `rivals-live-game` skill (`.agents/skills/`) before sending any input to the game.
   On the PLAY lobby the pad's `X` starts a live Quick Match.
3. Linear project **Rivals Agent** (team Vuhlp): what is done, in progress and blocked.
   Accepted results and evidence go on the issue; working notes stay in `docs/lanes/`.

## Where things live

| Path | Holds |
|---|---|
| `docs/plan.md` | Lead-only. One writer, because a shared edit lost sections once |
| `docs/lanes/<lane>.md` | Each lane's present-state notes and measured facts; the lane's owner is its only writer |
| `docs/spiderman-kit.md` | Sourced controller bindings, cooldowns, tracer rule, combos, settings |
| `docs/evidence/` | Inspected screenshots and contact sheets per lane |
| `agent/` | `State` contract, intents, scripted brain, Jev client, replay |
| `perception/` | HUD readers, enemy finders, training, offline State replay |
| `scripts/` | `pad.py` (pad token sequencer), `padrun.sh`, `capture.py`, `record.py` |
| `.env` | `OPENROUTER_API_KEY`; gitignored, also at `C:\rivals-agent\.env`. Never print or log it |

## Rules that came from real failures

- `State.frame` is required and comes from the frame actually processed. Every
  `Detection.bbox` is in those pixels. A default frame size once put every box 2x off.
- A perception reader returns a value or an explicit unknown (`None`), never a guess, and
  the brain never reads unknown as zero.
- Any loop that sends input confirms the range HUD on a fresh frame first and stops when
  it disappears. Workers never navigate the lobby; they hand back to the lead.
- Detections inside the player's own screen region are ignored before aiming: a labeller
  once boxed Spider-Man's arm as an enemy.
- Capture and pad code run inside the PC's desktop session, not plain SSH.
- The PC's GPU belongs to the game while it is running. Train on the Mac (MPS), niced.
- One agent drives the PC desktop at a time.

## Working here

- `uv run pytest` runs the offline suite; no network, no game.
- Python via `uv`; standard library first; add a dependency only when a few lines cannot do it.
- Several agents often share this checkout. Edit only the paths your brief names, and
  load the `shared-checkout` skill before committing.
