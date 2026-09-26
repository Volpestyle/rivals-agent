import hashlib,json
from pathlib import Path
O=Path(__file__).parent;H=O.parent;R=Path.cwd();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=json.loads((O/'delta-checks.json').read_text());a=json.loads((O/'audit.json').read_text())
assert a['cross_category_repro']!='ACCEPTED'
assert (O/'relocation-run.txt').read_text(encoding='utf-16' if (O/'relocation-run.txt').read_bytes().startswith(b'\xff\xfe') else 'utf8').strip()=='SealedError gate2 artifact is sealed'
for p,v in d['pins'].items():assert sha(R/p)==v['raw'],p
assert sha(H/'review-intake-0926.md')=='af85359c898730380761ae960c17a2af882f68b22c460d3cdf16e0f00025b03b'
report=f'''**Verdict: approve the B1/F2 delta. B1 is closed; F2 is closed. No remaining blocking or fix-forward finding in this delta.**

Independent reviewer: admission-review (Codex), 2026-09-26. Re-review of `admission-owner-final-27.md`, SHA256 `{d['handback_sha256']}`. This supplements `review-intake-0926.md` (`af85359c`); its other accepted checks and the unchanged session verdicts stand. Only B1/F2 were reconsidered.

## B1 — closed

`human_demos.read_splits` calls `_check_excluded` before returning placements; `human_intake.check_registry` reaches that same check after its denylist validation. Calibration/evaluation rows must be disjoint from split rows and from other excluded rows by session ID, resolved media path and supplied `expected_media_sha256`. Neither excluded category can carry `split` or `sealed`; evaluation `kind` cannot name train, val, test or gate2. The reader returns split rows only.

I reran the original **byte-identical** `audit.py` from a new scratch directory so the prior review evidence stays unchanged. Its formerly accepted calibration-as-train reproduction now refuses:

> calibration_sessions row 20260923T204707-487Z-45572-2 shares its session id with a split row or another excluded row

The current registry still validates: **16 split placements, 3 calibration entries, 8 evaluation entries**. No excluded entry resolves to a placement. Fifty independent synthetic checks across both public registry readers covered valid controls, ID/path/hash collisions, relative path normalization, within-list duplicates, cross-list collisions, forbidden split/sealed fields, and all four split-named evaluation kinds. Every expected refusal and valid control passed.

## F2 — closed

`load_dataset_relocated` now checks `hd.SEALED_SPLITS` against both the artifact header and the resolved registry placement. It also requires an exact Boolean sealed flag consistent with that placement, before reading the body.

The original **byte-identical** `relocation_repro.py` now returns **`SealedError: gate2 artifact is sealed`**, replacing the prior payload checksum error. Additional guarded-stream checks make any second `readline()` fail: each of the four cases below refused after exactly one header read, without reading the body.

| Header / access | Refusal |
|---|---|
| gate2, sealed=False, ordinary access | gate2 artifact is sealed |
| train, sealed=False, registry placement gate2 | gate2 session is sealed |
| gate2, sealed=False, unseal=True | sealed header mismatch |
| gate2, sealed flag absent, unseal=True | sealed header mismatch |

The positive relocated-load regression also passed in the targeted suite.

## Validation and scope

- **15 tests passed, 159 deselected:** isolated admission-review Python, `-B -m pytest -q -p no:cacheprovider tests/test_human_demos.py tests/test_human_intake.py -k "excluded or calibration_and_evaluation or relocated"`. No corpus tests requested.
- Original audit and relocation scripts were copied byte-for-byte to `review-intake-0926-2-work/` and executed there. Prior scripts, reports and outputs were preserved. `delta_checks.py` adds the 50 registry checks and four body-read guards.
- All four code/test hashes match final-27's LF pins and were checked again before writing this report. No decode, media content inspection, checkout/session edit, commit, Linear write or Mac action.
- The owner's existing `code-snapshot-3936f94-4c9638d1` predates these fixes. This receipt approves the current code bytes below; it does not assert that the old snapshot contains them. Existing session verdicts stand for their unchanged bytes. Tally regeneration at landing and the separate late-take evidence review remain outside this delta.

## Reviewed pins

| Path | LF SHA256 |
|---|---|
'''
for p,v in d['pins'].items():report+=f"| `{p}` | `{v['lf']}` |\n"
report+='\nEvidence hashes (raw SHA256):\n\n| Scratch file | SHA256 |\n|---|---|\n'
for name in ('audit.py','audit.json','audit-run.txt','relocation_repro.py','relocation-run.txt','delta_checks.py','delta-checks.json'):
 report+=f"| `review-intake-0926-2-work/{name}` | `{sha(O/name)}` |\n"
with (H/'review-intake-0926-2.md').open('x',encoding='utf8',newline='\n') as f:f.write(report)
print(sha(H/'review-intake-0926-2.md'))
