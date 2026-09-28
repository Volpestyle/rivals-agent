# Two-app v2 shakedown (not yet launched)

Authorized by herdr-lead after fit-review LAND, less than $1 total. No training or
sealed data. Existing prebuilt image im-FNjy4v5u4XYF29SBGvT0KD plus hash-inventoried
native source mount; no image build. Two fresh named apps and output volumes,
a fresh empty input volume, rivals/volpestyle, L40S/8CPU/32GiB, retries=0,
single-use containers, min/buffer=0, scaledown=10. Native AppCreates >=15s apart.

Diagnostic A: startup180, native work120, cleanup60 seconds; synthetic CUDA
checkpoint and RNG restore, then sleep90 and publish completed stage.
Diagnostic B: startup180, native work30, cleanup60; same checkpoint then sleep90,
so Modal timeout should interrupt it. Explicit exploratory timing, no p95 claim.
At the prior verified all-resource rate .000717888888889 USD/s, two full startup +
work + 10-second idle envelopes total 530s = $0.380481111; allowing $0.10 storage
and overhead gives $0.480482 forecast. This is a manual estimate, not guard code
or an exact provider billing guarantee. Lead checks billing and estimate before
launch and records billing afterwards. Existing native workspace cap remains $200.

Launch two host drivers, preserve app/call IDs, then terminate only those owned
host observers before calls finish. No cleanup process or deadline daemon remains.
Fresh read-only inventory records zero containers and each app's actual state,
without app.stop first. Reattach in fresh processes by call ID: A succeeds with
hash-collectable completed outputs; B returns native timeout and preserves its
complete synthetic epoch receipt. Record native timeout/container exit times and
scaledown latency, then scoped app.stop housekeeping proves stopped/zero containers.
Download small artifacts into fresh destinations and verify receipt hashes.
Checkpoint CUDA RNG restore is diagnostic only, not IDM training parity evidence.

Modal documents paid allocated compute and idle container charges, with scaling
to zero when there are no inputs. Zero-container app labels do not themselves
allocate compute (inference); retained storage remains billable separately.
Sources: https://modal.com/docs/guide/billing,
https://modal.com/docs/guide/scale, https://modal.com/docs/guide/cold-start.
