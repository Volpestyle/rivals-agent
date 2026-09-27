LAND WITH FIXES

# Review: live range_bc harness (VUH-1384), binds-review (Opus 5.5), 2026-09-26

Read-only, independent review of live-input code. I did not import vgamepad, send input, open capture or run any real checkpoint.

## Inputs

| File | SHA256 |
|---|---|
| `HANDBACK.md` | `4f57b199…` |
| `agent/live_range_bc.py` | `3caf70ce…2013` |
| `scripts/run_range_bc_live.py` | `4e13e491…477a` |
| `tests/test_live_range_bc.py` | `afdb4367…6cc6d` |

- All three source files match the handback's table. They are new and untracked; no existing file was edited.
- I ran `pytest tests/test_live_range_bc.py tests/test_live_pad.py` **read-only** (`--no-sync`) in the author's private env, which contains torch and cv2 but no vgamepad: **44 passed**.

**Verdict.** The safety design is sound; nothing here is a safety blocker. The fixes below concern whether a sitting would measure the policy or the harness. Fix 1 should land before any sitting.

## Brief items

**Single input path: holds.**
- The only non-neutral door is `Live.send_guarded`, with fresh range proof at commit and again at the actuator. The real-clock lease is capped to the 1/30 s release time and to the episode scope. Neutral-on-close is unchanged.
- The pad state comes only from `executor.pad_state`, and hence `pad_bindings`. No `press_button`, vgamepad or raw report call exists in the harness.
- The default CLI mode only prepares. The test replaces `Live` with a function that fails if called.

**Hard guards: hold.**
- Duration is capped at 600 s. It is enforced by an independent 10 ms monitor thread that calls `live.close()` (which permanently refuses writes), by `scope_not_after=end`, and by the Live guard's `attach_deadline`.
- Keypress uses `GetAsyncKeyState` over VK 8–254, excluding gamepad VKs, and is focus-independent. The keyboard must be released before the pad attaches.
- Focus loss is caught by `foreground_pid_guard`, both in the monitor and inside the Live guard.
- HUD loss is checked on every loop observation, on a fresh proof after inference, and by Live itself.
- An X in any decoded pad raises, and the run then closes neutral.
- Masks must equal `vocab.live_mask(counts, swing_mode)` exactly. `decode` also refuses any enabled action outside `PAD_SENDABLE`. `vocab.PREREGISTERED_UNSENDABLE` now keeps `goh_targeting` (X), ultimate, melee and team_up unsendable, so the X ban is a second barrier.

**Preprocessing parity: holds for colour and geometry.**
- The harness runs `cache.GRAPH` with `select=null` on raw BGR, which is the training transform.
- `CONVERT` specifies `in_range=tv`/BT.709 for OBS's YUV. I checked that it leaves RGB input untouched: a full 0–255 BGR ramp through FFmpeg 8.0.1 is identical after the channel swap, with zero difference. Desktop RGB therefore lands on the same full-range scale as the decoded training video.
- The manifest records the FFmpeg version and graph.
- The remaining differences are disclosed: chroma subsampling and HEVC compression in training frames; the pad HUD versus the M&K HUD.

**Checkpoint loader: holds.**
- Bytes are hashed, then loaded with `torch.load(weights_only=True)` from the same bytes.
- It checks domain, vocabulary and camera reps.
- Legacy checkpoints must have the cache dimensions. CM3 checkpoints must have `Config(arm, seed)` equality and `purpose == "fit"`, so smoke checkpoints are refused.
- It uses strict `load_state_dict`, rejects nonfinite weights, and requires DINO assets for H/W.

**Decode thresholds.** They are scalar or checkpoint-pinned per action, applied through `executor.decode_step` for all three channels. The manifest records them per action, along with the mask, settings, code aggregate, checkpoint metadata and input-file hashes.

**Scorecard: honest.**
- Presses are counted as *commands*, camera as *command estimates*, and KOs as feed appearances.
- It uses the range `is_killfeed` reader, not the failed Gate 2 reader, and in the range every line is ours.
- The initial visible line is excluded, and unknown frames count neither way.
- The supervised duration ends at the safety stop.

**Supervised sitting required.**
- `--live` requires Windows, a review-receipt file, a sitting ID and the game PID. The receipt is retained by hash only (see fix 5).

## Fixes

**1. Synchronous full-resolution PNG retention makes a sitting measure the harness, not the policy. Required before any sitting.**
- The loop writes a native lossless PNG on **every** observation, plus a send-proof PNG after each send, on the control thread.
- Measured on a native 2560×1440 game frame (JPEG-sourced, so real frames are likely larger): **144 ms and 4.6 MB per PNG** at compression level 1.
- The per-observation FFmpeg subprocess adds about **49 ms**, measured on the same frame.
- A result therefore typically waits behind a PNG write before its proof and send, so prediction age often approaches or exceeds the 0.25 s cap and the run stops with `prediction_expired`.
- Each send lasts only 1/30 s, so the duty cycle would be roughly 10%.
- Because `captured - previous_at >= STEP_S`, almost every request feeds **neutral history**, and the recurrent state steps at about 3 Hz instead of training's 30 Hz. The episode would mostly show latency-chopped 33 ms pulses and a history the policy never trained on.
- Disk runs at about 30 MB/s (about 2 GB per minute), with CPU contention on the game PC.
- **Fix:** move retention off the control path: a background writer with a bounded queue that records dropped frames. Or retain policy and send-proof frames natively plus a throttled or downscaled guard trace. Measure the end-to-end cycle before scheduling a sitting.
- Also time CPU DINO for H/W. It is unmeasured and may alone exceed the 0.25 s cap.

**2. `settle_s=0` skips pad enumeration. Medium; affects validity, not safety.**
- The CLI builds `Live(..., settle_s=0)`. The live-game skill records that the first input after a pad connects is swallowed by the device switch, even 4 s later, and the "Switching Devices" banner can obscure the HUD.
- The first policy commands would then be silently dropped while the harness records them as sent, desynchronising the history.
- Settling is neutral and watchdog-covered, so it is safe to wait.
- **Fix:** use the default 3 s settle, or longer, and record which initial interval is excluded from the scorecard.

**3. Out-of-distribution inputs are not refused. Low–medium.**
- **(a) Regime bit.** `cooldowns: "off"` sets `regime=1`. Legacy checkpoints record `meta.regimes` (usually `["normal"]`), and CM3 trains normal only. Refuse `off` unless the checkpoint's training regimes include `no_ability_cooldown`. Otherwise the bit is either unseen (`regime_bit=True`) or the policy runs in a regime it never trained on.
- **(b) Legacy HUD.** Legacy `hud=True` checkpoints read HUD crops from the M&K HUD fractions (`ABILITY_ROW`, `WEBS_BOX_MK`), which do not show the pad HUD layout. Refuse them, or require an explicit acknowledgement recorded in the manifest.

**4. Scorecard additions. Low.**
- Report the duty cycle: sends, total commanded seconds, and the neutral-gap distribution.
- Report how many presses were re-triggered by gaps, where a held action is re-pressed because the lease lapsed. Without that, commanded presses per minute are inflated by harness latency.
- Optionally read the range scoreboard's exact KO tally at start and end through the existing guarded `Live.scoreboard()`, instead of relying only on feed appearances.

**5. Bind the receipt. Low.** `--live` only checks that the receipt file exists. Require the receipt, as JSON, to list the three reviewed file hashes, and have the CLI compare them with the running bytes. That stops a stale receipt covering changed code.

## Not established

Nothing here establishes any of the following:
- real model latency;
- DINO runtime;
- sustained cadence;
- keypress-poll behaviour on the game desktop;
- camera tracking under the stale or unmeasured maps (`--camera-disabled` is the only honest mode until the maps are accepted);
- any policy performance.

## Disposition

**LAND WITH FIXES.**
- Safety holds.
- Fix 1, and ideally fix 2, must land and be timed before a supervised sitting.
- Fixes 3–5 are recommended.
- The owner and lead retain scheduling; this review authorises no sitting.

## Delta re-check, 2026-09-26: LAND

**Inputs.** Fixes hand-back `fixes/HANDBACK.md` is `4cc42531…`. The working-tree bytes match its pins:

| File | SHA256 |
|---|---|
| `agent/live_range_bc.py` | `d4c109e7…aa46` |
| `scripts/run_range_bc_live.py` | `8132096e…aedc` |
| `tests/test_live_range_bc.py` | `4e621bde…904f` |

I diffed these against the original reviewed `snapshot/`. Every hunk maps to fixes 1–5, plus one stop-reason classification for a `RangeLost` at or after the deadline, which is now reported as `duration`.

**Tests.** Read-only (`--no-sync`) in the author's env, which has no vgamepad: **58 passed**.

**250 ms cap untouched.** The `run(max_prediction_age=.25)` default, the CLI `--max-prediction-age` default of 0.25 and its bound of 1 s or less are all unchanged. The expiry check still breaks before any proof or send.

**#1 Retention off the control path: closed.**
- The control thread only copies the frame and does a non-blocking enqueue into a 2-frame queue with one frame in flight. A full queue drops the frame and counts it by role.
- A single writer thread owns PNG encoding, disk writes and its own `frames.jsonl`.
- The guard trace is throttled to 1 Hz.
- Drain happens only after `live.close()`, bounded at 2 s. Writer errors surface on the next enqueue, which then stops and closes the run.
- **My rerun** of `measure_synthetic.py` (native 2560×1440 noise, real FFmpeg graph, real CPU architectures, fake pad, synthetic capture, output in my scratchpad):
  - legacy no-HUD: sent-age p50 **79 ms**, p95 **91 ms**, duty 37%;
  - CM3 I: p50 82 ms, p95 91 ms;
  - CM3 H/W: first observed age **379 and 377 ms** (DINO about 148 ms per view), so `prediction_expired` with **0 sends**.
- This reproduces the hand-back within noise. The trace is now explicitly sampled: most send-proof frames were dropped and counted. That is honest, not complete, retention.

**#2 Settle: closed.** The settle defaults to 3 s and is bounded to 3–30 s. Pad enumeration is neutral and watchdog-covered. It is recorded as an excluded interval with `commands_sent: false`, and scoring starts after it. The Live guard deadline covers settle plus duration and is re-armed for the episode.

**#3 Out-of-distribution inputs: closed.** Refused before Live opens:
- CM3 with anything other than normal cooldowns;
- legacy with `config.hud` not False;
- legacy whose `meta.regimes` lacks the requested regime (missing metadata refuses).

The manifest records the validated distribution.

**#4 Scorecard: closed.** It now reports:
- commanded seconds and duty cycle;
- the neutral-gap distribution (count, total, min, p50, p95, max), with neutral time after lease expiry accounted;
- observed and sent prediction-age distributions;
- per-action gap re-triggers (previously held, lease lapsed, now held and pressed), with presses shown both excluding and including re-triggers.

The synthetic legacy case shows 35 raw commanded presses against 1 after removing re-triggers, which is exactly why this matters.

**#5 Receipt bound to running bytes: closed.**
- `range-bc-live-review-v1` must pin exactly the three files.
- Each pin must equal both the import-time `LOADED_HASHES` snapshot and the current file bytes.
- This is checked at startup and again after model and dependency loading, just before `Live` opens. A receipt changed during preparation refuses.
- The old prose review cannot satisfy it.

**Notes (not blocking):**
- **What the receipt does not cover.** It binds only these three files. Changes to `agent/controller.py` (Live), `executor.py`, `vocab.py` or `pad_bindings.py` do not invalidate it. The manifest's `code` aggregate records them, and they carry their own review and freeze obligations.
- **Duty cycle.** At about 37% duty with a median gap of about 50 ms, holds are still chopped. A sitting of legacy or I checkpoints observes a degraded policy.
- **H/W on CPU.** H and W cannot act on this CPU path. That is correct behaviour, not a bug. Running them needs a faster inference path under a separately reviewed change, never a relaxed cap.
- **Camera.** It must stay explicitly disabled until the maps are accepted.

**Receipt for exactly these reviewed bytes.** The lead may save this as the `--review-receipt` JSON. It authorises code identity only; it does not schedule or approve a sitting.

```json
{
  "format": "range-bc-live-review-v1",
  "files": {
    "agent/live_range_bc.py": "d4c109e7c7c503728df2ea82d021154f40a90b05a54bd37bdae64be41b2baa46",
    "scripts/run_range_bc_live.py": "8132096ee37ac82bc0c834a29b4a5fce55d6ad543a85d4e15c2176ec9bd9aedc",
    "tests/test_live_range_bc.py": "4e621bde77f40a694a3acf37b30b91b1d17ea670a2af4df42ec0306a3b59904f"
  }
}
```
