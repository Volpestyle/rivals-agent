# Receipt authority refresh after -12 acceptance

Owner: idm-owner, VUH-1353. 2026-09-28 UTC (2026-09-27 CDT). Metadata only.

Admission-codex landed `17dff14c3df5337002ba4d74425f8fe47aac1921`, adding `docs/evidence/idm-match-admission-061900-20260927/receipt/match-admission-061900.accepted.json`. Verified raw SHA256: `9f4bee42649f18d5e72db3729c1d4d94092e9a2cff54e4198d1e410edb23905e`, session `20260927T061900-143Z-150600-12`. This consumer refresh does not itself admit data.

The authority now has twelve canonical members covering all eight accepted night matches and the historical revocations. Index LF SHA256: `4c93196e14d04ee6a7d2d75d9e35e632539f2ced45b6b677e65aed1ef7aa1f87`. All eleven prior pins, both revocations and enforcement logic remain unchanged. Production code changes only the index constant. The regression adds -12 metadata while requiring the selected matches to remain exactly -4a1/-5a1/-6.

The refit remains **eight TRAIN ranges plus -4a1/-5a1/-6**. No -7/-8/-10/-11/-12 payload is read or included. The active upload, its manifest and frozen runtime11 stay unchanged. A fresh runtime12 requires independent LAND on this metadata delta before use. Admission reports the night set totals 45.882914832533334 counted minutes; that total is not this refit's match cohort. V is the existing melee binding; no vocabulary or runtime action change is made.

Final lead allocation remains $8.25: setup/storage $1.65, probe $0.40, full $6.20 with 7,800 work seconds, within IDM $25. No additional fit or retry. Manual CLI deletion of the exact input volume after the refit report remains required; automatic deletion was dropped.
