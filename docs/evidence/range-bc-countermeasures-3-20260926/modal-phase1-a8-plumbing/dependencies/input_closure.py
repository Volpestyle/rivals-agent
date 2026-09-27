"""Exact allowlist before upload; exact mounted-volume inventory before launch.
This module never discovers sources or uploads. The catalog is externally lead-pinned.
"""
import json,pathlib
from safety import require,relative,sha,digest,document,number,canonical,remote_path
TRAIN=("20260923T051828-422Z-33696-1","20260923T200129-346Z-33696-6","20260924T232304-170Z-12024-1","20260925T021320-371Z-7804-1","20260925T025230-605Z-7804-2")
DEV=("20260923T171533-187Z-33696-5","20260923T205528-900Z-45572-3")
def schema(m):
    require(m["format"]=="cm3-input-closure-v1" and m["sealed_excluded"] is True,"sealed exclusion missing")
    require(m["train_sessions"]==list(TRAIN) and m["frozen_dev_sessions"]==list(DEV),"changed authorized roster")
    require(m["profile"]=="rivals" and m["workspace"]=="volpestyle","wrong input account")
    require(isinstance(m["volume_name"],str) and m["volume_name"] and isinstance(m["volume_id"],str) and m["volume_id"].startswith("vo-"),"volume binding absent")
    code=relative(m["code_directory"]);asset=relative(m["asset_directory"])
    files=m["files"];require(isinstance(files,list) and files,"empty input closure")
    by_path={};seen_sessions=set();kinds=set()
    for row in files:
        path=relative(row["path"]);sha(row["sha256"])
        require(type(row["bytes"]) is int and row["bytes"]>=0,"invalid manifest bytes")
        require(str(path) not in by_path,"duplicate path")
        kind=row["kind"];require(kind in ("train","frozen-dev","code","asset","receipt"),"unapproved file category")
        if kind in ("train","frozen-dev"):
            sid=row["session_id"];require(sid in (TRAIN if kind=="train" else DEV),"unapproved/sealed session")
            require(sid in path.parts or path.stem==sid or path.name.startswith(sid+"."),"session/path mismatch")
            seen_sessions.add(sid)
        elif kind=="code":require(path.is_relative_to(code),"code outside closure")
        elif kind=="asset":require(path.is_relative_to(asset),"asset outside closure")
        else:require(path.suffix==".json","receipt must be explicit JSON")
        by_path[str(path)]=row;kinds.add(kind)
    require(seen_sessions==set(TRAIN+DEV) and kinds=={"train","frozen-dev","code","asset","receipt"},"incomplete input categories/roster")
    return by_path
def pinned_refs(value):
    if isinstance(value,dict):
        if "path" in value and "sha256" in value:yield value
        for child in value.values():yield from pinned_refs(child)
    elif isinstance(value,list):
        for child in value:yield from pinned_refs(child)

def bind_context(m,context,control_refs=None):
    files=schema(m)
    require(m["context_sha256"]==canonical(context),"manifest/context changed")
    # Only these context metadata fields may use approved output control refs.
    # Corpus, cache, registry, denylist, sidecars and assets retain /inputs rules.
    controls={} if control_refs is None else dict(control_refs)
    eligible={}
    for name in ("implementation_review","judge","judge_tests"):
        ref=context.get(name)
        if isinstance(ref,dict) and set(ref)=={"path","sha256"}:
            eligible[ref["path"]]=ref["sha256"]
    require(all(path in eligible and eligible[path]==pin for path,pin in controls.items()),"extra/unbound control authority")
    used=set()
    for field,value in context.items():
        for ref in pinned_refs(value):
            path=remote_path(ref["path"])
            if path.is_relative_to("/outputs/.modal-control"):
                require(ref["path"] in controls and controls[ref["path"]]==ref["sha256"],"control reference not externally pinned")
                require(field in ("implementation_review","judge","judge_tests") and eligible.get(ref["path"])==ref["sha256"],"control reference in unapproved context field")
                used.add(ref["path"])
                continue
            require(path.parts[1]=="inputs","common context outside frozen input or approved control mount")
            row=files.get(str(path.relative_to("/inputs")))
            require(row is not None and row["sha256"]==ref["sha256"],"common-context reference omitted/changed")
    require(used==set(controls),"unused control authority")
    for name,h in context["code"].items():
        key=str(relative(m["code_directory"])/relative(name))
        require(key in files and files[key]["kind"]=="code" and files[key]["sha256"]==h,"code closure omitted/changed")
    require(set(context["sources"])==set(TRAIN+DEV),"context source roster")
    for sid,source in context["sources"].items():
        require(source["role"]==("train" if sid in TRAIN else "dev"),"changed source role")
        require((source.get("sidecar") is not None)==(sid in TRAIN),"train sidecar closure missing or dev sidecar added")
        for key in ("table","sidecar"):
            ref=source.get(key)
            if ref is not None:
                path=remote_path(ref["path"]);require(path.parts[1]=="inputs","source outside input volume")
                row=files.get(str(path.relative_to("/inputs")))
                require(row is not None and row.get("session_id")==sid and row["sha256"]==ref["sha256"],"source reference not in manifest")
        cache=remote_path(source["cache"]);require(cache.parts[1]=="inputs","cache outside input mount")
        for name in ("global.u8","crop.u8","hud.u8","cache.json"):
            key=str(cache.relative_to("/inputs")/name)
            require(key in files and files[key].get("session_id")==sid,"cache closure incomplete")
        require(files[str(cache.relative_to("/inputs")/"cache.json")]["sha256"]==source["cache_manifest_sha256"],"cache manifest changed")
    require(str(remote_path(context["assets"]["directory"]).relative_to("/inputs"))==m["asset_directory"],"asset root changed")
    config=str(relative(m["asset_directory"])/"config.json")
    require(files.get(config,{}).get("sha256")==context["assets"]["config_sha256"],"asset config not pinned")
    return files
def checked_root(root,mounted_volume_id=None):
    root=pathlib.Path(root)
    require(root.is_dir(),"invalid staging/mount root")
    if root.is_symlink():
        # Only Modal's observed top-level alias is allowed, bound to the pinned volume.
        # Keep the logical root for traversal and all emitted reference namespaces.
        require(str(root)=="/inputs" and isinstance(mounted_volume_id,str)
                and mounted_volume_id.startswith("vo-")
                and pathlib.PurePosixPath(mounted_volume_id).name==mounted_volume_id,
                "unapproved staging/mount alias")
        expected=pathlib.Path("/__modal/volumes")/mounted_volume_id
        require(root.readlink()==expected and root.resolve(strict=True)==expected
                and not expected.is_symlink(),"mounted root differs from pinned volume")
    return root
def inventory(root,mounted_volume_id=None):
    root=checked_root(root,mounted_volume_id)
    found={}
    for path in root.rglob("*"):
        require(not path.is_symlink(),"symlink in closure")
        if path.is_file():found[path.relative_to(root).as_posix()]=path.stat().st_size
    return found
def check_bytes(m,root,mounted_volume_id=None):
    rows=schema(m);found=inventory(root,mounted_volume_id)
    require(set(found)==set(rows),"extra or missing input files; no payload read")
    require(all(found[k]==rows[k]["bytes"] for k in rows),"input size mismatch")
    for name,row in rows.items():require(digest(pathlib.Path(root)/name)==row["sha256"],"changed input bytes: "+name)
def freeze(catalog_ref,staging_root,destination):
    catalog=document(catalog_ref)
    require(catalog["approved_by"]=="herdr-lead","catalog not approved")
    bind_context(catalog,document(catalog["approved_context"]));check_bytes(catalog,staging_root)
    frozen=dict(catalog,status="FROZEN",catalog_sha256=catalog_ref["sha256"])
    with pathlib.Path(destination).open("x") as f:json.dump(frozen,f,indent=2)
    return frozen
def verify_mounted(manifest_ref,root,volume_id):
    m=document(manifest_ref);require(m["status"]=="FROZEN" and m["volume_id"]==volume_id,"wrong mounted volume")
    check_bytes(m,root,volume_id)
    return {"format":"cm3-volume-verification-v1","status":"PASS","exact_inventory":True,"sealed_excluded":True,
            "profile":"rivals","workspace":"volpestyle","volume_name":m["volume_name"],"volume_id":volume_id,
            "manifest_sha256":manifest_ref["sha256"],"files":len(m["files"]),"bytes":sum(x["bytes"] for x in m["files"]),
            "verifier_sha256":digest(__file__)}
def validate_input(p,context):
    m=document(p["input_manifest"]);require(m["status"]=="FROZEN","input manifest not frozen")
    rows=bind_context(m,context)
    require(context["code"].get("policy/range_bc/cm3_run.py")==p["entrypoint_sha256"],"manifest/owner entrypoint mismatch")
    require(m["volume_name"]==p["reviewed_input_volume"] and m["volume_id"]==p["input_volume_id"] and m["code_directory"]==p["code_directory"],"plan/volume/manifest mismatch")
    receipt=document(p["input_verification"])
    expected={"format":"cm3-volume-verification-v1","status":"PASS","exact_inventory":True,"sealed_excluded":True,
              "profile":"rivals","workspace":"volpestyle","volume_name":m["volume_name"],"volume_id":m["volume_id"],
              "manifest_sha256":p["input_manifest"]["sha256"],"files":len(rows),"bytes":sum(x["bytes"] for x in rows.values()),"verifier_sha256":digest(__file__)}
    require(receipt==expected,"remote exact verification not bound")
    for task in p["tasks"].values():
        allocation=task["attempt_receipts"][0]
        require(allocation["path"] in rows and rows[allocation["path"]]["kind"]=="receipt" and rows[allocation["path"]]["sha256"]==allocation["sha256"],"fit receipt omitted from frozen volume")
    if p["phase"]=="phase2":
        ref=p["phase1_gate"]["remote_ref"];key=str(remote_path(ref["path"]).relative_to("/inputs"))
        require(key in rows and rows[key]["sha256"]==ref["sha256"],"gate omitted from input closure")
    return m


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation",choices=("freeze","verify-mounted"))
    parser.add_argument("--reference",required=True,help="JSON {local_path,sha256} with external lead pin")
    parser.add_argument("--root",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--volume-id")
    args=parser.parse_args()
    ref=json.loads(args.reference)
    if args.operation=="freeze":freeze(ref,args.root,args.output)
    else:
        require(args.volume_id,"volume ID required")
        result=verify_mounted(ref,args.root,args.volume_id)
        with pathlib.Path(args.output).open("x") as stream:json.dump(result,stream,indent=2)
