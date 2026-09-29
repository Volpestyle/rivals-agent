# Baseline failure triage — 2026-09-29

Owner: live-loop, reporting to the lead. Offline, report-only after the pin
inventory. Started 06:59:24 UTC; deadline 08:59:24 UTC. This packet is separate
from the frozen safety delta under live-review.

**Fixed: 0 of 45. Remaining: 3 stale tests (a), 8 environment/order dependencies
(b), 34 failures/errors from a real production integration bug (c).** The lead
confirmed that the pinned tests must remain unchanged. All eleven (a)/(b) IDs
need changes in recorded test inputs; none was edited or bypassed through a
global pytest hook. Production fixes for (c) were expressly out of scope.

`classification.json` and `failures.md` enumerate every ID, class, evidence,
owner and next action. `pin-checks.json` records searches for both LF and CRLF
SHA-256 forms in docs/evidence and data metadata/source files. None of the
candidate paths belongs to checkpoint 698d8831's deployment closure, but all
proposed stale/environment repairs have existing byte records; those and the
sixteen-file deployment closure were preserved. No calibration/camera file,
test under review, frozen evidence or production source was changed.

## Production bug: incomplete denylist re-pin, fail closed

Owner: **admission owner / admission-codex**, routed by the lead; ownership is
recorded in `docs/lanes/human-admission-handoff-20260927.md`. The same integration
defect explains 34 of the 45 IDs. It also affects relocation, although relocation
does not add another ID to this inventory.

The current LF denylist hash is
`09e8b9d350c89eb41c1581e1bce47548bfb855bca5805cf2e65955b9b23597b5`.
Three consumers retain
`439c80df6cd5d6daa60b48e0acb2d3a3fa833134ff14edddc4121348c2dceb20`:

| Consumer | Stale constant | Refusal boundary |
|---|---|---|
| `scripts/transcode_recording.py` | line 72 | `transcode` loads at 571, before priority change/planning at 572–576. `plan_all` loads at 527, before registry/session iteration at 529–531. |
| `data/human/sessions/tally.py` | line 30 | `build` loads at 141, before registry validation at 142 and admitted-session reads at 143. Writes are only after `build` returns, at 170–172. |
| `data/human/sessions/relocate_session.py` | line 20 | `main` loads at 43, before registry validation at 44, imported-demo read at 48, receipt read at 51, dataset/reprobe at 57 and write at 60. |

**These entry points fail CLOSED. No automatic fallback to an embedded, older
or cached denylist was found.** They refuse before reaching session-specific
payload work, regardless of the requested SID, including the lead's examples
V-C/V-Q and 14-51-10. This describes the broken consumers' current behavior,
not an assertion about which allocation each held-out SID belongs to.

`scripts/transcode_recording.py:157–161` wraps any loader error in `Refused`;
its CLI returns 2 at 657–659. Deletion is already disabled at 438–439. If that
separate switch is enabled, the denylist is still loaded at 441 before receipt
or media reads. The plan-all per-folder catch at 557 occurs **after** the
top-level load; it cannot swallow a stale-pin failure and continue scanning.

The loader checks the supplied hash before parsing/returning the file:
`agent/human_intake.py:618–620`. The default snapshot selected by tally has the
same check at
`data/human/sessions/code-snapshot-107970b-3c8a3b7e/agent/human_intake.py:525–527`.
Both use explicit exceptions, not assertions. `snapshot-denylist-loaders.json`
records the current loader plus all 23 snapshot loader sources: each validates
a supplied pin and then reads the explicit path; none catches the failure or
returns cached membership. A snapshot selects implementation code, not an old
embedded denylist for these entry points.

The low-level transcode APIs do permit explicit caller-supplied path/pin or
denylist arguments (`transcode` 566–568, `delete_original` 434–435, `plan_all`
524–527, `plan` 481). Those are explicit overrides, not fallback behavior.
The CLI exposes no such override (631–655), and no current production call site
was found that supplies an older map. This verdict covers the current three
entry points and their default inputs, not arbitrary custom callers.

Evidence: `denylist-pin-probe.json` shows the current hash accepting metadata
and the stale hash refusing it. `fail-closed-probes.json` contains **12 passing
refusal probes**: transcode, plan-all, deletion disabled, deletion pin with the
switch changed only in the disposable child, tally and relocation, each in a
fresh normal interpreter and under `python -O`. All downstream traps remained
untouched. No payload, encoder, game, desktop or relocation operation ran.
Reproduce with `uv run python docs/evidence/baseline-triage-20260929/probe_fail_closed.py`.

Next action: the admission owner reconciles these three consumer pins with the
accepted current denylist, checks affected freezes/reviews, then reruns the
retained failing nodes. This packet does not update a pin, weaken a refusal or
change historical snapshots. The failure is availability, not an observed
fail-open path from the stale pin; the lead confirmed admission can take it later.

## Pinned stale tests and environment/order dependencies

| Class/count | Finding | Owner / next action once the pinned delta is authorized |
|---|---|---|
| (a), 1 | `test_sealed_denylist_v2` still requires exactly seven identities after intentional addition in 731cd7d. | Admission owner: update expected membership while preserving v1 prefix and split protections. |
| (a), 2 | `test_spatial_yaw_fallback` supplies obsolete `deadline_unix`; guard v2 intentionally requires five stable identity fields after ead3e6d. | Explore-policy: update synthetic identity fixtures to the current contract; keep completion/corruption/partial-stage checks. |
| (b), 4 | `test_intake_streaming.py:44–46` loads a scan whose line 31 prepends its snapshot root to `sys.path`; the test leaves it there. Later live-range imports load the snapshot and fail on a missing reviewed test file. | Admission owner: isolate/restore import state in the test. The frozen safety packet contains the exact baseline order reproduction. |
| (b), 3 | FPS test paths import real `capture.py`, whose NumPy dependency is absent in the stdlib environment. | Live-loop repair/evaluator owner: scope those tests to their optional dependencies without dropping the remaining stdlib checks. |
| (b), 1 | Replay-HUD uses every available session review frame rather than a bounded fixture and lacks the required corpus marker. | **pilot-prep / replay-HUD**, recorded lane writer in `docs/lanes/replay-hud.md`: add corpus marking in an authorized test delta and use explicit approved fixtures for any reader regression. |

For replay-HUD specifically, `tests/test_replay_hud.py:108–110` uses
`HUMAN.glob("*/review-frames/*.jpg")`; `HUMAN` is the live sessions directory
at line 20. `has_human` checks availability, not corpus opt-in. The zero-badge
assertion at line 113 is therefore dependent on the local session contents.
**This is a marker-rule violation, not a sealed breach.** The lead checked
directory names only: 51 session directories, all admitted, no sealed SIDs.
That is the lead's observation, not a new media inspection by this lane.
I did not rerun that corpus test or inspect its frames during this triage.
The underlying reader's correctness on a bounded, approved sample remains
unadjudicated; the environment dependency is established from the test source.
The pinned test remains untouched, as instructed.

## Validation and delivery

The previous safety packet already reproduces all 45 failures against the
8331c45 baseline; that evidence is reused. This task added metadata-only pin
probes, the twelve entry-point refusal probes and static snapshot-loader audit.
No full suite was repeated with the known unmarked corpus test. No source fix
was eligible under the confirmed pin boundary, so there is no fix commit and
no claim that main is green. The delivery commit contains this report/evidence
only; its SHA is reported separately to avoid a self-referential file hash.
