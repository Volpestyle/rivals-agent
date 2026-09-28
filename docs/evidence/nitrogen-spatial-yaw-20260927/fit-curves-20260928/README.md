# Supplementary curves for the matched spatial-yaw fits

The lead requested every arm's final `fit/status.json` and all 26 epochs of
`train_chunk_loss` and `dev_step_one.camera`, alongside the final results.
No earlier checkpoint is selected or evaluated. This adds no fit or extraction.

The completed **4×4** files are retained in `grid4/`, with stable double-read
hashes and final recipe/epoch/update checks. The [curve report](grid4-report/report.md),
[figure](grid4-report/curves.png) and [all numeric points](grid4-report/curves.csv)
supplement the unchanged [4×4 scientific result](../grid4-results-02/report.md).
All three curves lower TRAIN loss while worsening dev camera CE, consistent with
overfitting. This is an explanatory pattern, not a causal isolation or a new result selection.

`status.json` was not one of the original guard-declared artifacts. The collector
therefore labels its hashes as supplementary hashes first recorded at collection,
not original guard pins. It authenticates the terminal proof, recipe identity,
final epoch/update count, all 26 curve points and stable repeated reads. It retains
the already-guarded epoch-26 checkpoint pin as a reference, without claiming to have
independently compared checkpoint history in this collection.

For **8×8**, wait for all three completed, terminal results, then run the same
collector using SDK Python, niced, with these arguments:

```text
/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/collect-fit-curves-20260928.py
/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/guard-integration/fullfit-local-03
/Users/james/dev/range-bc-data/explore/nitrogen-spatial-yaw-20260927/fit-curves-grid8-20260928
8
```

The running apps, their source closure, guards and output artifact lists remain
unchanged. The ordinary scientific collector is still
`../fullfit-local-03/collect.py`. After collecting the supplementary 8×8 files,
run `report.py --collections <grid4/collection.json> <grid8/collection.json>
--out <fresh comparison-report directory>` on PC CPU. It emits CSV, PNG, SVG,
source hashes and the complete 26-epoch report. Link that report next to the final
base/4×4/8×8 scientific result before landing it.

Interpretation requested by the lead: falling TRAIN with worsening dev suggests
overfitting; both flat suggests a fitting/input problem; improved dev camera CE
with worse full-run MAE suggests decoding/evaluation context. The total TRAIN loss
also contains frozen heads; dev camera CE contains both axes and uses windowed
context. Preserve those distinctions when interpreting the curves.

If 8×8 is negative and the curves do not explain it, the next lead-directed bet is
the bounded intent/target audit from
[`recent-ai-research-20260927.md`](../../../research/recent-ai-research-20260927.md).
Oracle labels remain separate from causal inputs. No further grids or encoders.
