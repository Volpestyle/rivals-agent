# IDM SSL smoke result — 2026-09-27

Owner: idm-owner · VUH-1353 · **EXPLORATORY**

The pipeline completed, but this smoke demonstrates no representation benefit. On 80 inspected clips (1,280 frames) from four admitted S6.5 sources, the three temporal predictors ended with training losses 0.688497, 0.709852 and 0.684267. Copying the last feature frame scored 0.211714. All losses are in-training; no downstream IDM or policy comparison has run. These weights are not promoted.

The packet balances 20 clips per source, half dense 60 Hz and half 8 Hz. Its roughly 85 seconds of sampled temporal support is a pipeline smoke, not a completed 7.44-hour or ten-hour representation experiment. The 7.44 hours describe the admitted whole-file source pool. Native spot inspection and intervening-frame cut checks are recorded by the packet builder. Whole-file admission remains world-feature SSL only: no semantic labels, evaluation, camera-demo inference or publication follows from it. All four sources are February 2026, not calendar 2025.

Run: `ap-dlUQUitwSwNF6G0MCpnWh6`, created 18:49:03.349857 UTC, worker exit 0 after 260.584 seconds. DINO extraction took 14.190 seconds; the three ten-epoch fits took 2.104, 1.618 and 1.409 seconds. Terminal teardown verified zero owned containers at 18:53:42.520161 UTC. The conservative charge is **$0.95682665**, including the $0.75 setup allowance, under the $2 hard cap; this is not an invoice. Code `c2bef3e`, deployment `ec3ea50`. No automatic retry.

Frozen local result directory: `data/idm/cloud-20260927/ssl-result/`. Report and checkpoint hashes match the Mac collector receipt:

| Artifact | SHA-256 |
|---|---|
| report.json | 8236c2f7611ca1a806e9a67165c3b08322341b10fc94ae814f0c9e1577923448 |
| final.json | 5452fdfa3af0b48ce3e08a2f3bfdb0e9e37a2208b6513796c62fce46c031337d |
| temporal-seed0.pt | f88e7efd3af4b5a8dbf734146646bea4ab3841ea26768cd43f06820e13765123 |
| temporal-seed1.pt | 6c75c34aacdce11e54c3cb46e5eccb2f4c4215c2169b56dfd7e9fc8ca60ff12c |
| temporal-seed2.pt | c75b98473433972add79c63a64e6aa96ecfed2854d098ab41c2f62a9a670aeff |

Packet SHA-256: `3f56e98f573131bf8eaad2446a27bebcdc9c04d1124a85d820adf0c18454dc64`. Admission SHA-256: `864e54350343a26ce0111d03d6e76d39bddef2f1e3e1c5cdb898b93e1f42dd02`. The report's frozen `review: provisional` is a producer field, not a pending review request; under James's 2e00d3f rule exploratory results receive no independent review. It remains exploratory, with Gate 2 acceptance unchanged.

Next: idm-owner collects the separately running press diagnostic, including real-versus-zero visual inputs and TRAIN-only threshold results. Before further SSL spending, the useful scientific comparison remains matched supervised-only versus SSL-initialized camera fits on TRAIN-internal folds, with the identical architecture, paired examples and training budget. The smoke alone does not justify expanding to the whole archive. The queued camera demonstration uses only admitted TRAIN range footage because the archive's current admission excludes demo use. Match -4/-5 labels remain held until corrected accepted-a1 receipts; immutable relocation is not renewed admission.

Linear reconciliation could not be performed: both advertised connector calls (`linear.get_user`, `linear.get_issue`) returned `Unknown tool`. Lead handoff text follows; preserve the issue's existing acceptance and status:

> Current result (27 September): EXPLORATORY SSL smoke completed on 80 inspected clips from four admitted S6.5 sources. Three seeds finished worse than copy-last even on training loss (0.684–0.710 versus 0.212), so no representation gain or weight promotion is claimed. Exit 0, terminal/zero containers; conservative cost $0.957 under $2. Evidence: idm-ssl-smoke-result-20260927.md and report SHA-256 8236c2f7…
>
> Remaining acceptance: paired camera/press validation and live-to-replay/range-to-match transfer remain unresolved; this smoke does not pass Gate 2. SSL needs a matched downstream comparison. Corrected match admissions are required before consuming -4/-5.
>
> Next action: idm-owner collects the $4 press diagnostic with TRAIN-only thresholds and real-versus-zero/chance controls, then supplies a camera-only TRAIN-range demonstration. SPIDEY demo use is outside the present SSL-only admission.
