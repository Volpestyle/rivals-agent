# Expanded IDM runtime: complete night authority

EXPLORATORY, idm-owner, VUH-1353. 2026-09-28 UTC.

Accepted metadata delta 6ac019f is deployed separately at `/Users/james/dev/idm-data/expanded-refit-d4f05e0/runtime-authority12`. All twelve authority members cover the eight accepted night matches plus historical revocations. The selected refit remains eight TRAIN ranges plus -4a1/-5a1/-6 and the existing two range dev sessions. No -7/-8/-10/-11/-12 payload or action vocabulary change. Predecessor runtime11 and the ongoing upload remain immutable.

The exact four-file metadata delta is in delta.json. Scientific code, accepted v1.0.4 guard and input manifest are unchanged. The SDK 1.5.5 native source-mount proof passed on the Mac for 181 cloud files, with zero AppCreates and zero image builds. Archive SHA256: `0aac3125322318d5df92a25d6d37c864d3ea28d0c0b0615d341bdd76bea63f9d`; source inventory: `fb81937c4eb83e3326fc35042ec73b8466508117094281efef12f303ae016e52`; payload manifest: `6dbc288c558df5caaad4a9179c973ed70c34442aff5d71894be055d5da011057`.

Use `make-expanded-specs-authority12.py` after successful upload verification. It is prepared, not executed in this packet. Earlier watcher messages naming authority1927538 are historical notifications, not runtime selection. This freeze supersedes runtime11 for future spec creation.

Approved budget remains $8.25: setup/storage $1.65, probe $0.40, full attempt $6.20 with 7,800 work seconds; unchanged lane $25, prior terminal bound $6.335876068670252. Upload completion and a coordinated window precede the probe; probe PASS precedes the single full attempt. No additional fit or retry and no scientific result claimed.

After the report, manually check input volume `rivals-idm-expanded-20260928-01-inputs` / `vo-PnBxKAp9G4Y8nNwfBOgrdU` with `modal volume list --json`, delete it once by CLI and record deletion/absence. No automatic deletion code is used.
