LAND WITH FIXES

# Review: pad-binds (VUH-1384), binds-review (Opus 5.5), 2026-09-26

Read-only review. I made no edits, commits, game input or desktop actions.
- Brief `review-brief.md` sha256 `4535cc8f…af9cd`, verified.
- HEAD `e188323`. All 18 paths match `review-file-sha256.json`, and all 6 screenshots match `screenshot-sha256.json`.
- I read all five settings screenshots and the HUD crop myself.

Before landing, one fix is needed: finding 1 (a vocabulary sendability change nobody decided).
Findings 2 to 5 are small fixes or doc follow-ups. The rest of the change holds up.

## Findings

**1. Medium-high: the change makes four more actions live for the learned policy, and that silently changes what a fit trains, scores and emits.**
`policy/range_bc/vocab.py:26-27,31`
- `PAD_SENDABLE` is now `bool(controls(name))`. That flips `ultimate`, `melee`, `team_up` and `goh_targeting` from False to True.
- `vocab.live_mask` is not only the live emit mask:
  - `steps.py:777` stores it in the fit's `stats`.
  - `train.py:353,437` uses it in the self-conditioned and self-rolled history, so it changes training itself.
  - `metrics.py:234` uses it in executed metrics.
  - `gates.py:131` uses it in G5, which rate-checks every live action.
- **Failure scenario:** the next whole-session fit (or a rerun of the plumbing-fit pre-registration, `afff279`) has at least 50 train presses of `goh_targeting`, `melee` or `team_up`.
  - Those actions now enter the self-fed history and G5's pass/fail. A pre-registered gate can therefore flip.
  - The executor would also emit X holds, R3, and L3+R3 on a live run.
- This contradicts `docs/lanes/end-to-end-fit.md:576-586`. Item 5 says these are "Never sent". Item 7 says a sendability flip is a new pre-registration.
- `tests/test_range_bc.py:30-38` was rewritten to assert the new behaviour. The brief asked for mapping and executor semantics; it did not ask for a sendability flip.
- **Fix:**
  - Keep the four at `PAD_SENDABLE = False` for now. A separate explicit set is fine.
  - Keep the pad labels derived from `pad_bindings`.
  - Restore the old test assertions.
  - Flip them later only as a lead-recorded pre-registration change, together with the fit lane's owner.
  - Indices and `DEFAULT_BINDINGS` are unchanged, so existing caches and checkpoints stay loadable. I checked this.

**2. Medium: held X (`goh_targeting`) is a hero-change risk in the range, and the live-game skill is now wrong about X and B.**
`agent/pad_bindings.py:18`, `.agents/skills/rivals-live-game/SKILL.md:64`
- The skill's table says Range X "tap / hold: Amazing Combo / opens CHANGE HERO".
- The scripted Controller no longer presses X at all, because uppercut is now B. That is good.
- The learned path would now send X as a *held* action if finding 1 stands.
- **Failure scenario:** a sustained `goh_targeting` hold reaches the CHANGE HERO threshold. The range HUD then disappears, `Live` refuses and releases, and the run ends on the hero picker.
  - Guards still stop further input (fresh-frame proof at most 0.1 s old, 0.25 s lease). But this is an episode-ending path that combat now reaches.
- **Fix:**
  - Finding 1 closes the learned path for now.
  - The touch test (handback step 6) should measure whether X-hold still opens CHANGE HERO under the alt's UI binds. The UI tab was not screenshotted.
  - Update the skill table: Range B = Amazing Combo; X = GOH Targeting, with the hold behaviour marked unknown.

**3. Low: the recorder's pad now resolves every XUSB name, including START, BACK and the d-pad.**
`scripts/record.py:48`
- `codes = button_codes(self.vg, XUSB_NAMES)` replaces a six-entry map (A/B/X/Y/LB/RB).
- Before, any other name raised `KeyError` before any report was written. That was an implicit whitelist on a writer that proves the range per frame, not per send.
- Today's `routine` never emits these buttons (selftest and `test_record_pad_bindings`). This is lost defence in depth, not a live bug.
- **Fix:** `button_codes(self.vg, COMBAT_BUTTONS | {"X", "RB", "A"})`. That covers combat plus the hero-picker UI, with no START, BACK or d-pad.

**4. Low: `l4_measure` leaves an empty output file whenever a run fails.**
`scripts/l4_measure.py:301-312`
- The output is reserved with `open("x")` before `live_factory()`.
- Any `RangeLost` at construction, mid-run exception or Ctrl-C leaves a zero-byte `--out` file. A rerun to the same path is then refused.
- An empty `data/calibration/alt-NEW/*.json` also looks like a retained attempt with no content.
- It never overwrites and never opens the pad early; argument and focal validation run first. I verified this and the tests cover it.
- **Fix:** on exception, unlink the reserved file if it is still empty, or write a `{"failed": repr(e)}` record.
- Also a nit: with `--focal`, `yawmap` still runs the three equal-pulse candidate trials. That is harmless but costs pad time.

**5. Low: the documented hand-tool path needs the new module deployed.**
`scripts/pad.py:20-21`, `scripts/padrun.sh:10`, `SKILL.md:26-29`
- `padrun.sh` runs a flat `C:\rivals-agent\pad.py`. That now imports `agent.pad_bindings`.
- The import resolves through the script's own directory, so it works once `C:\rivals-agent\agent\pad_bindings.py` is deployed. That file is not there now.
- Until then it fails with `ImportError` before any device opens, so it fails closed.
- Add the file to the deployment list with `controller.py`, `loop.py` and `record.py`. Add the `combat:` and `LS+RS` tokens to the skill.

**6. Low (gap, not a regression): nothing checks that the wall-crawl hold settings match between the recordings and the pad.**
`policy/range_bc/vocab.py:96`
- `PAD_SWING_MODE` gates only swing (K6).
- The alt has Hold to Wall Crawl ON and Hold to Run on Walls ON. If James's M&K sessions were recorded with different keyboard hero toggles, trained jump and movement near walls will not transfer.
- **Failure scenario:** in the recordings, walking into a wall auto-crawls. On the pad, the same output walks into the wall.
- No header field records these toggles; I grepped intake and range_bc.
- **Fix:** record James's keyboard hero toggles in the recording header or pre-registration before any learned pilot.

**7. Info: the brief's pytest command cannot run as written.**
- `tests/test_record_pad_bindings.py` imports cv2. `conftest.pytest_ignore_collect` does not skip explicitly named files, so the stdlib run aborts at collection ("1 error in 0.31s").
- I split the run instead (results below).

**8. Info: `Live` cannot enforce the ultimate chord; the guarantee comes from how every caller builds it.**
- `ALLOWED` now accepts LS or RS alone, because those are legitimate team-ups. A caller that sends `("LS",)` then `("LS","RS")` would fire Team-Up B, then the ultimate.
- Every current emitter builds the ultimate through `combat_controls("ultimate")` and writes it in one `update()`. See Judgement 2.
- A policy that holds `team_up` and then adds `ultimate` emits R3 alone first. That is the policy's choice, not a mapping bug.
- Whether the game treats a same-report L3+R3 purely as the ultimate is for the touch test.

**9. Nits on `docs/spiderman-kit.md`.**
- The Wall Crawl primitive now states "tap alone cannot sustain crawl". That is inferred from the setting name, not observed; the kit convention would mark it **U** until the touch test.
- The "Crouch, sprint, pause | **U**" row was removed. Only its L3 part is superseded.

## Judgement against the brief

1. **Binding table: correct.**
   - The screenshots show Jump LB, Spider-Power RT, Web-Cluster LT, Melee NONE, GOH RB, Web-Swing A, Amazing Combo B, Team-Up A R3, Team-Up B L3, Ultimate L3+R3, and Environmental Interaction on View (`164632`, `164635`).
   - GOH Targeting is X, and the diagram shows Y blank (`164624`).
   - The HUD crop's only team-up slot is R, which supports `team_up` = Team-Up A.
   - `pad_bindings.py:11-24` matches exactly.
   - My own grep found physical button literals only outside combat:
     - `controller.py:207` (scoreboard BACK);
     - `record.py:229-238` (hero-picker X/RB/A/X);
     - `reenter.py:669,1040-1058` (menus; its `in_range` whitelist now derives RT from the table);
     - `l4_menu.py:124-125` (UI).
   - `XUSB_NAMES` is a device-name map, not a second action map.
2. **Ultimate atomicity: holds on every path.** Each one sets both buttons and then calls `update()` once:
   - `Live._write` (`controller.py:266-276`): reset, press all, then one `update()`.
   - The executor (`pad_state` via `combat_controls`).
   - `record.Pad.set`.
   - `pad.py` `run`: one update, and `finally` resets and updates.

   Every release (release, watchdog, close, `Pad.release`, pad.py `finally`) writes one neutral report that clears both. Tests cover Live, `send_guarded`, the recorder and the interrupted hand tool. The scripted Controller never emits LS or RS.
3. **Safety guards: preserved.**
   - Fresh-frame proof at commit and at the actuator, the lease watchdog, range refusal, and neutral-on-close/`__init__` failure are unchanged.
   - BACK stays outside `ALLOWED` and is reachable only through `scoreboard()`.
   - Every A, B and X in combat needs a fresh `in_range` proof. A lobby or menu frame fails it, so combat cannot press confirm, back or Quick Match on a menu.
   - `pad.py` still requires `--dangerous` for X, including `combat:goh_targeting`, and for BACK (`combat:environmental_interaction`).
   - reenter and l4_menu screen proofs are unchanged.
   - Residual risks: finding 2 (a combat input that opens a screen) and finding 3.
4. **Semantics.**
   - Melee is an alias for RT, OR-combined, and never R3. That is correct per the kit.
   - `team_up` = R3 is correct. Team-Up B has no action, and none is needed: the HUD shows only one team-up slot, R3.
   - Swing is held on A across held steps and released on the first inactive step.
   - A press-only prediction is one 33 ms step. With Hold to Swing ON that is a web-fire, not a swing, and the handback states this.
   - Wall crawl is only a scripted alias. The learned policy's sustained `jump` is the hold.
   - Anything that silently changes a trained checkpoint's outputs: **yes**, findings 1 and 6.
   - Recorder labels changed from `y`/`rb` to `team_up`/`get_over_here`. No code consumer parses them. The RNG call order is unchanged.
5. **Vocab.** Indices, names and `DEFAULT_BINDINGS` are unchanged, so checkpoints and caches stay valid. Sendability changed for four actions (finding 1). The `698d8831` range-skill head does not use `range_bc.vocab`.
6. **Calibration.**
   - `Cal` values are unchanged, and it is marked STALE in its docstring. No invented values.
   - The staleness is procedural, not code-enforced. That is acceptable, because editing `controller.py` already forces a re-freeze before any run.
   - `l4_measure`:
     - It parses arguments and validates focal (finite, positive, yawmap/yawleft only) before touching the file or the pad.
     - It creates the output exclusively and never overwrites.
     - It records focal provenance.
     - `watch_pad` is attached only after construction, and its bookkeeping cannot block writes.
     - Its only issue is finding 4.
7. **Kit prefix: identical.**
   - The first 2,000 bytes match HEAD in the LF form and in the CRLF form.
   - They are byte-identical to the author's `kit-prefix-before.bin` (the working copy is CRLF under `core.autocrlf=true`).
   - The prefix sha256 is `468c1859…0aeb`, and the "Patch reflected" line is intact.
   - The new controller column matches the screenshots. The combo translations are right: #7 "A to high ground", #8 "A, LT, LB".
8. **Freeze claim: exact.** The union of the `*-deployed.json` files is 16 paths. The touched ones are exactly `agent/controller.py`, `agent/loop.py` and `scripts/record.py`, plus the new dependency `agent/pad_bindings.py`.
9. **Tests (mine):**
   - `uv run pytest` on test_pad_bindings, test_controller, test_live_pad, test_loop and test_range_bc: **261 passed, 1 skipped** (19.8 s).
   - In a private `UV_PROJECT_ENVIRONMENT` with `--group perception`, test_record_pad_bindings, test_l4_scripts_close and test_pad_bindings: **53 passed**.
   - Nothing opened vgamepad or captured the screen; all pads and captures were fakes. `data/l4` was unchanged afterwards.

## Not established here

No offline check can show:
- the game's response to the new binds;
- same-report chord behaviour;
- the X-hold threshold;
- hold durations;
- camera rates.

The handback's calibration and touch-test procedure is the right next step.
