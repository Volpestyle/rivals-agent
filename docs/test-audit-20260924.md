# Test audit cleanup — 2026-09-24

The [OpenClaw test-audit workflow](https://github.com/openclaw/openclaw/blob/main/.agents/skills/test-audit/SKILL.md) identifies overstated behavioral proof, duplicate checks and incomplete corpus routing. The cleanup applies to baseline `4553072` and changes tests and documentation, with no production behavior changes.

## Resolutions

| Finding | Current proof or repair |
|---|---|
| Missing clock diagnostic breaks the default suite | `test_range_skill_loop.py` reads the existing tracked `docs/evidence/range-request-runtime-20260922/phase-band/report.json`. The original 82 decisions, four missed slots and 62 usable histories remain asserted. No recorded clocks are fabricated or copied. |
| Missing corpus opt-in | 22 existing tests across six files additionally carry `corpus`, including the four-test tracker module. Their recording reads require `--corpus`. Replay and outcome checks instead use tracked range fixtures. |
| Learned safety test only greps source | `test_policy.py` constructs LearnedBrain with a temporary head and controlled predictions, then executes the real gate, window, ranking, legality and adoption code. Retreat and adopted holds skip inference; cooling abilities cannot be adopted; legal combo and web-strike predictions establish their holds. |
| Interrupted-write test never writes | Two fault injections exercise `encode_source`: an archive write leaves partial bytes and raises; sidecar publication raises after the archive is complete. Readers cannot load an incomplete pair, any published archive is valid, and retry produces the expected vectors/timestamps and a resumable cache. |
| Missing recordings cause vacuous outcome passes | Two tracked positive range frames must actually be recognized as in play before unreadable damage/eliminations are checked. Replay serialization, finder semantics and missing-frame handling use three tracked frames. Missing fixture files fail visibly. |
| Three fault names execute one fault | Request-expiry tests retain `range`, `stale` and `closed`; redundant `focus` and `session_deadline` labels are removed. Actual scope/deadline tests remain in the range loop, owned-pulse loop and pulse-lifetime suites. |
| Source/thread inventories duplicate stronger proof | The process-wide exact thread count and L4 cleanup source grep are removed. Executable stalled-capture, lease-renewal, success, failure, interruption and log-error cleanup tests remain. |
| Countdown tests inject impossible distances | The two nonfinite-distance tests and `InjectDistances` are removed after inspecting both current and frozen owners: boolean Hamming distances are finite in `[0,1]`. Finite thresholds, topology, work counts and reader-equivalence tests remain. The diagnostic path points to its tracked `docs/evidence` directory. |

## Additional baseline defect

Enabling the policy group exposes 46 failures in the behaviour tests: their frozen event metadata is compared with the current producer source fingerprint. The synthetic fixture now models the explicitly accepted writer `21a390f547eb`; a separate two-case test changes either the event writer or producer fingerprint and verifies refusal before embedding access or output creation.

The production consumer's freeze is unchanged. Passing these isolated tests does not claim that current production sources satisfy that freeze or authorize training. `docs/lanes/policy.md` describes the synthetic fixture and executable controller proof.

## Validation

- Focused repaired suites: **164 passed, 21 skipped** with perception and policy dependencies.
- Behaviour suite, including writer-mismatch refusal: **77 passed**.
- In-memory mutations confirm the new tests fail when the scripted gate is bypassed, targeted legality is bypassed, or partial archive bytes are written to the final path. Production files remain untouched by these probes.
- Full suite with perception and policy dependencies installed (`uv run pytest -q` after the grouped sync): **2230 passed, 125 skipped**, 89.90 s.
- After `uv sync`, `uv run pytest -q`: **1258 passed, 60 skipped**, 25.00 s. The environment is restored to stdlib-only.
- Auto Review (Codex, local diff plus `policy/live.py`, `policy/encode.py`, `policy/behaviour.py` and `tests/conftest.py`): **scoped-clean**, no actionable P0–P2 findings. Its assessment is limited to the supplied diff and context.
- `git diff --check` passes. Production code: **0 lines changed**. Tests/support: **141 added, 123 removed**; remaining changes are documentation and a test-routing comment in `pyproject.toml`.

## Retained contracts and limits

Real watchdog timing, range-banner equivalence, player-zone/crop geometry, OpenCV-provider compatibility, CLI weight forwarding and measured HUD operation-count checks remain. No test-only production API is added. No model weights are downloaded; the learned-controller fixture creates a temporary random head and substitutes only predictions and encoding.

Corpus tests, live gameplay and sealed-source inspection are outside this validation. Tracked diagnostic code and previously accepted clock-only evidence are used directly. No Linear update is made; the direct workspace Linear connector is unavailable in this session.

Reflection: existing instructions already require corpus markers. The repair belongs in the tests and their fixtures; no duplicate instruction or new skill is added.

## Merge integration

The audit commit `0f249d1` joins upstream `7add7f8` through merge `226ddf5`. The upstream CI missing-data plugin is redundant with the repaired fixture paths and corpus markers; the workflow uses ordinary pytest failure reporting without blanket xfail suppression.

- Merged stdlib suite: **1875 passed, 113 skipped, 3 failed**. All failures are in unchanged upstream `tests/test_transcode_recording.py`: Windows priority inheritance, Windows case-insensitive sealed-path spelling, and `tasklist`, on this Mac. Its production owner and tests are byte-identical to upstream.
- Affected merged suites (scoreboard, countdown performance, replay states, range-skill loop, policy and behaviour): **247 passed, 34 skipped**.
- Ruff passes. Independent Auto Review of the CI delta is **scoped-clean at P0–P2**. `uv sync` restores the stdlib-only environment.
