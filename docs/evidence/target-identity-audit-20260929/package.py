"""Package compact review sheets; retain native frames/zooms with hashes on Mac."""
import hashlib
import json
import resource
import sys
import tarfile
import time
from pathlib import Path
from PIL import Image

ROOT=Path("/Users/james/dev/range-bc-data/explore/target-identity-audit-20260929")
CODE=ROOT.parent/"turn-onset-probe-20260929/runtime-ca1444c"
sys.path.insert(0,str(CODE))
from scripts.job_status import write

def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

write("target-identity-audit-20260929",stage="running",progress="Compact sheets and native artifact hash manifest")
dest=ROOT/"package"
dest.mkdir(exist_ok=False)
contacts=dest/"contacts"
contacts.mkdir()
manifest=[]
for phase in ("causal","outcome"):
    for path in sorted((ROOT/phase).rglob("*")):
        if path.is_file():
            manifest.append(dict(path=str(path.relative_to(ROOT)),size=path.stat().st_size,sha256=sha(path)))
    sheets=sorted((ROOT/phase).glob("E*-sheet.jpg"))
    assert len(sheets)==48
    for path in sheets:
        with Image.open(path) as im:
            im.resize((1280,im.height//2),Image.Resampling.LANCZOS).save(
                contacts/(phase+"-"+path.name.replace("-sheet","")),quality=85)
    assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<3_000_000_000
(dest/"native-artifacts.json").write_text(json.dumps(dict(root=str(ROOT),files=manifest),indent=2)+"\n")
for name in ("causal-complete.json","outcome-complete.json","source-availability.json"):
    (dest/name).write_bytes((ROOT/name).read_bytes())
receipt=dict(completed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
             peak_parent_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             native_manifest_entries=len(manifest),contact_sheets=96,
             contact_bytes=sum(p.stat().st_size for p in contacts.iterdir()))
(dest/"package-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
with tarfile.open(ROOT/"review-package.tar","w") as tar:
    for path in sorted(dest.rglob("*")):
        if path.is_file():
            tar.add(path,arcname=str(path.relative_to(dest)))
write("target-identity-audit-20260929",stage="done",progress="48-case audit evidence packaged; no further job")
print(json.dumps(receipt))
