# v2 real two-app shakedown: PASS

Accepted library commit **ead3e6d9a3f19c22f27fae0c39102b3d0e2f6ee9**, release
**e7fb306cfb7fa3f7e9047b78ef85a4824071c5a29eb17d6c85957f8d03531823**.
Fit-review LAND, then herdr-lead acceptance at 02:44 CDT, September 28.
Exact installed reviewer SHA749d024adf11a2d7b5919388892e928490cbd4f5ca27a23b40acb27095ca1868;
lead sidecar SHAdc2d22976b6300e816d3f48220b5f2a275d61ba31f4101c4147a53ae640bd9dd.
Canonical installed paths are in acceptance-installed.json. No financial journal
was read, reset, migrated or written. No custom billing/deadline daemon ran.

## Observed behavior

| Arm | App / call | Native outcome |
| --- | --- | --- |
| Success | ap-HoraDCDZS8z6YDezc2jneo / fc-01M3KFNAJPFMFCX1T8P65JTYKS | Completed, reattached and all four artifacts verified |
| Timeout | ap-xV8lfwUWeVjvF5jfWjCl82 / fc-01M3KFNRDZYHARF4DN490B4PZR | Modal FunctionTimeoutError at 30s; complete epoch preserved |

AppCreates were at **07:46:20 and 07:46:35 UTC**, one per attempt, using the
accepted 15-second global gate. Both functions used the existing image and exact
native source mount, L40S / 8 CPU / 32 GiB, min/buffer0, max1, single-use containers,
retries0 and scaledown10. Startup180; native work120 (success) / 30 (timeout).
Explicit exploratory envelope: no p95 or scientific training claim.

Both original host observers were SIGKILLed after app/call IDs persisted (PIDs
70779 and 70780). Neither cloud call was cancelled or replaced. Native execution
continued without its driver. Fresh processes reattached to the original IDs with
`--observe-only`; no app.stop, no extra spawn, no daemon or retries were used.

The second arm initially queued for L40S capacity, but capacity arrived before the
first finished. Six authenticated inventory snapshots, 027 through032, show both
L40S containers simultaneously, spanning **16.433030 seconds** of observations.
This proves concurrent allocated execution, not a full-workload performance p95.

Success wrote its final artifact at1790581698.11781. First authenticated zero task /
zero-container observation followed **8.891023 seconds** later, within scaledown10.
Timeout is logged at **07:48:36 UTC**; first zero observation followed within
**6.990797 seconds** (log time has one-second precision). Both zero observations
still listed apps `ephemeral (detached)`.

Then Modal itself changed both apps to **stopped**, tasks0, containers[]: success
at07:49:21UTC, timeout at07:49:36UTC. final-native-inventory-no-stop.json proves
both states. **There were zero host app.stop calls**, including housekeeping.
The library's terminal() validator independently accepted both final proofs.

## Artifacts and checkpoint boundary

Success: completed.json plus all four declared outputs hash-verified via stages.load.
Complete epoch payload is9349bytes, SHAb7fdc773e3ea2cd9aadce1f1ac0aa5fc2614fe295bd624a5e45d50e11d473ab2.
It contains synthetic CUDA model/AdamW/RNG/epoch state. After restore, the next
stochastic CUDA output matched exactly. Timeout preserved its separately committed
complete epoch and checkpoint-verified.json; no whole-stage completion was fabricated.
Both checkpoint receipts were verified against downloaded payloads. Fresh local
destinations and a1MiB/file download bound were used; no dataset or sealed input.
This is synthetic RNG/receipt evidence, not parity evidence for the IDM scientific fit.
IDM's CPU interrupted/uninterrupted optimizer/order/RNG tests belong to05a61b.

Execution, collection and lifecycle remain independent: native timeout is FAILED
execution with a recoverable complete checkpoint; successful execution was collected
before teardown proof. Neither depends on a billing observation or current host boot.

## Spend and next consumer

Lead's manual bill check is8d40afc ($78.24 metered month-to-date). Authorized
shakedown forecast **$0.480482**, including0.10 overhead, below the $1 allocation;
there is no coded dollar cap in v2. As an additional manual conservative check,
the two app lifetimes total362seconds at the displayed one-second precision;
364seconds *0.000717888889 +0.10 = **$0.361044**. This deliberately includes idle
app time without containers. It is an estimate, not a provider invoice. Lead owns
the post-run billing record; this toolkit made no billing query.

Modal docs charge allocated/used compute and idle containers; functions scale to
zero without inputs. Thus a detached app label with zero containers does not itself
allocate compute (inference from those rules). Retained output Volumes remain a
separate storage resource; this report does not claim their storage is free.
[Billing](https://modal.com/docs/guide/billing),
[Scaling](https://modal.com/docs/guide/scale),
[Idle containers](https://modal.com/docs/guide/cold-start).

Lead and IDM owner notified: accepted v2 is operationally demonstrated. IDM owns
its separately authorized full03 relaunch, epoch-resume integration, stop/discard
audit and scientific evaluation. No further AppCreate is planned by modal-port.

Summary SHA**20c747bde473968c01b5cded8d2a8d47d007d6c74558ca3f5cb810c391cefd47**.
Mac originals: /Users/james/dev/range-bc-data/handoff/modal/v2-shakedown-01/.
Transport archive SHA9f17b4c1d58b664a2d2c2e058d2282df0094394f11f18c5d41a40fabd01cf7d3,
56801bytes; all112 transported files verified before this report was added.
