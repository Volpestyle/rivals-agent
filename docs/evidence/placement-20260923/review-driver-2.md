# Re-check: placement driver fixes D1-D3 (review-place-driver.md)

Reviewer `admission-review` (Claude Opus 5.5), 2026-09-23. The re-check is read-only: no pad was opened and
nothing was committed.

- **Bytes:** `scripts/place.py` `8e25f991`, `tests/test_place.py` `4e57bb4a`.
- **Tests:** `tests/test_place.py`: **83 passed**.

## Verdict: D1 and D2 fixed. D3 fixed except one authorization flaw (E1): fix before any live declaration is issued

| Item | Status | Evidence |
|---|---|---|
| **D1** measurement gate | **Fixed** | See below. |
| **D2** replay exit | **Fixed** | See below. |
| **D3** entry and time binding | **Fixed** | See below. |
| **D3** countersigned look | **Fixed, with E1** | See below. |

**D1: the measurement gate.**

- `--measure-pitch`/`--reset-check` call `check_measurement_declaration` before `Live` exists.
- The declaration needs:
  - its kind and its modes;
  - `james_present_recording: true`;
  - the shared `check_entry`.
- `Live(...)` is constructed only after that and `_open_game`.
- There is no other path to `Live`.

**D2: the replay exit.**

- `ok` needs `compared > 0` unless `--allow-none`, and exit 2 means "nothing compared".
- The report carries `method` and `compared_label`/`compared_pose`.
- Labelled decisions check that the label lies within max(0.75 m, 10 % of range) of a feasible pose, and they
  compare against the sim rendered *at the label*. That removes the circularity where labels exist.
- The pose-basis comparison remains, correctly described as planner consistency only.
- It is still one first action from a fresh state, and `method` says so.

**D3: entry and time binding.** The declaration binds:

- the game PID;
- a pinned range-entry record: its sha256 is the binding id, and it repeats the PID and entry time;
- the process start time, within 2 s of the running process. I tested this: PowerShell's `'o'` UTC format
  (7 fractional digits, `Z`) parses correctly in `_utc`.

It also requires `entered ≤ issued < expires`, a window of 1 h or less, and `now` inside that window.

**D3: the countersigned look.** The live gate requires a pinned countersignature file that quotes the
findings' canonical sha256 and every evidence sha256.

## E1 (required): the authorization's mode check is a substring match

`check_entry` accepts the authorization if its text *contains* the binding id and the mode string
(`binding not in auth or mode not in auth`).

**Constructed:** an authorization reading "Lead authorizes measure-pitch for binding `<id>`. No live input is
authorized." **passes `check_entry(d, "live", …)`**, because "live" occurs in the negation. The call is
reproduced in my scratchpad.

The same applies to a measurement file that says "do not run reset-check".

- **Today:** live is still unreachable, because the constants are unmeasured and a countersigned look is
  required. The measurement modes are camera-only.
- **Once the look is done:** a measurement authorization for the same range entry would also authorize live.

**Required:** make the authorization structured JSON, `{kind, binding_id, modes: [...], issued_by,
issued_utc}`.

- Require `binding_id` to equal the entry's, and the mode to be an element of `modes`.
- Add a test with the negated text above.

## Minor

- **A stale comment.** `main` still says "No declaration: these are part of the look…" above the measurement
  branch, which now requires one.
- **Expiry is checked once, at the gate.** A run that is already started continues past `expires_utc`. Runs
  are short (seconds to about 2 min), so this is acceptable. Re-checking `now < expires` in `run_live`'s loop
  would make the window exact.
- **The countersignature and the authorization prove the binding, not the author.** The docstring says so. The
  lead's procedure must keep who writes them outside the driver's lane.

## Still standing

The pre-live conditions C1 and C2 from `review-placement-2.md` still apply:

- **C1:** the pitch-reset accuracy.
- **C2:** liveness per bin.
