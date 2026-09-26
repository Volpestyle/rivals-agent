# Sealed takes, 2026-09-26 (VUH-1359, VUH-1353)

The sealing of James's 2026-09-26 recordings, with admission-review's (Codex) independent review:
- the test take 10-38-35 and its held 10-38-12 false start, sealed test in `data/human/sealed-denylist.v2.json` (439c80df; v1 57cfe01f unchanged);
- Gate 2 pair 2 (the whole 2026-09-25 19-28-51 file plus the 10-57-37 Hall of Djalia replay);
- the Heart of Heaven replay 11-10-08 registered for reader development;
- the left-turn calibration 11-26-48, which shows the yaw gain is direction-symmetric (mean +0.011 %).

The first review returned FIX. B1: a sealed identity was accepted in the calibration and evaluation lists. B2: a gate2 identity could be relabeled train when its row was absent.
v2 now carries allowed_split plus the four gate2 identities, and check_registry covers every list. The delta re-review returned LAND. Non-blocking:
`tally.py` still defaults to code-snapshot-86a1912, which refuses the gate2 rows; regenerate with `--snapshot code-snapshot-e7f5045`.

| File | sha256 |
|---|---|
| `admission-test-take-20260926-delta.md` | `b8209ba09c82f522cb9c36856016573089f6913cdf98a0fbcba90a05a966b990` |
| `admission-test-take-20260926.md` | `34ec2258030814d76ceba23ad037ec546f230962afaf5392f6abfc8c26a3599e` |
| `admission-test-take-20260926.v1.md` | `f58cfd10c3a606472b554cc272c92b010b1742453567ec884916d3a5ca782b86` |
| `brief-admission-test-take-20260926.md` | `9c579713da57514fef0b38122234d40c0cd36d3f6eeffebfe47ae6468daf0a14` |
| `review-admission-test-take-20260926.md` | `77426ee71fe577d976bf8591ed86dd202d0e814eebcb04abf5875c43db6a1c1a` |
| `review-admission-test-take-20260926b.md` | `4fd93c00011771c6741e5c631eb15b1c5b16fea46776e316a78c5f8bc6b1b013` |
