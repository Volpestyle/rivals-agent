# fit-plumbing-2 (VUH-1359, VUH-1346): run 1's parity re-emitted in the current format; derive ok

**The real fit's pre-registration now exists.** Following the lead's decision (option 2), run 1's HUD parity was
re-emitted with `hudparity --rule p2` on run 1's exact 653 sources. It is identical to run 1 in every field except the
added `rule`. derive accepted it and wrote `preregistration.json`, which matches the by-hand table in
`fit-plumbing.md` exactly. The fit's own pre-flight accepts the pair.

No new measurement was made. P2 stays failed on record, the no-HUD arm stays the candidate, and P2′ still waits for
fresh pad stills. No commit, no Linear write, no game input, nothing written on the Mac.

## 1. The re-emission

**Command** (from the repo root; `hudparity.py` not modified):
```
PYTHONPATH=. uv run --group perception python <scratchpad>\plumb-afff279\reemit_run1.py <scratchpad>\plumb-afff279\hud-parity-1-p2.json
```
- **The wrapper** reads `docs/evidence/range-bc-20260923/hud-parity-1.json`'s `sources`, the exact 606 pad and 47 mk
  paths (no fresh globs), and calls
  `hudparity.main(["--rule", "p2", "--pad", *pad, "--mk", *mk, "--out", <out>])`.
- **Printed:** `{"P1": true, "P2": false, "P3": true, "pass": false}`.
- **Environment:** `uv sync` afterwards restored the stdlib-only environment.

**Compared with run 1:**

| Check | Result |
|---|---|
| `sources.pad`, path → sha256 | **equal**, 606 = 606 (path sets, sha256 sets and pairs) |
| `sources.mk`, path → sha256 | **equal**, 47 = 47 |
| `P1` | equal |
| `P3` | equal |
| `P2.quantities` | all **12** entries equal |
| `P2.gated`, `P2.untransformed_baseline`, `P2.pass` | equal (`P2.pass` false) |
| `thresholds`, `measured`, `pad_frames` / `pad_with_hp` / `mk_frames` / `mk_with_hp`, `consequence_if_failed` | equal |
| `pass` | **false** in both |
| Keys only in the re-emission | **`rule`** = `"p2"` |
| Keys only in run 1 | none |

## 2. derive

**Command** (Git Bash, from the repo root):
```
.venv/Scripts/python.exe docs/evidence/fit-readiness-20260923/range_bc_plumbing.py derive --plan <scratchpad>\plumb-afff279\plan.json --runs <scratchpad>\plumb-afff279\runs --hud-parity <scratchpad>\plumb-afff279\hud-parity-1-p2.json --out <scratchpad>\plumb-afff279\preregistration.json
```

**Printed** (exit 0):
```
{"epochs": 13, "weight_decay": 0.0001, "stride": 64, "hud_parity_pass": false}
```

**`preregistration.json`, against the by-hand table in `fit-plumbing.md`: every field matches.**

| Field | derive | By hand |
|---|---|---|
| epochs | 13 | 13 |
| weight_decay | 0.0001 (p3's minimum 1.44085 is not below p1's 1.43104) | 1e-4 |
| stride | 64 (E* > 10) | 64 |
| lag | 0 | 0 |
| seeds | 0, 1, 2 | 0, 1, 2 |
| hud_parity_sha256 | `e9efe999…` (the re-emission) | pending then |
| hud_parity_pass | false | |

**The rest of the file:**
- **source:**
  - plumbing pre-registration `b0ce04df…`;
  - plan `850aeded…`;
  - commit `afff279a3d787d6a3cefc32881d6a28711f0770d`;
  - the 9 report sha256 values, equal to `fit-plumbing.md`'s Bytes table.
- **Derivation fields:**
  - repeatability: "p1 and p2 checkpoints byte-identical";
  - lag minima: 1.42317 (lag 1) and 1.40770 (lag 2);
  - `scaling_reading_a`: `gap_positive_from_half: true`, `gap_rising_from_half: false`;
  - rules (b) and (c) are left to the lead, as pre-registered.

**The fit's own pre-flight accepts this pair.** I called `train.preregistered` and `train.parity_record` at `--scope
fit` with epochs 13, weight decay 1e-4 and stride 64, under `uv run --group execution`, then ran `uv sync`.
- Both calls accepted: parity record `rule p2, pass false, sha256 e9efe999…`.
- Changing epochs to 20, stride to 48 or weight decay to 1e-3 is refused with "… differs from the pre-registration".

## Landing note: the parity file's bytes

`hud-parity-1-p2.json` has CRLF line endings, because `hudparity` writes in text mode on Windows.
- **The pre-registration pins the raw bytes,** `e9efe999…`.
- **Git would store them LF-normalised,** `4ecb5e3e…`.
- **So give the Mac fit this exact file (scp), not a copy from a `git archive`.** Otherwise `parity_record` refuses it
  with "the parity file differs from the pre-registration's hud_parity_sha256".
- `preregistration.json` is LF only, so its two hashes are the same.

## Bytes (sha256)

| File | sha256 (raw bytes) | LF-normalised |
|---|---|---|
| `C:\Users\volpe\AppData\Local\Temp\claude\C--Users-volpe-repos-rivals-agent\ab8f5f2d-5ae0-4946-90a2-07ae87dfb27c\scratchpad\plumb-afff279\hud-parity-1-p2.json` | `e9efe999e4b7f7e9df14f3e311ae5bbf71ab476101af40d07ed5d2ac02c48801` | `4ecb5e3e050c6328fd0e6915b35b26e79c89e8184a2836e622ea67ab84136582` |
| `…\scratchpad\plumb-afff279\preregistration.json` | `e1b2cefb095b65bd64bb78b32596821f0384966151b6127e86660c873eb9c03a` | same |

Also in `…\scratchpad\plumb-afff279\`:
- `reemit_run1.py`, the wrapper;
- `preflight_check.py`, the pre-flight call.
