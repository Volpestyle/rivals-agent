# Review: whole-session intake design (VUH-1359)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-23. The review is read-only against `main`
`d6b360c`:

- **Read:** `docs/lanes/human-admission.md` lines 571-735, `admission-owner-final-9.md`,
  `docs/recording-protocol.md`, `agent/human_demos.py`, `docs/visual-range-supervision.md`, the v2
  source profile and the 2026-09-22 candidate split registry.
- **Not done:** no decode or import was run. No repo edits, commits, Linear writes or game input.

## Verdict: APPROVE WITH REQUIRED CHANGES

The core choice is right: reuse the reviewed importer unchanged and add only a proposer, assembly,
registry, freeze and tally. The importer's own window rules are sound (see "What is sound").

Every serious problem sits in the new layer. It is the proposer and the assembly that decide where
boundaries fall and what counts as accepted, and the design leaves those decisions under-specified. Items
R1-R5 must be in the build. R6-R9 are smaller.

## Ranked findings

### R1 (serious): UI keys and sampled HUD presence leak non-gameplay into training rows

**Why the importer can't catch it.** The importer bounds every window by the segment:

- `left = max(...)` and `right = min(...)` at `agent/human_demos.py:560-561`;
- anchors at `:563`, running to `right - bins*bin_ns`;
- pre-`left` frames refused at `:570`.

So any leak must enter through where the proposer puts `end_ns`/`start_ns`. The design derives
boundaries from "range-HUD presence per sampled frame" and the 5 fps regime scan (lines 606-615). Neither
sees the input that causes the transition.

**Case.** The range overlay offers PRACTICE SETTINGS (Esc), CHANGE HERO (H), VIEW DESTRUCTIBLE OBJECTS (B)
and HERO PROFILE (F1). I saw this list on screen during ordinary gameplay in 051828 (e.g. file 2.4-3.7 s).

1. James presses Esc at t_esc. The menu draws about 1-3 frames later.
2. With HUD presence sampled at 5 fps, the first sample without the HUD falls anywhere in
   (t_esc, t_esc + 200 ms]. The proposer sets the accepted segment's `end_ns = e` there.
3. With the schema's example options (`bin_ns` 100 ms, `bins` 5, `docs/human-demo-schema.md:271`),
   every anchor in (t_esc - 500 ms, e - 500 ms) is emitted. That interval is never empty, because
   e > t_esc.
4. Those rows' future `ActionBin`s contain the **Esc key-down as a target action**. Their `FrameRef`
   history (anchor ≥ t_esc) can include menu frames.

The policy learns to press Esc, H, B or F1.

**Two worse variants.**

- **The idle kick.** The ~60 s AFK run-up has the HUD present, so the proposer proposes it as normal
  gameplay. Only `idle_tail` saves it, and that is undefined.
- **A menu that keeps the banner.** If the settings menu keeps the "PRACTICE RANGE" banner (not
  established), HUD presence never drops and the menu span is proposed as gameplay.

**Required.**

- **Input-caused cuts.** The proposer must cut at the causing input packet: `end_ns ≤ t_ns` of any
  UI/menu key (Esc, H, B, F1, Tab, Enter, Alt; list it in code), with reason `ui_key`.
- **Native-frame boundaries.** Every HUD-derived boundary must be refined to 120 fps native frames, and
  must be conservative on both sides:
  - an accepted segment ends at or before the last verified gameplay frame;
  - it starts at or after the first verified gameplay frame after the closing input.
- **Tests.** Add synthetic tests for "Esc inside an accepted segment" and "Esc at the segment end". Each
  must assert that no emitted sample has the key in a future bin.

### R2 (serious): mouse-count targets have no settings identity

**The problem.**

- **What the rows train on.** The BC targets are raw mouse counts (`ActionBin` dx/dy).
- **What the profile knows.** The v2/shared source profile records `motor_settings: {sensitivity: null,
  dpi: null, ...}` and explicitly refuses to forward-date the 09-21 report
  (`051828-request-timing-v2/source-profile.json:22-29`; `docs/visual-range-supervision.md:9-10`).
- **What the design does.** It fills the importer's required `settings`/`bindings` provenance "from the
  shared source profile" (design line 627). The importer only requires a non-empty value and a source
  string (`agent/human_demos.py:405-409`). A profile digest therefore passes as the "value", while the
  actual counts→angle mapping stays unknown.

That was harmless for the event head, which used no motor labels. It is not harmless for a policy that
emits mouse counts: a DPI or sensitivity change between sessions silently mixes incompatible targets.
Nothing can detect it, because `load_datasets` compares only patch and cooldown (`:711`).

**Required.**

- **Actual values.** `settings`/`bindings` provenance must carry actual values (sensitivity, DPI, swing
  mode, bindings) with a per-session source: a settings screenshot at session start, or James's per-session
  statement. The protocol can ask for a 5 s look at the settings screen before play.
- **Enforcement.** Assembly must refuse null motor fields.
- **Fit-side check.** The fit must compare motor settings across sessions, as it does patch and regime.
- **Existing sessions.** Where this cannot be recovered, mark them `held: motor settings unknown`, not
  admitted.

### R3 (serious): a mid-session regime or settings change cannot be localized from the scan

**The problem.**

- **What the design does.** It splits a segment on a regime change found by the scan
  (`regime_differs_from_session`).
- **Why that is late.** The regime is read behaviorally, from countdowns after an ability is used. A
  No Ability Cooldown toggle is therefore detected only at the next cast, seconds later. The rows in
  between carry the wrong regime.
- **Why it matters.** The importer has one `cooldown_regime` per review (`:405-409`, checked at `:711`).
  Changing it requires the Esc menu, which R1 already cuts on.
- **What the protocol says.** A settings change inside a session means the session "cannot be admitted as
  one identity" (`docs/recording-protocol.md`).

**Required.**

- Any settings-menu opening ends the accepted segment.
- Everything after it is `unresolved` at least, until the regime is re-established on native frames.
- The default is to **hold the session**, following the protocol, unless the lead decides otherwise.
- Never `accepted` on scan evidence alone.

### R4 (serious): the sealed 053616 take is protected only by registry content

**The problem.**

- **What guards it today.** `read_splits` enforces group→split and media→(group, split) consistency
  *within one file* (`:186`, `:190`). A sealed refusal happens only if that file says `test`
  (`:212-217`).
- **Why that is not enough.** `import_human_demo.py import --splits <any path>` accepts any registry.
  Nothing has been imported for 053616, so no sealed artifact header exists to catch a later load. Any
  registry that lists 053616 as `train` would import it into train with no error: a stray experiment
  registry, an edited corpus registry, or a group renamed to a train group.
- **Two registries are a standing risk.** The 2026-09-22 candidate registry already coexists with the
  proposed corpus registry.

**Required.**

- **Pinned registry.** `session-splits.corpus.json` is frozen and hash-pinned in every session artifact
  and in the corpus manifest (R7).
- **An independent sealed denylist.** A small pinned file of session ids plus media sha256 for 053616.
  It is checked by the proposer, assembly, tally and fit driver *before* reading any registry. Any
  registry naming a denylisted id or hash with split ≠ test is refused.
- **Media hash.** Compute 053616's media sha256 without opening its logger folder: hashing the
  immutable file does not unseal content. Otherwise list its path.
- **Test.** A registry with 053616 as train must be refused.

### R5 (serious): acceptance enforcement and independent review are not specified

**What the design says.** "The proposer never sets `accepted`" and "the reviewer then decides" (lines
617-620). Nothing in the importer can tell a real verdict from a default string: it requires only
`reviewed_gameplay is True` plus non-empty text (`:419-425`).

**Required in code.**

- **A different key for proposals.** The proposal field in `segments-evidence.json` must not be named
  `imitation_suitability`.
- **Where accepted can come from.** Assembly may emit `accepted` only from a verdict record that carries
  a reviewer id, a time, and inspected native frame refs with decoded-BGR hashes.
- **The default.** A missing verdict becomes `unresolved`.
- **Tests.** One test for each.

**Dropped from today's admission.** Every event packet admitted so far had an **independent review
before lead admission** (`AGENTS.md`: code and data deciding what enters a training set get a review from
outside the lane). The design has the owner as the only reviewer of each session's accepted segments.

- **Required:** an independent review per session, at least of the proposer's boundaries and a sample
  of accepted spans, with its hash in `review.json` provenance.
- **Suggested:** stratify the sample by proposer reason and include every segment edge.

### R6: minutes accounting

**What the design gets right.** "Admitted minutes = accepted duration" (lines 677-679) is
rate-independent, so a 30 Hz sampling change cannot inflate it.

**What must change.** The tally's purpose is the ~3 h *trainable* mark, and three things make the plain
sum overstate it:

- **Per regime.** `load_datasets` refuses mixed cooldown (`:711`), so one fit can use only one regime.
  The headline against 180 min must be **per regime, train split only**, not a sum. The design's footer
  already splits by regime; make that the headline.
- **Trainable minutes.** Report `trainable min = eligible anchors × stride_ns / 60e9`, with the
  sampling parameters named next to the count. This exposes the history head and future tail lost at
  every segment edge. That loss grows with many short segments, which R1 will create.
- **AFK spans.** They must not count. Define `idle_tail` and mid-session idle as N seconds with no
  control-affecting input (`_control_affecting`, `:350`), rejected with a reason, not just a tail.

Keep the anchor count beside the minutes, as designed. Always print it with its `stride_ns`.

### R7: pins are incomplete for fit-time drift refusal

`intake.json` pins media, logger files, build, regime, anchor evidence and the perception snapshot. That
is good. Missing:

- **Importer code.** The git blob of `agent/human_demos.py` (the sampling semantics *are* the rows) and
  the proposer and assembly code.
- **Registry and denylist.** The corpus split registry hash and the denylist (R4).
- **Tool versions.** The `ffprobe` version, since decoded PTS enter the artifact.
- **Scan outputs.** The HUD-presence and regime scan output files, not only the code that made them.
- **Review evidence.** The reviewer's native frame hashes.
- **Per-session anchor applicability.** Each session's own first-16-packet/profile applicability check,
  not only the accepted 033319 derivation.
- **A corpus manifest for the fit.** The design has a tally but no manifest. It needs one, like today's
  `cohort-manifest.json`, pinning each session's `artifact-hashes.json`, `sampling.json` and export
  digest, with a `--check` the fit driver runs and refuses on drift.
- **Relocation.** Mac fits need `recorded_video_path` and `expected_media_sha256` in the registry
  (`:193-201`, `docs/machines.md`). State it.

### R8: the old "no-button periods are not Idle negatives" rule is silently superseded

`docs/visual-range-supervision.md:62-65` forbade no-button, movement and menu periods as neutral labels.
Under whole-session BC every quiet bin is a supervised "no action".

- **That is fine for genuine play.** Say so explicitly, as a superseding decision for this head.
- **The rule still applies to menus, lobby, AFK and focus loss.** Those spans must always be rejected
  (R1, R6).
- **Focus snapshots are already handled.** The importer treats them as unknown holds; state it in the
  design.

### R9: minor

- **Sampling description.** `sampling.json` says anchors are "every 4th 120 fps frame". The unchanged
  importer instead uses a ns grid `range(left + history_ns, …, stride_ns)` (`:563`) that restarts at
  every segment start. So re-tiling changes the row set. Describe it accurately; the export digest
  already pins the result.
- **Rejected segments still need `reviewed_gameplay: true`.** The importer requires it on every segment,
  including rejected lobby and menu spans (`:419`). Record in `segments-evidence.json` what was actually
  seen, so the flag is not read as "this was gameplay".
- **Raw-input gaps refuse the whole session.** A logger `gap` event does not exclude an interval; it
  refuses the session (`:309`). The design's `capture_gap` reason covers frame gaps only. Say that
  raw-input gaps make the session `held`.
- **Controller input is invisible.** The logger records keyboard and mouse only; XInput is invisible.
  `device_scope.source` should carry James's attestation that no pad was used.

## Idle kick mid-recording: what happens now, and what should

**Now.**

- **Before the kick.** The HUD is present through the ~60 s AFK run-up, so it is proposed as gameplay
  (see R1/R6).
- **After the kick.** The HUD is absent, so the lobby is proposed with `no_range_hud`. The proposer
  never accepts, so the lobby is rejected on review. That part is correct.
- **Coming back.** If James re-enters the range from the lobby, a new HUD-present span appears. It is
  re-admittable, but a new range instance (bots respawned, ult state) should get its own segment and a
  reason.

**Should.** `idle_tail` rejects the AFK run-up, and the lobby spans are rejected with the lobby keys cut
(R1).

## What is sound

- **Reusing the importer.** Nothing is forked. The design also commits to stopping and reporting if the
  importer needs a change.
- **The importer's window rules.**
  - Causal `FrameRef` history, with pre-boundary frames refused (`:570`).
  - Future bins strictly inside `right` (`:563`), so a future bin never crosses a focus/pause interval
    or segment end.
  - Capture-gap windows excluded over the whole history+future (`:547`, `:582`).
  - Focus and pause events end intervals (`_timeline`, `:489-513`), and focus snapshots are unknown
    holds.
  - Only `accepted` trains (`:557`), and training refuses the test split.
- **The proposer's role.** It never sets `accepted`, and every segment carries a machine reason.
- **Minutes as accepted duration.** Rate-independent, and shown beside the anchor count.
- **Tags.** Start `unknown`, and never enter observations.
- **Rows not materialized.** They are deterministic `samples()` output plus an export digest.
- **The lead's placement decisions.** 053616 in its own sealed group and 171533 afternoon as train are
  consistent with the importer's one-split-per-group rule. The registry `purpose` should state that
  053616 is the same evening and OBS process as 051828, so a test result on it is not
  session-independent.
- **Mixed regimes.** Recorded at intake and deferred to the fit.

## First action for the owner

Build R1 (UI-key cuts and native-resolution boundaries) and R5 (a verdict-only `accepted`) into the
proposer and assembly before running 171533. Settle R2 with James before counting any minutes as
admitted.
