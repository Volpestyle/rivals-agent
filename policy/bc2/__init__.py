"""Step-2 learned range policy: frozen NitroGen features plus explicit ego-motion from consecutive frames.

`data` turns step tables and frame caches into per-session arrays, `features` adds frozen tower features and small
grayscale motion frames, `model` is the policy, `train` fits and evaluates it on whole held-out sessions, `cloud` runs
both on Modal. `policy.live_policy` loads the resulting bundles. Findings: docs/lanes/policy.md.
"""
