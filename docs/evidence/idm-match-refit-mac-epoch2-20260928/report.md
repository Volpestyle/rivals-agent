# EXPLORATORY Mac refit: epoch 2 complete

Epoch2 of3 is independently verified: **90,260 total optimizer updates**, checkpoint **1fc6ae2f0bb9b35f90674726732cc940ed5c5e702cdd767d6f0254bf465ebde5**, completion receipt **5ac8b44f9e633c070c357a7caf6085dee44302b58b592a2d961aea7fbbcc3853**. The5,142,267-byte payload remains local under `data/idm/match-refit-mac-20260928/watch/epoch-2/` and in its original native epoch directory. Strict `EpochJournal.read` checked hashes, finite state, optimizer steps, complete cursor/history, contract and MPS RNG. Whole -11/-12 families remain absent from checkpoint provenance.

Epoch2 took **2,566.603 seconds / 42.777 minutes**, **17.584 updates/s**, versus44.007minutes for epoch1. Cumulative trainer time86.784min. Roughly43min remained at the epoch2 boundary if that rate holds, putting fit completion around15:22CDT; TRAIN calibration and evaluation still follow. Training loss0.695784 is not held-out accuracy.

## Requested swap comparison

Across453 epoch2 memory observations, swap usage never exceeded its epoch1 endpoint: **12,330.25M -> 12,314.19M** in sysctl's printed units. Fresh14:39:41CDT observation confirms the latter and77% reported free memory. Between13:56:44 and14:39:41, cumulative VM **swap-outs increased by0**, swap-ins by746. Thus swap occupancy is not growing at this check; this does not claim zero historical swapping or zero file-backed paging.

Peak process RSS remains **88.625GiB**, with memory-mapped stores included; MPS driver allocation remains about1.03GiB. Neither RSS nor system free percentage is process-private physical footprint. Original PID12434 was already training epoch3 and continues unchanged; no restart, deletion, new compute or paid work.

Remaining: epoch3; TRAIN-only press calibration and range-dev real/zero visual report; unchanged37,980-row held-out -11/-12 camera readout (new/full03/prior/zero, per-source first, own/common coverage, still/moving and one-second slices). Owner IDM retains the Mac slot, collects the result, reports remaining acceptance/next action to herdr-lead for VUH-1353 and explicitly releases the slot afterward. No tuning on held-out sources or Gate2/corpus-labeling claim. Source/manifest remain59d2404/17b0f96 and73d486da.
