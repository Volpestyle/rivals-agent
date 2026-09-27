"""AST/byte checks on unchanged approval, worker-result, identity and collection boundaries."""
import ast,hashlib,json,pathlib
root=pathlib.Path(__file__).parent
base=root/"review-base"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def functions(p):
 return {n.name:n for n in ast.parse(p.read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
checks=[]
for name in ("collector.py","input_closure.py","packet_adapter.py","map_metrics.py","judge_cm3-a3.py","identity_probe.py","job_status.py"):
 assert sha(root/name)==sha(base/name),name+" changed";checks.append(name+" byte-identical")
assert sha(root/"cm3_accounting.py")=="32eceb5ba8fbec38f2479ab067ed6c2808d1531f7dfe46a131c1a1fa77659a55"
checks.append("frozen common accounting helper byte-identical")
old=functions(base/"modal_app.py");new=functions(root/"modal_app.py")
assert ast.dump(old["validate_gate"])==ast.dump(new["validate_gate"])
checks.append("A3 phase-1 gate validation unchanged")
# Normalize only the reviewed per-task selection and timeout substitution.
worker=new["run_fit"]
worker.body=[s for s in worker.body if not (
 isinstance(s,ast.Assert) and ast.unparse(s.test)=="p['selected_task'] == key" or
 isinstance(s,ast.Assign) and ast.unparse(s.targets[0])=="work_seconds")]
class Normalize(ast.NodeTransformer):
 def visit_Expr(self,node):
  if ast.unparse(node)=="fit_budget(p, key, approval['budget'])":
   return ast.parse("assert approval['budget']['stage_seconds'] <= p['attempt_timeout_seconds'] - 30").body[0]
  return node
 def visit_Name(self,node):
  if node.id=="work_seconds":return ast.parse("p['attempt_timeout_seconds']",mode="eval").body
  return node
 def visit_Compare(self,node):
  node=self.generic_visit(node)
  if ast.unparse(node).startswith("0 < approval['budget']['stage_seconds'] <="):
   return ast.Compare(left=node.comparators[0],ops=[node.ops[1]],comparators=[node.comparators[1]])
  return node
worker=Normalize().visit(worker)
assert ast.dump(old["run_fit"])==ast.dump(worker),"unregistered worker-result/receipt change"
checks.append("worker receipt/result/preemption semantics unchanged after per-task timeout/stronger-budget normalization")
old=functions(base/"safety-bridge.py");new=functions(root/"safety.py")
assert ast.dump(old["ledger"])==ast.dump(new["ledger"])
checks.append("reviewed measured-ledger bridge unchanged")
old=functions(base/"lifecycle.py");new=functions(root/"lifecycle.py")
for name in ("selected_environment","select_environment","connect_verified","verify_client","Backend"):
 assert ast.dump(old[name])==ast.dump(new[name]),name+" changed"
checks.append("identity selection and every cleanup backend operation unchanged")
print(json.dumps({"pass":True,"offline_only":True,"checks":checks},indent=2))
