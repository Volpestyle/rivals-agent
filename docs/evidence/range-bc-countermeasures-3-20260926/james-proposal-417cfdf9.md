# VUH-1346 comment 417cfdf9 (James Volpe; written by blog-writer on his behalf), as updated 2026-09-26T20:31:51Z

**Proposal for round 3 (not a decision yet, round 2 carries on as pre-registered):** stop asking the policy to learn to see from scratch on 3 h of one player, stop asking it to read the HUD from pixels, and stop letting idle frames dominate the loss.

**1. Pretrained frozen scene encoder.**
- Swap the three from-scratch IMPALA encoders for a frozen pretrained vision backbone (DINOv2-class, or a video model), and train only the head + LSTM on our data.
- Why: 180 train minutes is tiny for learning vision from random init. The frames carry weak initiation signal (history-blanked press-F1 `0.079`), so the history shortcut wins. That's the copycat setup (Wen et al. 2020, arXiv 2010.14876). Stronger frame features make the shortcut less attractive, and the frames-only arm becomes a fair test (arm B in round 1 was really a normalisation bug, mean |f| 29, max 738).
- Pair with dropping or weakening the prev-action input. VPT (arXiv 2206.11795)'s policy takes no action history at all: `MinecraftPolicy.forward(ob, state_in, context)`, images + recurrent state only, with a causal Transformer-XL over past frames (App. E.1).
- VPT is not precedent for the pretrained part. Its encoder trained from scratch (fan-in init, App. D.1), which worked because it had ~70k h of IDM-labelled video on top of 1,962 h of contractor data. The pretrained-backbone argument rests on our data size, not on VPT.
- Costs: weights hash pinned in the preregistration, and MPS/CPU determinism re-checked for the new backbone. Nobody's measured whether general features transfer to Rivals, so that's a question to answer with data, not an assumption.

**2. HUD as reader values, not pixels.**
- Feed the policy the HUD readers' outputs (webs, per-ability ready / charges / cooldown, HP, ult) as a small vector, in place of the 80×200 HUD crop.
- Why: the readers already work on both layouts (VUH-1294), so pad vs M&K stops mattering. No `hudmap` pixel transform, no seams, and no "can a from-scratch CNN read digits" problem. It replaces the pixel-parity question the no-HUD candidate exists to avoid.
- P2′ still matters. It becomes a check on reader parity (low webs / spent charges / cooldown coverage from a fresh pad capture), which is what it already measures.
- The recorded frames need one reader pass to produce the vectors, same pinning rules as the cache.

**3. Null-frame filtering.**
- VPT hit our collapse without any action history (App. E.2): humans take the null action 35 % of the time, their BC model took it "often upwards of 95 %". The fix was dropping null-action frames from training. They compared filtering runs of 1, 3 and 21 consecutive nulls against none, and filtering "generally helps, increasing all crafting rates".
- So idle-dominated data is a cause next to history, not only through it. Today we reweight presses (`pos_weight`, capped at 20) but train on every idle step, and holds are plain BCE.
- Cheap to try: filter or downweight runs of ≥ k fully idle steps (no key, zero camera class) from the train split, with k pre-registered. Dev and validation stay unfiltered, so the self-fed checks still judge it against real play.
- Worth noting it pulls the opposite way from round 2's known-idle corruption, which adds idle history. If round 2 fails, this is the natural next arm.

**Also open, separate from the above:** the HUD arm's +0.05 self-fed macro press-F1 margin ... amend it to "P2′ passes and it's not worse" when that draft is finalised, before any real-fit result exists.

Refinement by James in chat (2026-09-26 ~15:45 CDT): "fully idle would be NOTHING pressed at all": no key or button and zero mouse counts on both axes.
