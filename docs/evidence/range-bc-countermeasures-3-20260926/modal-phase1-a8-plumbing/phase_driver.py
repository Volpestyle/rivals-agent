"""Explicit approved entry point; import and legacy CLI remain launch-disabled."""
import json,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
def main():
 from phase_transport import validate_authority
 import modal_app
 p=json.loads((ROOT/"phase1-plan.json").read_bytes())
 validate_authority(p)
 # Ephemeral process flag only after exact six-row batch authority validation.
 modal_app.DEPLOYMENT_ENABLED=True
 return modal_app.orchestrate(p)
if __name__=="__main__":main()
