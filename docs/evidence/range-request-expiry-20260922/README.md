# Accepted request cancellation

Root accepts the independently reviewed request-expiry delta in
[the implementation note](../../lanes/range-request-expiry.md). An expired
request is consumed, released and recorded; learned range play may then keep
observing and act on a later fresh decision. Lost/stale proof, closed devices,
failed release or failed cancellation/origin persistence still stop play.
The 100 ms authority, 33 ms pulse, exclusivity and watchdog remain unchanged.

Independent reviewer: `learned-range`, reviewing root-written Controller/Loop
code, September 22, 2026 at 18:07 local. The reviewer first reproduced a release
record persistence defect; root reproduced and fixed it. Final review approved
integration with no remaining finding: 37 independent checks passed (17 owned,
eight additional reviewer controls, 12 adjacent). Both exact failing cases now
stop with zero later accepted pulses, while returned-release truth and original
failure metadata remain intact. Valid expiry recovery and isolated/all writer
failure controls pass. No native/model/perception imports or source edits.

Frozen raw pins verified by the reviewer before and after:

- Controller `08fe8a62463f5bebefde37b0f9c492d3754f7a7c2486984eeadfa905626a8a12`
- Loop `0316aecb16aae2e913297403f8c3dca908515784f4eab3904c825458a5ab30a0`
- Tests `1b4a305380a45d96baaeb225366c5f07f935f408e032a5ec5648552f1ec7522d`
- Note `22a2e14cbf8739b1278a29fbf9329488703c2c147fed2499bd608487f2064412`

Root additionally ran 369 integrated checks before the last persistence cases,
then the focused 41-case repair selection, and eight actual synthetic checkpoint
CLI/consumer/controller/log joins. Prior accepted source/runtime semantics and
unchanged input guards are reused. The independently accepted HUD work is separate.
Neither software result establishes a native cast, improved latency or policy
quality. Previous runs and consumed bindings retain their original outcomes.
