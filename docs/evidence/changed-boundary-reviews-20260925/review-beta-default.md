# Review: β-NLL as the IDM's default camera loss (VUH-1353)

Reviewer `fit-review` (Claude Opus 5.5), 2026-09-25. Read-only: no edits, no commits, no Linear, no game, no Mac. The
shared tree was not written to, and the shared `.venv` was not used.

**Reviewed:** scoreboard-fix's uncommitted flip (`idm-beta-default.md`) on main, now at **`a517ec6`**. The hand-back
named `9a39228`; `a517ec6` adds only the pitch-calibration evidence, and the flip's two code files are unchanged between
the two commits.
- `policy/idm/train.py`: LF `f6e0bc27…`, matching the hand-back.
- `tests/test_idm_model.py`: LF `36346b4a…`, matching.
- `docs/lanes/inverse-dynamics.md`: LF **`b3d07d8d…`**, not the hand-back's `7cb26479`. The pitch-calibration
  pre-registration was added afterwards, as `idm-pitch-calibration.md` states.

**Evidence read:** `docs/evidence/idm-beta-nll-20260925/`, all twelve files (hashes at the end).

**How I checked:**
- **Private trees:** `git archive a517ec6` twice into my scratchpad (`bd/base`, `bd/changed`), overlaying the three
  working-tree files on `bd/changed`.
- **My own environments** from `uv.lock` (unchanged): `venv-exec` (dev plus execution, torch 2.14.0+cpu) and
  `venv-stdlib`.
- All runs were at below-normal priority.

## Verdict: land with one doc fix

- **The code is right.** `--beta-nll 0` reproduces the plain loss byte for byte, and the default reproduces the
  β-NLL run byte for byte. Both identity chains back to my earlier review hold (section 2).
- **The fix:** the lane doc's decision entry still calls the post-hoc pitch-std calibration "the next item". That test
  has since run and **failed** (`a517ec6`), and the lane doc does not say so.
- **Before landing,** add its result to the lane doc: FAIL on coverage in the extrapolated band on both folds, so the
  pitch cost stands and replay pitch labels stay untrusted until a pitch fix passes a new pre-registration.
- No code change is needed.

## 1. The default-on conditions from `review-beta-nll.md`, against the evidence

| # | Condition (my §5) | Evidence | Status |
|---|---|---|---|
| A4 | Gate 1 re-run with the flag on (I asked for all four folds) | `idm-beta-nll-2-a4.md`: the dev fold (171533 held out), seed 0, the plain side re-scored with the same `fe5c9ca` harness. **Yaw is better on every Gate 1 figure:** moving median 0.352° → 0.263°, direction 0.964 → 0.995, 1 s sum 3.35° → 2.84°, abstention 3.7 % → 0.3 % | **Met as pre-registered** (the dev fold). Not the four-fold breadth I asked for: fold 200129 has no β-NLL run, and 171533 has one seed |
| A1 | More than one fold, with seeds | `idm-beta-nll-2.md`: fold 205528, three seeds per loss. β-NLL learns yaw on 3/3 (0.937 / 0.968 / 0.971 held out); across both folds β-NLL is **6/6** and plain **2/6** | **Met.** Independently re-judged (below) |
| A2 | A judged pitch non-inferiority margin (I suggested 0.03) | Pre-registered at 0.05. The pooled mean is β 0.7755 against plain 0.7925, a difference of **−0.017**. The paired differences run from −0.157 to +0.209: pitch is seed-fragile under both losses | **Met**, at 0.05 and also at my 0.03 |
| A3 | Calibration per axis and regime | **Yaw:** the extrapolated band's distance from nominal falls from 0.219 to **0.073**, the calibrated band's from 0.109 to 0.075. **Pitch was not part of A3.** At A4 the extrapolated pitch band's 1σ coverage is **0.604** (plain 0.734): the stated std is too tight. The post-hoc pitch calibration then **failed**, at 1σ′ 0.621 on 051828 and 0.660 on 205528, against ≥ 0.70 (`idm-pitch-calibration.md`) | **Yaw: met. Pitch: not met.** This is the open item |
| – | The abstention bounds re-confirmed under β | **Yaw:** the 1°/3° bounds hold on **6/6** β-NLL runs against 2/6 plain. **Pitch:** they hold on all six β-NLL runs (the calibration test's component 2: 0.925–1.000) | **Met** |
| – | β stays 0.5, and a per-axis β needs its own pre-registration | Yaw-only β-NLL was pre-registered (`idm-beta-yaw-only-prereg.md`) and **failed** all three components; the default is both axes at 0.5 | **Met** |
| – | Loss values not compared across losses | The reports record `camera_loss`, and every judge used held-out metrics | **Met** |

**Is the pitch cost recorded as the open item?**
- **In the evidence: yes.**
  - The README's decision line records the cost: moving median +0.06°, extrapolated 1σ coverage 0.734 → 0.604. It
    also says a post-hoc calibration is required before any replay label is trusted.
  - `idm-pitch-calibration.md` records that calibration's **FAIL**. `a517ec6`'s message says the pitch cost "gates
    replay pitch labels".
- **In the lane doc: not yet.** Its decision entry ends with "A post-hoc pitch-std calibration is the next item". The
  result section is missing; that is the doc fix above.
- The evidence README does not yet index `idm-pitch-calibration(-prereg).md`. That is the lead's call under the
  evidence rules.

**The evidence reproduces:**
- **Hashes.** The six A1 checkpoints and reports, `a4-beta` (`90aa4bef…` / `43c2f8bb…`) and
  `a4-plain-rescore/gate1.json` (`e15a2770…`) all match the evidence tables.
- **A1, re-judged independently** from the per-row predictions, with truth from the target files:
  - β-NLL s0/s1/s2: yaw 0.937 / 0.968 / 0.971 held out, 0.956 / 0.986 / 0.986 in-sample, all learned; pitch
    0.641 / 0.830 / 0.787;
  - plain s0/s1/s2: yaw 0.480 / 0.899 / 0.493 held out and 0.460 / 0.922 / 0.493 in-sample, so s1 learned; pitch
    0.799 / 0.621 / 0.847;
  - every figure equals `idm-beta-nll-2.md`.
- **A2's means** recompute to 0.7925 and 0.7755.
- **The pitch-calibration pre-registration** in the lane doc is byte-identical to its frozen evidence copy (`e6b5d526…`,
  the pin).

## 2. `--beta-nll 0` is the plain loss, byte for byte, and the identities still hold

**Full-scale `run_fit`** (synthetic stores from `bn/id/inputs/full`, smoke, 2 epochs, seed 0; my own self-pinned
patch-equivalence file naming the fixture's build):

| Comparison | Weights | Meta (besides closure) | Report (besides closure, timings and checkpoint sha) | Losses |
|---|---|---|---|---|
| HEAD `a517ec6` with no flag (plain) vs **the flip with `--beta-nll 0`** | **identical** | identical; no `camera_beta_nll` in either | **identical**, `camera_loss` `gaussian_nll` in both | identical |
| HEAD with `--beta-nll 0.5` vs **the flip's default** (no flag) | **identical** | identical; `camera_beta_nll` 0.5 in both | **identical**, `camera_loss` `beta_nll 0.5` in both | identical |

- The only closure difference is `policy/idm/train.py`.

**The chain back to `review-beta-nll.md`:**
- The flip's `--beta-nll 0` weights **equal** `1df31e7`'s plain weights from that review (every tensor `torch.equal`).
- The flip's default weights **equal** `4e7f005`'s `--beta-nll 0.5` weights.
- **TINY `fit()`, 6 epochs, seed 3.** The state `sha256` is:
  - **plain** (`camera_beta=None`): `272b6617…` at HEAD, on the flip, and at `1df31e7` in my earlier review;
  - **β 0.5** (HEAD explicit, the flip's default, the flip explicit): `0e242d07…`, equal to `4e7f005`'s.
- So the flag-off identity from my earlier review holds under `--beta-nll 0`, and β-NLL's own identity holds under the
  new default.

**Code, read:**
- `camera_beta_from_cli` maps 0 to `None` (−0.0 too). A negative, NaN or > 1 β reaches `fit()` and is refused.
- `loss_terms`' own default stays `None` (the plain loss).
- The meta records `camera_beta_nll` whenever β is on, and the report records `camera_loss` either way.
- `fit()`'s programmatic default changed to 0.5. Its only in-repo callers are the tests, which the change updates.

## 3. Tests (own environments)

| Suite | `a517ec6` | The flip |
|---|---|---|
| Execution: `test_idm_model`, `test_idm_decode`, `test_idm_targets`, `test_idm_eval`, `test_replay_camera` | 84 passed | **85 passed** (+1: `test_the_camera_loss_defaults_to_beta_nll_half_on_both_axes`) |
| stdlib, whole repo | | **1,945 passed, 76 skipped, 0 failed** |

- The renamed primitive test keeps its assertions.
- The end-to-end `run_fit` test now asserts the default `camera_loss` and meta.
- The byte-reproducibility test passes under the β default.

## Findings

- **D1 (doc, fix before landing).** Record the post-hoc pitch-std calibration's FAIL in the lane doc, and replace
  "A post-hoc pitch-std calibration is the next item" with the standing open item: the pitch cost stands, and replay
  pitch labels are untrusted until a new pre-registered pitch fix passes. Name the two directions
  `idm-pitch-calibration.md` offers as future pre-registrations.
- **N1 (breadth).** A4 is one fold and one seed. Fold 200129 has no β-NLL run, and pitch is seed-fragile under both
  losses. Nothing here rests on more than that, but any gate claim for pitch should.
- **N2 (provenance, noted by the author).** A default checkpoint now carries `camera_beta_nll: 0.5`, so it is not
  byte-comparable with a pre-change default one. That is truthful: the loss changed.
- **N3 (not code).** No replay-label export exists yet. When one is written, it must refuse IDM pitch (or mark it
  untrusted) until the pitch item closes, so "gates replay pitch labels" becomes a check, not a sentence.

## Bytes reviewed (sha256)

| File | Raw (working tree) | LF |
|---|---|---|
| `policy/idm/train.py` | `534f80914ecd555e10395e5277cb66c43dcbce6638e586aac4240867e5fda029` | `f6e0bc27bc721c2a28f3396e8d115df248aabfcf136c6c06791af6698b4f8d62` |
| `tests/test_idm_model.py` | `3e75f2824cb6d3d23c38d2ec8d7da045e825a979614369e656ba9f454e53325c` | `36346b4a8f96414a4269f536dbe5b5d0aea65918baa70a7a99e8562b46fa8b11` |
| `docs/lanes/inverse-dynamics.md` | (working tree) | `b3d07d8dc7b44774b2d99ceaac0b0e7334f6add508eae1c71e9bcf73ac150af6` |

**Evidence folder at `a517ec6`** (sha256 prefixes):

| File | sha256 |
|---|---|
| `README.md` | `2ce64e857e54f788` |
| `idm-beta-nll-2.md` | `20b6283f236b4b4f` |
| `idm-beta-nll-2-a4.md` | `0faf5556cc45aa80` |
| `idm-partA-prereg.md` | `42beb90e34d321e9` |
| `idm-partB-prereg.md` | `4247102d1e328b13` |
| `idm-beta-yaw-only-prereg.md` | `d6f63ff6b87df5c0` |
| `idm-beta-yaw-only.md` | `e38a74bd0a195798` |
| `idm-edge-input.md` | `0dba8450239d6835` |
| `idm-edge-input-2-prereg.md` | `61e47c57e249a641` |
| `idm-edge-input-2.md` | `18ef2f530e4cb8fe` |
| `idm-pitch-calibration-prereg.md` | `e6b5d5265d6e3aff` |
| `idm-pitch-calibration.md` | `1c9fb3cd648c7eab` |

My scripts and logs are in my scratchpad under `bd/`: `id/`, `t-*.log`.
