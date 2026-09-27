# live-harness handback — VUH-1384

To: pad-binds (accountable Live owner). Cc: herdr-lead.

Delivered code and synthetic verification only. **NO live runs, desktop input,
real checkpoint inference, corpus reads, training, GPU work or commits.** This
packet is ready for binds-review (Opus); it is not independent acceptance or
permission for a sitting. Pad-binds and the lead retain scheduling authority.

Brief verified as SHA-256
`cedf27d6a5b89f2d6612a6cc768a917033e11c47f2f8518c51c02e5d30527881`.
Checkout HEAD at handback: `107970b4aef9676f9cb6ccc0ebad6dd49a00be88`.

## Owned files and frozen hashes

Only these three repository files were created. No existing repository file was
edited. `snapshot/` holds copies of these exact bytes; `source-hashes.json` holds
the same pins. Other lanes' changing files were left alone; compare
`before-status.txt` and `after-status.txt` for the shared-checkout inventory.

| File | SHA-256 |
|---|---|
| agent/live_range_bc.py | 3caf70ce18097d6b31d65c640de9f7950aa0f0882c020b616ccbace467602013 |
| scripts/run_range_bc_live.py | 4e13e491c70abaad4cd39e120ae9495b3883145dc30ea9b2cad13b99c3c4477a |
| tests/test_live_range_bc.py | afdb4367a14ea16261a76a2b6f2843f926decd496f754aa616c52a9ad969cc6d |

## Delivered behavior

- Checkpoint bytes are hashed before safe CPU deserialization. Legacy v2 and CM3
  I/H/W schemas, domain, vocabulary, model state and dimensions are checked;
  CM3 smoke checkpoints and nonfinite weights are refused. H/W use local pinned
  `FrozenDino` plus the existing `extract_views` preprocessing; no downloads.
- Native BGR capture uses the exact `cache.GRAPH` in FFmpeg. RGB cache results
  feed the legacy/I encoders directly, or CM3's existing feature preprocessing.
- Scalar `--threshold` or checkpoint-pinned `--thresholds-json` supports the
  decoder audit's per-action threshold (shared across hold/press/release).
  Each action is decoded through `executor.decode_step`; camera uses the median,
  executor saturation and `executor.pad_state`. Successful action history feeds
  the next inference; a neutral gap feeds neutral. First history is unknown.
- The support artifact is checkpoint-pinned. Its counts and swing mode must
  reproduce `vocab.live_mask` exactly. Current preregistered unsendable actions
  remain masked, and an independent final check rejects every physical X report.
- `Live.send_guarded` is the only non-neutral input door. Fresh range proof,
  its whitelist, real-clock lease and neutral-on-close remain in force. The
  harness also checks HUD loss on neutral steps. Independent key/focus/deadline
  monitoring closes Live even when inference or capture stalls. Each decision
  authorizes at most 1/30 second of input; late predictions stop the episode.
- Run directory creation refuses overwrite. Manifest includes checkpoint hash,
  code file hashes and aggregate, thresholds, mask, settings, graph, tool versions,
  calibration or explicit camera-disabled mode, review-file hash and sitting ID.
  Every observed policy/guard/send-proof frame is retained as native lossless PNG,
  with acquisition timestamp, dimensions and hash. Events record decoded requests,
  histories, proof times, sends and release deadlines; result records stop reason.
- Scorecard gives commanded action presses and presses/minute, calibrated command
  camera deg/s, command idle seconds, and deduplicated range kill-feed appearances
  and appearances/minute. Initial visible feed is excluded; unknown stays unknown.
  Supervised duration ends at the safety stop, not a delayed capture return.

## Verification

Private environment:
`C:/Users/volpe/AppData/Local/Temp/rivals-live-harness-env`.
Created through `uv sync --locked --group execution --group perception`; shared
`.venv` was not synchronized or modified by this lane. Torch CPU only.

Final command (with UV_PROJECT_ENVIRONMENT pointing at that private environment):

```text
uv run --no-sync pytest tests/test_live_range_bc.py tests/test_live_pad.py -q
44 passed in 6.14s
uvx --offline ruff check agent/live_range_bc.py scripts/run_range_bc_live.py tests/test_live_range_bc.py
All checks passed!
```

Raw final outputs: `pytest-final.txt`, `ruff-final.txt`. CLI `--help` also exited 0.
An earlier command named a nonexistent `tests/test_range_bc_executor.py`; pytest
exited 1 without collecting. The corrected final command above passed.

The tests use the actual Live class with a fake pad and synthetic capture,
including duration, keypress, focus loss, HUD loss, expired inference, stalled
inference, blocked capture and disk failure after a successful send. They also
test forbidden X output, support masks, audit thresholds, camera sign/saturation,
feedback/cadence, scorecard unknowns/deduplication and refusal to overwrite.

Synthetic legacy and all three CM3 checkpoint types were saved, reloaded with
identical weights, and forwarded on CPU. H/W use a synthetic backbone in this
test; the real pinned DINO assets have **not** been loaded or timed here.
A native synthetic colour texture transformed through the new BGR path was
byte-identical in all three streams to `cache._decode` of its lossless PNG.
Native retention was decoded and shown pixel-identical. CLI preparation was
tested with Live replaced by a function that fails if called; no pad was opened.

## Inputs for preparation and later review

Default CLI mode prepares only; it does not open capture or a pad:

```text
uv run --no-sync python scripts/run_range_bc_live.py --checkpoint CHECKPOINT.pt --checkpoint-sha256 HASH --support-json support.json --settings-json settings.json --output NEW_DIRECTORY --threshold 0.5 --camera-disabled
```

Populate `support.json` from the checkpoint's existing training report, without
reopening source data: `checkpoint_sha256`, `press` (nonnegative integer list in
`vocab.NAMES` order), `swing_mode`, and `live_mask` (exact vocab-derived Boolean
list). The pin binds these supplied statistics to the named checkpoint; it is
not independent authentication that the author copied the correct report.

`settings.json` requires `binding_profile: james-alt-spiderman-20260926`,
`swing_mode: {automatic_swing: false, hold_to_swing: true}`, explicit `cooldowns`
(`normal` or `off`) and `patch`. Without `--camera-disabled`, it additionally
requires `calibration` with `evidence`, `yaw_map`, `pitch_map`, `yaw_deadzone` and
`pitch_deadzone`. Maps must span [0,1] stick and contain increasing measured
rates. **No accepted current maps are claimed or supplied.** The sitting's
touch tests already occurred; this handback does not request their repetition.

`--thresholds-json` accepts the decoder artifact's `checkpoint_sha256` and
`actions: {ACTION: {threshold: NUMBER}}` instead of a scalar. H/W additionally
require `--dino-assets` and `--dino-config-sha256`; their pinned dependencies/assets
must already be installed. No automatic model fetch is performed.

Live mode adds `--live`, `--review-receipt`, `--sitting`, `--game-pid`. The CLI
checks receipt presence and retains its hash; it does not interpret approval
text or independently verify coverage. The owner must obtain binds-review on
these exact bytes and schedule the supervised sitting before using it. Capture
and pad dependencies and the desktop session are needed only for live mode.

## Limitations and next consumer

- No gameplay, hardware key polling, real model latency, DINO runtime or camera
  tracking has been validated. The policy graph's transform parity does not
  establish equivalence between desktop pixels and OBS encoding, or the pad HUD
  and the M&K HUD used by legacy HUD-enabled models.
- FFmpeg currently runs once per observation, and PNG writing is synchronous.
  Both costs count toward prediction age. Inference requests are capped at 30 Hz;
  slower processing yields neutral gaps and may end with `prediction_expired`.
  This does not establish sustained 30 Hz control or training-rate recurrence.
  Holds can be interrupted when their one-step leases expire; no stale prediction
  is repeated to conceal slow inference. Live timing/duty cycle must be measured.
- KOs are observed feed appearances, not scoreboard-exact kills. Simultaneous or
  overlapping feed lines can be missed. Camera totals are command estimates,
  not visually measured rotation; presses are not confirmed casts.
- Hard input release uses Live's existing watchdog resolution. If capture or disk
  I/O never returns, the process can remain blocked after the independent monitor
  closes the pad; it cannot send again. `loop_returned` separates that delay from
  the supervised scorecard denominator.
- Direct workspace Linear tools were unavailable. No substitute connector or
  external issue write was used; the owner/lead can attach this result to VUH-1384.

Next: pad-binds sends this frozen delta to binds-review (Opus), verifies findings,
and hands the accepted artifact to the lead for a separately scheduled sitting.
