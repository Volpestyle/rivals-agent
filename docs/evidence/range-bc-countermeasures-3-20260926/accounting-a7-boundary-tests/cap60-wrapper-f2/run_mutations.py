from pathlib import Path
import hashlib,json,os,subprocess,sys,tempfile
B=Path(__file__).resolve().parent;source=B.parent/"cap60-wrapper/serial-runtime/safety.py"
raw=source.read_bytes();sha=lambda x:hashlib.sha256(x).hexdigest()
expected=json.loads((B.parent/"cap60-wrapper/files.json").read_text())["files"]["serial-runtime/safety.py"]
assert sha(raw)==expected
rows=[]
for name,before,after,test in [("baseline",None,None,None),
 ("dollar-plus-one-cent",b'["cap_usd"]<=60 ',b'["cap_usd"]<=60.01 ',"test_60_01_refuses"),
 ("seconds-plus-one",b"<=69120,",b"<=69121,","test_69121_refuses")]:
 with tempfile.TemporaryDirectory() as tmp:
  p=Path(tmp)/"safety.py"
  if before:assert raw.count(before)==1
  changed=raw.replace(before,after) if before else raw;p.write_bytes(changed)
  r=subprocess.run([sys.executable,str(B/"test_serial_cap_boundaries.py")],
   env=dict(os.environ,SERIAL_SAFETY_SOURCE=str(p),PYTHONDONTWRITEBYTECODE="1"),text=True,capture_output=True)
  log=r.stdout+r.stderr;(B/(name+".log")).write_text(log)
  if test:assert r.returncode!=0 and "FAIL: "+test in log and "FAILED (failures=1)" in log and "ERROR:" not in log,log
  else:assert r.returncode==0,log
  rows.append(dict(case=name,exit_code=r.returncode,expected_failure=test,candidate_sha256=sha(changed)))
assert source.read_bytes()==raw
(B/"results.json").write_text(json.dumps(dict(source_sha256=expected,python=sys.version,cases=rows),indent=2)+"\n")
print(json.dumps(rows,indent=2))
