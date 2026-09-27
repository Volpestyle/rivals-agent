"""A3 packet assembly after owner verification. No training/cloud/data access.
Production entry: assemble_collected rehashes a MATRIX_VERIFIED artifact closure.
assemble is a pure internal mapping helper used by synthetic fixtures.
The independent judge remains mandatory; successful assembly is not acceptance.
"""
import copy
from map_metrics import map_arm,require_report_diagnostics,judge

def assemble(verification, rows, report_metadata, execution, gate, launch, elapsed_compute_seconds):
    assert verification["format"]=="cm3-matrix-verification-v1" and verification["status"]=="PASS"
    assert len(rows)==13
    refs=[r["ref"] for r in rows]
    canonical=lambda xs:sorted((x["path"],x["sha256"]) for x in xs)
    assert canonical(refs)==canonical(verification["outputs"])
    assert len(set(canonical(refs)))==13
    expected={(a,s,"registered") for a in ("A","H","I","W") for s in range(3)}|{("H",0,"repeat")}
    keys=[(r["result"]["arm"],r["result"]["seed"],r["result"]["purpose"]) for r in rows]
    assert set(keys)==expected and len(keys)==len(set(keys))
    for row in rows:
        assert row["result"]["status"]=="PASS"
        assert row["result"]["context_sha256"]==verification["context_sha256"]
        assert row["result"]["hardware"]==verification["hardware"]
        assert row["result"]["code_sha256"]==verification["code_sha256"]
        assert row["result"]["software_sha256"]==verification["software_sha256"]
    executed={(e["arm"],e["seed"]):e for e in execution}
    assert len(executed)==len(execution)==13
    for row in rows:
        r,d=row["result"],row["details"]
        key=("H-repeat" if r["purpose"]=="repeat" else r["arm"],r["seed"])
        assert executed[key]["checkpoint_sha256"]==d["checkpoint_sha256"]
        assert executed[key]["content_sha256"]==d["stable_sha256"]
    assert launch["amendment"]==3 and launch["execution_mode"]=="two-phase"
    assert launch["benchmark_provider"]=="modal"
    assert launch["device"]["model"]==launch["device"]["instance"]
    assert launch["device"]["model"]=="modal:L40S"
    assert verification["hardware"]["class"]=="cuda:L40S"
    core={}
    for arm in ("A","H","I","W"):
        selected=[r for r in rows if r["result"]["arm"]==arm and r["result"]["purpose"]=="registered"]
        mapped=map_arm(selected)
        report=copy.deepcopy(report_metadata[arm])
        assert not (set(report)&{"metrics","epochs_log","checkpoints","context","raw_diagnostics"})
        assert report["arm"]==arm and report["device"]==launch["device"]
        report.update(mapped)
        report["context"]=require_report_diagnostics(arm,{str(r["result"]["seed"]):r["details"]["context"] for r in selected})
        core[arm]=report
    packet={"format":"cm3-reports-v1","status":"COMPLETE","interruption":None,"core":core,
            "execution":copy.deepcopy(execution),"phase1_gate":copy.deepcopy(gate),
            "elapsed_compute_seconds":elapsed_compute_seconds,"reader":None}
    # Actual timestamps and checkpoint/content identities are supplied unchanged.
    # This rejects missing jobs, substituted gate outputs and phase-order violations.
    assert judge().check_execution(packet,launch),"aggregate 16-hour compute cap exceeded"
    return packet

def assemble_collected(destination,collection_manifest_ref,report_metadata,execution,gate,launch,elapsed_compute_seconds):
    from collector import load_verified
    verification,rows=load_verified(destination,collection_manifest_ref)
    return assemble(verification,rows,report_metadata,execution,gate,launch,elapsed_compute_seconds)
