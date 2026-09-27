"""Bounded transport into a fresh directory. No training or artifact/receipt rewriting.
Use supervised_collect/CLI: its separate process also bounds blocked network reads.
"""
import hashlib,json,os,pathlib,signal,subprocess,sys,time
from safety import require,document,remote_path,sha,number,digest,canonical
from lifecycle import atomic,connect_verified
def refs(value):
    if isinstance(value,dict):
        if "path" in value and "sha256" in value:
            remote_path(value["path"]);sha(value["sha256"])
            yield {"path":value["path"],"sha256":value["sha256"]}
        for child in value.values():yield from refs(child)
    elif isinstance(value,list):
        for child in value:yield from refs(child)
def validate_sources(m):
    require(m["format"]=="cm3-collection-v1" and m["approved_by"]=="herdr-lead","unapproved collection manifest")
    require(m["identity"]["profile"]=="rivals" and m["identity"]["workspace"]=="volpestyle","collection identity")
    require(m["runner_class"]=="cuda:L40S","collection class")
    require(set(m["volume_ids"])=={"inputs","outputs"},"missing source volume binding")
    manifests={r["sha256"]:document(r) for r in m["input_manifests"]}
    require(manifests and m["launch_bindings"],"missing collection approval closure")
    from input_closure import schema
    inputs={}
    for manifest in manifests.values():
        require(manifest["status"]=="FROZEN" and manifest["volume_id"]==m["volume_ids"]["inputs"],"collection input volume")
        for path,row in schema(manifest).items():
            key="/inputs/"+path
            require(key not in inputs or inputs[key]==row,"conflicting input closure")
            inputs[key]=row
    allocations={}
    for ref in m["launch_bindings"]:
        b=document(ref)
        require(b["format"]=="cm3-modal-launch-binding-v1" and b["approved_by"]=="herdr-lead","collection launch approval")
        require({k:b[k] for k in ("profile","workspace","workspace_id")}==m["identity"],"collection account binding")
        require(b["input_volume_id"]==m["volume_ids"]["inputs"] and b["output_volume_id"]==m["volume_ids"]["outputs"],"collection volumes changed")
        require(b["gpu"]=="L40S" and b["judge_model"]==b["judge_instance"]=="modal:L40S" and b["runner_class"]=="cuda:L40S" and b["benchmark_provider"]=="modal","collection class changed")
        require(b["input_manifest_sha256"] in manifests,"unbound collection manifest")
        require(manifests[b["input_manifest_sha256"]]["context_sha256"]==b["context_sha256"],"collection context changed")
        tasks=document(ref)["tasks"]
        require(canonical(tasks)==b["tasks_sha256"],"collection task routing changed")
        for key,task in tasks.items():
            require(len(task["attempt_receipts"])==1,"collection attempt count")
            a=task["attempt_receipts"][0]
            allocations[(key,a["attempt_id"])]=(a,b["context_sha256"])
    for selected in m["selected"]:
        key="H-repeat-0" if selected["purpose"]=="repeat" else selected["arm"]+"-"+str(selected["seed"])
        bound=allocations.get((key,selected["attempt_id"]))
        require(bound is not None,"selected attempt not lead bound")
        a,context=bound
        require(selected["output"]==a["output"] and selected["approval_ref"]=={"path":"/inputs/"+a["path"],"sha256":a["sha256"]} and selected["context_sha256"]==context,"selected routing changed")
    for f in m["files"]:
        if f["path"].startswith("/inputs/"):
            row=inputs.get(f["path"])
            require(row is not None and row["sha256"]==f["sha256"] and row["bytes"]==f["bytes"],"download outside frozen input closure")
    return m

def collect(manifest_ref,destination,reader,clock=time.monotonic):
    m=validate_sources(document(manifest_ref))
    require(m["format"]=="cm3-collection-v1" and m["approved_by"]=="herdr-lead","unapproved collection manifest")
    require(m["identity"]["profile"]=="rivals" and m["identity"]["workspace"]=="volpestyle","collection identity")
    require(m["runner_class"]=="cuda:L40S","collection class")
    for key in ("max_bytes","max_files","timeout_seconds"):number(m[key],key,True)
    require(type(m["max_files"]) is int and m["max_files"]<=100000 and m["timeout_seconds"]<=3600,"unbounded collection")
    files=m["files"];require(0<len(files)<=m["max_files"],"file bound")
    table={}
    for f in files:
        remote_path(f["path"]);sha(f["sha256"])
        require(f["path"] not in table and type(f["bytes"]) is int and f["bytes"]>=0,"duplicate/invalid collection entry")
        require(f["kind"] in ("json","checkpoint","opaque") and (not f["path"].endswith(".json") or f["kind"]=="json"),"unparsed JSON artifact")
        table[f["path"]]=f
    require(sum(f["bytes"] for f in files)<=m["max_bytes"],"byte reservation exceeds limit")
    destination=pathlib.Path(destination);destination.mkdir(parents=False,exist_ok=False)
    staging=destination/"partial";staging.mkdir()
    started=clock();total=0;docs={}
    try:
        for f in files:
            require(clock()-started<m["timeout_seconds"],"collection deadline")
            path=staging/remote_path(f["path"]).relative_to("/")
            path.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256();size=0
            with path.open("xb") as stream:
                for chunk in reader(f["path"]):
                    require(isinstance(chunk,bytes),"non-byte transfer")
                    require(clock()-started<m["timeout_seconds"],"collection deadline")
                    size+=len(chunk);total+=len(chunk)
                    require(size<=f["bytes"] and total<=m["max_bytes"],"transfer size bound")
                    stream.write(chunk);h.update(chunk)
            require(size==f["bytes"] and h.hexdigest()==f["sha256"],"missing/corrupt artifact: "+f["path"])
            if f["kind"]=="json":
                require(size<=64*1024*1024,"JSON artifact too large")
                docs[f["path"]]=json.loads(path.read_bytes())
        for doc in docs.values():
            for ref in refs(doc):
                require(ref["path"] in table and table[ref["path"]]["sha256"]==ref["sha256"],"referenced artifact absent/substituted")
        selected=m["selected"];keys=set()
        require(selected,"no selected results")
        for expected in selected:
            key=(expected["arm"],expected["seed"],expected["purpose"])
            require(key not in keys,"duplicate selected attempt");keys.add(key)
            ref=expected["result_ref"];result=docs[ref["path"]]
            require(table[ref["path"]]["sha256"]==ref["sha256"] and ref["path"]==expected["output"]+"/result.json","selected result binding")
            require(result["format"]=="cm3-stage-result-v1" and result["status"]=="PASS" and result["stage"]=="fit","partial/completed result refused")
            for field in ("arm","seed","purpose","attempt_id","context_sha256"):require(result[field]==expected[field],"selected attempt mismatch: "+field)
            require(result["approval"]==expected["approval_ref"] and result["hardware"]["class"]=="cuda:L40S","approval/hardware mismatch")
            approval=docs[result["approval"]["path"]]
            require(approval["attempt_id"]==expected["attempt_id"] and approval["output"]==expected["output"],"approval/output mismatch")
            require(canonical(approval["context"])==expected["context_sha256"],"approved context changed")
            detail=docs[result["artifacts"]["details"]["path"]]
            checkpoint=detail["checkpoint_file"]
            require(checkpoint["sha256"]==detail["checkpoint_sha256"] and table[checkpoint["path"]]["kind"]=="checkpoint","checkpoint identity missing")
        mode="ARTIFACTS_VERIFIED"
        if m.get("verification_ref"):
            ref=m["verification_ref"];require(table[ref["path"]]["sha256"]==ref["sha256"],"verification substituted")
            verify=docs[ref["path"]]
            require(verify["format"]=="cm3-matrix-verification-v1" and verify["status"]=="PASS","owner verify missing PASS")
            actual={(x["arm"],x["seed"],x["purpose"]) for x in selected}
            expected={(a,s,"registered") for a in ("A","H","I","W") for s in range(3)}|{("H",0,"repeat")}
            require(actual==expected and len(selected)==13,"incomplete verified matrix")
            canonical_refs=lambda rows:sorted((r["path"],r["sha256"]) for r in rows)
            require(canonical_refs(verify["outputs"])==canonical_refs([r["result_ref"] for r in selected]),"owner verify selected different attempts")
            require(all(x["context_sha256"]==verify["context_sha256"] for x in selected),"mixed matrix context")
            mode="MATRIX_VERIFIED"
        staging.rename(destination/"artifacts")
        receipt={"format":"cm3-collected-v1","status":mode,"manifest_sha256":manifest_ref["sha256"],"bytes":total,
                 "files":files,"selected":selected,"verification_ref":m.get("verification_ref")}
        atomic(destination/"collection.json",receipt)
        return receipt
    except BaseException as exc:
        atomic(destination/"INCOMPLETE.json",{"status":"INCOMPLETE","reason":str(exc),"bytes":total})
        raise
def load_verified(destination,manifest_ref):
    destination=pathlib.Path(destination);m=validate_sources(document(manifest_ref))
    c=json.loads((destination/"collection.json").read_bytes())
    require(c["status"]=="MATRIX_VERIFIED" and c["manifest_sha256"]==manifest_ref["sha256"],"matrix collection not verified")
    require(c["files"]==m["files"] and c["selected"]==m["selected"] and c["verification_ref"]==m["verification_ref"],"collection receipt changed")
    docs={}
    for f in c["files"]:
        path=destination/"artifacts"/remote_path(f["path"]).relative_to("/")
        require(not any(x.is_symlink() for x in (path,*path.parents) if x==destination or x.is_relative_to(destination)) and path.resolve().is_relative_to(destination.resolve()),"symlink/escaped collected artifact")
        require(path.is_file() and not path.is_symlink() and path.stat().st_size==f["bytes"] and digest(path)==f["sha256"],"collected bytes changed after promotion")
        if f["kind"]=="json":docs[f["path"]]=json.loads(path.read_bytes())
    verification=docs[c["verification_ref"]["path"]]
    require(verification["format"]=="cm3-matrix-verification-v1" and verification["status"]=="PASS","owner verification required before assembly")
    rows=[]
    for selected in c["selected"]:
        result=docs[selected["result_ref"]["path"]]
        rows.append({"ref":selected["result_ref"],"result":result,"details":docs[result["artifacts"]["details"]["path"]]})
    return verification,rows
def network_collect(manifest_ref,destination):
    m=validate_sources(document(manifest_ref));client,_=connect_verified(m["identity"])
    import modal
    require(set(m["volume_ids"])=={"inputs","outputs"},"missing source volume binding")
    volumes={k:modal.Volume.from_id(v,client=client) for k,v in m["volume_ids"].items()}
    def reader(path):
        p=remote_path(path);mount=p.parts[1]
        yield from volumes[mount].read_file(str(p.relative_to("/"+mount)))
    return collect(manifest_ref,destination,reader)
def supervised_collect(manifest_ref,destination):
    m=validate_sources(document(manifest_ref));timeout=number(m["timeout_seconds"],"collection deadline",True)
    require(timeout<=3600 and not pathlib.Path(destination).exists(),"fresh bounded destination required")
    command=[sys.executable,__file__,"--worker",json.dumps(manifest_ref),str(destination)]
    proc=subprocess.Popen(command,start_new_session=True)
    try:require(proc.wait(timeout=timeout)==0,"collection subprocess failed")
    except BaseException:
        if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        dest=pathlib.Path(destination);dest.mkdir(exist_ok=True)
        # Never promote after interruption, even if all bytes happened to arrive.
        receipt=dest/"collection.json"
        if receipt.exists():receipt.rename(dest/"unpromoted-collection.json")
        atomic(dest/"INCOMPLETE.json",{"status":"INCOMPLETE","reason":"collection supervisor interrupted/timeout"})
        raise
if __name__=="__main__":
    if sys.argv[1]=="--worker":network_collect(json.loads(sys.argv[2]),sys.argv[3])
    else:supervised_collect(json.loads(sys.argv[1]),sys.argv[2])
