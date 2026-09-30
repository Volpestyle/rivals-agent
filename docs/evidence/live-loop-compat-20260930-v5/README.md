# Compatibility v5: E1 evidence-integrity delta over v4

Owner live-loop, VUH-1319. Offline fix produced for the same live-review reviewer,
E1 only. No LAND/RUN authority, commit or live input. v4 and all earlier packets
are immutable. The existing v4 input/caps/guards review is reused unchanged.

## E1 and corrected retention contract

The v4 reviewer reproduced corruption when pulse() returned early after its fresh
post-retention observation was already inside the deadband. No pulse was sent and
the index did not advance, so a later retain reused pulse-{n}-before.png. That
filename could be hard-linked to the previous response PNG. Writing through it
with cv2.imwrite rewrote the shared inode and changed the earlier response image.

**Correction to the v4 README and NativeRetention docstring:** a hard-linked inode
is not intrinsically immutable. The v4 claim of an "immutable inode" was false.
Aliases share an inode, and a particular filename can be replaced with a new
inode. Evidence preservation depends on every writer using that replacement
operation, rather than opening an existing filename for in-place writing.
The frozen v4 README remains as historical evidence; this delta corrects its claim.

NativeRetention now creates a unique private temporary .png in the same output
directory, closes the initial tempfile handle, writes the complete PNG there,
and calls os.replace over the destination filename only after imwrite succeeds.
Replacing a before filename swaps that directory entry; earlier hard-linked
response names continue to reference their original bytes. The temporary file
is removed in finally on success or failure. A failed encode or replace propagates
and leaves existing retained destination/source images unchanged. No image write
is performed through an existing destination inode.

Hardlink alias selection, fresh post-retention observation, target identity,
command recomputation, every pulse strength/duration and all input/safety bounds
are unchanged. NativeRetention.alias still refuses an existing destination or
missing source instead of guessing a fallback. The only runtime delta is the
NativeRetention docstring/write method plus the tempfile import.

## Regression evidence

87 tests in tests/test_camera_compat.py pass, including six new cases:

- Fake codec and real OpenCV/NumPy: write the original response, alias the before
  name, re-retain that same before name with a different frame. The response's
  exact bytes remain unchanged, the names no longer share an inode, and the new
  before file contains the new frame. Real PNGs decode to the intended arrays.
- Encoder false return, encoder exception and replace exception: partial temporary
  bytes cannot change either existing hardlink, and no temporary PNG remains.
- Reach the actual pulse() early deadband return: the pulse index stays at 1,
  no input is sent, then a later observation re-retains pulse-1-before. The earlier
  pulse-0-response remains byte-identical while the before filename changes.

Ruff passes. Tests use scratch paths/fake capture only; no live game, pad, capture,
OBS decode, training or run-02 frame access was needed. No unrelated files were
edited. v4's 512 affected-suite review and accepted input-side evidence are reused;
there is no new convergence claim, benchmark or simulation.

## Freeze and handoff

review-inputs.json pins the exact current runtime/dependencies, v4 preimages,
v5 snapshots, delta.diff, this note and test/lint outputs; bytecode is excluded.
The original v4 freeze/receipt/review hashes are carried as prior evidence.
Lead w2:p1J routes re-review E1 only to live-review w2:p3E and owns VUH-1319
reconciliation: v4 FIX, v5 produced, next E1-only acceptance and then any separately
authorized landing/sitting. This packet is not a live grant.
