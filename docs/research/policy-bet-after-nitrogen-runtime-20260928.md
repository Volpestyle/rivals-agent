# Policy decision after NitroGen runtime failure

2026-09-28, 19:09 CDT. Outside evaluator; out-of-cycle request from herdr-lead.
Recommendation only; no execution, implementation or compute authorization.

**Park idm-owner for this decision cycle. Choose one bounded attempt to remove
redundant computation from NitroGen while preserving its sampled policy, before
funding a different model or another reader follow-up.** The unchanged sampler
is correctly closed. A specific code finding makes this narrow follow-up worth
distinguishing from an open-ended effort to make a slow model work.

## Why this is the next bet

The [measured result](nitrogen/native-policy-feasibility-20260928.md), `a24a475`,
establishes 342/388 ms p50/p95 and thirty violations of the 250 ms limit. It does
not establish the latency floor of the same policy with redundant work removed.

In pinned upstream `nitrogen.py`, `get_action` computes the image encoder once,
but calls `vl_self_attention_model(vl_embs)` **inside all sixteen Euler steps**.
`prepare_input_embs` constructs `vl_embs` from fixed visual features, image/game
tokens and image-drop masks; evolving actions enter the separate `sa_embs`.
The visual mixer's forward takes only those context embeddings. Under `eval()`,
this context therefore appears reusable within one prediction, without changing
weights, precision, sixteen steps, horizon, or target timing. **This is a source
dependency finding, not a measured speedup or tested parity claim.** Sources:
[model](https://github.com/MineDojo/NitroGen/blob/32608444660950ffda95e1e57c79632ad65bea10/nitrogen/flow_matching_transformer/nitrogen.py#L375),
[mixer](https://github.com/MineDojo/NitroGen/blob/32608444660950ffda95e1e57c79632ad65bea10/nitrogen/flow_matching_transformer/modules.py#L314).

This could retain the pretrained action behavior our custom heads discarded.
It offers a cheaper discriminating question than retraining another head or
building a new corpus before knowing which deployable policy will consume it.
No claim is made that the saving will be large enough or that NitroGen knows
how to fight as Spider-Man.

## One attempt, with an explicit stop

Recommend explore-policy as the existing owner: **at most 45 minutes of work,
five minutes of authorized isolated GPU measurement, $0 new cloud spend.**

1. Profile the repeated visual-mixing cost and try only caching that static
   context once per sampler invocation. Reset on every new observation. Reuse
   the retained checkpoint, fixtures, runtime and original benchmark. Keep all
   sixteen sampling steps and the complete output contract. No compiler campaign,
   distillation, fewer-step sweep, data extraction or trainer work in this attempt.
2. Compare original and cached paths using identical initial noise, evaluation
   mode and precision across different images. Require raw-action agreement
   within a tolerance fixed beforehand against baseline numerical repeatability,
   plus unchanged decoded button decisions and stick signs. Verify that a new
   image does not reuse the preceding observation's context.
3. **Stop and park the full actor if parity fails, the time box expires, or
   standalone sampler p95 remains above 150 ms.** This is a proposed investment
   cutoff, leaving room under the existing 250 ms age limit; it is not a new
   live safety threshold or proof of sufficient in-game headroom. Do not extend
   leases, lower quality, or widen the attempt after a near miss.

If it passes, return to **one native-label adaptation proposal** using the already
admitted demonstrations and current calibration/timeline requirements. The
original full-policy runtime result remains valid for the unchanged path. A
cache success would only reopen feasibility: eventual evidence still needs yaw
versus the custom-head/zero baselines, retained buttons/pitch, and calibrated
practice-range target acquisition and combat outcomes. No paid fit follows
automatically from passing this probe.

## Why park the reader follow-up now

The [reader result](../evidence/idm-reader-support-20260928/report.md), `d6ff7a4`,
is honestly negative. Even a reader repair leaves V-Q replay coverage, cut
acceptance, angular scale and source admission before new labels become usable.
Preserve full03 and the frozen support artifact. Parking is a short portfolio
choice while resolving policy feasibility, not a conclusion that corpus
expansion is unnecessary or that IDM qualification must first prove live play.

Finally, [the 12.9 Hz result](../evidence/live-fps-20260928b/RESULT.md), `1f5ea5d`,
used the small legacy fallback with discarded outputs. It showed no visible
median FPS loss at a 240 FPS cap; it does not establish zero GPU cost, NitroGen
coexistence, or learned fighting. Continue the already-owned pose/calibration
repair independently. No new lane is needed.
