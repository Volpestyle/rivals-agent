# Corrected -5 targets, 2026-09-27

Owner: idm-owner, VUH-1353. Table-only preparation; no training or video decode.

The lead authorized the new denylist pin after admission verified it in 946a243.
Independent metadata comparison here checks the old LF hash against bcf5495,
checks the new LF hash, and proves all seven old entries and all other metadata
are unchanged. Only sealed test 20260927T195110-265Z-152960-1 was appended.
No sealed original, logger or frame was opened, hashed or copied.

The consumer pin is now
`09e8b9d350c89eb41c1581e1bce47548bfb855bca5805cf2e65955b9b23597b5`.
The existing builder authenticated accepted-a1 receipt `94701525132536f5794b4fefd9e06e6bdecdccb1f70c8bef0589a3b6af02c216`,
corrected steps `2c25a3fc96fb7e5a3ec41b173e958b79fd14e76293b09ad9d4c842f2de11dcf8`
and demo `f0fa88940e7190bd5ca74b083e2e790d814bdf20e705370a9eab3ef5c0f95d79`.
It built and reloaded the new target file under
`data/idm/cloud-20260927/match5-a1-targets/`.
Historical target files and Mac tables remain untouched and must not be consumed.

Target SHA256: `bdb36216f6017ba345949c55d9a2874c2c08570739829150fd5b9ca1d07f2ebd`.
31,704 target rows, 20,534 eligible: exactly twice the corrected 30 Hz table's
15,852 rows and 10,267 eligible rows. Accepted duration remains 342.399986311 s.
Job `idm-match5-a1-targets-20260927-attempt2` finished done; no paid hold.
The preceding denylist refusal remains recorded as failed; its checks were not bypassed.

Verification: `uv run pytest tests/test_idm_targets.py tests/test_idm_camera_demo.py -q`
passed all 36 tests. The raw JSON receipt hashes are:

- denylist verification: `f3f823e2d7a160bba1c1c8da261609a4979ed268288e8c633dd833385001a401`
- target receipt: `7c876351cecac8403cc8b28de3215eede70e32438779bdb369e0a05753dadb76`

Next: move corrected small artifacts to a fresh Mac a1 path, reusing the already
verified original. Native store decoding still waits for the sitting hold to end.
The three missing range stores remain approved; -4 remains held, so the expanded
refit trigger is not yet met. No validation or Gate 2 result is claimed.
