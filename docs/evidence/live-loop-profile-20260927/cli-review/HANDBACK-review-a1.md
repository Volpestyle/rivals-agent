LAND

# Pre-run re-check a1: live-CLI delta, test skip fix (VUH-1384), binds-review (Opus 5.5), 2026-09-27

This supplements `HANDBACK-review.md` (`0b4258a9…`) and `review-receipt-v2.json` (`4023ab34…`). Both are preserved unchanged.

**The delta is exactly one line.**
- `tests/test_live_range_bc.py` `08722dad…` → **`d6643319…`**. The diff against the reviewed snapshot is line 372 only: `not torch.cuda.is_available()` → `torch.cuda.device_count() == 0`.
- `scripts/run_range_bc_live.py` (`446ef0bb…`), `policy/range_bc/live_inference.py` (`d0331d60…`), `tests/test_live_inference.py` (`2be9c640…`) and `agent/live_range_bc.py` (`d4c109e7…`) are unchanged.

**Tests.** With `CUDA_VISIBLE_DEVICES=""`, the four suites give **73 passed, 1 skipped**. The skipped case is `[cuda-compact-bgr]` ("CUDA unavailable"), which previously failed on CUDA initialisation. Condition 2 is closed.

**Condition 1 is already met.** James approved live-agent GPU inference while the game runs at 12:36 CDT (`4f81722`: `AGENTS.md`, `docs/compute.md`). The owner still measures and reports the game's FPS cost.

**New receipt.** `review-receipt-v2-a1.json` pins the five files above, and `run_range_bc_live.verify_review_receipt` accepts it against the running bytes; that check did not create Live. It covers code identity only. The lead owns scheduling, camera maps and re-freeze.
