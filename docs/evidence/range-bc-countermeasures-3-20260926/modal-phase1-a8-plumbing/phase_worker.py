"""Transport-only wrappers around the unchanged reviewed owner fit supervisor."""
def stage_controls(spec):
 import modal,pathlib,json,hashlib,time
 p=spec["plan"];m=spec["manifest"];raw=spec["manifest_bytes"]
 assert hashlib.sha256(raw).hexdigest()==p["control_manifest"]["sha256"] and json.loads(raw)==m
 claim=modal.Dict.from_id(p["claim_dict_id"])
 assert claim.put("phase1-02-controls",True,skip_if_exists=True),"duplicate control invocation"
 assert p["selected_task"]=="A-0" and m["root"]=="/outputs/.modal-control/phase1-02"
 assert m["format"]=="cm3-phase-control-manifest-v1" and m["output_volume_id"]==p["output_volume_id"]
 from safety import canonical
 assert m["identity"]=={"profile":"rivals","workspace":"volpestyle","workspace_id":"ac-kMLf5bJKqF5CAlSbfNhGh0"}
 assert m["tasks_sha256"]==canonical(p["tasks"]) and m["input_manifest_sha256"]==p["input_manifest"]["sha256"]
 assert set(spec["payload"])==set(m["files"]) and 0<len(m["files"])==101
 assert sum(len(v) for v in spec["payload"].values())<=8*1024**2
 root=pathlib.Path("/outputs");target=pathlib.Path("/__modal/volumes")/p["output_volume_id"]
 assert root.is_symlink() and root.readlink()==target and root.resolve(strict=True)==target and not target.is_symlink()
 for name,raw in spec["payload"].items():
  path=pathlib.Path(name);row=m["files"][name]
  assert str(path)==name and path.is_relative_to(m["root"]) and ".." not in path.parts and path.suffix==".json"
  relative=pathlib.PurePosixPath(row["local_path"])
  assert not relative.is_absolute() and ".." not in relative.parts and name==m["root"]+"/"+str(relative)
  assert isinstance(raw,bytes) and len(raw)==row["bytes"]<=1024**2
  assert hashlib.sha256(raw).hexdigest()==row["sha256"];json.loads(raw)
  assert not path.exists()
  for parent in (path,*path.parents):
   if parent==root:break
   assert not parent.is_symlink()
 for name,raw in spec["payload"].items():
  path=pathlib.Path(name);path.parent.mkdir(parents=True,exist_ok=True)
  with path.open("xb") as f:f.write(raw)
 modal.Volume.from_id(p["output_volume_id"]).commit()
 return {"status":"PASS","manifest_sha256":p["control_manifest"]["sha256"],"completed_at":time.time(),"files":len(m["files"])}
def run_fit_v4(arm,seed,purpose="registered",runtime_plan=None):
 import modal,os,sys,json,pathlib,hashlib,subprocess,time,signal
 sys.dont_write_bytecode=True;p=runtime_plan
 assert isinstance(p,dict) and p.get("transport_v4") is True and p["phase"]=="phase1"
 key="H-repeat-0" if purpose=="repeat" else arm+"-"+str(seed)
 assert key in ("A-0","A-1","A-2","H-0","H-repeat-0") and p["selected_task"]==key
 assert purpose==("repeat" if key=="H-repeat-0" else "registered")
 allocation=p["tasks"][key]["attempt_receipts"][0]
 claim=modal.Dict.from_id(p["claim_dict_id"])
 assert claim.put("fit-"+allocation["attempt_id"],True,skip_if_exists=True),"provider reinvocation refused"
 from diagnostic_capture import validate_contract
 validate_contract(p["diagnostic_contract"])
 assert p["diagnostic_contract"]["status"]=="REVIEWED"
 from safety import digest,canonical,fit_budget
 from volume_inventory import verify_metadata
 from input_closure import bind_context
 root=pathlib.Path("/outputs");target=pathlib.Path("/__modal/volumes")/p["output_volume_id"]
 assert root.is_symlink() and root.readlink()==target and root.resolve(strict=True)==target and not target.is_symlink()
 code=pathlib.Path("/inputs")/p["code_directory"]
 assert digest(code/"policy/range_bc/cm3_run.py")==p["entrypoint_sha256"]
 assert hashlib.sha256(p["input_manifest_text"].encode()).hexdigest()==p["input_manifest"]["sha256"]
 assert hashlib.sha256(p["control_manifest_bytes"]).hexdigest()==p["control_manifest"]["sha256"]
 controls=json.loads(p["control_manifest_bytes"])
 for name,row in controls["files"].items():
  path=pathlib.Path(name);assert path.is_relative_to(controls["root"]) and ".." not in path.parts
  for parent in (path,*path.parents):
   if parent==root:break
   assert not parent.is_symlink()
  assert path.is_file() and path.stat().st_size==row["bytes"] and digest(path)==row["sha256"]
 receipt=pathlib.Path(p["receipt_root"])/allocation["path"]
 assert digest(receipt)==allocation["sha256"]
 approval=json.loads(receipt.read_bytes())
 assert approval["stage"]=="fit" and approval["format"]=="cm3-stage-approval-v1"
 assert (approval["arm"],approval["seed"],approval["purpose"])==(arm,seed,purpose)
 assert approval["attempt_id"]==allocation["attempt_id"] and approval["output"]==allocation["output"]
 assert approval["context_sha256"]==canonical(approval["context"])==p["context_sha256"]
 assert set(approval["predecessors"])=={"inputs","proof128","smoke","extract"} and approval["fit_predecessors"]=={}
 assert approval["predecessors"]["extract"]==p["extraction_result"]
 fit_budget(p,key,approval["budget"])
 bind_context(json.loads(p["input_manifest_text"]),approval["context"],p["control_refs"])
 output=pathlib.Path(allocation["output"]);journal=root/".modal-journal"/p["run_id"]/key
 for path in (output,journal):
  assert not path.exists(),"immutable attempt output or journal exists"
  for parent in (path,*path.parents):
   if parent==root:break
   assert not parent.is_symlink()
 journal.mkdir(parents=True)
 verification=verify_metadata("/inputs",p["input_witness_bytes"],p["input_witness"]["sha256"],p["input_volume_id"],p["input_version_id"])
 (journal/"metadata-input-verification.json").write_text(json.dumps(verification,indent=2))
 volume=modal.Volume.from_id(p["output_volume_id"]);volume.commit()
 started=time.time();remaining=min(p["attempt_timeout_seconds_by_arm"][arm]-30,p["absolute_deadline_unix"]-started)
 assert remaining>0,"funded deadline"
 with (journal/"attempt-start.json").open("x") as f:json.dump({"attempt_id":allocation["attempt_id"],"started_at":started,"automatic_retries":0},f)
 env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONHASHSEED="0",CUBLAS_WORKSPACE_CONFIG=":4096:8")
 command=[sys.executable,"-B","-m","policy.range_bc.cm3_run","fit","--receipt",str(receipt),"--receipt-sha256",allocation["sha256"],"--arm",arm,"--seed",str(seed)]
 record={"mounted_verification":verification,"arm":arm,"seed":seed,"purpose":purpose,"attempt":0,"attempt_id":allocation["attempt_id"],"started_at":started,"result":None}
 try:
  with (journal/"runner.log").open("xb") as log:
   proc=subprocess.Popen(command,cwd=code,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:exit_code=proc.wait(timeout=remaining)
   except subprocess.TimeoutExpired:
    os.killpg(proc.pid,signal.SIGKILL);proc.wait();exit_code=124
  assert exit_code==0,"owner fit failed: "+str(exit_code)
  result_path=output/"result.json";assert result_path.is_file(),"no supervisor PASS result"
  result=json.loads(result_path.read_bytes())
  assert result["format"]=="cm3-stage-result-v1" and result["status"]=="PASS" and result["stage"]=="fit"
  for field in ("arm","seed","purpose","attempt_id","context_sha256"):assert result[field]==approval[field]
  assert result["approval"]=={"path":str(receipt),"sha256":allocation["sha256"]}
  files=[]
  for path in sorted(output.rglob("*")):
   assert not path.is_symlink()
   if path.is_file():
    assert path.suffix in (".json",".pt",".f32") and path.stat().st_size<=512*1024**2
    files.append({"path":str(path),"bytes":path.stat().st_size,"sha256":digest(path)})
  assert 0<len(files)<=64 and sum(r["bytes"] for r in files)<=2*1024**3
  record.update(exit=0,status="COMPLETE",finished_at=time.time(),result={"path":str(result_path),"sha256":digest(result_path)},files=files)
 except BaseException as exc:
  from diagnostic_capture import capture_diagnostic
  record.update(exit=locals().get("exit_code",125),status="INCOMPLETE",finished_at=time.time(),reason=str(exc),
    owner_diagnostic=capture_diagnostic(journal/"runner.log",p["diagnostic_contract"]))
 with (journal/"attempt-result.json").open("x") as f:json.dump(record,f,indent=2)
 volume.commit()
 return record
