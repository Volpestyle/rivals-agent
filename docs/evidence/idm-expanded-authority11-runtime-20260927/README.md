# Expanded IDM runtime: eleven-member authority

EXPLORATORY, idm-owner, VUH-1353. 2026-09-28 UTC.

Accepted metadata delta f2f179a is deployed separately at `/Users/james/dev/idm-data/expanded-refit-d4f05e0/runtime-authority11`. Its predecessor runtime10 and ongoing input upload remain unchanged. The four changed source files are recorded in delta.json; scientific code, guard and input manifest are byte-identical. No -7/-8/-10/-11 payload is included: the fit remains eight TRAIN ranges plus current -4a1/-5a1/-6, with the existing two range dev sessions.

The SDK 1.5.5 native source-mount proof passed on the Mac for all 180 cloud files (181 files including the host job-status helper), with zero AppCreate RPCs and zero image builds. Runtime archive SHA256: `ccbe735f9232834b9a1b314b47432cfb398a60b17b3cd53f54e9be454b7895d8`. Source inventory SHA256: `669afd90b72f1b7a57bd75d3de3fb00cde82ce9b7902009030464afe93570773`. Payload manifest SHA256: `bf76150f189d2aab51db38d5297a46c4726ed64492789cce97841060e47021e8`.

The fresh spec builder is prepared but not executed. It refuses an unfinished upload and binds fresh output volumes to the accepted guard, fixed input volume and exact runtime. Upload completion, final spec verification and a coordinated AppCreate remain prerequisites for the approved $0.40 probe. Full $6.20/7,800-second attempt follows probe PASS. Total campaign allocation is $8.25: setup/storage $1.65, probe $0.40, full $6.20, within IDM $25. Prior terminal lane bound is $6.335876068670252. No new GPU reservation or scientific result is claimed here.

Input volume `rivals-idm-expanded-20260928-01-inputs` (`vo-PnBxKAp9G4Y8nNwfBOgrdU`) must be manually deleted once after the refit report, after checking its exact ID/name with `modal volume list --json`. Keep the CLI deletion/absence receipt. No automatic deletion code is deployed.

The existing completion watcher was launched under runtime10 metadata and may name 1927538 in its notification. That notification does not select runtime or authorize data. Use this accepted runtime11 and `make-expanded-specs-authority11.py` for the future probe/full bindings.
