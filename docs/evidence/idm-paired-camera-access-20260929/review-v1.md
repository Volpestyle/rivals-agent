# Independent boundary review v1: phase-one paired camera access audit, VUH-1353, 2026-09-29

Reviewer: live-review (Claude Opus 5.5, `w2:p3E`, outside the IDM lane). Read-only. I did **not** run `audit.py`, and
I opened no video, ledger or corpus file. The only data bytes I read were those of `data/human/sealed-denylist.v2.json`,
to compute its raw and LF sha256 and whether it contains a CR. I printed neither its contents nor anything else from it.

Reviewed files, matching `SHA256SUMS.json`:
- `audit.py` `81d4aae8…a0f0`
- `README.md` `75ea4346…27b8`
- `.gitattributes` `705fd4d6…da`
- `agent/human_demos.py` `222b346a…a208`, which equals the working tree and is unmodified

## Verdict: **FIX**

The scope is right. The audit has no admission, label export, fit or decode path, and it writes nothing into the repo
or data. But two of its sealed-data checks are weaker than the contract this repo landed today, and one of them can
never fire on this PC. Both fixes are a few lines.

### D1 (blocking): the denylist is authenticated by one read and parsed from another

- `audit.py:33-35` hashes the file (`sha(deny) == DENY`) and then parses a **second** read (`deny.read_text()`). That
  is the hash-then-reparse pattern that the landed denylist-pin hardening (`8b87cfa`, "Require authenticated denylist
  bytes at intake boundaries") removed from every maintained loader.
- The raw-byte hash also differs from the repo's convention. `09e8b9d3…` is the **LF-normalized** pin
  (`steps.DENYLIST_SHA256`).
  - Today the on-disk file has no CR, so its raw and LF hashes coincide and the check passes.
  - A CRLF rewrite by a checkout, stash or restore would make the audit refuse. That fails closed, but for the wrong
    reason.
- The audit also skips the loader's schema and row validation (`schema_version`, a non-empty `sessions` list, a 64-hex
  `media_sha256` per row, and the rules on `allowed_split`/`session_group`).
- **Fix.** Use `agent.human_intake.load_denylist(deny, sha256_pin=DENY)`. It makes one LF-normalized read, hashes and
  parses the same bytes, and validates the rows. Then use its `sessions`.

### D2 (blocking): the path clause of the sealed check can never match on Windows

- `audit.py:40` compares `str(path).casefold()` with `row['media_path'].replace('\\', '/').casefold()`. On Windows,
  `str(Path('C:/Users/volpe/Videos/…'))` renders with **backslashes**, while the right side is forced to forward slashes.
- I reproduced this with the live venv's Python on this PC. For the audit's own live-source path, the clause returns
  "not the same file" whether the denylist stores it with forward or back slashes.
- The session-ID/group clause and the media-hash clause still work, so this is a dead layer of defense, not an open
  hole. The actual file is also hashed and required to equal its pinned `expected`.
- **Fix.** Normalize both sides the same way, for example `p.as_posix().casefold()` on both, or compare resolved `Path`
  objects. Add a small synthetic test (a fake denylist row carrying the source's path, ID or hash, each separately)
  that must refuse, and do it without touching real data.

### Verified (no finding)

1. **Which paths are opened.**
   - Only these are hardcoded: the denylist, the two named videos (hashed only, by streaming), and the live SID's three
     RivalsInput files (`metadata.json`, `inputs.jsonl`, `frames.csv`). The replay's ledger is **not** opened.
   - There are no CLI paths, registry discovery or traversal.
   - `human_demos._event` and `_validate_raw` are pure: no `open`, `read`, `subprocess` or write. Importing the module
     has no side effects.
   - The sealed check runs **before** any source is hashed.
   - Neither source identity (live `20260926T010620-721Z-63684-5` / `2026-09-25 20-06-20`, replay
     `20260926T161008-331Z-116800-2` / `2026-09-26 11-10-08`) matches any sealed item named in the brief: V-C/V-Q
     `-150600-1/2/3`, Gate 2 `19-21-09`/`23-49-58`, `053616`, `153835`/`153812`, `14-51-10`, DayMR/ReqMR.
2. **Read-only.** The only write is `D:/rivals-agent-evidence/idm-paired-camera-development-20260929/access-audit.json`,
   created exclusively (`'x'`), so a rerun refuses rather than overwriting. The repo and `data/` are only read.
3. **No admission, label export or fit.** Input events are parsed in memory. Only counts, state-event payloads (focus,
   pause, raw-input status, marker), logger metadata and hashes are written: no camera or mouse samples, frames, labels,
   registry or checkpoint.
4. **Failures refuse.** Every check is a `require` or an uncaught exception:
   - a changed pin, a sealed match or a video hash mismatch;
   - a logger-identity mismatch or a schema or column mismatch;
   - `_validate_raw` failures, a clock regression, a packet discontinuity;
   - malformed JSON or CSV, or a missing file.

   Nothing is skipped.

### Notes (not blocking)

- **N1.** `read_text()` and `open()` for `metadata.json` and `inputs.jsonl` use the platform default encoding (cp1252
  on this PC). Pass `encoding='utf-8'`, as `human_demos` does, so non-ASCII metadata cannot be misread.
- **N2.** The ledger hashes are trust-on-first-use, as the README states: they become pins at this first reviewed
  access. Record them in the later packet before it runs.

## Re-review scope

Re-review only D1, D2 and the synthetic refusal test. Everything else reuses this review.
