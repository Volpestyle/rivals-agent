# Encoder launch fixes after 1a9bcaf (2026-09-27)

These are NEW corrected copies for the next explicitly funded encoder launch. They
are not installed over any completed or running run. No compute is launched here.
Source: reviewed Mac `explore/encoder-historyoff-20260927/siglip/`; review receipt
SHA256 88314b57bac5a7dc233d930eea9d6a93f0f6f0bcec01444166157a66a93c1c7f.

- F1: corrected driver uploads the hash-pinned run-config.json beside code.tar and
  passes its expected hash. Worker verifies that hash, matching arm and explicit
  enabled/disabled history mode, records the actual config in its receipt, and
  derives the CLI history argument from it. Both modes are supported.
- F2: repository explore_chunks_eval.py records skipped_decodes on a persistence
  stop; it is empty after a full evaluation. The updated test checks exact names,
  equality and the disabled stop switch. The completed no-history pair ran all
  twelve conditions, so NONE were skipped; its frozen evaluation files are unchanged.
- F3: prepare_manifest.py writes the image ID, CUDA and package versions into the
  runner manifest, as well as the config and all launch-file hashes. It refuses
  to overwrite an existing manifest and launches nothing.

To consume: create NEW campaign/arm directories. Copy the unchanged reviewed
encoder_budget.py, encoder_lifecycle.py, explore_mounts.py, appcreate_gate.py,
lifecycle.py and vendored job_status.py from the named reviewed root. Use the two
corrected driver/worker files here. Set new app/output-volume names and the newly
authorized caps in the copied budget module. Use an explicit run-config.json
containing arm and history, and a launch.sh targeting only the new directory.
Build code.tar from the chosen landed source commit (including the F2 change).
Generate a NEW runner-manifest.json using prepare_manifest.py and that exact code
commit and caps. Recheck the manifest, identity and guard before any paid launch.
These copies deliberately preserve existing guard/resource behavior; they do not
supply authority, reserve a budget, or choose the next scientific recipe.

Image: im-FNjy4v5u4XYF29SBGvT0KD; Torch 2.14.0+cu130 / CUDA 13.0,
transformers 4.57.1, safetensors 0.6.2, huggingface-hub 0.35.3. Driver still uses
that immutable image. AppCreate remains the reviewed gate with cross-lane global
15-second coordination. Never execute copied budget defaults against an existing
campaign. No game_env.py or model download is introduced by these fixes.
