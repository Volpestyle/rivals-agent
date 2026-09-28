"""Read-only authenticated collection of a complete dropout probe/fit batch."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def collect(packet, destination):
    packet, destination = Path(packet).resolve(), Path(destination)
    sys.path.insert(0, str(packet/"code"))
    from cloud.modal_guard.common import DEFAULT_ROOT
    from cloud.modal_guard.lifecycle import validate_proof
    from cloud.modal_guard.provider import connect
    import modal
    assembly = json.loads((packet/"assembly.json").read_bytes())
    records = []
    for pin in assembly["specs"]:
        raw = Path(pin["path"]).read_bytes()
        assert sha(raw) == pin["sha256"]
        spec = json.loads(raw)
        local = DEFAULT_ROOT/"attempts"/spec["attempt_id"]
        result = json.loads((local/"result.json").read_bytes())
        row = result["accounting"]
        assert result["status"] == "COMPLETE" and row["state"] == "TERMINAL"
        assert row["stage_identity"] == spec["stage_identity"]
        assert row["release_sha256"] == assembly["release_sha256"]
        validate_proof(row, row["proof"])
        stages = result["result"]["stages"]
        assert len(stages) == len(spec["stages"])
        for stage, expected in zip(stages, spec["stages"], strict=True):
            assert stage["stage"] == expected["name"] and stage["exit_code"] == 0
            assert set(stage["artifacts"]) == set(expected["artifacts"])
            assert stage["identity"] == {**spec["stage_identity"], "deadline_unix": row["stop_at"]}
        records.append((spec, local, result))
    assert len(records) == 3
    client = connect()
    destination.mkdir(parents=True, exist_ok=False)
    attempts, intervals = [], []
    for spec, local, result in records:
        volume = modal.Volume.from_name(spec["output_volume"], create_if_missing=False)
        volume.hydrate(client=client)
        assert volume.object_id == spec["stage_identity"]["output_volume_id"]
        dest = destination/spec["attempt_id"]
        dest.mkdir()
        for name in ("result.json", "teardown.json", "rates.json", "call.json", "watchdog.log"):
            (dest/name).write_bytes((local/name).read_bytes())
        pins = {}
        for stage in result["result"]["stages"]:
            for name, pin in stage["artifacts"].items():
                if not name.endswith(".json"):
                    continue
                relative = stage["stage"]+"/"+name
                remote = spec["output_root"].removeprefix("/outputs")+"/"+relative
                raw = b"".join(volume.read_file(remote))
                assert len(raw) == pin["bytes"] and sha(raw) == pin["sha256"]
                path = dest/relative
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(raw)
                pins[relative] = pin
        if assembly["mode"] == "probe":
            probe = json.loads((dest/"probe/probe.json").read_bytes())
            assert probe["hidden_dropout"] == .5 and probe["evaluation_dropout_disabled"]
            assert probe["checkpoint_sha256"] == result["result"]["stages"][0]["artifacts"]["probe-yaw.pt"]["sha256"]
            intervals.append((probe["work_started_at"], probe["work_finished_at"]))
        else:
            fit = json.loads((dest/"fit/fit.json").read_bytes())
            evaluation = json.loads((dest/"evaluation/evaluation.json").read_bytes())
            assert fit == evaluation["fit"] and fit["epoch"] == 26 and fit["updates"] == 15288
            assert evaluation["spec"]["grid"] == 4 and evaluation["spec"]["hidden_dropout"] == .5
            assert fit["checkpoint_sha256"] == result["result"]["stages"][0]["artifacts"]["epoch-26.pt"]["sha256"]
            assert fit["frozen_base_exact"] and fit["device"] == evaluation["device"] == "cuda"
            relative = "fit/status.json"
            remote = spec["output_root"].removeprefix("/outputs")+"/"+relative
            raw = b"".join(volume.read_file(remote))
            assert raw == b"".join(volume.read_file(remote))
            status = json.loads(raw)
            assert status["epoch"] == 26 and status["updates"] == 15288 and status["status"] == "complete"
            assert status["recipe"]["run_identity"] == spec["stage_identity"]["recipe_sha256"]
            assert [h["epoch"] for h in status["history"]] == list(range(1, 27))
            (dest/relative).write_bytes(raw)
            pins[relative] = dict(sha256=sha(raw), bytes=len(raw), authority="supplementary stable collection; not original guard artifact pin")
        attempts.append(dict(attempt_id=spec["attempt_id"], app_id=result["accounting"]["app_id"],
                             bound_usd=result["accounting"]["bound_usd"], pins=pins))
    value = dict(status="PASS", release_sha256=assembly["release_sha256"], attempts=attempts,
        active_holds_usd="0", mode=assembly["mode"], bound_usd=str(sum(Decimal(a["bound_usd"]) for a in attempts)),
        collected_at=time.time(), collector_sha256=sha(Path(__file__).read_bytes()))
    if intervals:
        value["three_way_work_overlap_seconds"] = max(0, min(b for _, b in intervals)-max(a for a, _ in intervals))
        value["full_fit_p95_claim"] = False
        assert value["three_way_work_overlap_seconds"] > 0, "three-way worker overlap not demonstrated"
    (destination/"collection.json").write_text(json.dumps(value, indent=2)+"\n")
    return value


if __name__ == "__main__":
    print(json.dumps(collect(sys.argv[1], sys.argv[2]), indent=2))
