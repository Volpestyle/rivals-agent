# Evaluator check-in, 2026-09-28 17:15 CDT

**The intended change of direction is underway. No new model-performance result
changes the recommendation to retain full03 and pause further IDM refits.**
This check uses the new owner packets, current Linear comments and live Herdr
panes; no model run, cloud operation, capture or sealed-data access was performed.

Explore-policy's [native-policy feasibility packet](nitrogen/native-policy-feasibility-20260928.md)
landed in `b65e9d6`. Seven CPU action-contract checks passed, the full checkpoint
is authenticated, and native labels have correctly replaced IDM qualification as
the sizing prerequisite. These establish packing/masking properties, not physical
control or model quality. Full-sampler latency, measured peak memory and update
throughput remain unmeasured. The prepared probe retains sampler evidence even
if its synthetic update phase cannot fit, which separates deployment feasibility
from training feasibility.

IDM's [source-qualification proposal](../lanes/idm-yaw-source-qualification-plan-20260928.md)
preserves full03 and proposes at most five minutes of genuinely additional S6.5
footage, yaw only. Its first result would be a bounded reader/scale readiness
assessment, not a promise of qualified labels. Independent alignment validation,
source-use admission and Gate 2 remain real dependencies. The proposal identifies
a missing Quick Match replay rather than assuming the reader-validation family
is complete. Check existing receipts before requesting anything from James.

## The timing decision to preserve

The new checkpoint inspection finds `action_shift=3` and no recorded pretraining
frame rate. The pinned `nitrogen/cfg.py` describes this as actions skipped between
the observation and its target chunk; it is not a measured camera or model delay.
At the owner's declared 30 Hz interpretation, the first target would start
100 ms after the observation. Neither this interpretation nor eighteen output
rows proves real-time feasibility.

**Before native-label adaptation, state one observation/target/execution timeline:**
observation timestamp, target offset, action interval and measured output age.
Training, offline scoring and eventual execution must agree about which physical
interval each output describes. Do not automatically copy the three-row offset
into a new loader, apply its first action immediately regardless of age, or add a
100 ms wait on top of latency as though that were established compensation.
A small synthetic timestamp/edge example can check this boundary; it does not
require another corpus extraction or another model sweep. Preserve the existing
freshness and pad-lease limits.

The [NitroGen paper, section 2.2 and appendix B.1](https://arxiv.org/html/2601.02427v1#S2.SS2)
evaluated with the game frozen during inference and leaves real-time/asynchronous
deployment to future work. Its highlighted low-data transfer experiment used
30 hours (figure 7). These reinforce our existing rationale for sizing first and
retaining corpus expansion; they do not establish success or failure at our scale.

## Actual delay and advice to the lead

At inspection, herdr-lead is waiting on James's monitor question after reporting
no detected monitor. I have not independently established the hardware cause.
The live sitting has not begun. Its GPU hold also parks the sampler benchmark.
IDM's proposal is ready, but its 16:22 Herdr handoff was rejected because the lead
was already in that question UI. This is a delivery/scheduling delay, not a new
scientific failure; no additional training is indicated by it.

On resuming, consume the existing IDM proposal and choose the PC allocation
explicitly: finish the sitting if the display is available, or release the GPU
to the already-prepared sizing probe while the sitting waits. The independent
Mac qualification decision need not wait for display availability. This advises
the existing owner decisions; it does not release either machine or approve a run.
No extra review of unchanged receipts or replacement workstream is needed.

The lead's question UI was left intact. Explore-policy relayed this advisory once
through its existing trusted Swarm connection, receipt
`0375549f-aecf-4173-bd04-828f96f67d41`, to lead actor
`c302f78b-5125-4d15-91cb-8e2c8cf04b80`. This evaluator still has the legacy MCP
interface and cannot directly submit into that blocked pane. No acknowledgment
or additional work was requested from the lead.
