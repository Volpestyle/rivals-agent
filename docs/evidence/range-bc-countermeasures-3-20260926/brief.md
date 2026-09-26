# Brief: round-3 design + pre-registration draft (fit-review, Codex gpt-6-astra high), 2026-09-26 17:40 CDT

**Owner:** fit-review (drafts). **Reviewer:** admission-review (Codex, independent of the draft). **Lead:** herdr-lead
decides and approves. Record: VUH-1346. James asked (2026-09-26): "When round 2 reads out, scope round 3 as a design
with preregistration and independent review, and reply on the issue." The lead posts on Linear; you don't.

## Where we are
- Round 1 (`docs/evidence/range-bc-countermeasures-20260926/`) and round 2
  (`docs/evidence/range-bc-countermeasures-2-20260926/`, landed 1e47ea8): **neither works**. The self-fed policy
  stays near-idle, and every self-fed camera fails S3. E (sequential self-conditioning) is the best so far: self-fed F 0.072,
  presses at 27-42 % of the human rate. D lifts onset recall but presses at 1-5 %.
  Round 2's "Neither works" row names these candidates: full rate P=1.0, D+E combined (a code change), and a normalised
  frames-only arm.
- James's proposal: VUH-1346 comment 417cfdf9. Read it in full (the lead has it; the text is in
  `handoff/round3/james-proposal-417cfdf9.md`). Its candidates:
  1. A frozen pretrained vision backbone (DINOv2-class) in place of the from-scratch IMPALA encoders. Features are
     cached once, then the head and LSTM train. VPT's encoder was trained from scratch, so VPT is no precedent for this;
     the argument rests on our data size. Frozen pretrained features for control are an empirical question here.
  2. Drop or weaken the prev-action input. VPT's policy takes no action history; it has recurrent memory over frames only.
     Test both dropped and weakened, not one assumed.
  3. HUD as reader values, not pixels. The readers' outputs (webs, per-ability ready/charges/cooldown, HP, ult) become a
     small vector, with an explicit unknown flag per field, never zero for unknown. The reader-accuracy spot-check on
     training frames is part of the pre-registration. This removes the hudmap pixel-parity problem; P2′ becomes the
     reader-parity check.
  4. Null-frame filtering (VPT App. E.2). In train only, drop or downweight runs of ≥ k **fully idle** steps.
     Fully idle means no input of any kind: no key or button held or pressed, and zero mouse counts on both axes
     (James's definition). k is pre-registered; dev and validation stay unfiltered. It's a target-side fix,
     complementary to D/E's input-side fixes.
- Lead decisions already made (record them; don't reopen):
  - The real fit, when it comes, is **no-HUD only**. The pixel-HUD arm is dropped, and the HUD returns in round 3 as
    reader values.
  - The +0.05 HUD margin becomes "P2′ passes and not worse beyond the seed range".
  - Codex does the drafting and review; Opus only where the lead asks.
- The corpus is now 180.57 train / 15.58 val min, admitted. Rounds 1-2 used the 80.5-min interim data for comparability.
  Decide, with reasons, which data round 3 uses, and keep an interim-comparable control if you switch.

## Deliverable
`handoff/round3/round3-design.md` (a design doc, with the rejected alternatives and why) and
`handoff/round3/fit-countermeasures-3-prereg-draft.md`. The draft uses the same shape as rounds 1-2: the question, the arms,
settings fixed now with reasons, the unchanged S1-S4/K rules (or an explicit, argued change), the outcomes table and what
each means for the real fit, the judge checks (the judge is written and tested on synthetic inputs before any result),
the run plan with a Mac time estimate, and the limitations.

Be ruthless about Mac time: the M5 Max trains one arm at a time (~1-1.5 h per seed at 80 min, ~2× at 180 min).
Prefer the fewest arms that separate the hypotheses:
- Is the collapse a feature-strength problem? (Backbone.)
- Is it a history-shortcut problem? (No or weak prev-action.)
- Is it a target-imbalance problem? (Null filtering.)

Name which combination is the headline arm, and which are controls.

State the code changes each arm needs, with owners and review gates, so the lead can dispatch them:
- the backbone feature cache and its pinned weights hash;
- the null-filter;
- the reader-vector cache;
- the prev-action option.

Also cover these, and don't hand-wave them:
- MPS determinism for a new backbone;
- live inference latency on the PC GPU for a backbone: note it as a pre-pilot measurement, not a round-3 gate;
- how any reader errors propagate.

## Rules
- Design only: no training, no code edits, no commits, no Mac jobs. Read the repo freely (`docs/lanes/end-to-end-fit.md`,
  `policy/range_bc/`, both evidence folders, `docs/learning-plan.md`).
- Sealed or test data is never named for tuning. Validation stays untouched until a real fit.
- Hand back with a one-paragraph summary and both files' sha256.
