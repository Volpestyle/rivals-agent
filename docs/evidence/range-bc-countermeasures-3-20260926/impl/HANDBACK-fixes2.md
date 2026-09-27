# Fixes2 hand-back — frozen for independent review

Code and synthetic tests only. No commits, real frames, smoke, extraction, fits,
accelerator work or launches. Amendment 3 is pinned at 595753d, judge e23b3212….

- **F5:** H/I/W train and dev explicitly use stride 64. The constructed 256-row
  regression gives starts 0/64/128/160, verifies tail/burn-in multiplicities and
  weighted U/C/E, and 39 updates over five sessions/13 epochs. Legacy A retains
  0/48/96/144/160 and 52 updates. Its five source files remain unchanged from 9d61d59.
- **F6:** authenticated `inputs` stage builds/verifies all seeds' paired tensors
  and 13 epoch orders before proof128. Later approvals bind its `pairing` reference;
  workers recheck that manifest and train provenance before numerical work.
  Bad shared tensors, arm window order or frozen manifest refuse before the
  backbone/numerical sentinel. Extraction and fits retain later rechecks.
- **Diagnostics:** every fit emits actual evaluation context and measured memory.
  H/I/W compute unweighted train loss and feature/gate diagnostics on the documented
  first complete 96-row window per train session with no dropout/augmentation/idle
  weighting. Actual CPU calculations pass pinned A3 `check_report`; memory APIs use
  explicit synthetic stand-ins in tests. No accelerator measurement is claimed.
- **Memory:** CUDA resets/reads max_memory_allocated. MPS requires a pinned A3
  acceptance capability and emits null peak plus the six specified disposition/
  sample fields, fixed integer 10 ms interval and driver-memory source. Poll errors
  refuse; original judge pins refuse MPS. A3 check_memory/check_report accept the
  emitted MPS fields. An initial float 10.0 type mismatch was caught and corrected.
- **A3 receipts:** `FIT-RECEIPT-a3.md` replaces old stage/dependency ordering:
  phase 1 A0/A1/A2/H0/repeat in parallel, authenticated gate afterwards, phase 2
  remaining fits. Exactly one fit/attempt per invocation. Complete synthetic A2/A3
  matrices, changed-repeat refusal and preemption guards pass. Modal-port was notified.

Validation on current main `fb0d450897d584377ea48326b1738dd7721672f4`: cm3-fixes2-tests.xml: 156 passed, 0 skipped; regression-current-main-fixes2.xml: 2227 passed, 77 skipped.
Fatal Ruff checks pass. Corpus remains skipped. Existing F1–F4 closure locks,
feature/model/byte-proof primitives remain unchanged; full hashes are in
`fixes2-files.json` (`a9193d80013b2d35454bf68e206850fc4141ffb96189313e238936774f3291b2`). Software stays proposed
until the lead freezes the chosen runtime. Implementation review and lead probe
approval remain required. Prior frozen hand-backs/contracts were not edited.

| Changed file | SHA256 |
|---|---|
| `policy/range_bc/cm3_run.py` | `bcb638d057ba7b55fb906653569ef249fc755d39d0445df738d284c4ec63c817` |
| `policy/range_bc/cm3_train.py` | `e05ca55056f7cb561afa23934572aa1ae1abdf972eab43f3b818bd8ec4a19426` |
| `tests/test_range_bc_cm3.py` | `38a248e30b042110d0daf74513c08eb8d023edaaff0ed00c1cc80cad03333716` |
| `tests/test_range_bc_cm3_run.py` | `92c9afd5b285340ce53474f80997f4e34dcc8575c14827311785561d9988ed23` |
| `tests/test_range_bc_cm3_diagnostics.py` | `6689df90f59ea27337e89810d1f67d4add2a0e66da702767cf6383311b59c28f` |
| `FIT-RECEIPT-a3.md` | `5a6c1b4089e9e1790e5ed29a2b0ed1c5947558933dbae14a97d4a2b8323fc619` |
| pinned `judge_cm3-a3.py` (not edited) | `e23b3212a0eadc98bc590e5081a92c9fab6740e93808aba2d245d6020b3f8eb0` |

The source/test/contract packet is now frozen; no edits during the next review.
