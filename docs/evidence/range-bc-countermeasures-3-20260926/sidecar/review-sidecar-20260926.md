LAND

# Review: round-3 physical-idle sidecar (VUH-1346), binds-review (Opus 5.5), 2026-09-26

This was a read-only, independent review. I made no edits, commits, training runs or game input.

**Contract:** §6 (with Amendment 1) and §2 of
`docs/evidence/range-bc-countermeasures-3-20260926/fit-countermeasures-3-prereg-draft.md`, at `9d61d59`.
HEAD is `9d61d593ac7a…`.

**Pins I verified:**

| Artifact | Checked against |
|---|---|
| `HANDBACK.md` `96bab376…` | the lead's brief |
| producer `6afc06f5…` | the handback |
| tests `f1a6ed6f…` | the handback |
| `manifest.json` `03bbf983…` | the handback |
| registry `e8a1d060…` | the manifest; also equals its git blob, so it is portable to the Mac |
| denylist `439c80df…` | the manifest; also equals its git blob |
| `agent/human_demos.py` `64f21da2…` | the manifest; unchanged from HEAD |
| each of the five sidecars | its `sidecar_sha256` in the manifest |

`verification-replay/` is byte-identical to the primary output (the manifest and all five sidecars).

## Verdict on the four checks

### 1. "Fully idle" matches §6 and is conservative

A row is `true` only when both the state at the anchor and every event in `(anchor, anchor+step_ns]` prove idleness (`idle_sidecar.py:159-168`).

**State at the anchor.** It must be:
- registered, not paused and focus-observed;
- free of unresolved snapshot VKs;
- relative;
- holding no key and no mouse button.

Unmapped and unsupported keys count as held keys, because the key set holds every physical key regardless of action binding.

**Events in the interval.** Each of these makes the row active:
- any key event (make, break or autorepeat);
- any mouse packet with nonzero dx or dy, button flags or either wheel axis, or that is non-relative (`human_demos._control_affecting`).

Each packet is checked on its own, so opposing motion that nets to zero still counts as motion.

**Unknown instead of false.** Each of these makes the row unknown rather than false:
- focus, pause, `raw_input_status` or gap events;
- mouse flags other than NOCOALESCE;
- a gap-free=false row;
- a frame-continuity gap, duplicate or backwards CTS;
- an interval outside the logger's start and end.

**Fail-closed refusals.** Injected (device 0) or multi-device control-affecting packets, and malformed records, refuse the whole export.

**Weights.** Unknown never enters a run and keeps weight 1.0. A run requires `null==1`, an accepted normal gap-free row, the same `run` and `segment`, contiguous anchors and the same focus generation (`run_lengths`, `:232-253`). Runs are fixed before any windowing. I found no path by which unknown counts as idle.

### 2. k=30 and 0.1 are fixed

- They are module constants (`:26`), with no CLI option, argument or data-dependent path.
- Nothing reads the null rates to choose either value.
- `load_weights` refuses any manifest whose `k` or `idle_weight` differs (`:382-383`).
- Every sidecar header and the manifest say 30 and 0.1.

### 3. Only the five train sessions were read

- The allowlist `TABLE_HASHES` (`:19-25`) is exactly §2's five train ids, with §2's table hashes.
- `export` iterates only those ids, and the logger path is `logger_root / sid`.
- `authorize` requires, for every id before any logger opens:
  - exactly one registry entry;
  - `split == "train"` and an independent `session_group`;
  - no denylist match on id, media hash or media path.
- My own regex scan of `manifest.json` finds exactly those five ids and no other session id.
- In the pinned registry, all five are `train`. None is in denylist v2.
- The registry's non-train ids (1 val, 3 test, 4 gate2) and §2's two dev ids never appear.

**Limitation:** this establishes what the code *can* read and what the outputs name. It is not an OS access audit of what the producer actually opened. That part rests on the handback.

### 4. Spot-check: done, and extended to all five sessions

I wrote my own recomputation (`recompute_idle.py` in my scratchpad). It does not import `idle_sidecar` or `human_demos`. It streams each session's `inputs.jsonl` and the frozen table, and it re-derives nulls, maximal runs and weights under my own reading of §6. It is stricter than the producer on absolute packets: those stay unknown until the next focus event.

Result: the `null` field, `idle_run_length` and `weight` were compared on all 148,963 rows.

| Session | Rows | null agree | run length agree | weight agree | Runs ≥30 |
|---|---:|---:|---:|---:|---|
| 051828 (requested spot-check) | 12,558 | all | all | all | 30, 45, 46 |
| 025230 | 6,667 | all but 2 | all | all | none |
| 232304 | 15,841 | all | all | all | none |
| 200129 | 48,195 | all | all | all | 33, 33, 54, 109 |
| 021320 | 65,702 | all | all | all | 32, 37, 52, 88, 194 |

The two 025230 disagreements are rows 1 and 2, where the producer says `null` and I say `false`. Both have weight 1, so this is not an error. Those rows overlap the known duplicate-CTS frame at packet 120 (CTS `372626517370863`, backwards in PTS order). The producer's frame-continuity check correctly makes them unknown; I did not check frames. They are `rejected` rows in any case.

The public reader, run with an independently computed manifest hash, returns exactly 0.1 or 1.0 for every row: 121 / 229 / 0 / 403 / 0 weighted rows (753 in total), matching the handback. `uv run pytest tests/test_idle_sidecar.py -q` gives **65 passed**; the tests are synthetic and open no corpus.

## Findings (none blocking)

1. **Real data barely exercises the boundary logic. Info.**
   - Each session has 1 `raw_input_status` event and 2–4 focus events. There are no pause, gap or absolute-mouse events and no injected packets.
   - Focus, pause, gap, absolute-mouse and generation handling are therefore proven only by the synthetic tests (`test_idle_sidecar.py:62-160`), which do cover each case.
   - My recomputation is independent code but a shared reading of §6. A misreading we both share would not show up here.

2. **Relative-input validity comes back sooner than it could. Low; allowed by the contract.**
   - After an absolute or flagged packet, `relative` comes back on the next clean relative packet, not the next focus event (`:143-155`).
   - The step containing the bad packet, and any steps before the next clean packet, stay unknown. This satisfies "no absolute mouse event" in the interval.
   - The stricter rule makes no difference on this cohort, which has no such packets.

3. **Motion exactly at the anchor can go uncounted. Nit.**
   - A motion packet with `t_ns == anchor` belongs to the previous row's interval, which is right-closed. That follows §6's `(anchor, anchor+step]` literally.
   - Where the previous row is not contiguous (after a table gap), that packet falls in no interval, so a run-starting row could still be `true`.
   - This would need a nanosecond-exact coincidence. It cannot join runs across the gap, because continuity requires contiguous anchors.

4. **Handoff notes for r3-impl. Info.**
   - The reader also accepts a table named `<sid>.jsonl`. This is harmless, because the content hash is still enforced.
   - Row masses are pre-window. Amendment 1's exact per-head U_h / E_h / C_h audit over `Batches.windows` (burn-in and overlap included) is still owed by r3-impl and still gates the queue.
   - At row level, C > 0 in three of the five sessions, so N appears active. Only the audit decides that.
   - The consumer must keep §6's denominator as `max(1, sum(mask))`. That is outside this producer.

## Disposition

**LAND:** the lead can freeze manifest SHA256 `03bbf9836dc06824d2380bcaa9c096ea2b6f8cea46758c18316bb70b7eb016ba` as reviewed.

This review does not accept the Amendment 1 scored-window audit, the N disposition or any launch.
