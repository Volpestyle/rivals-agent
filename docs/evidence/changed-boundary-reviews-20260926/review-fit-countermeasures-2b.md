LAND

Independent fit-review delta review, 2026-09-26: round-2 F1 is resolved. No blocking findings. Earlier accepted checks and their qualifications remain in review-fit-countermeasures-2.md; this review covers only the sampler endpoint fix.

Verified LF SHA256:

- policy/range_bc/train.py: 4c48a86558edbeb240c55a627cfa45b7c1b0a2c4a8be3ff3e40f19323369327c
- tests/test_range_bc_torch.py: e8d3e8d8f13b6dbcee2443609984564cb46b5aeaae22d5e14f3430c0ac547d4f
- fit-countermeasures-2-code-2.md: bcd1e395b6c90608c508893f80233f33496ad02b379c50f29e5e47cffc61c6a7

**F1 resolution.** train.py:453 computes hi=T-1-K, uses burn-in as lo where possible and otherwise 1, and refuses hi<1. self_rolled_forward at :466 samples that inclusive interval. For every admitted start, s+K<=T-1, so the unchanged rolled_history loop executes K times and writes precisely s+1..s+K. fit at :499 validates the range only when self_roll is enabled, before seeding, model construction or training.

**Independent validation.** The new boundary test and existing closed-loop executor-reference test passed locally: 2 passed, 42 deselected, using the fit-review UV environment, CPU, no pytest cache and a temporary output directory. Additional wrapper probes forced torch.randint to the minimum and maximum endpoints, used a sentinel previous-action vector and inspected the trained pass's actual history input for both sequences:

| T | K | Start bounds | Written steps at minimum | Written steps at maximum |
|---:|---:|---|---|---|
| 96 | 32 | 32..63 | 33..64 (32) | 64..95 (32) |
| 96 | 1 | 32..94 | 33 (1) | 95 (1) |
| 96 | 60 | 32..35 | 33..92 (60) | 36..95 (60) |
| 96 | 70 | 1..25 | 2..71 (70) | 26..95 (70) |
| 96 | 94 | 1..1 | 2..95 (94) | 2..95 (94) |

All other history positions retained the sentinel. The new test verifies helper and fit refusal for K=95. A separate probe verified fit's refusal before Policy construction and with the torch RNG state unchanged.

**Mutation.** Replacing self_roll_starts in memory with the old hi=max(1,T-K) implementation caused the new test to fail its range assertion at tests/test_range_bc_torch.py:944: actual (32,64), expected (32,63). I required pytest's TESTS_FAILED exit code 1, not merely a nonzero exit; this was a genuine assertion failure. The independent wrapper probes also verify use of the helper, beyond testing its returned numbers. No code on disk was mutated.

**Delta and default compatibility.** Reversing only the rule-string edit, added helper, wrapper sampler replacement and conditional fit guard reproduced the prior train.py LF hash 693f12a60cdf14fa29c321c95c56d23075b03e50a2af337d6e9043d19507890b exactly. Removing only the new boundary test reproduced the prior test-file LF hash 85ee15007c9e107f3d7a2e036d596f3b5ac8aad1e0567d1d9c3d8827c5da6aff exactly. Thus no other bytes changed in either reviewed file. The new guard is skipped when self_roll=0; the rule string is recorded only for enabled self-roll. Default execution, RNG draws, checkpoint metadata and report config remain unchanged by this delta. Proofs (a) and (b) stand with the prior review's distinction between identical checkpoints/existing report blocks and intentional config additions; no corpus retrain was repeated.

**Note — hand-back arithmetic only.** The hand-back's exact-writes bullet describes K=32, s=63 as “33-95”. That individual rollout writes 64..95; 33..95 is the union of possible replacement positions across starts 32..63. The code, updated rule and test are correct. Correct that wording in any subsequent hand-back or pre-registration explanation; no code change or additional review is needed for this typo.

No checkout edits, commits, game input, Mac jobs, Linear writes or sealed-data reads. This is a new review file; earlier reviews were preserved.
