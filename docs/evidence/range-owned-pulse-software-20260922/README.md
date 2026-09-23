# Request start and owned pulse, September 22

The lead accepted the independent review of `request-start-owned-pulse-v1`.
A fresh start must commit before its original request/resource deadline; an
accepted pulse has a separate immutable nominal end at Controller acceptance
plus the calibrated press time. Phase and absolute session limits cap it.
Refusal, target loss and faults still cancel. This intentionally changes held
input authority without changing the learned label or prediction horizon.

Both root and independent reviewer ran 407 passing controller/loop/actuator
checks, with nine expected skips, followed by eight passing real synthetic
checkpoint-to-main/consumer/Controller/RunLog joins. The independent reviewer
also exercised 99 ms acceptance and 99.5 ms commit, return after the request
deadline but before the owned end, continuation followed by fresh Idle,
proof-time request expiry, original ammo age, return after pulse/scope limits,
and failed release logging. No concrete blocker remained. All nine candidate
hashes matched before and after those checks; [the receipt](review-receipt.json)
pins them.

The actual implementation contract and commands are in
[the Controller note](../../lanes/range-request-pulse-lifetime.md) and
[the caller note](../../lanes/range-owned-pulse-loop.md). Their pending-review
wording records the frozen candidate stage; this lead disposition supersedes
that stage without rewriting those reviewed bytes.

Only cached isolated runtimes, synthetic checkpoints and fake devices were
used. The historical C corpus test was not run. This proves software behavior,
not physical pulse timing, visible casts or model quality. Historical run
receipts remain unchanged. A native experiment requires a new genuine runtime
semantic decision, deployed manifests, effective setup and one-run binding.
