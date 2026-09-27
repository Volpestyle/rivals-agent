"""Enable one task only after external six-row batch authority validates."""
import json,pathlib,sys
from safety import require,digest
import modal_app,task_driver
from phase_transport import validate_authority
def main():
 require(len(sys.argv)==4,"approved task arguments required")
 local,runtime_path,runtime_sha=sys.argv[1:]
 require(digest(runtime_path)==runtime_sha,"runtime pin mismatch")
 runtime=json.loads(pathlib.Path(runtime_path).read_bytes())
 validate_authority(runtime["plan"])
 task_driver.DRAFT_LAUNCH_ENABLED=True
 modal_app.DEPLOYMENT_ENABLED=True
 task_driver.execute(local,{"path":runtime_path,"sha256":runtime_sha})
if __name__=="__main__":main()
