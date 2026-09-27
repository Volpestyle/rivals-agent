# Match communication bindings

Owner: idm-owner, VUH-1353. James's clarification relayed by the lead, 2026-09-27.

| Match notes | Non-gameplay bindings |
|---|---|
| -5, 20260927T052001-827Z-150600-5 | `G` = map interact; keyboard `4` = thank-you communication ping, used for heals |
| -7, 20260927T053838-153Z-150600-7 | `G` = map interact; keyboard `4` = thank-you communication ping, used for heals |
| -8 | `G` = map interact; keyboard `4` = thank-you communication ping, used for heals |

James states that `4` opens no menu, consistent with frame-review's no-overlay observation reported by the lead. **No cut is needed for this key.** This does not remove the existing cuts for mouse button 3's held ping wheel. Admission-codex owns the corresponding admission notes; the clarification was sent directly to that owner. Frozen receipts, accepted intervals, tables and target bytes are unchanged.

The current IDM gameplay vocabulary excludes both keyboard `4` (`key:5:0`, VK52) and `G` (`key:34:0`, VK71). The target builder counts only physical IDs present in the admitted gameplay bindings. The actual accepted -5a1 target header was checked: neither key is mapped. No -7/-8 target or media payload was inspected, and neither match is added to the approved refit roster. Keyboard `4` is distinct from `mouse:4`, which remains the existing goh_targeting gameplay binding.

Synthetic regressions exercise make, repeat and break events while preserving camera motion, plus simultaneous movement and mouse-button-4 gameplay presses. They verify that thank-you/map-interact keys add no gameplay press, release or hold labels and do not themselves remove the two target intervals. No target-builder or vocabulary implementation change is needed.

For the later match stage, thank-you pings and the ping wheel belong to a future **team comms** action family. Their timestamps remain in the original input logs. This note records the intended future scope; it creates no current semantic label, model output or live-game action.
