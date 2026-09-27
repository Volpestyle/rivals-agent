# d6d56b7 transport/guard delta review — LAND

Independent fit-review (Codex), 2026-09-27. No findings in the requested transport/supervision boundary. The ongoing copy was not inspected through media access or altered.

- Compared relocate_mac.py against the predecessor in `handoff/admission-handoff-20260927/relocate_mac.py`. Changes are exactly the explicit Git SSH/SCP executables/options, fixed -5-only refusal, and MSYS local source path conversion. The six-file selection, immutable metadata copy, pin checks, destination-exists refusal, destination hash comparison and final receipt content remain unchanged.
- Explicit Git transport retains BatchMode, a connection timeout and strict host-key checking, and adds keepalive interval/count. Local SCP filenames are argv elements, not shell strings. Independently evaluated the committed conversion: the current spaced C:/Users/.../2026-09-27 00-20-01.mkv name becomes /c/Users/.../2026-09-27 00-20-01.mkv intact. The producer's actual spaced-path SCP roundtrip/hash test is inherited evidence; no network probe was repeated.
- Independently invoked the committed fixed-session gate with a V-C session and filesystem/process traps: it refuses before either trap. This retry cannot select another session through its CLI.
- The new supervisor uses exactly the accepted 8593ef5 OwnedProcessJob.cs bytes. It owns the worker before execution, checks resources before launch and each polling iteration, monitors descendant working sets, and closes the private job in finally. Live descendants, nonzero exit or missing receipt each prevent success. Prelaunch failures also receive a run record. A minute heartbeat updates the job status; polling cadence includes the time spent in OS/status queries, so this is not a hard real-time one-second response guarantee.
- Independent probes of the committed Check-Resources function refuse one KiB below 4 GiB, allow exactly 4 GiB, and refuse a matching Marvel process. Static inspection confirms the obs64 check and >=2,800,000,000-byte per-process refusal. Prior real Job Object cleanup evidence is reused unchanged.
- The committed removal audit names only `/Users/james/dev/idm-match-data/originals/2026-09-27 00-20-01.mkv`, exact partial size 2,336,501,760 bytes, timestamp and lead authorization. The user's supplied authorization covers that recorded restart/removal. Neither reviewed executable contains removal logic. This review did not repeat or independently observe the deletion.

Committed SHA256 pins (working files match after LF normalization):

- relocate_mac.py: `72fd8f0fb60d13a3f7cce11999843a1dac0a4e949a11e74ed427f45aee1bb81e`
- run_relocation_052001.ps1: `e77b9d8de2fe07371b20cc34580cf97b9db7d75b1c731e16c38a0f5412d75891`
- removal audit: `9da34d8d43b7ab13726ed168e8bbc6cd96665f6fa7ac828f738dfab62085fd31`

No media read/hash/decode, SSH/SCP invocation, process launch/termination, transfer restart, owner-path edit, commit or receipt acceptance. LAND applies to this transport/guard delta; it does not assert that the running relocation has completed or that its future destination receipt verifies.
