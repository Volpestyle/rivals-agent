# F1 owner regression supplement

2026-09-27, VUH-1346. This record adds verification only; no frozen candidate bytes
were edited. Current main supporting checkout: c461658d3eb1a0744f0700f91f1d8930258105a0.

Loaded the exact frozen candidate cm3_run and cm3_accounting as policy.range_bc
modules, with ROOT pointing to the current repository for unchanged supporting
lock/resource files. Owner SHA327f51225949f4bdb16da427fbabbf9439005f8e5b09a9455e760ba75acf4900;
helper SHAad2d3c568ad0e7c08a4ae3c2680d02344288594b0bc985591108f9707e968835.

105 tests passed in 95.95 seconds, zero skips:

- tests/test_range_bc_cm3_runtime_identity.py
- tests/test_range_bc_cm3_runtime_diagnostics.py
- tests/test_range_bc_cm3_namespace.py
- tests/test_range_bc_cm3_run.py

Interpreter: existing private fit-review-cm3-torch-20260926 Python environment.
PYTHONDONTWRITEBYTECODE=1; CUDA_VISIBLE_DEVICES empty; HF_HUB_OFFLINE=1;
TRANSFORMERS_OFFLINE=1; OMP_NUM_THREADS=2; pytest cache provider disabled.
Synthetic/offline regression only; no real frames, source arrays, weights, GPU
jobs, launch, approval-ledger edit or commit. This supplements the 35 F1 tests,
10 original Writer tests and modal-port's 80 wrapper tests already submitted.
