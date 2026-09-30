# Independent E1 re-review v5: compatibility-mode retention write semantics, VUH-1319, 2026-09-30

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, reviewer of compat v1–v4, outside the live-loop lane). Read-only; no
game, pad, capture or run data. My filesystem check used a scratch directory only.

Reviewed against `review-inputs.json` sha256 `618c906e52a8a78f7d3f53436c132f0f806755386f2abf1e2543832f10c50a8e`.
- All pins match.
- Only `agent/camera_compat.py` and `tests/test_camera_compat.py` differ from v4. The v4 packet and receipt
  (`e4b025f8…41f2`) are intact, and v4's `after/` snapshot equals the v4 pin.
- My own diff against the v4 bytes: `import tempfile`, the `NativeRetention` docstring, and `NativeRetention.__call__`
  (`camera_compat.py:43-54`). Nothing on the input side changed: `command()`, `pulse()`, `retain()`, the caps, the
  guards and the parser are all byte-identical to v4.

## Verdict: **LAND**

### E1: fixed

- `__call__` now creates a unique temporary file in the **same directory** (`mkstemp(prefix='.{name}-', suffix='.png',
  dir=out)`) and encodes into it. It then calls `os.replace(temp, dest)`, which swaps the directory entry, so a name that
  was a hard link to an earlier PNG now points at a new inode and the earlier file keeps its bytes.
- `finally: temporary.unlink(missing_ok=True)` removes the temporary file after any failure: `imwrite` returning False,
  an exception, or a failed replace.
- An aliased name that is re-retained now leaves the earlier evidence untouched. A retention failure still propagates,
  so the existing release-and-record path runs.
- **Independent reproduction.** My v4 scratch script, run against the real v5 `NativeRetention`:
  1. write `pulse-0-response`;
  2. alias it as `pulse-1-before`;
  3. re-retain `pulse-1-before` with a new frame.

  The response hash stays `de24fbc9…`, and the reused name gets the new frame, `87623871…`. No `.`-prefixed temporary
  file remains. Under v4 both names had changed to the new frame.
- **Owner tests.** New tests cover:
  - re-retaining a hard-linked name, with both a real OpenCV codec and a fake one;
  - failed re-retains (encode returns False, encode raises, replace fails), each keeping the linked evidence and
    removing the temporary file;
  - the actual `pulse()` early deadband return that reuses an index without corrupting the response.

  The docstring and README claim is corrected: it no longer says "immutable inode".

### Unchanged from v4 (evidence reused)

The input set, the caps, the guards, alias selection and the fresh proof before every send are unchanged. The eight
affected suites in the live venv give **518 passed**.

## Conditions

This covers code only. The live run still needs the lead's grant, the on-PC hash preflight, a fresh placement
preflight, an explicit profile and settings declaration, and hands-off operation. The coarse-pitch gains remain
hypotheses to be measured by the run.
