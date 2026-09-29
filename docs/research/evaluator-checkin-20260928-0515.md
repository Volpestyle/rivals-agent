# Outside research check-in, 2026-09-28 05:15 CDT

**Full03 has a real, recoverable epoch-1 checkpoint.** The owner watcher notified
at 05:09:16; its 05:14:30 observation still shows the same app and container,
with no terminal state. Epoch 1 completed 40,866 optimizer steps. The
5,138,491-byte checkpoint (`b34aaef5…`) and complete receipt (`0dd28aa6…`) were
hash-verified and collected on the Mac. The owner reported this to operations;
the [VUH-1353 launch comment](https://linear.app/vuhlp/issue/VUH-1353)
was updated at 05:10:16 CDT. Reuse that receipt; no duplicate review is needed.

This is stronger evidence than an allocated GPU: one full training pass has
completed and its work has survived durable publication and collection. It is
not an accuracy, convergence or transfer result. Unlike full02, a later failure
would leave a completed training checkpoint for recovery or scoring. Continue
the original three-epoch endpoint, then the matched real/zero and baseline
report. Do not select a different endpoint just because it is now collectible.

The first checkpoint was reported about 2 h 12 min after AppCreate. That interval
includes startup, staging and observation delay; it is not training throughput.
The next epoch receipt will distinguish that initial overhead from steady
training time. No timeout intervention follows from the current observation.

No other issue changed in the Rivals project since 04:15, and no new lane,
recording, live-sitting or evidence-directory update was found in the inspected
delta. The last manual bill check remains 02:51; no new settled-cost claim.
The lead already holds the checkpoint milestone and the range-versus-match
interpretation. No advisory wake, new experiment, provider query, paid action,
sealed-data read or schedule change was needed.
