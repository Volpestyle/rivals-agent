"""Read only this bounded result set; no new benchmarks or input reads."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def read(name):
    return json.loads((OUT / name).read_text())


def main():
    before, after = read("before.json"), read("after.json")
    assert before["rows"] == after["rows"]
    timing = []
    for name in ("000000.jpg", "000012.jpg", "000054.jpg"):
        old = read(f"timed-{name}-baseline.json")
        new = read(f"timed-{name}-candidate.json")
        assert old["output"] == new["output"]
        assert old["opencv_threads"] == new["opencv_threads"] == 32
        assert not old["torch_imported"] and not new["torch_imported"]
        assert old["hud_sha256"] == before["hud_sha256"]
        assert new["hud_sha256"] == after["hud_sha256"]
        row = dict(name=name, old_ms=old["unprofiled_cold_read_ms"],
                   new_ms=new["unprofiled_cold_read_ms"], exact_output=True)
        row["difference_ms"] = row["old_ms"] - row["new_ms"]
        for label, result in (("old", old), ("new", new)):
            stats = result["separate_cache_cleared_profile"]
            row[label + "_profile"] = [r for r in stats if r["function"] in (
                "_countdown_char", "<setcomp>", "read_cooldown", "_classify",
                "<method 'min' of 'numpy.ndarray' objects>")]
        timing.append(row)
    report = dict(
        before_hud_sha256=before["hud_sha256"], after_hud_sha256=after["hud_sha256"],
        complete_native_output_equal=23, boundaries=["read_cooldown", "read", "state_kwargs -> State"],
        before_edit_reproduction={"test": "test_repeated_reduction_is_removed",
                                  "observed_min_calls": [1024, 1024], "expected": [1024, 1],
                                  "result": "1 failed, 29 deselected"},
        after_edit_checks={"new_tests": "30 passed including 23-frame native equivalence",
                           "accepted_readiness_controls": "22 passed, 6 deselected"},
        timing_order=["000000: old/new", "000012: new/old", "000054: old/new"],
        timing=timing,
        limits=["One fresh child per version/frame, three pairs; no statistical speedup estimate.",
                "Each child has one separate cache-cleared profiled call; nested profile times overlap.",
                "Saved-JPEG reader cost excludes capture/decode/import/State construction.",
                "Unknown outputs are retained exactly; equality is not a new correctness label.",
                "No claim about native loop cost, event deadlines or visible casts."],
    )
    with (OUT / "summary.json").open("x") as out:
        json.dump(report, out, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
