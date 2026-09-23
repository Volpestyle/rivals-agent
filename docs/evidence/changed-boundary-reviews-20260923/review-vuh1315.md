# Review: VUH-1315 observed option status (`vuh-1315-observed-option-status`, `0f71336..0ba2805`)

Reviewer: `option-review`. This was a read-only review. No repo file was edited, nothing was committed, no input was sent to the
game and nothing was written to Linear. Scratch work is in `scratchpad/review-1315/`: the probes (`probe_*.py`),
`mutate_extra.py` with its result `mutate_extra.json`, and `ev/` (the reruns of `run.py`, `replay.py` and `mutation.py`).

## Verdict: approve, with required fixes

The core mechanism is sound:
- One function ends an option.
- Evidence carries its observation and `State.t`.
- The controller's cut is identity-guarded.
- Range-skill mode is byte-identical.
- The Jev launch timing is equivalent.

I reproduced every number the author reported. Four things are required before this lands or before the result goes on
Linear:
- **F2:** a doc correction.
- **F3:** a small debounce fix with a test.
- **F1:** a lead decision on the "only cut or shorten" invariant, which does not hold by construction.
- **F4:** the two missing tests that pin the arrival and swing rules.

## Findings, most severe first

### F1: "only cut or shorten" is false by construction. It holds on both recordings. Lead decision required.

An option ending can make the loop press sooner, and in one path press more. There are two mechanisms.

**(a) On `Pull` or `WebStrike`, `stop` can never remove a press. It only moves the next attack earlier.**
- `web_strike` and `pull` are an RB tap plus a no-press wait of `strike_s` 0.7 or `pull_s` 0.8 (`agent/controller.py:456-457`).
  Cutting that wait cuts no input. It releases `Engage`'s `not self.seq` gate (`controller.py:561`), so X or RT starts during
  the time the controller reserved for the zip.
- Arrival is "box `near`" (`brain.py:338`). That means about 4 m by outline height, not contact.
- Probe (`probe_arrival.py`): a tagged mid-range bot, `WebStrike`, RB at 0.067, and the box `near` from RB+0.35.
  - Base presses: RB 0.067, **X 0.850**, RT 1.433.
  - Branch presses: RB 0.067, **X 0.500**, RT 1.083.
- Arrival never fired on trial 0 or plaza30, so no real-data evidence covers this path.

**(b) A KO reopens the choice on the same decision, and the same option can be re-committed on a target that is still boxed.**
- `gate` falls through on `completed` (`brain.py:205-219`). `policy` (`brain.py:266`), `jev._stand`→`adopt` and
  `LearnedRangeBrain` can commit a new `Combo` at once. `stop` then cuts the old burst, and `self.played is not intent` plays the
  new one (`controller.py:496-497, 568-572`).
- Probe (`probe_recommit.py`):
  - Setup: `Combo(A)` committed at 0.0, first LT at 0.067; the kill feed reads False, then True at 0.2 and 0.3.
  - A is still boxed and PULL and UPPERCUT read ready. That happens in the cooldowns-off regime, or on any KO before the
    burst's RB at about +0.31 s.
  - Branch: an **extra LT at 0.300**, and the burst restarts 0.233 s late (RB 0.617, X 1.383).
  - Base: never presses LT there.
- The KO names no victim. Two cases follow:
  - Another bot's KO restarts A's burst.
  - A downed A that is still boxed gets a fresh burst. When its box goes, `TRACK_LOST` ends that option without a stop, so the
    restarted burst plays out on nothing.
- The `probe_commit_tick.py` trace "first True on the commit tick" shows `completed` and the new option `running` on the same
  decision at 0.1.

**On the data:** trial 0 and plaza30 have **zero rows** where the branch sends an attack input the base did not. The branch sends
33 and 24 fewer rows respectively (scratch `ev/*-tree.json` against `*-base.json`).

**Options for the lead:**
1. Emit `stop` only where the remaining primitive holds presses, that is `Combo`/`burst`. Or at least emit no `stop` on
   `ARRIVAL`. Completion itself stays.
2. On the decision a KO completes an option, start no new option on that target id.
3. Restate the invariant as: "the ending option's own remaining presses are only removed; later choices may start sooner". Then
   pin (b) with a test either way.

I recommend 1 plus 3.

### F2: The trial 0 "before" is misstated. The base hold did not run to 3.400. Required doc fix before the Linear post.

The replay's own base decisions show the hold cancelled by track loss at **2.348**. From then on, `hold_until` is None and the
intent is Search (scratch `ev/trial0-base.json`). `summary.json` agrees: `base_holds` records the Combo last repeated at 2.2338.

The base's RT 2.275-3.375 and LT 3.450 came from the **controller primitive playing on** after the hold had ended, because only
`Idle` and `Disengage` cut one.

So on trial 0:
- The brain-level gain is one decision: 2.234 against 2.348.
- The real gain is `stop`: RT 2.275-3.375 and LT 3.450 are removed.

Rows to correct:
- `docs/evidence/option-status-20260923/README.md:52` ("The option ends | hold to 3.400")
- `docs/lanes/l5-brain.md:154` ("held to 3.400")
- `option-status-final.md`, acceptance 4 ("the hold runs to 3.400")

Acceptance 4's claim ("ends at the KO, not at 3.0 s") should say the option ended at the KO and its primitive stopped there. On
the base, the option had already ended on track loss while the burst played on to 3.45 s.

### F3: `_ko` re-arms on a single False. The extractor it cites needs two. Required small fix.

- `brain.py:304-305` resets on any one False read. The code comment says `FEED_CONFIRM` mirrors `perception/events.py`
  `DEBOUNCE["killfeed"]=2`. `_Channel.push` (`events.py:727-750`) needs two consecutive Falses to leave a confirmed True.
- Probe (`probe_debounce.py`, the same reads through both): for `False, T, T, T, False, T, T`, `_ko` finds onsets at reads 2
  **and 6**. The extractor finds one, at read 2. The two agree on the brief's cases:
  - `F,None,T,None,T` gives read 4 in both.
  - A flicker gives nothing in both.
  - Line up at start gives nothing in both.
- Consequence: one misread False while a line is still up yields a spurious KO. That completes the running option on a live bot
  and cuts its burst.
  - Lines stay up about 4.9 s. Live reads every decision frame, about 49 reads per line.
  - Neither recording has a mid-line False: the feed sequences are clean.
- Fix: after a confirmed onset, re-arm only after `FEED_CONFIRM` consecutive False reads, as `_Channel` does. Add the case to
  `test_a_ko_is_two_true_reads_after_a_false`.

### F4: Test gaps (low). I ran 14 extra mutants; 3 survived

The 14 mutants cover `tests/test_options.py`, `test_brain`, `test_tracker`, `test_jev`, `test_jev_async` and `test_loop`.

- **`arrival_on_any_target_box` survives.** It makes `_own_box` return the picked target instead of the held id's box
  (`brain.py:320`). Add a test: a `WebStrike` on id 1 that is coasting, with a near heir or another hostile present, gives
  no arrival.
- **`stop_on_ko_for_any_kind` survives.** `test_a_ko_stops_no_swing` only covers a *running* swing, and there `gate` returns before
  the stop line (`brain.py:203-204`). No test covers a SwingTo that has ended at its bound followed by a KO.
- **`loop_stop_when_stale` survives,** but it is equivalent: a stale decision is `Idle`, which clears `seq` anyway.
- **Unpinned but correct:** a KO confirmed on the commit tick is consumed by `gate` before `policy` commits, so the new option runs
  on (`probe_commit_tick.py`). Also unpinned: the same-tick re-commit in F1(b).

### F5: A replay debounce note (info)

- 34 of 304 plaza30 decisions reuse the previous decision's saved frame.
- The **25.075 KO is confirmed from one frame, `000165.jpg`, read twice.**
- The README's timing claim stays true. The replay confirms no earlier than live: the first True read is at a decision at or after
  the saved frame, which is at or after the line's onset.
- But that KO does not exercise the two-frame debounce. The README should say so.
- Live confirms up to 0.12 s sooner, so it cuts sooner and also chooses sooner (F1). Its denser reads mean more exposure to F3.

## Confirmed sound

1. **Ordering** in `brain.py` is `_ko` → retreat → `option_status` → `stop` → RETREAT → flicker → policy.
   - Retreat ends a running option (`RETREAT_HP`), and RETREAT's `commit(Disengage)` supersedes any option. So no option runs in
     RETREAT mode. The mutant `retreat_does_not_end_option` is killed.
   - A completed option is never re-issued through the flicker grace:
     - It is blocked by `not completed` on the completing decision.
     - After that, `memory.intent` is always a newly committed intent. `policy`, `adopt` and `LearnedRangeBrain._refuse` all
       commit, and range-skill starts no options.
   - `commit` of a non-option leaves `Memory.option` as the ended option, by design. A stale `stop` is harmless:
     - The cut needs `played is stop`, a non-empty `seq` and `seq_name ==` that option's primitive.
     - `Engage`'s `web_cluster`, `uppercut` and `melee_combo` never match.
2. **KO rules** match the brief on every case except F3.
3. **Lost target.**
   - `_hold_stands` is byte-identical to the base, called under the same `t < bound` condition.
   - Legacy `State.coasting` is still `tuple(tracker.coasting)` (`loop.py:561`, the `observation=False` path). VUH-1314 changed
     only the range-mode observation path.
4. **`Controller.step(stop=)`.**
   - It compares by identity. An equal intent that is another object does not cut (the `stop_by_equality` mutant is killed).
   - A repeated stop is a no-op. The `seq_name` guard holds (its mutant is killed).
   - A cut sends `rt=0` on the same step, because `out` is rebuilt from `NEUTRAL`, so there is no stuck hold.
   - `Idle` and `Disengage` are unchanged.
   - `stop` is passed on **every fresh reflex tick** until the next decision (`loop.py:765,772`), not once. The guards make the
     repeats no-ops.
5. **Range-skill identity.**
   - The slot-4 corpus test passes on my rerun.
   - Stdlib run: 328 passed; the 16 skips are torch only.
   - With torch: **344/344**.
   - The Decider reads the feed only if `feed and percept.killfeed`. `range_skill_mode` is set at `loop.py:523`, before the
     Decider at `:567`.
   - `is_killfeed` exists at base (`perception/scoreboard.py:203`), so the import cannot raise.
   - `LearnedRangeSkillBrain` calls `gate` but never starts an option, and its `kill_feed` is None, so the new code is inert.
   - The only log change is `"kill_feed": null` in state dicts. `row["option"]` is written on the legacy path only.
   - State consumers read named keys (`policy/train.py:_state_features`).
6. **Replays.**
   - My rerun of `run.py` reproduces `summary.json` exactly. The one difference is `run.py`'s own hash, because I repointed
     `ROOT` in the scratch copy.
   - Trial 0: KO at 2.234, last press 2.195.
   - plaza30:
     - KOs at 13.526 and 25.075.
     - Base fidelity is 1542/1542 attack rows.
     - Without the feed bit, 0 pad rows and 0 intents differ.
7. **Safety.**
   - On both recordings the branch adds no attack input.
   - `clean`, `ALLOWED` and the range-HUD guards are untouched.
   - Retreat still preempts.
   - Not guaranteed by construction: see F1.
8. **Mutation.**
   - The author's `mutation.py`, rerun on a scratch copy, kills 12/12 with failing-test sets identical to `mutation.json`.
   - My extra mutants: 11 of 14 killed. The killed ones include:
     - the Jev launch guard;
     - equality instead of identity in the cut;
     - the `seq_name` guard;
     - a bound that is ignored;
     - None read as a reset;
     - a line already up read as an onset;
     - `superseded`;
     - `stop` never reset;
     - a KO re-firing after confirmation;
     - the Decider feed flag.
9. **Jev.**
   - `OPTIONS` covers exactly the old `HOLD_S` names.
   - `not brain.running(memory)` equals `hold_until <= t` in every case:
     - an option started on this tick blocks the launch;
     - an option cancelled, ended or lapsed allows it.
   - Only the timing moves: a launch can come sooner when evidence ends an option.
10. **Suites.** `uv run pytest` gives 1289 passed, 62 skipped. `git diff --check` is clean and the worktree is clean. I did not
    rerun the perception group or re-time the kill-feed read.

## Delta c455621

`0ba2805..c455621` is 11 files. The code changes are in `agent/brain.py` only; `controller.py` changes a comment and the
docstring. The tests are `test_options.py` and the new `test_options_extractor.py`. The author's report is `option-status-final-2.md`.
This was read-only: nothing was edited or committed, and the worktree stays clean. Scratch files are `mutate_extra2.py`,
`mutate_extra2.json` and `ev2/`.

### Verdict: approve

Every finding is closed as the lead decided. Nothing new was found. The one residual is F1(b), the burst re-commit after a KO. It
stands as accepted behavior: it is pinned and documented.

- **F1: confirmed.**
  - `stop` is now set only when `ko is not None` and the latest option's kind has `stops_on_ko`. Only `Combo` does (`brain.py`
    `OPTIONS`, `gate`). Arrival completes an option and never stops one, and neither does a KO on a pull, web strike or swing.
  - My `probe_arrival` on c455621 equals the base exactly: RB 0.067, X 0.850, RT 1.433. The earlier X at 0.500 is gone.
  - `probe_recommit` still gives the extra LT at 0.300, and `test_a_ko_reopens_the_choice_and_a_burst_on_a_target_still_boxed_restarts`
    pins it as accepted. `test_arrival_ends_a_web_strike_but_its_primitive_plays_out` pins the arrival case.
  - `summary.json` now computes `attack_rows_tree_only`: **0** on trial 0 and 0 on plaza30. `attack_rows_base_only` is 33 and 24.
  - The restated invariant is in the lane doc and the README.
- **F2: confirmed.** "3.400" no longer appears in the README, `l5-brain.md`, `test_options.py` or `brain.py`.
  - Each now says: hold cancelled on track loss at 2.348, the primitive played on to 3.45 s, and the gain is the stop (README
    lines 64-72, `l5-brain.md` 170-177, `test_options.py` 279).
  - `base_holds` records `ended`/`ended_t`: trial 0 `cancelled` at 2.3477; plaza30 `cancelled` at 9.7868 and 14.0361, `lapsed` at
    25.5697.
  - The handoff's first `option-status-final.md` still carries the old sentence. It is superseded by `-2`: post `-2`'s acceptance-4
    wording.
- **F3: confirmed.**
  - `_ko` is now line for line the extractor's `_Channel`:
    - the first read sets the value;
    - a change needs `FEED_CONFIRM` consecutive reads, and a read of the confirmed value restarts the count;
    - None is ignored;
    - only False→True emits.
  - `tests/test_options_extractor.py`, rerun in an isolated env (`uv run --no-project --with pytest --with numpy --with
    opencv-python-headless`, so the worktree `.venv` is untouched): **9 passed**, including `F,T,T,T,F,T,T` → [2] and
    `F,T,T,F,F,T,T` → [2, 6].
  - My `probe_debounce` now matches the extractor on all 6 of its cases.
- **F4: confirmed.**
  - I reran `mutate_extra2.py` on a scratch copy. That is my 14 mutants, re-pointed where c455621 rewrote the line, with the same
    intent. The unmutated copy passes 270.
  - **13 of 14 die**, including both earlier survivors:
    - `arrival_on_any_target_box` dies to `test_arrival_is_read_on_the_held_targets_own_box_not_on_its_successor`;
    - `stop_on_ko_for_any_kind` dies to `test_a_ko_after_a_swing_has_ended_stops_nothing`.
  - `loop_stop_when_stale` survives. It is equivalent, as before.
  - Four new mutants aimed at this delta all die:
    - `stop_on_arrival_again`;
    - `web_strike_stops_on_ko`;
    - `one_false_rearms` (F3 reintroduced);
    - `burst_not_stopped_on_ko`.
  - `test_a_ko_on_the_commit_tick_is_consumed_before_the_choice` pins both commit-tick traces. `probe_commit_tick` on c455621 gives
    the same traces.
- **F5: confirmed.**
  - `replay.py` now looks the feed up at `round(t, 4)`, so the decision's own saved frame is used. The logged 25.0754 frame is no
    longer skipped against `State.t` 25.075384.
  - `ko_confirming_frames` holds two distinct frames for every KO: 13.5255 → 000060/000061, **25.0754 → 000165/000166**, and
    trial 0's 2.2338 → 000027/000028.
  - `decisions_reusing_the_previous_decisions_frame` is 32 on plaza30 and 0 on trial 0, and the README says so.
  - My rerun of `run.py` (scratch copy with `ROOT` repointed) equals the committed `summary.json` except for `run.py`'s own hash.
  - Against 0ba2805's `summary.json`, **no existing value moved**. The only differences are:
    - the code and script hashes;
    - the added keys: `attack_rows_*`, `base_holds[].ended*`, `ko_confirming_frames` and
      `decisions_reusing_the_previous_decisions_frame`.
  - KO times, options, stops, presses, differing rows, fidelity and the no-feed identity (1542/1542) are unchanged.
- **Suites:**
  - stdlib `uv run pytest`: 1298 passed, 62 skipped.
  - `--corpus` range and option files: 337 passed; the 16 skips are torch only, and the slot-4 identity test passes.
  - `git diff --check 0ba2805..c455621` is clean.
  - I did not rerun the perception group or the torch run. The author reports 5 known failures and 353/353.
