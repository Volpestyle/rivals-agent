"""The inverse-dynamics model (VUH-1353; docs/lanes/inverse-dynamics.md, F3).

    frames  the frame store the model reads: grey frames at >= 448 wide and native HUD crops, per session
    model   stacked frame differences over the +-8-interval window through a small conv; the HUD crops for edges;
            per-action press logits and camera yaw/pitch with a log-variance
    train   masked loss, the deterministic trainer, checkpoints, the predictor (abstentions) and Gate 1 evaluation
            through policy.idm_eval, and the report writer

Targets come from policy.idm_targets (rivals-idm-targets-v1). Nothing here decodes video or trains on real data.
"""
