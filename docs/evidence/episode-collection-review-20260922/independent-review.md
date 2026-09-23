# VUH-1319 independent changed-boundary review

Narrow software acceptance: no blocker found in the three frozen files against 93dc9f1. Root owns acceptance/landing/runtime evidence; E owns any further changes. This is not readiness, designated completion, KO or live authorization.

Exact SHA-256, verified before and after review:

- agent/loop.py: 2365b4fb75cb0c012fa6713f061eb14623e0f3b35bf5497f322eb908e8dbda0e
- tests/test_episode_collection.py: ea7a7b88b3ab4756c335bd319a782e5c85a0f77785b24ba107fd0b0556b445e7
- docs/lanes/range-episode-collection.md: 5d1a79c0b9550687635cab523ae33d68bcc9c52a136c8c9130b06ff69bf13be9

Read the full production diff, new tests and lane contract. Reused accepted unchanged Controller/Live/reader/model behavior; no new implementation audit of those boundaries.

Verification actually performed:

- 59 focused tests passed: `uv run --offline --no-project --with pytest python -B -m pytest tests/test_episode_collection.py -q -p no:cacheprovider`.
- Six existing actual CLI/default/legacy-pose controls passed: same isolated command against tests/test_range_skill_loop.py, selection `live_cli_valid_actual_joined_stack or live_cli_legacy_pose_only or live_cli_explicit_diagnostic_and_existing_default`.
- 18 additional independent synthetic controls through imported existing fixtures and actual Loop/Controller/RunLog. Eight use actual main/start_pose/LiveIO/Live with fake device/capture/pixels and loader-only stub: valid paired controls, foreground loss immediately before the first offensive guarded send, terminal-image save exception after neutral, and feed-reader exception during phase, each for scripted and range-skill. Remaining controls cover writer success-without-file, writer false-with-file, missing phase acquisition, unknown intermediate feed, missing required first-phase file for both policies, and transient/persistent release failures for both policies.

The actual caller checks showed same-Live baseline before decisions/offense, original acquisition/resource clocks, fresh post-baseline first phase, original 14+max_s session deadline and no authority reset. Both policies refused post-baseline focus loss at the guarded send and cleaned up. Required baseline/first-phase save failures left zero decisions and refused collection. Terminal image failure retained file:null and its error rather than asserting terminal evidence. Feed-reader exceptions released, propagated and did not fabricate a candidate or terminal board.

Optional feed presence remains candidate evidence only. Intermediate unknown is not recorded as proven absence. Candidate stop performs release attempts before candidate image saving and no further phase decision/offense. A first release failure followed by a successful retry is truthfully retained; persistent release failures produce release_returned:false and errors. Evidence saving can still occur after failed release attempts: the code does not guarantee successful physical neutral merely because a candidate image exists. Root must retain those failure records. This is consistent with the explicit null completion/readiness contract and is not new authority or automatic episode acceptance.

Scope/limits: the model loader in joined fixture runs is explicitly stubbed; no real or synthetic checkpoint load was needed because its unchanged boundary is reused. No native factories, media, human/scout data or model contents were opened. No original/source/test/doc edits, shared installs, gameplay input/capture, commits, Linear or other agents. Python used the existing offline cached pytest environment; bytecode and pytest cache writes were disabled. Synthetic artifacts only are under the temporary directories below.

Independent control records:

- C:\Users\volpe\AppData\Local\Temp\episode-collection-review-kzx0rtg9\independent-controls.json (12 controls, including eight actual caller joins)
- C:\Users\volpe\AppData\Local\Temp\episode-release-review-1y_1c1kj\controls.json (six required-save/release controls)

Acceptance is limited to collection software and these exact bytes. `phase_started`, exit 0, parsed baseline counters and feed presence do not establish an accepted episode, a full-health designated incarnation, a KO, or successful terminal-board evidence. The explicit original scope and existing physical/watchdog resolution remain in force. No additional general gate or repeated unchanged-code review is requested.
