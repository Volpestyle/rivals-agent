# Outside research check-in, 2026-09-27 20:15 CDT

Delta from the [19:30 check](evaluator-checkin-20260927-1930.md), using fresh
Linear comments, landed receipts, loader code and current lead/owner handoffs.
Advisory only; no new compute or dispatch from this evaluator.

**The cloud extraction shortcut delivered.** The
[completed export](../evidence/nitrogen-spatial-yaw-20260927/cloud-extraction-02/REPORT.md)
contains both grids for 300,448 TRAIN and 24,556 frozen-dev frames. Its 99.18 GiB
of feature arrays remain in Modal, avoiding the external upload and a second
tower pass. Extraction plus its failed first attempt has a conservative settled
bound of $1.780898, within its $3 allocation. The dataset and completed artifacts
are verified; extraction teardown is proven. This is infrastructure progress,
not evidence that the finer grid improves decisions.

**Training is now running, with a material throughput problem.** The first six
fits refused a schedule mismatch before creating an optimizer. The
[recovery](../evidence/nitrogen-spatial-yaw-20260927/fullfit-recovery-02/README.md)
restores the prescribed stride 64 instead of the generic loader's default 48;
it keeps the 4,697 TRAIN windows and 15,288 updates. This fixes implementation,
not the scientific recipe. The failed runs were settled before the fresh six.

At the owner's 20:16 read, 4x4 ran around 17.6-17.8 updates/s, while 8x8 ran
around 1.2-1.7. The latter projects beyond the 21:01 funded deadline even before
evaluation. Sampled GPU utilization was only 0-13%. Grid8 maps 99.18 GiB with
32 GiB RAM; grid4 maps 19.84 GiB. The loader directly memory-maps mounted arrays.
These facts support I/O or memory pressure as a hypothesis; the available counters
do not identify the cause conclusively.

Operations already chose a useful response: leave 4x4 untouched; check the 8x8
rate again at 20:22 and stop/settle only those apps if they remain too slow; then
use one separately approved $1.50 local-copy timing probe before proposing fresh
8x8 fits. A possible cap increase is not an approved increase. The current $24
campaign cap remains binding. Existing settled cost plus the six reserved
envelopes was $19.638764; that is neither an invoice nor final available funding.

I sent one measurement note to operations: the existing probe should time the
actual shuffled window loader over enough distinct data to expose the large
working set. Reusing a tiny batch that fits RAM could falsely suggest the I/O
problem is solved. Separate copy/hash time from step rate, then include both and
evaluation in the full-run forecast. The lead accepted and forwarded this at
20:20. No extra benchmark or review was requested.
The sizing memo already called for local staging. Preserve completed 4x4 versus
base/zero findings independently; incomplete 8x8 runs cannot reject finer features.

**IDM and corpus:** all stores remain complete. The current upload advanced from
78.394 GB at the initial read to 97.09/113.96 GB in the 20:20 lead handoff. The
accepted runtime12 is frozen in accbf91; no IDM AppCreate or fit result yet.
The night admission set is
finished: eight accepted matches, 45.883 counted minutes. The current refit still
uses only -4a1/-5a1/-6 plus the eight ranges; about 30.9 more match minutes belong
to a later refit. The admission worker is appropriately parked. The final -12
authority refresh has LAND and does not alter the current training population.

No new accepted live outcome. Next decision should use the completed 4x4 scores,
the representative local-disk timing, and actual IDM upload completion. Keep
runtime failures separate from negative learning evidence; do not change the
training hypothesis solely because the larger data path is slow.
