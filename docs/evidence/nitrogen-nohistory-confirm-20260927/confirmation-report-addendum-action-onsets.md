# EXPLORATORY per-action initiation: 1 s and 2 s

This lead-requested post-result analysis replaces the strict joint cold split as an informative initiation probe. The earlier joint split was **uninformative**, with only 5 cold press targets at 0.5 s and none at 1 s. Neither analysis changes the confirmation verdict or its reviewed judge.

For each action independently, previous 30 or 60 rows contain no press of THAT action. Other action/camera activity is allowed. Current labels are excluded from the history. Prior own-action press channels must be fully known/valid; run-boundary and unknown-history rows are excluded. First current press in quiet-history rows is an onset; recent-own-press rows are continuations.

Original run coordinates and +/-1 one-to-one matcher; true and predicted presses restricted to the same action stratum. Quiet-history false positives count against onset F1. Boundary-permitting recall additionally allows a prediction across the onset/continuation boundary and can credit a one-frame late echo. Macro F1/recall use zero for actions without positives. EDGE_ACTIONS macro matches the confirmation metric; live-actions macro is secondary. All semantic actions shown with their TRAIN live-mask status.

All six existing checkpoints use unchanged original TRAIN cutoffs and the median decoder on the same MPS stack. No refit, re-extraction or cloud compute. The analyses use James’s past labels only to stratify evaluation; those labels are not new model inputs.

**Finding:** unlike the uninformative joint cold split, this split has 977 six-action onset presses at 1 s and 577 at 2 s. Candidate onset F1 is **0.134030 / 0.122656**, above matched control **0.003740 / 0.005151**. Candidate macro onset recall is nevertheless only **0.091084 / 0.081857** (micro recall **0.091778 / 0.065858**). Continuation micro recall is about **0.350 / 0.347**. The candidate has measurable onset signal when other activity is allowed, but misses most onsets; this does not establish dependable independent initiation.

The action breakdown is uneven. Candidate spider_power onset recall is only **0.0044 / 0.0028** for the 1 s / 2 s windows, versus web_cluster **0.1511 / 0.1273** and get_over_here **0.1917 / 0.2018**. Same-action silence does not remove visual cues from James?s other actions.

## Six-action macro, means over seeds 1/2/3

| History | Stratum | Arm | True presses | Mean F1 | Mean recall | Mean micro recall | Mean matched presses |
|---|---|---|---:|---:|---:|---:|---:|
| 1.0s | onset | candidate | 977 | 0.134030 | 0.091084 | 0.091778 | 89.67 |
| 1.0s | onset | control | 977 | 0.003740 | 0.001905 | 0.003071 | 3.00 |
| 1.0s | continuation | candidate | 456 | 0.108131 | 0.175189 | 0.350146 | 159.67 |
| 1.0s | continuation | control | 456 | 0.003982 | 0.002041 | 0.004386 | 2.00 |
| 2.0s | onset | candidate | 577 | 0.122656 | 0.081857 | 0.065858 | 38.00 |
| 2.0s | onset | control | 577 | 0.005151 | 0.002628 | 0.002889 | 1.67 |
| 2.0s | continuation | candidate | 854 | 0.155699 | 0.207183 | 0.347385 | 296.67 |
| 2.0s | continuation | control | 854 | 0.004037 | 0.002069 | 0.004294 | 3.67 |

The macro covers spider_power, web_cluster, get_over_here, amazing_combo, web_swing and jump, matching the confirmation press metric. Undefined action F1/recall counts as zero; per-action support is shown below. True counts describe one human cohort, not three independent copies.

## Per action

F1 and recall are seed means. “Enabled” is the unchanged TRAIN-derived execution mask; disabled actions remain visible in this table but cannot be sent by either model. Quiet-history false positives count against onset F1. Other actions and camera motion are permitted throughout the prior interval.

| History | Stratum | Action | Enabled | True presses | Candidate F1 | Control F1 | Candidate recall | Control recall |
|---|---|---|---|---:|---:|---:|---:|---:|
| 1.0s | onset | move_forward | True | 196 | 0.037715 | 0.000000 | 0.027211 | 0.000000 |
| 1.0s | onset | move_left | True | 250 | 0.037669 | 0.000000 | 0.028000 | 0.000000 |
| 1.0s | onset | move_back | True | 161 | 0.057322 | 0.000000 | 0.043478 | 0.000000 |
| 1.0s | onset | move_right | True | 186 | 0.026589 | 0.000000 | 0.019713 | 0.000000 |
| 1.0s | onset | jump | True | 300 | 0.158179 | 0.006630 | 0.116667 | 0.003333 |
| 1.0s | onset | web_swing | True | 141 | 0.037158 | 0.000000 | 0.023641 | 0.000000 |
| 1.0s | onset | get_over_here | True | 40 | 0.280468 | 0.000000 | 0.191667 | 0.000000 |
| 1.0s | onset | amazing_combo | True | 96 | 0.098327 | 0.000000 | 0.059028 | 0.000000 |
| 1.0s | onset | ultimate | False | 4 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 1.0s | onset | melee | False | 5 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 1.0s | onset | spider_power | True | 153 | 0.006944 | 0.000000 | 0.004357 | 0.000000 |
| 1.0s | onset | web_cluster | True | 247 | 0.223101 | 0.015812 | 0.151147 | 0.008097 |
| 1.0s | onset | team_up | False | 27 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 1.0s | onset | goh_targeting | False | 7 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 1.0s | onset | simple_swing | False | 9 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 1.0s | continuation | move_forward | True | 52 | 0.012379 | 0.000000 | 0.025641 | 0.000000 |
| 1.0s | continuation | move_left | True | 75 | 0.030783 | 0.000000 | 0.057778 | 0.000000 |
| 1.0s | continuation | move_back | True | 36 | 0.014322 | 0.000000 | 0.027778 | 0.000000 |
| 1.0s | continuation | move_right | True | 64 | 0.006839 | 0.000000 | 0.010417 | 0.000000 |
| 1.0s | continuation | jump | True | 273 | 0.292595 | 0.004840 | 0.388278 | 0.002442 |
| 1.0s | continuation | web_swing | True | 18 | 0.071076 | 0.000000 | 0.240741 | 0.000000 |
| 1.0s | continuation | get_over_here | True | 2 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 1.0s | continuation | amazing_combo | True | 0 | 0.000000 | — | — | — |
| 1.0s | continuation | ultimate | False | 0 | — | — | — | — |
| 1.0s | continuation | melee | False | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 1.0s | continuation | spider_power | True | 27 | 0.035819 | 0.000000 | 0.074074 | 0.000000 |
| 1.0s | continuation | web_cluster | True | 136 | 0.249297 | 0.019052 | 0.348039 | 0.009804 |
| 1.0s | continuation | team_up | False | 23 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 1.0s | continuation | goh_targeting | False | 2 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 1.0s | continuation | simple_swing | False | 4 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 2.0s | onset | move_forward | True | 139 | 0.037321 | 0.000000 | 0.023981 | 0.000000 |
| 2.0s | onset | move_left | True | 141 | 0.038402 | 0.000000 | 0.028369 | 0.000000 |
| 2.0s | onset | move_back | True | 122 | 0.068410 | 0.000000 | 0.049180 | 0.000000 |
| 2.0s | onset | move_right | True | 138 | 0.027290 | 0.000000 | 0.019324 | 0.000000 |
| 2.0s | onset | jump | True | 103 | 0.103309 | 0.019109 | 0.074434 | 0.009709 |
| 2.0s | onset | web_swing | True | 114 | 0.043587 | 0.000000 | 0.026316 | 0.000000 |
| 2.0s | onset | get_over_here | True | 38 | 0.291162 | 0.000000 | 0.201754 | 0.000000 |
| 2.0s | onset | amazing_combo | True | 91 | 0.100074 | 0.000000 | 0.058608 | 0.000000 |
| 2.0s | onset | ultimate | False | 4 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 2.0s | onset | melee | False | 5 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 2.0s | onset | spider_power | True | 121 | 0.004695 | 0.000000 | 0.002755 | 0.000000 |
| 2.0s | onset | web_cluster | True | 110 | 0.193110 | 0.011799 | 0.127273 | 0.006061 |
| 2.0s | onset | team_up | False | 26 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 2.0s | onset | goh_targeting | False | 7 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 2.0s | onset | simple_swing | False | 6 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 2.0s | continuation | move_forward | True | 108 | 0.035505 | 0.000000 | 0.052469 | 0.000000 |
| 2.0s | continuation | move_left | True | 183 | 0.042244 | 0.000000 | 0.051002 | 0.000000 |
| 2.0s | continuation | move_back | True | 75 | 0.022947 | 0.000000 | 0.031111 | 0.000000 |
| 2.0s | continuation | move_right | True | 112 | 0.021613 | 0.000000 | 0.026786 | 0.000000 |
| 2.0s | continuation | jump | True | 468 | 0.350058 | 0.002834 | 0.378917 | 0.001425 |
| 2.0s | continuation | web_swing | True | 45 | 0.163169 | 0.000000 | 0.296296 | 0.000000 |
| 2.0s | continuation | get_over_here | True | 4 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 2.0s | continuation | amazing_combo | True | 5 | 0.018913 | 0.000000 | 0.133333 | 0.000000 |
| 2.0s | continuation | ultimate | False | 0 | — | — | — | — |
| 2.0s | continuation | melee | False | 1 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 2.0s | continuation | spider_power | True | 59 | 0.044539 | 0.000000 | 0.062147 | 0.000000 |
| 2.0s | continuation | web_cluster | True | 273 | 0.357514 | 0.021389 | 0.372405 | 0.010989 |
| 2.0s | continuation | team_up | False | 24 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 2.0s | continuation | goh_targeting | False | 2 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| 2.0s | continuation | simple_swing | False | 7 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |

## Every seed: six-action macro

| Run | History | Stratum | F1 | Recall |
|---|---|---|---:|---:|
| candidate-s1 | 1.0s | onset | 0.138111 | 0.090828 |
| candidate-s1 | 1.0s | continuation | 0.100201 | 0.158788 |
| candidate-s1 | 2.0s | onset | 0.129786 | 0.083386 |
| candidate-s1 | 2.0s | continuation | 0.150490 | 0.206456 |
| control-s1 | 1.0s | onset | 0.002452 | 0.001230 |
| control-s1 | 1.0s | continuation | 0.003628 | 0.001836 |
| control-s1 | 2.0s | onset | 0.003205 | 0.001618 |
| control-s1 | 2.0s | continuation | 0.003125 | 0.001577 |
| candidate-s2 | 1.0s | onset | 0.127587 | 0.087798 |
| candidate-s2 | 1.0s | continuation | 0.111584 | 0.180937 |
| candidate-s2 | 2.0s | onset | 0.116334 | 0.079339 |
| candidate-s2 | 2.0s | continuation | 0.156203 | 0.189830 |
| control-s2 | 1.0s | onset | 0.002208 | 0.001111 |
| control-s2 | 1.0s | continuation | 0.003623 | 0.001836 |
| control-s2 | 2.0s | onset | 0.006349 | 0.003236 |
| control-s2 | 2.0s | continuation | 0.001920 | 0.000967 |
| candidate-s3 | 1.0s | onset | 0.136391 | 0.094626 |
| candidate-s3 | 1.0s | continuation | 0.112609 | 0.185842 |
| candidate-s3 | 2.0s | onset | 0.121848 | 0.082846 |
| candidate-s3 | 2.0s | continuation | 0.160403 | 0.225263 |
| control-s3 | 1.0s | onset | 0.006562 | 0.003374 |
| control-s3 | 1.0s | continuation | 0.004695 | 0.002451 |
| control-s3 | 2.0s | onset | 0.005900 | 0.003030 |
| control-s3 | 2.0s | continuation | 0.007067 | 0.003663 |

## Boundary sensitivity

The strict onset score prevents a prediction one frame after the human onset from being credited across the stratum boundary. Allowing that late match raises recall substantially; it can credit a visual echo and is not substituted for the headline score.

| History | Arm | Strict macro onset recall | Boundary-permitting macro onset recall |
|---|---|---:|---:|
| 1.0s | candidate | 0.091084 | 0.280487 |
| 1.0s | control | 0.001905 | 0.002130 |
| 2.0s | candidate | 0.081857 | 0.274203 |
| 2.0s | control | 0.002628 | 0.002628 |

## Reproduction and limits

| Run | Aggregate F1 difference | Aggregate camera MAE difference |
|---|---:|---:|
| candidate-s1 | +0.000000000000 | +0.000000000000 |
| control-s1 | +0.000000000000 | +0.000000000000 |
| candidate-s2 | +0.000000000000 | +0.000000000000 |
| control-s2 | +0.000000000000 | +0.000000000000 |
| candidate-s3 | +0.000000000000 | +0.000000000000 |
| control-s3 | +0.000000000000 | +0.000000000000 |

These are exploratory conditional metrics on the existing frozen-dev recordings. An action onset can still occur during James’s movement, another action’s animation or an ongoing turn. Recurrent visual memory may therefore remain useful through cross-action cues. A positive onset score does not prove independent initiation in a live feedback loop. The same caveat applies to future pixel ego-motion features. True and predicted events must share the stratum for the headline ±1 match; raw JSON also carries boundary-permitting recall, which can credit late visual echoes.

Four synthetic tests cover own-action timing, other-activity independence, unknown/gap exclusion, quiet-period false positives and boundary-crossing echoes. Raw JSON includes all per-seed counts, exact-frame matches and a secondary macro over all enabled actions.

Evidence: [action-onsets-results.json](action-onsets-results.json), [action-onsets-results.zip](action-onsets-results.zip); source `e466963`. See [confirmation-report.md](confirmation-report.md) for the unchanged confirmed result.

Raw packet SHA-256 `7033556436600ce930b1ed8c5dd42b00a588f343d3bbebf021d4c33f85ac2602`. All six aggregate F1/MAE reproduction deltas are exactly zero. Process exit 0 and terminal proof are retained. Cloud cost $0; Mac slot released to lead and IDM after completion.
