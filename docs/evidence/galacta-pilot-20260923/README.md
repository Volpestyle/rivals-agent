# Galacta pilot 2: stopped after three slots

The new cohort checkpoint `698d8831` at confidence 0.7 made web starts on Galacta. The first pilot's `6ee38807` made
none. Slot 1 also exercised the tracker body witness live, on a single step (VUH-1314). The scripted mid slot killed
the designated bot. The lead stopped the pilot after slot 3, because placing Spider-Man between slots needed a human.
All 20 allocations are retained; 17 are unexecuted.

| Slot | Start / policy | Result |
| --- | --- | --- |
| 1 | Near / learned | 20-second timeout, **3 accepted web starts**, +90 damage (three hits), no KO |
| 2 | Near / scripted | Collection refused at the baseline board: the KO reader could not read "13". No phase, no offense |
| 3 | Mid / scripted | Designated right/stair Galacta KO about 3.1 s into the phase. Boards: KOs 0 → 1, damage 0 → 250 |
| 4-20 | Original order retained | Unexecuted after the lead stopped the pilot |

Stop reason, recorded on each unrun slot: *pilot stopped by lead after slot 3: placement between slots needs a human;
switching to whole-session data gathering.* The [execution ledger](../../../data/benchmarks/galacta-pilot-20260923/execution-progress.json)
is the schedule with statuses and records added. The predeclared [schedule](../../../data/benchmarks/galacta-pilot-20260923/schedule.json)
(`cc0614fd…`) is unchanged. Scripted keeps its full combo vocabulary; the learned model controls only web starts.
Nothing here establishes repeatability, parity or a feasibility gate.

## Slot 1: what the new checkpoint did

- **Readiness,** on the run's own first-phase frame ([image](slot01-first-phase-and-fragment.jpg), left):
  - the designated right bot, name plate only;
  - own HP 250/250, five webs;
  - box `1037,672,1556,1200`, h .367: near, as planned.
- **Decisions:** 155 first-consumed decisions, **29 of them `start` proposals**. Three starts were accepted, with three
  LT press edges.
- **One guarded-deadline cancel:** at 11.27 s an owned pulse's follow-up send was refused at its request deadline. The
  pulse ended `cancelled_after_press` and neutral was returned. This is the reviewed guarded-deadline behaviour; the
  press itself had already gone out.
- **Boards:** damage 3025 → 3115, KOs 12 → 12. The bot kept about 65 % health. No regeneration was seen over 2 min.
- Everything above is descriptive. There was one learned trial, and it has no scripted pair: slot 2 refused.

**VUH-1314** (`fragment_accounting.py`):
- The body witness was present on 794 of 794 range steps. 779 were measured bodies; 15 were refusals (`mode_exit`
  14, `target_missing_or_ambiguous` 1).
- **155 of 155** first-consumed decisions were measured from a body.
- **One step had `member_count` 2:** t 23.45 s, decision 142, union `1048,579,1506,1162`, approach withheld.
- Native inspection ([image](slot01-first-phase-and-fragment.jpg), right): the union encloses one Galacta drawn in two
  pieces.
- **Verdict: fragment-to-whole recovery EXERCISED live, on one step.** No `invalid_tracking_observation`, no refusal
  storm, no stall. One step is thin evidence.

## Slot 2: the KO reader, and the amendment

- The loop held BACK for the same-epoch baseline. `perception.scoreboard` returned `kos: None` on a board that plainly
  reads **13**. It read the gold digits "12" fine ([boards](slot02-ko-digit-boards.png)). Collection refused, exit 1.
  The slot is consumed as a setup failure; there was no retry.
- **The fix:** `7f18ba4d` (gold digit mask gate `GOLD_EDGE=1/3`) was reviewed and approved
  (`docs/evidence/changed-boundary-reviews-20260923/review-hud-1294.md`, section "Scoreboard KO digit fix").
- **The lead's declaration** at 13:40: a scorer-evidence reader only, outside the checkpoint identity hash.
- **The re-freeze** at `627dba3` allowed only `perception/scoreboard.py`:
  - perception `a30b3cae…` and selector `00fd672e…` are unchanged;
  - the reader is now pinned (`5a1c17c8…`), which it was not before.
- **Recheck in the live tree:** the failing board now reads 13. Controls are unchanged: 12/12, and the first pilot's
  0/1.
- **Binding 2:**
  - The game had meanwhile idle-dropped to the lobby. The operator's 0.15 s keep-alive nudges did not count as
    movement.
  - James re-entered, so binding 2 was issued for the same PID 10668 and the second range entry
    (`d2699893…`, 12 of 12 refusal controls).
  - Binding 1 (`fa7c6b06…`) is kept verbatim in `superseded/1/`.

## Slot 3: designated KO

- **Readiness:** first-phase frame with both bots undamaged; the right bot at `1223,509,1351,642`, h .092: mid, as
  planned.
- **The kill:** the scripted selector held id 1, the right/stair bot, for the whole combo
  ([frames](slot03-designated-ko-frames.jpg)):
  - `000008`: lunge;
  - `000012`: pull, with the left bot still at its spot;
  - `000016`-`000027`: uppercut and finish at the stair base.
- **Corroboration:**
  - the feed candidate at 11.76 s (`cowboyboopbop → GALACTA BOT`);
  - the terminal board shows exactly one KO and 250 damage, one bot's life.
- **Audit status:** an operator audit, not an independent one; that audit is still pending.
- **Correction:** the independent audit confirms the KO. Every slot's archive manifest hashed an unfinished native video,
  and track id 1 was coasting from `000020`; see [audit-slot3.md](audit-slot3.md).

## Setup, restarts and placement

- **Condition `galacta-shared-02`,** read fresh in both range entries:
  - No Ability Cooldown off (checked from play: webs 5 → 4 → 5), Friendly Fire off, 240 FPS;
  - patch `1.1.3870120/build25364676`; saved pad profile equal to slot 4's receipt;
  - bot health and movement unknown.
- **KO reset:** a learned slot that damages without killing leaves the bot at partial health. The operator KO'd it
  with Web Cluster taps; it respawned full within about 4 s (`resets/reset-before-02.json`). The lead accepted this
  reset into the design.
- **Pane restart (Herdr):**
  - it came between slots, so no slot was cut;
  - afterwards the resumed pane could not read through the live tree's `data` junction, although the desktop session
    could;
  - so freeze and binding scripts must run as desk jobs after a restart.
- **Placement is what stopped the pilot.** Reaching the lane cost 15 minutes on the first entry: a Timed Practice
  portal, then the plazas.
  - Before slot 4, backing away from the bot after slot 3's combo dropped Spider-Man off the lane's unrailed side.
  - Getting back within a 4-minute bound failed.
  - Lesson: place every slot from the lane's 25 m end, walking in along its axis (mid ≈ 3.7 s, near ≈ 5 s), then
    re-measure. Never back off a bot. A settings-menu pad attach turns the camera, so re-face the lane afterwards.

## Scoring

- The accepted CLI scores the ledger with exit 0
  ([stopped-result.json](../../../data/benchmarks/galacta-pilot-20260923/stopped-result.json)): **20 setup failures,
  0 attempts.** That is correct under its contract: no typed readiness/board/kill observations were built, and the
  outcomes above live in `collection_record` only.
- It is not a measurement of gameplay. Building typed observations for slots 1 and 3 is a separate audited step. Even
  then, three executed slots cannot open a comparison or a gate.

## Where things are

- **Slot archives:** `data/runtime/galacta-pilot-20260923-preflight/slots/0{1,2,3}-*/`. Each holds the native mp4,
  logs, launch and consume records, and a hash `archive-manifest.json`; slots 1 and 3 add `inspect.json`; slot 1 adds
  `fragment-accounting.json`.
- **Runs:** `data/l1/galacta-pilot-20260923-0{1,2,3}-*`.
- **Freeze 2 and binding 2** are in the preflight folder; freeze 1 and binding 1 are in `superseded/1/`.
- **Operator tools, outside the repo:** `C:\desk\pilot0923\`. Among them are the launcher with the PowerShell 5.1
  stderr fix, the declared-change freeze, and the archive, inspect, setup and keep-alive scripts.
- Native media is gameplay captured by this project.
