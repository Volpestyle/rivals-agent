# Expanded IDM full03 launched with epoch recovery

EXPLORATORY, idm-owner / VUH-1353. Lead GO at 02:52 CDT on 2026-09-28 followed verified v2 installation, real shakedown PASS, the evaluator audit, and offline epoch-resume implementation 05a61b4 (105 tests passing).

One RPC created **ap-S6lLYCw0bpGcPfFhcMyLgy** at **2026-09-28T07:56:46.807216Z** (02:56:46 CDT). Call **fc-01M3KG8EMEDPHPJMGVTGN5KZV1** is detached; the Mac host observer PID was 81578. The creation window was released at +15 seconds and both IDs/time were sent to herdr-lead. No further AppCreate is planned. The first provider observation showed one active container, starting at 07:56:54Z; this is execution evidence, not scientific success.

Spec SHA256 `a30d4f55a395a014b816734076c211e37137b8ac98e162dd5ed49d61df5e874f`. Native timeout **36,310 seconds**, measured total-pipeline projection 27,930.558779 seconds with 30% margin, including roughly 6,692 seconds of post-fit inference. This is an accepted extrapolation, not full-fit p95. The native provider controls queue/startup; queueing alone does not imply a data failure or authorize a replacement.

## Frozen execution and data

Accepted guard v2 is ead3e6d / release `e7fb306cfb7fa3f7e9047b78ef85a4824071c5a29eb17d6c85957f8d03531823`. Installed reviewer SHA `749d024adf11a2d7b5919388892e928490cbd4f5ca27a23b40acb27095ca1868` and lead SHA `dc2d22976b6300e816d3f48220b5f2a275d61ba31f4101c4147a53ae640bd9dd` were verified. The shakedown preserved CUDA checkpoint artifacts after observer death and native timeout, with both apps stopped and zero containers without host stop calls. Its proof and summary are retained here.

The new source packet contains 191 files, with 190 under the native cloud mount; SDK 1.5.5 verified the exact source closure. It uses existing image `im-FNjy4v5u4XYF29SBGvT0KD`, without building an image. Epoch adapter 05a61b4 is combined with the unchanged accepted authority12/source base. Payload manifest SHA `e6eec4f528643f0cbdd0857e075b420a087f387fe77b9302e23e3b754377e93f`; source inventory SHA `93c36a60a75e8b80bcfbae9d9c972c69998634edd85655d887684f5da98b3e93`.

The retained input volume **vo-PnBxKAp9G4Y8nNwfBOgrdU** / `rivals-idm-expanded-20260928-01-inputs` was authenticated and remains read-only. The existing upload receipt, run-manifest hash, 13-source roster and 39 store-file sizes were verified before launch. There are exactly eight TRAIN ranges plus current -4a1/-5a1/-6 (181.89 minutes), and the two original range-dev sources. No extra match, sealed, test or archive source is included. Scientific recipe hash `fa4c98b31a34187480f378f305da282daf91ab662ac9a83eed597862c29d2dcb` is unchanged: seed 0, three epochs, existing camera/legacy press, TRAIN-only calibration, real/zero controls.

Fresh output volume **vo-dpykVEKfIL22lf5pWsMeQA** / `rivals-idm-expanded-20260928-full-03-outputs` belongs only to this attempt. The first diagnostic callback performs actual admission/mount/platform preflight before native pixels are copied. Generic v2 staging then copies and verifies 113,401,840,789 bytes onto local disk, preserving source-relative paths. Native FrameStore verification remains enabled. No random training reads come directly from the Volume.

The fit descriptor injects output `Volume.commit` and the strict epoch validator. Model, AdamW, RNG, order/cursor and step state are published every epoch, payload before receipt, preserving previous checkpoints. Epoch 1 is independently scoreable. Fresh launch has no prior checkpoint because full02 produced none. Complete epochs permit recovery under an authorized invocation; partial checkpoint bytes never do. The configured invocation still targets three epochs.

There are no custom runtime billing, ledger, hold or work-deadline gates and no input deletion lease. The lead checked metered spending at $78.33 and projected the weekend at approximately $104.62 with full03, below the $150 notification threshold; IDM lane allocation is $50. These are lead planning records, not coded dollar guarantees. The provider's native timeout and workspace limit govern running work.

## Observation and remaining delivery

PC watcher PID 82416 uses the pinned `probe-full03.zsh` and `observe-full03.py`. It runs BelowNormal, polls metadata and validates completed epoch artifacts by output ID, and will notify idm-owner at epoch 1 and provider-confirmed terminal/zero-container status. SSH/status/notification failures retry without stopping work. The read-only observer initially lacked PYTHONPATH for the provider subprocess; this was corrected before arming it. No paid worker was affected. The watch's latest observation is under `data/idm/cloud-20260927/full03-watch/latest.json`.

All 21 original collected launch artifacts matched their transferred hashes. The initial collector compared the pretty-printed spec to the guard's canonical serialization byte-for-byte and refused; the corrected collection retained both raw files and verified parsed equality. Both attempts were metadata-only. The successful archive SHA is `f62a2f61d316f1287b32b153141469ad9a30ef8ff3dc0ee8e5b2ae5e686dcdd9`. `hashes.json` pins the original collected artifacts; helper scripts and this report are added separately.

Next: report the first verified epoch checkpoint to herdr-lead. After terminal execution, collect each valid checkpoint/stage independently of host summary or billing state, prove teardown, and compare camera error to baseline `bce156fc` (old MPS versus new CUDA disclosed) and press precision/recall/coverage to `dd09f3b3` on matched dev rows/scoring with real/zero controls. No accuracy, Gate 2 or larger-corpus labeling claim exists at launch. Inputs remain retained until a complete report and the authorized manual cleanup condition.
