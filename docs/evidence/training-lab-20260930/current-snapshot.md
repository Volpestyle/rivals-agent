# Current result snapshot · 2026-09-30 15:59 CDT

This supersedes the result-data portion and screenshots of the initial
[deployment record](README.md), whose code, tests and single restart remain
unchanged. Live URL: <https://jamess-macbook-pro.tailb90f24.ts.net:9443/>.

Final source reconciliation found the RL owner's corrected audit (`fe1d795`):
BC had zero hits/KOs; RL had **one hit, zero KOs and a fall**. The raw
`curve.jsonl` reported three false hits, and those false rewards were used by
the live updates. The board now cites `rl/out/rl-sitting-20260930-01/episodes.json`,
labels the sitting as plumbing only, and includes the existing corrected event
GIF. The requested original KO curve remains valid (all zero), alongside the
takeover check sheet. The reward-reader entry also carries the corrected 0.969
recall instead of silently retaining 0.981.

Only the small curated JSON and additional GIF were copied. The JSON is read
on the next metadata scan, so **no second restart** was needed. Its prior bytes
were backed up. The deployed `/api/status` returned the corrected audit text;
local and Mac JSON/GIF SHA-256 values matched. [data-update.json](data-update.json)
pins this update and the current screenshots. Sixteen image copies are now
allowlisted, all with source paths, sizes and hashes in the projection.

Current screenshots: [desktop, 1440 px](desktop-current.png) ·
[phone, 390 px](phone-current.png). Both were captured again from the deployed
HTTPS URL after the correction. All seven visible media elements decoded, no
JavaScript errors occurred, and neither layout overflows horizontally;
[browser-check-current.json](browser-check-current.json) records this check.

Footage's viewer prerequisite landed as `42538da`. Its owner reported 51 tests
and Ruff passing, plus live v2-cd playback/strip and tailnet POST-to-render v2-a
playback passing after this lane's single restart. This lane independently
checked the board/index/span GET routes and its 30 focused board tests. No
viewer implementation was edited or committed by this lane.

Delivery is complete; acceptance and any tracker transition belong to the new
lead, w2:p3X. The dispatch supplied no dashboard issue identifier, so no separate
issue or duplicate project result was created. Results/billing remain explicit
dated snapshots; they are not a continuously recomputed evaluation or invoice.
