"""Recompute descriptive paired comparisons from frozen annotations; stdlib only."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
THRESHOLD = 0.46303320000000003

def read(name):
    return json.loads((ROOT/name).read_text(encoding="utf-8"))

def main():
    for name, expected in (
        ("causal-annotations.json", "73d29d5c8964de4f41d4c22b9fac9330a2ab943e8bf0a1fe13ed2e0d5be2ddc7"),
        ("outcome-annotations.json", "e3ddf65c0e649c39d0a08710ff4e99fdea7b681307a9888c62765a538b5602f2"),
    ):
        # Git checkouts may use CRLF; frozen content/hash uses LF.
        assert hashlib.sha256((ROOT/name).read_bytes().replace(b"\r\n", b"\n")).hexdigest() == expected
    causal = {r["id"]: r for r in read("causal-annotations.json")["examples"]}
    outcome = {r["id"]: r for r in read("outcome-annotations.json")["examples"]}
    key = read("frame-key.json")
    assert len(key) == len(causal) == len(outcome) == 48
    assert set(causal) == set(outcome) == {r["id"] for r in key}
    assert len({r["session"] for r in key}) == 8
    rows = []
    for e in sorted(key, key=lambda r:r["id"]):
        c, o = causal[e["id"]], outcome[e["id"]]
        bots = {b["id"]: b for b in c["candidates"]}
        for b in bots.values():
            x = (b["box"][0]+b["box"][2])/2/2560
            assert x == b["x"]
            assert b["side"] == ("left" if x < .49 else "right" if x > .51 else "abstain")
        near = bots[c["nearest"]]["side"] if c["nearest"] else "abstain"
        oracle = bots[o["pre_anchor_id"]]["side"] if o["pre_anchor_id"] else "abstain"
        truth = "left" if e["yaw"] < -THRESHOLD else "right" if e["yaw"] > THRESHOLD else "none"
        assert (e["kind"] == "onset") == (truth != "none")
        rows.append(dict(id=e["id"],session=e["session"],kind=e["kind"],yaw=e["yaw"],truth=truth,
            causal_status=c["focus"],causal_id=c["focus_id"],causal_side=c["focus_side"],
            causal_confidence=c["confidence"],prediction=c["prediction"],nearest_id=c["nearest"],
            nearest_side=near,outcome_target=o["eventual_target"],outcome_id=o["pre_anchor_id"],
            oracle_side=oracle,outcome_confidence=o["confidence"],categories=";".join(o["categories"])))
    with (ROOT/"comparisons.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

    def paired(rs, field, support):
        supported=[r for r in rs if support(r)]
        both=[r for r in supported if r[field] in ("left","right") and r["nearest_side"] in ("left","right")]
        win=[r["id"] for r in both if r[field]==r["truth"] and r["nearest_side"]!=r["truth"]]
        loss=[r["id"] for r in both if r[field]!=r["truth"] and r["nearest_side"]==r["truth"]]
        return dict(supported=len(supported),supported_ids=[r["id"] for r in supported],
            target_center_abstain=sum(r[field]=="abstain" for r in supported),
            nearest_abstain=sum(r["nearest_side"]=="abstain" for r in supported),
            both_directional=len(both),paired_ids=[r["id"] for r in both],
            target_correct=sum(r[field]==r["truth"] for r in both),
            nearest_correct=sum(r["nearest_side"]==r["truth"] for r in both),
            wins=win,losses=loss,ties=len(both)-len(win)-len(loss))
    def summarize(rs):
        onset=[r for r in rs if r["kind"]=="onset"]
        still=[r for r in rs if r["kind"]=="still"]
        return dict(onset_n=len(onset),still_n=len(still),
            causal_status=dict(Counter(r["causal_status"] for r in rs)),
            onset_causal_status=dict(Counter(r["causal_status"] for r in onset)),
            still_causal_status=dict(Counter(r["causal_status"] for r in still)),
            causal=paired(onset,"causal_side",lambda r:r["causal_status"]=="one"),
            oracle=paired(onset,"oracle_side",lambda r:r["outcome_id"] is not None),
            outcome_unknown=sum(r["outcome_target"]=="unknown" for r in rs),
            outcome_known_unlinked=[r["id"] for r in rs if r["outcome_target"]!="unknown" and r["outcome_id"] is None],
            onset_outcome_unknown=sum(r["outcome_target"]=="unknown" for r in onset),
            still_outcome_unknown=sum(r["outcome_target"]=="unknown" for r in still),
            still_offcenter_focus=[r["id"] for r in still if r["causal_side"] in ("left","right")],
            still_center_focus=[r["id"] for r in still if r["causal_status"]=="one" and r["causal_side"]=="abstain"],
            still_directional_prediction=[r["id"] for r in still if r["prediction"] in ("left","right")],
            still_nearest_directional=[r["id"] for r in still if r["nearest_side"] in ("left","right")],
            categories=dict(Counter(cat for r in rs for cat in r["categories"].split(";"))))
    sessions={}
    for sid in sorted({r["session"] for r in rows}):
        subset=[r for r in rows if r["session"]==sid]
        assert Counter(r["kind"] for r in subset)=={"onset":3,"still":3}
        anchors=sorted(e["anchor_ns"] for e in key if e["session"]==sid)
        assert all(b-a>=2_000_000_000 for a,b in zip(anchors,anchors[1:]))
        sessions[sid]=summarize(subset)
    result=dict(all=summarize(rows),sessions=sessions)
    (ROOT/"results.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
