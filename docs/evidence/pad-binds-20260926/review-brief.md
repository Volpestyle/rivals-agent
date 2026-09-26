# Brief: binds-review (Opus 5.5, high), read-only independent review, VUH-1384, 2026-09-26 17:20 CDT

You are reviewing another lane's uncommitted change in the shared checkout `C:\Users\volpe\repos\rivals-agent` (HEAD e188323).
The author is pad-binds (Codex). The code sends input to the live game, so the repo requires an independent review, preferably
from another model family: that's you. The lead verifies your findings before dispatching any fix.

**Read:** `brief.md` (the author's brief), `HANDBACK.md`, the screenshots in `screens/` (the ground truth for the alt's settings),
and the 18 paths in `paths-to-stage.txt`, diffed against HEAD. Load the `rivals-live-game` skill from `.agents/skills/` for the
live-input rules.

**Judge:**
1. The binding table matches the screenshots exactly: Jump LB, Spider-Power RT, Web-Cluster LT, GOH RB, Web-Swing A,
   Amazing Combo B, GOH Targeting X, Team-Up A R3, Team-Up B L3, Ultimate L3+R3, Melee none, Y unbound.
   Is there any remaining hardcoded combat button outside `agent/pad_bindings.py`? Grep for it yourself; don't trust the AST claim.
2. The ultimate is atomic: every down report carries LS and RS together and the release clears both, on every path
   (Live, the executor, the recorder, the hand tool, interrupt/close). No path can emit R3 or L3 alone when ultimate was meant.
3. The safety guards are preserved: fresh-frame range-HUD proof, lease, range refusal, neutral-on-close, the lobby-X ban and the
   menu screen proofs. The combat whitelist now contains A, B and X. Check that none of them can reach a menu or lobby screen
   through the combat path, where A, B and X mean confirm, back and Quick Match.
4. Semantics: melee aliasing to RT (OR-combined); team_up means Team-Up A only. What about Team-Up B? Web-Swing held on A;
   the 33 ms press-only swing; the wall-crawl hold. Anything that silently changes what a trained checkpoint's outputs do?
5. `policy/range_bc/vocab.py`: the action indices are unchanged, so existing checkpoints and caches stay valid.
   Did "sendable" change for any action a frozen or pinned run depends on?
6. Calibration: `Cal` is marked stale and not silently used with invented values. Check the `l4_measure.py` changes: exclusive
   output, focal handling, report timing. They must not open a pad before validating arguments.
7. `docs/spiderman-kit.md`: its first 2,000 characters are byte-identical to HEAD (check both LF and CRLF). Check that the
   new controller column is right.
8. The deployment-freeze claim: exactly controller.py, loop.py and record.py of the 16 deployed files are touched,
   plus the new dependency pad_bindings.py.
9. Run the focused tests yourself: `uv run pytest tests/test_pad_bindings.py tests/test_record_pad_bindings.py
   tests/test_controller.py tests/test_live_pad.py tests/test_loop.py tests/test_range_bc.py -q`.
   Do NOT run anything that opens vgamepad or captures the screen.

**Rules:** read-only. No edits, commits, game input or desktop actions; the game may be open. Keep each process under ~3 GB.

**Output:** `review-binds-20260926.md` in this folder. Its first line is `LAND`, `LAND WITH FIXES` or `FIX`.
Then numbered findings, each with file:line, a failure scenario and severity. Tell the lead in your final message.
