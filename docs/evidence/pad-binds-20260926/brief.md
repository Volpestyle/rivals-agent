# Brief: pad-binds (Codex, gpt-6-astra high), 2026-09-26 16:55 CDT

**Owner:** pad-binds. **Lead:** herdr-lead (actor c302f78b). **Scope changes:** lead only. Linear: a new issue on the Rivals Agent board, filed by the lead.

## Result
The agent's pad executor, and every script that presses pad buttons, uses James's current alt-account Spider-Man controller
settings instead of the defaults listed in `docs/spiderman-kit.md`. James decided (2026-09-26 16:45) to keep his custom binds
on the alt and move the agent to them. Until this lands, calibrates and passes a touch test, **no agent run on the alt is safe.**

## The alt's settings (screenshots in `screens/`, taken 16:46 CDT; read them yourself and confirm)
Jump LB. Spider-Power RT. Web-Cluster LT. Melee Attack **NONE**. Get Over Here RB. **Web-Swing A. Amazing Combo B.
Get Over Here Targeting X. Team-Up A = R3, Team-Up B = L3. Ultimate L3+R3.** Y unbound. Environmental Interaction = View.
Hero toggles: Hold to Swing ON, Simple Swing OFF, Hold to Wall Crawl ON, Hold to Run on Walls ON, Direction of Wall
Crawling "Advance Vertically Upwards", Targeting Sensitivity While Aloft 100.
**Spider-Man stick override: Horizontal 247, Vertical 124** (All Heroes: 265 / 195). The Advanced stick curve is not shown.
James says he changed all of this today, so every pad camera gain and every tap-vs-hold assumption measured before
2026-09-26 is stale for Spider-Man.

## Do (offline only)
1. Map every place a semantic action becomes a pad button. Start from `agent/controller.py`, `agent/loop.py`,
   `policy/range_bc/executor.py`, `policy/range_bc/vocab.py`, `scripts/pad.py`, `scripts/record.py`, `scripts/reenter.py`,
   `scripts/l4_menu.py` and `scripts/replay_steps.py`, and grep further. Separate combat binds (these change) from menu/UI
   navigation (lobby, practice settings, hero select), which normally does not follow combat binds. Say which is which,
   with evidence.
2. Put the combat mapping in **one** table and make every caller use it. No second copy.
3. Semantics:
   - melee has no bind; kit line 53 says Spider-Power is the melee, so say what the executor should do;
   - team_up goes to Team-Up A (R3);
   - the ultimate must press L3 and R3 on the same report, and never one alone, because either alone fires a team-up;
   - R3 is no longer melee;
   - Web-Swing and Wall Crawl are now hold-to-act: check what the executor sends (tap vs hold) and say what must change.
4. Camera: find the pad camera calibration constants and where they came from. Mark them stale for Spider-Man at 247/124,
   and don't invent new values. Write the exact calibration procedure the next PC session must run with the agent's pad,
   reusing the existing calibration script if there is one.
5. Update the controller column of `docs/spiderman-kit.md` with source "James's alt settings, screenshots 2026-09-26".
   Its first 2,000 characters, the "Patch reflected" line, must stay byte-identical.
6. List which of the 16 files hashed in `data/runtime/galacta-pilot-20260923-preflight/*-deployed.json` you touch.
   Don't re-freeze: that happens after calibration.
7. Offline tests: `uv run pytest`. For perception-group runs use a private `UV_PROJECT_ENVIRONMENT`, because the checkout
   is shared.

## Don't
- No game input and no PC desktop actions: the game may be open, and James may be playing.
- No commits. Stage nothing; the lead lands after an independent review by Opus 5.5.
- Don't touch other lanes' uncommitted files: `perception/replay_cuts.py`, `tests/test_replay_cuts.py` and `docs/lanes/idm-gate2-anchors*`.
- Load the `shared-checkout` skill before editing.

## Hand back
`handoff/pad-binds-20260926/HANDBACK.md` with: the mapping inventory (file:line), the diff summary, the semantics decisions,
the camera constants and calibration procedure, the touched deployed files, the test output, and the exact list of paths to stage.
Then tell the lead in this pane's final message.
