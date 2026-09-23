"""Before/after for VUH-1315 (observed option status): the base commit's agent/ against this tree's, on burst trial 0 and plaza30.

  uv run --offline --no-project python -B docs/evidence/option-status-20260923/run.py

Needs feed-trial0.json and feed-plaza30.json (feed.py, which needs opencv) and reads the two recordings in place under C:/rivals-agent/data.
Writes summary.json here, nothing else. The base's agent/ is exported with `git archive` into a temporary directory. No perception, model,
Loop, Live or pad is imported, and no input is sent.

Runs, per recording: the base (holds), this tree with the kill-feed bit, and for plaza30 this tree without it, which must differ from the
base only where arrival ended an option (no KO can be read). Pins: each log's sha256, the saved frames' digest (feed.py), the code's
LF-normalized sha256.
"""
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT, HERE = Path(__file__).resolve().parents[3], Path(__file__).resolve().parent
BASE = "0f71336"
LOGS = {"trial0": Path(r"C:\rivals-agent\data\l4\burst\log.jsonl"), "plaza30": Path(r"C:\rivals-agent\data\l1\plaza30\frames.jsonl")}
CODE = ["agent/brain.py", "agent/controller.py", "agent/loop.py", "agent/state.py", "agent/jev.py", "agent/tracker.py", "agent/intents.py"]


def text_digest(path):
    return sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def frames_digest(run_dir, reads):
    d = sha256()
    for _, name, _ in reads:
        d.update(sha256((run_dir / name).read_bytes()).digest())
    return d.hexdigest()


def pressed(p):
    return bool(p["lt"] or p["rt"] or p["buttons"])


def presses(pads, after=float("-inf")):
    """The attack presses sent after `after`: [t, what] per row, what = the playing primitive and the inputs held."""
    return [[round(r["t"], 4), r["seq"] or "-", {k: r["pad"][k] for k in ("lt", "rt") if r["pad"][k]} | ({"buttons": r["pad"]["buttons"]}
            if r["pad"]["buttons"] else {})] for r in pads if r["t"] > after and pressed(r["pad"])]


def spans(ts, gap=0.05):
    out = []
    for t in ts:
        if out and t - out[-1][1] <= gap:
            out[-1][1] = t
        else:
            out.append([t, t])
    return [[round(a, 4), round(b, 4)] for a, b in out]


def options(decisions):
    """This tree's options: each one's start, and the decision on which it ended, with its evidence."""
    out, seen = [], {}
    for d in decisions:
        o = d["option"]
        if o is None:
            continue
        key = (o["kind"], o["target"], o["start_t"])
        if key not in seen:
            seen[key] = len(out)
            out.append({"kind": o["kind"], "target": o["target"], "start_t": round(o["start_t"], 4), "bound_t": round(o["bound_t"], 4),
                        "status": o["status"], "evidence": o["evidence"], "stop_t": None})
        row = out[seen[key]]
        row["status"], row["evidence"] = o["status"], o["evidence"]
        if d["stop"] is not None and row["stop_t"] is None and d["stop"].startswith(o["kind"]):
            row["stop_t"] = round(d["t"], 4)
    for row in out:
        if row["evidence"]:
            row["evidence"] = {**row["evidence"], "t": round(row["evidence"]["t"], 4)}
    return out


def holds(decisions):
    """The base's holds: each one's start (the decision that set it), its hold_until, and the decision on which it was last repeated."""
    out = []
    for d in decisions:
        if d["hold_until"] is None or d["t"] >= d["hold_until"]:   # cancelled, or lapsed (the base leaves hold_until set until the next commit)
            continue
        if not out or out[-1]["hold_until"] != round(d["hold_until"], 4):
            out.append({"held": d["held"], "start_t": round(d["t"], 4), "hold_until": round(d["hold_until"], 4), "last_t": round(d["t"], 4)})
        out[-1]["last_t"] = round(d["t"], 4)
    return out


def kos(decisions):
    """The decisions on which this tree confirmed a KO (the kill feed's second True read after a False)."""
    out, off, on = [], False, 0
    for d in decisions:
        if d["feed"] is False:
            off, on = True, 0
        elif d["feed"] is True and off:
            on += 1
            if on == 2:
                out.append(round(d["t"], 4))
    return out


def attack(p):
    return (p["lt"], p["rt"], tuple(p["buttons"]))


def differing(a, b):
    rows = [x["t"] for x, y in zip(a, b) if x["pad"] != y["pad"]]
    assert [x["row"] for x in a] == [y["row"] for y in b]
    return {"rows": len(rows), "spans": spans(rows)}


def main():
    feeds = {k: json.loads((HERE / f"feed-{k}.json").read_text()) for k in LOGS}
    for k, log in LOGS.items():
        assert sha256(log.read_bytes()).hexdigest() == feeds[k]["log_sha256"], k
        assert frames_digest(log.parent, feeds[k]["reads"]) == feeds[k]["frames_digest"], k
    runs = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        zipped = subprocess.run(["git", "archive", "--format=zip", BASE, "agent"], cwd=ROOT, check=True, capture_output=True).stdout
        zipfile.ZipFile(io.BytesIO(zipped)).extractall(tmp / "base")
        plan = [("trial0", "base", tmp / "base", "none"), ("trial0", "tree", ROOT, HERE / "feed-trial0.json"),
                ("plaza30", "base", tmp / "base", "none"), ("plaza30", "tree", ROOT, HERE / "feed-plaza30.json"),
                ("plaza30", "tree_unread", ROOT, "none")]
        for which, name, code, feed in plan:
            out = tmp / f"{which}-{name}.json"
            subprocess.run([sys.executable, "-B", str(HERE / "replay.py"), str(code), which, str(feed), str(out)], cwd=ROOT, check=True)
            runs[which, name] = json.loads(out.read_text())
    summary = {"inputs": {"base_commit": BASE,
                          "logs": {k: {"path": str(v), "sha256": feeds[k]["log_sha256"], "saved_frames": feeds[k]["frames"],
                                       "frames_digest": feeds[k]["frames_digest"]} for k, v in LOGS.items()},
                          "code_lf_sha256": {p: text_digest(ROOT / p) for p in CODE},
                          "scripts_lf_sha256": {p.name: text_digest(p) for p in (HERE / "feed.py", HERE / "replay.py", HERE / "run.py")}},
               "kill_feed_read_ms": {k: {"size": feeds[k]["size"], **feeds[k]["read_ms"]} for k in LOGS}}
    for which in LOGS:
        base, tree = runs[which, "base"], runs[which, "tree"]
        ko = kos(tree["decisions"])
        first = ko[0] if ko else None
        summary[which] = {
            "kos_confirmed_t": ko,
            "base_holds": holds(base["decisions"]),
            "tree_options": options(tree["decisions"]),
            "base_presses_after_each_ko": {str(k): spans([p[0] for p in presses(base["pads"], k)]) for k in ko},
            "tree_presses_after_each_ko": {str(k): spans([p[0] for p in presses(tree["pads"], k)]) for k in ko},
            "last_press_t": {"base": presses(base["pads"])[-1][0] if presses(base["pads"]) else None,
                             "tree": presses(tree["pads"])[-1][0] if presses(tree["pads"]) else None},
            "pads_differing_tree_vs_base": differing(tree["pads"], base["pads"]),
            "pads_identical_before_first_ko": first is None or all(x["pad"] == y["pad"] for x, y in zip(tree["pads"], base["pads"])
                                                                  if x["t"] < first),
            "base_replay_fidelity": {"rows": len(base["pads"]),
                                     "attack_inputs_as_recorded": sum(attack(r["pad"]) == attack(r["recorded"]) for r in base["pads"]),
                                     "whole_pad_as_recorded": sum(r["pad"] == {**r["recorded"], "buttons": list(r["recorded"]["buttons"])}
                                                                  for r in base["pads"])},
            "tree_stop_takes_effect_t": {str(k): next((x["t"] for x, y in zip(tree["pads"], base["pads"]) if x["t"] >= k and x["pad"] != y["pad"]),
                                                      None) for k in ko},
        }
    unread = runs["plaza30", "tree_unread"]
    summary["plaza30"]["tree_without_feed"] = {
        "options": options(unread["decisions"]),
        "pads_differing_vs_base": differing(unread["pads"], runs["plaza30", "base"]["pads"]),
        "intents_differing_vs_base": sum(a["intent"] != b["intent"] for a, b in zip(unread["decisions"], runs["plaza30", "base"]["decisions"]))}
    (HERE / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("kill_feed_read_ms",)}, indent=1))
    for which in LOGS:
        s = summary[which]
        print(which, "KOs", s["kos_confirmed_t"], "last press", s["last_press_t"], "differing", s["pads_differing_tree_vs_base"])


if __name__ == "__main__":
    main()
