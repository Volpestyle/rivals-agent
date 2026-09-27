"""Check F1's exact delta against the preceding independently reviewed packet."""
import ast,hashlib,json,pathlib
root=pathlib.Path(__file__).resolve().parent
base=root/"f1-reference"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def functions(p):
 return {n.name:ast.dump(n) for n in ast.parse(p.read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
assert sha(base/"files.json")=="395643cae0e1a86d49407402051274c9a46f04a2f52a5498b20fc95eff50a764"
pins=json.loads((base/"files.json").read_text())["files"]
checks=[]
changed={"safety.py","cm3_accounting.py","test_fixes.py"}
for name,digest in pins.items():
 if name in changed or name=="HANDBACK.md":continue
 path=root/name
 if path.is_file():
  assert sha(path)==digest,name+" changed outside F1"
  checks.append(name+" byte-identical")
assert sha(base/"safety.py")==pins["safety.py"]
old=functions(base/"safety.py");new=functions(root/"safety.py")
assert set(new)-set(old)=={"measured_inventory"}
for name in old:
 if name not in {"ledger","validate_binding"}:
  assert old[name]==new[name],name+" changed outside F1"
checks.append("all safety functions except ledger/validate_binding unchanged, including fit_budget exact SHA equality")
assert sha(root/"cm3_accounting.py")=="ad2d3c568ad0e7c08a4ae3c2680d02344288594b0bc985591108f9707e968835"
checks.append("shared helper byte-identical to r3-impl frozen F1")
assert "DEPLOYMENT_ENABLED=False" in (root/"modal_app.py").read_text()
plan=json.loads((root/"launch-plan.json").read_text())
assert not plan["integration_review_pass"] and not plan["fixes2_review_pass"] and not plan["tasks"]
checks.append("launch disabled and plan unapproved")
print(json.dumps({"pass":True,"offline_only":True,"checks":checks},indent=2))
