# Review: intake code before it lands (VUH-1359)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-23. The review is read-only against `main` `299ffba` plus the uncommitted
intake files.

**Measured against:**
- the intake design review's R1-R9 as decided (`review-whole-session-design.md`);
- the fit's K2 contract (`review-fit-code.md`).

**Read:**
- `agent/human_intake.py`, all 955 lines: proposer, verdicts, assembly, denylist, registry, minutes, tally, manifest,
  `step_table` and `write_steps`;
- `tests/test_human_intake.py` and `tests/human_intake_fixtures.py`;
- `data/human/sealed-denylist.json` and `data/human/session-splits.corpus.json`;
- the 429-line amendment to `docs/lanes/human-admission.md`;
- the drivers that call this code, for order of operations only: `data/human/sessions/intake_session.py` and
  `tally.py`;
- 171533's frozen `review.json` and `.steps.jsonl` header, to check one real output.

**Ran:**
- **Tests.** `tests/test_human_intake.py`, `tests/test_range_bc_contract.py` and `tests/test_human_demos.py`, in my own
  environment made from the lockfile, at below-normal priority: **116 passed, 1 skipped** (the opt-in blank-OBS
  fixture), **1 xfailed** (the strict xfail for Mouse 5 as a second melee binding).
- **A cross-check probe:** `write_steps` with values that contradict the reviewed provenance.
- **171533's `settings_identity`,** recomputed from its review.

**Not done:** no repo edits, no commits, no Linear writes, no game input, and no media opened; 053616 not read.

## Verdict: APPROVE LANDING WITH REQUIRED CHANGES

**The acceptance gate is sound.** No proposer reason or default can become `accepted`. The UI-key cut sits on the exact
packet. The sealed denylist is applied before the registry is interpreted, and before any recorder file or media is
opened on the intake driver's path. The settings identity covers the motor values and the full binding table. The
`write_steps` header is complete, and the minutes definitions are the ones R6 and R11 asked for.

**Before more sessions are admitted or step files are written for a real fit:**
- **I1:** `write_steps` must derive, or verify, its settings, bindings, swing mode, patch and regime against the
  reviewed provenance.
- **I2:** the fixed 2 s settle after Enter and the overlay keys must become open/close spans.
- **I3:** the denylist must guard every path, not only the driver's.

## Findings

### I1 (required): `write_steps` trusts caller-supplied identity instead of the reviewed provenance

**What it takes.** `write_steps(dataset, …, bindings, calibration, swing_mode, settings_hash, patch, regime,
device_report, …)` takes every identity field as a free argument (`human_intake.py:844-876`). It never compares them
with `dataset.review_json`'s provenance, which is the reviewed, cited source.

**Probe.**
- On an importer dataset, I passed:
  - E/F swapped bindings (`get_over_here` on E);
  - `settings_hash` of `"0"*64`;
  - swing mode `{automatic_swing: true, hold_to_swing: false}`;
  - patch `some-other-patch`;
  - regime `no_ability_cooldown`.
- `write_steps` wrote the file, and the fit's `steps.load` accepted it.

**The real file is consistent today.** 171533's frozen step file carries the review's bindings. Its `settings_hash`
`eb9e66a0…` equals `settings_identity(review settings, review bindings)`, and its patch equals the review's. The
driver did it right by hand.

**Why it matters now.**
- The E/F binding is contested (James's HUD against the kit).
- A step file written with a different binding table than the review silently swaps Get Over Here! and Amazing Combo
  labels.
- Nothing downstream can see it: the fit checks only that the cohort agrees with itself.

**Required.** Inside `write_steps`:
- **Derive or check each field against the reviewed provenance:**
  - `bindings` equal the review's bindings, restricted to the fit's actions;
  - `settings_hash == settings_identity(review settings, review bindings)`;
  - `patch` equals the review's `game_patch`;
  - `regime` equals the review's `cooldown_regime` when no regime spans are given.
- **Compute the device report** with `device_scope_report(dataset.events)` instead of taking it.
- **Pick one swing-mode form.** The review's `swing_mode` is free text ("default: hold_to_swing true, automatic
  (simple) swing false on Shift; Simple Swing on Caps Lock"), while the header's is a dict. Store the dict in the
  review provenance, and hash that.
- **Test that each mismatch is refused.**

### I2 (required): a fixed 2 s settle cannot bracket chat or overlays that keep the HUD up

**What works.** The cut starts on the key packet. The gameplay piece's end bracket `hi` is capped by the cut start,
and native refinement moves an edge outward only over contiguous present frames inside its bracket
(`human_intake.py:167-190`). So `end_ns ≤ t_key`, and the importer's strict `< end` keeps the key out of every future
bin. The Esc tests, with the importer's own `samples()` and a naive-boundary control that does leak, are exactly R1's
tests.

**The gap.** After a non-Esc UI key, gameplay can resume at any HUD-present sample 2 s later (`UI_SETTLE_NS`).
- **Enter opens chat.** The HUD stays up while James types. Letters he types that are bound (W A S D E F Q V C) would
  become action presses inside a proposable gameplay span once 2 s have passed, until the closing Enter.
- **F1, B, H and Tab overlays.** The same holds wherever the overlay leaves the range HUD reader "present". R1 already
  flagged "a menu that keeps the banner" as not established.

**Human review mitigates this, but the proposer's boundary should not depend on the reviewer noticing chat text.**

**Required.**
- Enter opens a span closed by the next Enter or Esc. Cut from the opening packet to the closing packet plus the
  settle.
- For the toggle overlays (F1, B, Tab while held, H), cut until the closing key, or until the reader's *gameplay* HUD
  (not the banner) is re-verified on native frames.
- Measure once what `hud_present` reports while each overlay is open.

### I3 (required): the denylist guards the driver's path, not every path through this module

**What is right.**
- `check_registry` checks denylisted ids, media hashes and resolved paths against the raw registry rows before
  `hd.read_splits` interprets them (`:364-381`).
- The driver loads the denylist, then `check_registry`, requires the session to be registered and not test, and only
  then opens `metadata.json` (`intake_session.py:81-94`). Media hashing uses the immutable file only.
- The denylist file and the registry agree: 053616 is `test`, `sealed: true`, with media `ea49d523…` in both.
- Groups are one recording each (F6).

**Gaps:**
1. **`load_cohort`** (`:786-811`) calls `hd.load_dataset(path, splits=…)` directly, with no denylist and no
   `check_registry`. A registry naming 053616 as `train` would load through it, which is the case R4 was about. Take
   `denylist` as a required argument and run `check_registry` first.
2. **`write_steps` and `step_table`** have no sealed check. The fit catches the media hash, but intake's own writer
   should refuse too: call `assert_not_sealed(dataset.placement.session_id, dataset.media_sha256, denylist)`.
3. **The driver** loads the denylist without its sha256 pin (`load_denylist(DENYLIST)`). The fit pins it at `57cfe01f…`.
   Pin it in every intake driver too.
4. **The driver's guards are `assert`s:** "session not registered" and "split != test". They vanish under `python -O`.
   The request-fit driver refuses `-O` for exactly this reason. Use explicit raises.

### I4 (moderate): the Esc session is "held by default" only on paper

- The proposer emits the flag `settings_menu_opened` ("session held by default (R3)").
- Nothing in assembly or the tally enforces it: `assemble_review` does not take the flags, and tally statuses are
  entered by hand.
- R3 made holding the default unless the lead decides otherwise.
- **Required:** assembly refuses `accepted` segments in a session carrying that flag, unless a lead-decision record
  (`{path, sha256}`) is supplied. 171533 already has a `lead-decisions.json`, so the pattern exists.

### I5 (moderate): the acceptance evidence is thinner than its docstring

**What is required today.** `accepted` needs at least one inspected native frame inside the segment, with a
decoded-BGR hash (`_frames_ok`, `:240-244`).

**Two weaknesses:**
- **One frame is enough.** A ten-minute segment can be accepted on a single frame. R1's leaks happen at the edges.
  Require inspected frames within, for example, 0.5 s of *both* edges.
- **The hashes are claims.** Nothing re-decodes the listed frames to check them. A small `verify_frames(review, video)`
  that re-hashes the listed ordinals would make them evidence. The independent review could run it.

### I6 (moderate): confident HUD absence is absorbed as a reader miss

**The behaviour.**
- In the proposer, `False` samples are skipped exactly like `None` samples. They split a gameplay run only when the
  gap between present samples exceeds 2 s (`:161-168`).
- The test calls a 0.6 s run of `False` a "short reader miss" (`test_short_reader_misses_stay_inside_gameplay…`).
- **But `False` is the reader saying the HUD is absent.** At 5 fps up to nine consecutive confident-absent samples are
  absorbed into gameplay.

**The driver** also collapses unknown into absent: `bool(r["hud_present"])` (`intake_session.py:386`). That is against
the repo rule that unknown is never read as zero, although here it only changes hole labels.

**Required.** Absorb `None` gaps up to 2 s, but let at most one isolated `False` sample through. Keep `None` as `None`
in the driver.

### I7 (moderate): two step grids and two meanings of "admitted"

**Two grids.**
- `step_table` (the columnar function) keeps anchors inside a capture gap with stale frames.
- `write_steps` skips them and ends the run.
- Only `write_steps` feeds the fit. Retire `step_table`, or make it a thin view of `write_steps`, so the tally and the
  fit cannot count different rows.

**Two meanings of "admitted".**
- `session_minutes()["admitted_minutes"]` is the accepted duration.
- The tally's `admitted_min` is `counted_minutes` (focused ∩ accepted ∩ gap-free runs ≥ 1.6 s; `tally.py:56`), which
  is the R11 definition and the 3 h trigger. Correct, but two numbers share one name.
- Rename one of them.
- Compute `trainable_min` from the written step file with the fit's own `steps.train_minutes`, so the tally's trainable
  minutes are the fit's rows by construction.

### I8 (minor)

- **Display settings are outside the settings identity.** `settings_identity` covers DPI, both sensitivities, swing
  mode and the full binding table, as R2 and R7 asked. But FOV, HUD scale and the crosshair change the pixels the fit's
  fixed crops and global frame see, and none of them is in the identity or the step header. Add them from the same
  settings look.
- **Simple Swing on Caps Lock.** 171533's review binds `simple_swing` to Caps Lock (`key:58:0`), which is not a fit
  action, so its presses land in `unsupported`. That is correct (K6), and the fit's unsupported share will show it as a
  ceiling. Say so in the lane doc beside C.
- **A pending calibration means a rewrite.** 171533's frozen step file carries `yaw_deg_per_count: null` ("pending"),
  so the fit refuses it until the 360° take is applied. Rewriting means a new step file and a new freeze. Plan it as a
  versioned artefact, not an edit.
- **The code under review is not the code that ran.** The drivers import `agent.human_intake` from archived snapshots
  (`code-snapshot-c0892ab`, and `74db8be` for the tally). After this lands, take a new snapshot, and record per session
  which snapshot produced its artefacts. 171533 was produced by an earlier snapshot, not by this reviewed file.

## The six priorities, settled

1. **Can a proposer reason or default become `accepted`?**
   - No. `accepted` comes only from a verdict record with reviewer, time, evidence and hashed native frames, on a
     `range_hud_present` candidate. A missing verdict is `unresolved`.
   - The proposer's field is `proposal`, and it refuses to say `accepted`.
   - Play after Esc is `after_settings_menu` and cannot be accepted (tested).
   - Residues: I4 (the held default is unenforced), I5 (one frame, unverified hashes), I6 (absorbed absences).
2. **The UI-key cut.** It is exact on the packet, with native refinement bounded by the cut, and tested with the
   importer's own samples plus a leaking control. The residue is the settle rule for chat and overlays (I2).
3. **Denylist before registry and media.**
   - Yes on the driver's path: denylist, then registry rows, then registered and non-test, then the recorder files.
   - `load_cohort` and the writers bypass it, and the driver misses its pin and uses `assert`s (I3).
4. **Settings identity.** It covers DPI, both sensitivities, swing mode and the full binding table. It is not tied to
   the step header, which is caller-supplied (I1); display settings are outside it (I8).
5. **`write_steps` header completeness.** Complete against the fit's `HEADER_KEYS`: the contract test passes, and a
   capture gap ends the run without stale frames. Integrity: I1.
6. **The tally's minutes.** The 3 h trigger is counted minutes (focused ∩ accepted ∩ gap-free runs ≥ 1.6 s).
   Trainable minutes carry their stride, the headline is per regime and train-only, and sealed, held and pending rows
   carry no minutes. Naming and the single grid: I7.

## What is sound

- **The shape of the pipeline.** The reviewed importer is kept; around it are a proposer that never accepts,
  verdict-only acceptance, an assembly that runs the importer's own `_review`, and a session tiling check.
- **Motor refusal (R2).** Assembly refuses null DPI, sensitivities, swing mode or bindings, requires per-session
  sources, and requires the no-pad attestation (R9).
- **The independent review (R5)** is required for any `accepted` segment.
- **AFK (R6)** is 20 s without control-affecting input, rejected. The focus settle after every focus regain is a
  measured fix (the taskbar frame in 171533).
- **Denylist and registry (R4).** An independent pinned-format denylist with id, path and media hash; the registry is
  refused if it names a sealed session outside test.
- **Freeze and manifest (R7)** detect drift, including unpinned new files.
- **Device scope.** Handle-0 control input refuses a session; zero-effect handle-0 packets are counted, not accepted
  silently.
- **`write_steps`.** Actions map through bindings (so E/F follows the table given), a stale-frame anchor ends the run,
  and holds are known only when both ends are known.
- **Tests.** 116 pass, including the R1 Esc tests with their leaking control, the sealed-train registry refusal,
  mixed-motor refusal, and minutes, tally, freeze and manifest drift.
