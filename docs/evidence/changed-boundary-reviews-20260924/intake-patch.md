# intake-patch: the intake records the build each recording ran on (patch-equivalence-design.md item 3)

**Result.**
- `assemble_session.py` no longer carries a `PATCH` constant. Each session's build is derived from the Steam evidence its
  provenance step read at intake, and it becomes:
  - the review's `provenance.game_patch.value`, with that evidence cited and the derivation attached;
  - through `write_steps`, which derives `patch` from the review, the step header's `patch`.
- The assembly refuses before writing anything when the build cannot be read.
- The header contract is unchanged: `patch` is the real build string.
- **Tests:** the intake suite has **49 passed** (36 before, 13 new). The full stdlib suite has **1954 passed, 70 skipped**;
  it also runs the fit and IDM lanes' uncommitted items 2 and 4.
- **Checked against the real Steam files on this PC** (read-only):
  - all four of tonight's takes derive **`1.1.3892207/build25501035`**;
  - 205528 (09-23) is **refused** from the current install, as designed. Its build, 1.1.3870120/build25364676, lives in
    its own intake record, and admitted sessions are not re-assembled.

## The rule (`agent/human_intake.py`, `recorded_build`)

The installed build (appmanifest `buildid`, with the version string from the game's `version.json`) is taken as the
recording's build only when all of these hold:
1. Steam last updated the game **before the recording started** (appmanifest `LastUpdated`, epoch UTC).
2. **No update step falls inside the recording** in the content log (`update started`, `starting commit` or
   `finished update`).
3. **No installing step comes after the start** (`starting commit`, `finished update`). A download-only `update started`
   afterwards is allowed; it changes no installed files.
4. **`version.json` was written by that same update:** its mtime is within 1 h before to 60 s after `LastUpdated`. On
   09-17 it was 7 s before, on 09-24 21 s before.
5. **The log agrees with the manifest:** the content log's last `finished update … (BuildID N)` before the recording names
   the installed build. Content-log lines are local time; the PC's offset at the recording is recorded with the evidence.

It never guesses a build that is no longer installed. Once a later update is installed, a recording's build can come only
from evidence recorded before that update.

**Refusals.** Any failure of the rules above, and an unreadable appmanifest (`buildid`/`LastUpdated`), `version.json`
(version/changelist) or `version.json` mtime.

## Changes

- **`agent/human_intake.py`** (+104 lines): `steam_build_evidence`, `recorded_build` and `_utc`.
  - `steam_build_evidence` parses the raw text of the three Steam files into the evidence record.
  - The logic sits in the reviewed module, so that the provenance step and the assembly share one derivation and it is
    unit-tested.
  - New imports: `re`, `datetime`. Nothing else in the module changed.
- **`data/human/sessions/intake_session.py`** (provenance step):
  - hashes and parses each Steam file from the same bytes;
  - records the new fields `build.appmanifest` {path, sha256}, `build.evidence` and `build.recorded` (the derived build, or
    `{value: null, refused}`).
  - Existing fields are kept.
  - **The hard-coded note is gone.** It said "no app update line after the 2026-09-17 install of build 25364676", which
    would have been false for tonight's takes. The note now says how `recorded` is derived.
- **`data/human/sessions/assemble_session.py`:**
  - `PATCH` is removed and `session_patch(d, meta, hi)` added. It re-derives the build from `provenance.json`'s `evidence`.
  - It refuses when the evidence is missing (a provenance record made before today) or does not settle the build.
  - It also refuses when the re-derivation differs from the `recorded` value.
  - It is called before step 0, so a refusal writes nothing. `game_patch` = {value, source, evidence: provenance.json,
    derivation}; `write_steps(patch=…)` gets the same value.
- **`tests/test_human_intake.py`** (+118 lines, 13 tests). They use this PC's real Steam lines and values (content log,
  appmanifest `LastUpdated` 1790248531, the `version.json` versions and mtimes):
  - a session on the new build records `1.1.3892207/build25501035`, with the content log's finished update and
    `LastUpdated` agreeing;
  - the old build still records `1.1.3870120/build25364676`;
  - a download after the recording leaves the build readable;
  - **nine refusal cases:**
    - an old take read from the new install;
    - no appmanifest `buildid`;
    - unreadable `version.json`;
    - an inconsistent changelist;
    - `version.json` from another install;
    - unknown mtime;
    - an update step during the recording;
    - an install after the recording;
    - a content log naming another build;
  - **the assembly end to end:** `session_patch` on a `provenance.json` gives the new and the old string, and refuses a
    pre-2026-09-24 record without evidence, an unreadable build, and a record that disagrees with its evidence.

| File | Working tree (CRLF) | Bytes | LF form (the blob git stores) | Bytes |
|---|---|---|---|---|
| `agent/human_intake.py` | `ddb34e383488eab60ee18b0a7a5eb26135a254ebb5d32a0c18fd0d6e7c8b8fb6` | 79,602 | `b0a837ea15c195a05554de32827ceae9d6437b8c73355713f667a310e45087e1` | 78,276 |
| `tests/test_human_intake.py` | `83b933a849fc371358c9cd4fc066e1f8e0f75c0ce4b638f5f9beb6db9f27374b` | 50,123 | `7029032ff54265149a143f29f37dc2fd1d7adfeaf4040499f25af09912cbf944` | 49,280 |
| `data/human/sessions/assemble_session.py` | `27d611250e2e34a27f56134f67a355af69667049cf1756e1e0bd284669214891` | 20,936 | `ca7fd15ac5c87ec7c9275115ea4e76858a175ecdaa46a593af77867fca04acc3` | 20,634 |
| `data/human/sessions/intake_session.py` | `9d373e55176a398dee81e6a7e2f05330de2a08e1e8a9dc3baccf77bb874d3cb1` | 34,792 | `200e9a77abcae5c5d433f4d20039e321ee12479af37145d5fd4d93e658ea841f` | 34,222 |

`ruff` is not installed offline, so the lint rule set was not run. All four files compile, and no `PATCH` name remains.

## For you

- **`hi.load_cohort` (`agent/human_intake.py:907`) still refuses a mixed `game_patch`.**
  - Nothing calls it outside the module; there are no tests and no scripts.
  - The fit reads cohorts through `policy/range_bc/steps.py`. I have not changed it (not in this brief).
  - Either route it through `data/human/patch-equivalence.json` like item 2, or retire it. Your call.
- **Timing risk for tonight's takes.**
  - Their provenance step runs after OBS exits. If Steam installs another update first, `recorded_build` refuses them by
    design.
  - As insurance I copied tonight's Steam files, read at 22:30, into my scratchpad (`…/scratchpad/steam-20260924/`):

    | File | sha256 |
    |---|---|
    | appmanifest | `831d22bc…` |
    | content log | `639add21…` |
    | `version.json` | `a5e39e36…` |

    Each is listed in its `MANIFEST.txt` with mtime.
  - The game exited at 22:06:27 (Steam log "Fully Installed,"), so no update can have run during tonight's takes.
- **Review:** per the design, admission-review checks this with the first new session. `recorded_build` and the
  provenance fields are the boundary.
- **The next intake snapshot** (`archive_code_snapshot.py`) must include this `human_intake.py`. I'll archive it when
  intake starts.

## Arrivals status

- The game exited at 22:06:27.
- `obs64` is still running; the poll reads every 5 minutes, last at 22:26.
- There are no new recordings after 22:01, and no message naming the kinds yet.
- Registration and decode wait for both.
- No commits, no Linear, nothing on the Mac.
