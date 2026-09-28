# Receipt authority refresh after -11 acceptance

Owner: idm-owner, VUH-1353. 2026-09-28 UTC (2026-09-27 CDT). Metadata only.

Admission-codex landed `310d78e21417367f064d87d664d331979e92edd6`, adding `docs/evidence/idm-match-admission-061107-20260927/receipt/match-admission-061107.accepted.json`. Its verified raw SHA256 is `c37d7ff11c67224005cb865f335b7798c877ec260e02a8696bbe59e687843a5d`, bound to session `20260927T061107-953Z-150600-11`. This consumer refresh does not itself admit data.

The complete authority has eleven canonical members. Index LF SHA256: `f8b574f97483605807867014e85676a4f6e9391bdcd7c25c2da800a38627645e`. All ten prior raw hashes, both historical revocations and enforcement logic remain unchanged. The production code delta is the index constant only. The regression adds -11 metadata while requiring the selected matches to remain exactly -4a1/-5a1/-6.

The expanded refit remains **eight TRAIN ranges plus -4a1/-5a1/-6**. No -7/-8/-10/-11 payload is read or included. No -12 receipt exists in this bundle. The active upload, its data manifest and frozen `runtime-authority10` remain unchanged. A fresh eleven-member cloud runtime may be prepared after independent LAND on this admission-consumer delta.

The lead's final allocation is **$8.25 within the unchanged $25 IDM lane**: setup/storage $1.65, probe $0.40, full attempt $6.20 with 7,800 work seconds. Automatic input-volume deletion was dropped. After the refit report, check the exact input volume ID/name using `modal volume list --json`, delete that volume once using the CLI, and retain a deletion receipt. This metadata refresh authorizes no additional fit, retry or data inclusion.
