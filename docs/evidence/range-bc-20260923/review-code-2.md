# Review round 3: the K1-K10 fixes, `hudmap` / `hudparity` / `verify`, the contract test, the `Cal` change, and the P2 amendment

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-23. The review is read-only against `main` `299ffba` plus the
uncommitted package, as of the files dated 15:43-16:06 that `fit-impl-2.md` describes.

**Read:**
- `fit-impl-2.md` and the lane doc sections "Review round 2" and "Pilot pre-registration";
- every changed module: `steps`, `vocab`, `metrics`, `gates`, `executor`, `cache` and `train`;
- the three new modules: `hudmap`, `hudparity` and `verify`;
- `tests/test_range_bc_contract.py`;
- intake's `write_steps` (`agent/human_intake.py:812-990`);
- the `agent/controller.py` diff;
- `hud-parity-1.json` (sha256 `158649e6…`, which matches the report).

**Ran:**
- **Tests.** `test_range_bc.py`, `test_range_bc_contract.py`, `test_range_bc_hudmap.py`, `test_range_bc_torch.py` and
  `test_controller.py`, in my own environment made from the lockfile (execution and perception groups), at below-normal
  priority: **124 passed, 1 skipped** (the corpus parity test).
- **`pad_to_mk` timing** on a synthetic 2560x1440 frame.
- **The parity file's per-quantity counts,** against the untransformed baseline.

**Not done:** no repo edits, commits, Linear writes, game input or Mac jobs.

## Verdict: land the package as offline code. Do not declare the P2 amendment as written

- **The fixes.** K1-K10 are implemented as decided, and the contract test runs intake's real writer into the fit's
  loader.
- **What remains.** Nothing blocks landing offline code: nothing here sends input or reads a sealed row. What remains
  is either a pre-pilot item or small (L1-L7).
- **The amendment.** Its evidence is good, but its rule cannot fail on the quantity it is written for. See "The P2
  amendment" below, which also gives an honest path.

## The K fixes as implemented

| # | State | Evidence and residue |
|---|---|---|
| K1 | **Fixed** | `steps.load_denylist` goes through intake's reader with the sha256 pin. `57cfe01f…` matches the file today. Every CLI loads it (fit, cache, verify). The header requires `media_sha256`. Refusal is on an exact id or media match before any row, and on a file named exactly for a sealed id. The cache re-hashes the video against `media_sha256`, so the pixels of a forged header cannot be decoded. **Residue (L5):** a CLI user can pass a different denylist *and* a matching pin; the report records it, but nothing flags it |
| K2 | **Fixed** (intake's writer plus the fit's test) | `write_steps` maps actions through the header bindings. A stale-frame anchor is skipped and ends the run, and a capture gap ends the run. The contract test covers the plain session, the gap, `team_up` on C, the sealed media hash, the pending yaw gain and the action list. It passes. The multi-binding case for melee on Mouse 5 is an honest strict xfail |
| K3 | **Fixed in code; the measurement is pending** | `Cal.yaw_deadzone` / `pitch_deadzone` (None = unmeasured). `stick_for` places a small request just past the deadzone. Tracking error is reported by requested-rate band. `replay_profiles` takes train-split recordings only. Feasibility reports moving steps below the smallest measured rotation. **Residues:** L3 (pitch bands), L4 (the live controller ignores the deadzone) |
| K4 | **Fixed** | G4 compares self-fed with the self-fed twin. Self-fed change-F1 counts from the model's own previous executed hold, which is updated before the validity skip, so stratified views keep it (`metrics.py:77-102`). The twin is evaluated self-fed |
| K5 | **Fixed** | `code_closure` is the LF sha256 of every repo module imported. `--scope fit` runs `git ls-files --error-unmatch` and `git status --porcelain` on that closure, and verifies every cache byte (`cache_hashes_verified`) |
| K6 | **Fixed** | `swing_mode` is in the header and must agree across the cohort. `live_mask` drops `web_swing` unless it equals `PAD_SWING_MODE`, and an unknown mode drops it |
| K7 | **Fixed** | Every fit trains `model`, `model_nohud` and the twin, with gates per arm. `--hud-parity` is required at fit, and `candidate_arm` picks the arm before training. **Residue (L6):** the parity file is accepted on its `pass` field alone |
| K8 | **Fixed** | The lane doc's budget is encoder-only and names the unmeasured costs. The batch-32 slowdown is re-attributed. The consequence is stated: **≈ 19 h at 20 epochs** for 2 arms × 3 seeds |
| K9 | **Fixed** | tv-range BT.709 to full-range RGB at native size, with `accurate_rnd+bitexact+full_chroma_int`, and bitexact area scales. Any other tagging is refused, so a 10-bit HEVC source would fail loudly, not silently. The showinfo timebase is checked, the video hash must match `media_sha256`, basename collisions are refused, and caches are built on Mac arm64 only |
| K10 | **Fixed** | `--model-config` is refused at fit. `--preregistration` (epochs, weight decay, stride) is required at fit and must match the CLI, and `--max-steps` is refused there. The G5 note is in the report. The F3 no-leak test is added |

## The new modules and the contract test

### `hudmap.py` (the pad→M&K HUD transform)

**Sound.**
- The geometry follows the measured constants: 96 px slot columns swapped whole, the web count moved +241 px on the
  measured rows, and badges inverted inside the detected disc with a synthetic ring.
- `hud_stream` reproduces the cache's crop and truncation, with RGB before cropping.

**L1 (before the live wiring): apply the transform to every stream, not only the HUD crop.**
- The docstring and the lane doc say it is applied "before the HUD stream is cropped".
- The global 256x144 stream also shows the HUD. At 1/10 the swapped icons, the left-side web count and the inverted
  badges are 6-8 px blobs in different places from every training frame.
- Run `pad_to_mk` once on the native frame, and feed the transformed frame to the global, crop and HUD streams. The crop
  is central and unaffected.
- State this in the lane doc's live contract.

**L2 (before the live wiring): the transform costs 8-14 ms per native frame.**
- Measured on a 2560x1440 frame with light discs in all three badges: 8.4-13.6 ms. Without discs: 3.1 ms.
- The cost is a full-frame copy (11 MB) plus a pure-Python flood fill (`_largest_component`, `_fill_holes`) over three
  54x43 boxes.
- On a 33 ms tick that already holds the capture and a CPU model step, this is a real share.
- Copy only the bottom HUD band, use `cv2.connectedComponents` / `floodFill` (cv2 is already a dependency of
  `hud_stream`), and include the transform in the measured frame-to-send latency.

### `hudparity.py`

**Sound.**
- It is structured and pre-registered: thresholds fixed in the module, and a consequence stated ("drops the HUD stream,
  not that thresholds move").
- It excludes 053616 by path, hashes its sources, and reports an untransformed baseline.

**The weakness matters for P2 below.**
- Agreement on *ready flags* barely separates the transform from no transform:

  | Quantity | Transformed agreement | Untransformed agreement |
  |---|---|---|
  | `uppercut.ready` | 99.8% | 95.3% (25 contradictions) |
  | `get_over_here.ready` | 57.5% (347 / 256 lost / 0 contradictions) | 56.6% (341 / 248 lost / 14 contradictions) |

- The discriminating signals are webs, charges and cooldowns (0% without the transform, 99-100% with it), and the
  contradiction counts.
- Cooldowns rest on 20 + 5 frames. The pad stills are "almost all at full resources" (lane doc). So parity is thinnest
  on exactly the states the HUD stream exists for: low webs, spent charges, running cooldowns.

### `verify.py`

**Sound.**
- It checks: the reference hash recorded in the report; the candidate's sha; the LF-normalised code closure; the
  pinned denylist; the step tables; and the caches.
- It then reloads on the CPU and requires identical teacher-forced and self-fed decisions, reporting the first
  divergent step, with a probability delta ≤ 1e-4. It asserts no live I/O modules and writes its report exclusively.

**L7:**
- **Report hash.** Without `--report-sha256` the checks are self-consistent: a report, reference and checkpoint
  altered together would pass. Make the out-of-band report hash required; the lead records it on the issue.
- **Cache bytes.** Without `--full-hash` the caches are checked by manifest claim only. Make full hashing the default
  for the evaluation set.
- **Self-fed divergence.** Exact equality of self-fed decisions is right, but one probability within float noise of 0.5
  (or of a median-class boundary) flips every later step. At the first divergent step, report that step's distance from
  the threshold, so numeric noise can be told from a real mismatch.

### `tests/test_range_bc_contract.py`

- It runs intake's own fixtures through `write_steps` into `steps.load` with the real denylist, which is the contract
  test K2 asked for.
- The capture-gap case asserts two runs, with no frame older than two periods.
- The sealed case renames the file and forges only the media hash, and is still refused.
- `hi.FIT_ACTIONS == vocab.NAMES` pins the order.
- The strict xfail for Mouse 5 as a second melee binding documents a real gap rather than hiding it.

## The `agent/controller.py` change, as an independent review of live-input code

**Backward compatible.**
- `Cal` gains `yaw_deadzone` / `pitch_deadzone = None`, and every `Cal(...)` in the repo uses keywords (the tests use
  `press_s=`).
- With `deadzone=None`, `stick_for` is the old code path unchanged. `Live._aim`'s two calls (`controller.py:1100-1101`)
  pass no deadzone, and `test_controller.py` passes.

**L4.**
- Once the low-end job fills `Cal.*_deadzone`, the executor uses it and the scripted `_aim` still does not.
- That split is the L4 owner's decision. Record it, so a measured deadzone does not look adopted by the live controller
  when it is not.

**Pinned identities.**
- No existing artefact changes: past pilot freezes pinned their own copies (`controller-deployed.json`).
- The next pilot freeze will pin a new `agent/controller.py` hash. That is expected, and this section is the review it
  needs.

## The P2 amendment: honest or bent?

**My judgement: as written, it is a rule bent to pass, although the evidence behind it is good.**

**The evidence is genuinely strong in three places.**
- **P1 and P3** pass.
- **Webs, swing and combo charges and both cooldowns** go from 0% (untransformed) to 99-100% agreement.
- **There are zero contradictions on every quantity.** The untransformed frames give 14 on `get_over_here.ready`, 25 on
  `uppercut.ready`, and 5 on each cooldown.

The transform almost certainly puts the right content in the right places.

**The proposed rule is still not an honest test, for four reasons.**
1. **It was written after the result, for the one quantity that failed.** The module's own pre-registration says a
   failure means "the live arm drops the HUD stream, not that thresholds move".
2. **Its loss clause cannot fail at that slot.** The *untransformed* pad frames lose 248/603 = 41% there, also below
   the proposed 64% ceiling. So "losses ≤ native abstention" admits the no-transform case too, and the rule collapses to
   "zero contradictions".
3. **The 64% is weak.**
   - It is 30 of 47 frames (95% interval roughly 50-76%).
   - Those frames come from different scenes and resource states. The guard fires on the ult diamond's glow, so the
     abstention rate depends on how often the ult shows that glow in each frame set, not on the transform.
   - A comparison of two unmatched rates is not a test of the transform.
4. **Parity would still be shown mostly on full resources,** where the HUD stream carries the least decision
   information.

**An honest path. It costs nothing now, because both arms are trained in every fit.**
1. **Keep run 1 on record as FAIL.** The no-HUD arm is the candidate, as pre-registered. "HUD arm as candidate, with the
   no-HUD arm as fallback" needs a pre-registered switch condition; as proposed it has none.
2. **Pre-register P2′ before any new data.** The ready flags are scored only where the M&K reader's occlusion guard is
   not firing at that slot, for example ult not glowing, which the reader's own `ult_ready` or guard state can supply.
   On those frames:
   - agreement ≥ 0.95, with ≥ `MIN_KNOWN` frames;
   - zero contradictions on every quantity;
   - **a power check:** the untransformed baseline must fail P2′;
   - **a coverage floor per quantity,** for example ≥ 20 frames each with webs ≤ 2, a spent charge, and a running
     cooldown per slot.
3. **Run P2′ on fresh frames that did not shape it.** New pad stills from the placement or pilot runs, and M&K frames
   from the new campaign takes (for example `2026-09-23 15-55-28`, never 053616).
4. **Make the HUD arm earn its transfer risk offline.** It becomes the candidate only if P2′ passes *and* it beats the
   no-HUD arm on validation by a pre-registered margin: +0.05 self-fed macro press-F1, or a resource-stratified gain.
   Otherwise the live HUD shift is risk with no measured benefit.

If the lead declares an amendment anyway, the report must say "P2 amended after run 1, on the run-1 data", with the
original FAIL beside it. It must not read as a pass.

## Small items

- **L3.** `tracking_error`'s rate bands are the yaw map's for both axes. Pitch's unmeasured region runs to 43°/s, which
  straddles the 18.5-61.5 band. Use per-axis bands, for pitch 0-9, 9-43, 43-99 and saturated.
- **L5.** Flag a non-default denylist or pin in the report, and have the verifier compare it with the constant.
- **L6.** `candidate_arm` accepts any JSON whose `pass` is true. Require `hudparity`'s own fields (thresholds, P1-P3,
  sources) and pin the parity file's sha256 in the pre-registration.
- **Budget.** With parity failed, the HUD arm cannot be the candidate in this fit, yet it takes half of the ≈ 19 h.
  Training it on one seed, as a reported comparison, would fit the 5 h target sooner. That is the lead's call.
- **Cosmetic.** `executor.py:74` carries a duplicated trailing comment.

## What is sound

- **The sealed chain.** Intake's pinned JSON denylist is checked by id and by media hash before any row. The cache
  re-hashes the video, so a forged header decodes nothing. Every CLI loads the denylist.
- **The intake→fit contract** is now a tested, running pipeline.
- **The gates.** G4 compares like with like. Unknown pitch gain masks pitch everywhere, and the verdict is then never
  pilot-worthy. A pending yaw gain refuses the fit.
- **Provenance.** Code closure plus commit enforcement, verified cache bytes, a pre-registration file and a parity file
  are all hashed into the report.
- **The verifier** reproduces the 09-22 and 09-23 chain for this checkpoint format.
- **Honesty in the hand-back.** The lane reported P2 as a failure and did not change the rule itself.
