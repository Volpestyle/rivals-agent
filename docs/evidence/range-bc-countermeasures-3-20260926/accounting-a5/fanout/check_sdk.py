"""Installed Modal API/CLI surface inspection only; no client, App, Volume or RPC."""
import hashlib,inspect,json,pathlib,subprocess
import modal,modal.cli.app,modal.cli.container
from modal_proto import api_pb2
checks=[]
assert "client" in inspect.signature(modal.Volume.from_id).parameters
assert "client" in inspect.signature(modal.App.run).parameters
checks.append("explicit client supported for App.run and Volume.from_id")
normalize=modal.cli.app.display_table.__globals__["_col_name_to_json_key"]
assert [normalize(x) for x in ("App ID","Description","State","Tasks")]==["app_id","description","state","tasks"]
assert str(modal.cli.app.APP_STATE_TO_MESSAGE[api_pb2.APP_STATE_STOPPED])=="stopped"
checks.append("cleanup JSON keys and stopped terminal state match installed CLI")
fields=api_pb2.TokenInfoGetResponse.DESCRIPTOR.fields_by_name
assert {"workspace_name","workspace_id"}<=set(fields)
checks.append("TokenInfoGet identity field names present")
for args in (["app","list"],["app","stop"],["container","list"]):
    p=subprocess.run(["/Users/james/.local/bin/modal",*args,"--help"],capture_output=True,text=True,check=True)
    assert "--profile" in p.stdout
checks.append("profile argument supported on every cleanup leaf command")
sources={}
for module in (modal.cli.app,modal.cli.container):
    path=pathlib.Path(module.__file__)
    sources[module.__name__]=hashlib.sha256(path.read_bytes()).hexdigest()
print(json.dumps({"pass":True,"offline_only":True,"modal_version":modal.__version__,"checks":checks,"installed_source_hashes":sources},indent=2))
