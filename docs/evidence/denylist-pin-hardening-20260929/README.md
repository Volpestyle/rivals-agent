# Denylist pin hardening ? 2026-09-29

Owner: admission. Review handoff to herdr-lead, who routes independent live-review.
This packet records a produced source delta, not acceptance or permission to run it.
Landing requires LAND. No corpus, media, intake, transfer, decode or compute job ran; spend $0.

## Exposure and change

**steps and cm3 authenticated upstream, and the defect was re-reading unverified bytes.**
Their direct calls to intake omitted its expected pin (`steps.py:207` and `cm3_run.py:249`
before this delta). The core intake loader also let a direct caller omit the pin or
explicitly pass None and skip authentication. There is no breach claim.

- `agent/human_intake.py`: the expected pin is a required keyword. None, empty,
  malformed and non-string pins fail before opening the denylist. A mismatched
  64-hex pin fails before JSON parsing. One read supplies both authentication and
  parsing, using LF-normalised bytes. Uppercase and lowercase hex digests work.
- `policy/range_bc/steps.py`: forward the caller's pin to intake instead of hashing
  the file upstream and invoking the unpinned intake reader. Keep the fixed default.
- `policy/range_bc/cm3_run.py`: preserve the context reference check, then explicitly
  supply `steps.DENYLIST_SHA256` to intake before registry or payload access.
- `policy/idm_targets.py` already forwards its fixed pin to intake and needs no edit.
  Its default and explicit invalid-pin paths are covered by the new synthetic tests.

No auto-repin, bypass switch, embedded replacement denylist or changed denylist constant.
The lead clarified that no-argument wrappers keep their fixed default: they authenticate.
Omission at the core reader is an error; omission at those wrappers supplies their constant.

## Caller and loader audit

Current admission/IDM entry points in agent/, policy/, scripts/ and the maintained
`data/human/sessions/*.py` drivers were searched for denylist reads and calls.
The two omitted-pin direct intake callers above are fixed. No explicit None caller
was found among maintained production code. The IDM and transcode wrappers and
intake_session, assemble_session, restep_session, match_admission, tally and
relocate_session already pass explicit pins. Current wrapper callers remain valid.
Historical code under data/ and docs/evidence/ remains untouched; the full retained
loader path list is in [excluded-loaders.json](excluded-loaders.json).

**Explicit uncovered boundary:** `policy/range_bc/idle_sidecar.py:66` (`authorize`)
loads the denylist via `small_json` without authentication. By the lead's decision,
round 3 is parked permanently and this boundary is outside this fix. It must be fixed
before any round-3 or sidecar training use. This packet does not claim every reader
in the repository authenticates its input.

The three stale `439c80df` consumers remain unchanged and fail closed:
`scripts/transcode_recording.py`, `data/human/sessions/tally.py`, and
`data/human/sessions/relocate_session.py`. Updating these pins is out of scope.
Frozen `code-snapshot-*` implementations and all other historical retained sources
remain unchanged, including historical omitted-pin calls; use their recorded commit
and recorded inputs to reproduce those runs, never silently combine old snapshots
with this new core API.

## Verification

63 selected synthetic tests passed (60 new parametrized cases and 3 existing intake
regressions). [verification.json](verification.json) records the exact command and
results. Coverage includes omitted/None/empty/malformed/mismatched core pins,
invalid-pin refusal before any file access, mismatch refusal before parsing and
registry access, LF and CRLF controls, uppercase pins, wrapper-default tamper
refusal, one authenticated read, sealed-ID/hash refusals and valid controls.
The transcode wrapper is exercised only as a loader with a synthetic explicit pin;
its stale default is unchanged and no transcode operation runs.

The cm3 check executes the actual `check_sources` function extracted from its AST,
with synthetic context and stubbed dependencies. It verifies pin forwarding and
refusal before registry access; it does not validate the torch runtime, training,
receipt authentication, or a real cm3 launch. Existing intake regressions cover
registry sealed-ID/hash protection, CRLF pins and sealed step writing.
Compile checks and path-scoped `git diff --check` passed. No broad suite ran.

## Historical source records and deployment boundary

The lead authorized this source delta: these matching hashes describe past runs;
they do not lock current development source. Evidence files themselves are unchanged.
**Rerunning any exact run listed below requires its recorded commit and recorded
inputs, not the current checkout.** Old bytes remain in Git and retained snapshots.
The pre-edit baseline commit is `e0e3fc83b64ad8839d63d8a6f6fbc41c78c9f7da`.

[pin-checks.json](pin-checks.json) records pre-edit LF and CRLF hashes and all matching
record paths found in docs/evidence/ and data/ JSON/Markdown metadata (excluding
session payload directories, target/store directories and held-out directories).
The changed paths have no intersection with the 16-file checkpoint `698d8831`
deployment closure in the two `*-deployed.json` records; that closure is untouched.
The following table lists every matching retained record, including local copies
and packaging inventories; a hash match does not make a run record a deployment lock.

| Record | Changed source whose old hash it records |
|---|---|
| `data/human/sessions/code-snapshot-f8fd92c-ping-20260927/manifest.json` | `agent/human_intake.py (LF)` |
| `data/idm/cloud-20260927/expanded-inputs-d4f05e0/native-mount-proof.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/expanded-runtime-1927538/code/cloud/idm-payload-manifest.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/expanded-runtime-1927538/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/expanded-runtime-6ac019f/code/cloud/idm-payload-manifest.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/expanded-runtime-6ac019f/native-mount-proof.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/expanded-runtime-6ac019f/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/expanded-runtime-d4f05e0/code/cloud/idm-payload-manifest.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/expanded-runtime-d4f05e0/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/expanded-runtime-f2f179a/code/cloud/idm-payload-manifest.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/expanded-runtime-f2f179a/native-mount-proof.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/expanded-runtime-f2f179a/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/full03-result-collected/artifacts/fit/epochs/epoch-0001-2dd7075287e74cb78183b8e79afd24bc.complete.json` | `agent/human_intake.py (LF)` |
| `data/idm/cloud-20260927/full03-result-collected/artifacts/fit/epochs/epoch-0002-d6790c8a0a90414daae552464aa0bfe6.complete.json` | `agent/human_intake.py (LF)` |
| `data/idm/cloud-20260927/full03-result-collected/artifacts/fit/epochs/epoch-0003-173cdbd67e2f4b9da1b8780a82594456.complete.json` | `agent/human_intake.py (LF)` |
| `data/idm/cloud-20260927/local-timing-runtime-362ec92/code/cloud/idm-payload-manifest.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/local-timing-runtime-362ec92/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/local-timing-runtime-adda577/code/cloud/idm-payload-manifest.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/local-timing-runtime-adda577/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/local-timing-runtime-v105-fix1/code/cloud/idm-payload-manifest.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/local-timing-runtime-v105-fix1/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/match-store-packet-39f8365/inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/match-store-packet-9989f32/inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/runtime-full03-05a61b4/code/cloud/idm-payload-manifest.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/runtime-full03-05a61b4/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/cloud-20260927/upload-resume-cache.json` | `policy/range_bc/cm3_run.py (CRLF)` |
| `data/idm/match-refit-mac-20260928/collected/result/fit/epochs/epoch-0001-6b507421bf68411399ac3fd06fc78006.complete.json` | `agent/human_intake.py (LF)` |
| `data/idm/match-refit-mac-20260928/collected/result/fit/epochs/epoch-0002-b3d2d0af1cd64196bdd393ea9890e4cc.complete.json` | `agent/human_intake.py (LF)` |
| `data/idm/match-refit-mac-20260928/collected/result/fit/epochs/epoch-0003-5af04d975023447db8e33c8b8266724a.complete.json` | `agent/human_intake.py (LF)` |
| `data/idm/match-refit-mac-20260928/collected/runtime-inventory-a1.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/match-refit-mac-20260928/runtime-inventory-a1.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/match-refit-mac-20260928/runtime-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/match-refit-mac-20260928/watch/epoch-1/epoch-0001-6b507421bf68411399ac3fd06fc78006.complete.json` | `agent/human_intake.py (LF)` |
| `data/idm/match-refit-mac-20260928/watch/epoch-2/epoch-0002-b3d2d0af1cd64196bdd393ea9890e4cc.complete.json` | `agent/human_intake.py (LF)` |
| `data/idm/match-refit-mac-20260928/watch/epoch-3/epoch-0003-5af04d975023447db8e33c8b8266724a.complete.json` | `agent/human_intake.py (LF)` |
| `data/idm/range-to-match-20260928/mac-packet-a1/inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/range-to-match-20260928/mac-packet-a2/inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/range-to-match-20260928/mac-packet/inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `data/idm/reader-support-20260928/collected/inventory-support-a2.json` | `policy/range_bc/cm3_run.py (LF)`, `policy/range_bc/steps.py (LF)` |
| `data/idm/reader-support-20260928/collected/inventory-support-a3.json` | `policy/range_bc/cm3_run.py (LF)`, `policy/range_bc/steps.py (LF)` |
| `data/idm/reader-support-20260928/collected/inventory-support.json` | `policy/range_bc/cm3_run.py (LF)`, `policy/range_bc/steps.py (LF)` |
| `data/idm/reader-support-20260928/inventory-support-a2.json` | `policy/range_bc/cm3_run.py (LF)`, `policy/range_bc/steps.py (LF)` |
| `data/idm/reader-support-20260928/inventory-support-a3.json` | `policy/range_bc/cm3_run.py (LF)`, `policy/range_bc/steps.py (LF)` |
| `data/idm/reader-support-20260928/inventory-support.json` | `policy/range_bc/cm3_run.py (LF)`, `policy/range_bc/steps.py (LF)` |
| `docs/evidence/idm-expanded-authority11-runtime-20260927/native-mount-proof.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-expanded-authority11-runtime-20260927/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-expanded-authority12-runtime-20260927/native-mount-proof.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-expanded-authority12-runtime-20260927/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-expanded-cloud-preparation-20260927/native-mount-proof.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-expanded-cloud-preparation-20260927/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-expanded-full02-launch-20260928/native-mount-proof.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-expanded-full02-launch-20260928/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-expanded-full03-launch-20260928/native-mount-proof.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-expanded-full03-launch-20260928/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-expanded-full03-result-20260928/artifacts/fit/epochs/epoch-0001-2dd7075287e74cb78183b8e79afd24bc.complete.json` | `agent/human_intake.py (LF)` |
| `docs/evidence/idm-expanded-full03-result-20260928/artifacts/fit/epochs/epoch-0002-d6790c8a0a90414daae552464aa0bfe6.complete.json` | `agent/human_intake.py (LF)` |
| `docs/evidence/idm-expanded-full03-result-20260928/artifacts/fit/epochs/epoch-0003-173cdbd67e2f4b9da1b8780a82594456.complete.json` | `agent/human_intake.py (LF)` |
| `docs/evidence/idm-local-timing01-failed-20260928/native-mount-proof.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-local-timing01-failed-20260928/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-local-timing02-launch-20260928/native-mount-proof.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-local-timing02-launch-20260928/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-match-refit-mac-epoch1-20260928/epoch-0001.complete.json` | `agent/human_intake.py (LF)` |
| `docs/evidence/idm-match-refit-mac-epoch2-20260928/epoch-0002.complete.json` | `agent/human_intake.py (LF)` |
| `docs/evidence/idm-match-refit-mac-epoch3-20260928/epoch-0003.complete.json` | `agent/human_intake.py (LF)` |
| `docs/evidence/idm-match-refit-mac-freeze-20260928/runtime-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-match-refit-mac-freeze-a1-20260928/runtime-inventory-a1.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-match-store-preparation-20260927/inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-match-store-preparation9-20260927/inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-range-to-match-preparation-20260928/inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/idm-reader-support-20260928/inventory-support-a2.json` | `policy/range_bc/cm3_run.py (LF)`, `policy/range_bc/steps.py (LF)` |
| `docs/evidence/idm-reader-support-20260928/inventory-support-a3.json` | `policy/range_bc/cm3_run.py (LF)`, `policy/range_bc/steps.py (LF)` |
| `docs/evidence/idm-reader-support-20260928/inventory-support.json` | `policy/range_bc/cm3_run.py (LF)`, `policy/range_bc/steps.py (LF)` |
| `docs/evidence/live-loop-fallback-20260927/prepared/manifest.json` | `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/cache-attempt-01/source-manifest.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/cloud-extraction-01/native-mount-proof.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/cloud-extraction-01/source-inventory.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/cloud-extraction-02/native-mount-proof.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/cloud-extraction-02/source-inventory.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/fullfit-01/native-mount-proof.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/fullfit-01/source-inventory.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/fullfit-local-03/native-mount-proof.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/fullfit-local-03/source-inventory.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/fullfit-recovery-02/native-mount-proof.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/fullfit-recovery-02/source-inventory.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/guard-integration-probe2/native-mount-proof.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/guard-integration-probe2/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/guard-integration-probe3/native-mount-proof.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/guard-integration-probe3/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/guard-integration/native-mount-proof.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/guard-integration/source-inventory.json` | `agent/human_intake.py (LF)`, `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/local-disk-probe-01/native-mount-proof.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-spatial-yaw-20260927/local-disk-probe-01/source-inventory.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-yaw-dropout-20260928/fit-packet-01/code/cloud/yaw-payload-manifest.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-yaw-dropout-20260928/fit-packet-01/native-mount-proof.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-yaw-dropout-20260928/fit-packet-01/source-inventory.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-yaw-dropout-20260928/probe-packet-01/code/cloud/yaw-payload-manifest.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-yaw-dropout-20260928/probe-packet-01/native-mount-proof.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/nitrogen-yaw-dropout-20260928/probe-packet-01/source-inventory.json` | `agent/human_intake.py (CRLF)`, `policy/range_bc/cm3_run.py (CRLF)`, `policy/range_bc/steps.py (CRLF)` |
| `docs/evidence/range-bc-countermeasures-3-20260926/accounting-a7/fanout/owner-files.json` | `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/range-bc-countermeasures-3-20260926/accounting-a7/files.json` | `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/range-bc-countermeasures-3-20260926/accounting-a7/integration-sources.json` | `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/range-bc-countermeasures-3-20260926/accounting-a7/owner/files.json` | `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/range-bc-countermeasures-3-20260926/accounting-a7/owner/lineage.json` | `policy/range_bc/cm3_run.py (LF)` |
| `docs/evidence/range-bc-countermeasures-3-20260926/accounting-a8/unchanged-closure.json` | `policy/range_bc/cm3_run.py (LF)` |

## Preserved snapshot loaders

- `data/human/sessions/code-snapshot-107970b-3c8a3b7e/agent/human_intake.py`
- `data/human/sessions/code-snapshot-107970b-3c8a3b7e/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-107970b-3c8a3b7e/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-23c8482/agent/human_intake.py`
- `data/human/sessions/code-snapshot-23c8482/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-299ffba/agent/human_intake.py`
- `data/human/sessions/code-snapshot-2ad0992/agent/human_intake.py`
- `data/human/sessions/code-snapshot-2ad0992/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-2ad0992/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-3936f94-4c9638d1/agent/human_intake.py`
- `data/human/sessions/code-snapshot-3936f94-4c9638d1/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-3936f94-4c9638d1/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-3936f94/agent/human_intake.py`
- `data/human/sessions/code-snapshot-3936f94/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-3936f94/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-6bbb276/agent/human_intake.py`
- `data/human/sessions/code-snapshot-6bbb276/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-6bbb276/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-6f4dba2/agent/human_intake.py`
- `data/human/sessions/code-snapshot-74db8be/agent/human_intake.py`
- `data/human/sessions/code-snapshot-83c05f1/agent/human_intake.py`
- `data/human/sessions/code-snapshot-83c05f1/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-83c05f1/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-86a1912/agent/human_intake.py`
- `data/human/sessions/code-snapshot-86a1912/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-b7d4592/agent/human_intake.py`
- `data/human/sessions/code-snapshot-b7d4592/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-b7d4592/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-c0892ab/agent/human_intake.py`
- `data/human/sessions/code-snapshot-dfbb4dd-98e52781/agent/human_intake.py`
- `data/human/sessions/code-snapshot-dfbb4dd-98e52781/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-dfbb4dd-98e52781/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-dfbb4dd/agent/human_intake.py`
- `data/human/sessions/code-snapshot-dfbb4dd/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-dfbb4dd/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-e7f5045/agent/human_intake.py`
- `data/human/sessions/code-snapshot-e7f5045/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-e7f5045/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-f8fd92c-08c36e68/agent/human_intake.py`
- `data/human/sessions/code-snapshot-f8fd92c-08c36e68/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-f8fd92c-08c36e68/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-f8fd92c-3c585dc1/agent/human_intake.py`
- `data/human/sessions/code-snapshot-f8fd92c-3c585dc1/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-f8fd92c-3c585dc1/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-f8fd92c-6046514b/agent/human_intake.py`
- `data/human/sessions/code-snapshot-f8fd92c-6046514b/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-f8fd92c-6046514b/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-f8fd92c-bounded-20260927/agent/human_intake.py`
- `data/human/sessions/code-snapshot-f8fd92c-bounded-20260927/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-f8fd92c-bounded-20260927/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-f8fd92c-ping-20260927/agent/human_intake.py`
- `data/human/sessions/code-snapshot-f8fd92c-ping-20260927/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-f8fd92c-ping-20260927/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-f8fd92c/agent/human_intake.py`
- `data/human/sessions/code-snapshot-f8fd92c/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-f8fd92c/policy/range_bc/steps.py`
- `data/human/sessions/code-snapshot-fbe6693/agent/human_intake.py`
- `data/human/sessions/code-snapshot-fbe6693/policy/idm_targets.py`
- `data/human/sessions/code-snapshot-fbe6693/policy/range_bc/steps.py`

The complete excluded loader list, including evidence and other runtime copies, is in `excluded-loaders.json`.

## Review and handoff

`review-inputs.json` pins the three changed production files, the new test and this
packet's supporting files. Independent reviewer: live-review via herdr-lead.
Review the authentication/read boundary and callers, reusing prior evidence for
unchanged behavior. Lead owns LAND and current Linear reconciliation (VUH-1359,
related VUH-1353); no direct workspace Linear tools are exposed in this worker.
Pending record text: produced denylist pin hardening with synthetic checks passing;
independent review and LAND remain; lead routes review and reconciles the issue.
