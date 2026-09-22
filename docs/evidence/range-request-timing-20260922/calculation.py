"""Arithmetic over accepted reports only. No runtime imports or media access."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / "docs/evidence/range-cast-calibration-d-20260922"
SETTINGS = Path(__file__).with_name("current-saved-settings.json")
OUTPUT = Path(__file__).with_name("results.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    paths = {name: ARCHIVE / name for name in
             ("audit-results.json", "execution-diagnosis.json", "code-receipt.json", "shadow-report.json")}
    docs = {name: json.loads(path.read_text()) for name, path in paths.items()}
    settings = json.loads(SETTINGS.read_text())
    assert sha(SETTINGS) == "26b48957c1c8cfaa2f9ab846ef097183786f5f7f879926106066de6a6e3575c9"
    visual = docs["audit-results.json"]
    execution = docs["execution-diagnosis.json"]
    offset = visual["jpg_video_correspondence"]
    median = offset["median_offset_seconds"]
    lo, hi = offset["one_frame_expanded_empirical_envelope_seconds"]
    events = []
    for event in visual["events"]:
        if not event["observed_casts"]:
            continue
        slot = next(s for s in execution["slots"] if s["decision_id"] == event["owned_decision"])
        edge = next(e for e in execution["execution_edges"] if e["decision_id"] == event["owned_decision"] and e["press_edge"])
        first_send = slot["lt_sends"][0]
        emission_lo, emission_hi = event["projectile_emission_bracket_open_closed"]
        references = {"decision_acquisition": slot["observed_t"], "controller_press_edge": edge["execution_t"],
                      "first_LT_attempt": first_send["attempted_t"], "first_LT_return": first_send["returned_t"],
                      "decision_acquisition_plus_100ms": slot["observed_t"] + .1,
                      "actual_D_request_deadline": slot["request_valid_until"]}
        elapsed = {name: {"reference_t": t,
                          "median_offset_bracket_ms": [(emission_lo - median - t) * 1000, (emission_hi - median - t) * 1000],
                          "broad_empirical_envelope_ms": [(emission_lo - hi - t) * 1000, (emission_hi - lo - t) * 1000]}
                   for name, t in references.items()}
        events.append({"decision": event["owned_decision"], "native_emission_bracket": [emission_lo, emission_hi],
                       "mapped_emission_empirical_envelope": [emission_lo-hi, emission_hi-lo],
                       "elapsed": elapsed,
                       "first_LT_attempt_to_return_ms": (first_send["returned_t"]-first_send["attempted_t"]) * 1000,
                       "acquisition_to_first_LT_attempt_ms": (first_send["attempted_t"]-slot["observed_t"]) * 1000})
    code_paths = ("policy/range_policy.py", "policy/range_skill_policy.py", "agent/learned_range_skill.py",
                  "agent/brain.py", "agent/tracker.py", "agent/state.py", "agent/controller.py", "agent/loop.py",
                  "agent/intents.py", "perception/hud.py", "perception/outline.py")
    code = {}
    for name in code_paths:
        raw = (ROOT / name).read_bytes()
        code[name] = {"current_bytes_sha256": hashlib.sha256(raw).hexdigest(),
                      "LF_normalized_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()}
        deployed = docs["code-receipt.json"]["paths"].get(name)
        if deployed:
            code[name]["D_deployed_sha256"] = deployed["sha256"]
            code[name]["exact_match_to_D_deployed"] = code[name]["current_bytes_sha256"] == deployed["sha256"]
    result = {"scope": "report_only_arithmetic_and_read_only_code_identity_comparison",
              "formula": "emission PTS = acquisition-clock coordinate + offset; broad elapsed envelope = (PTS_lo-offset_hi-reference, PTS_hi-offset_lo-reference]",
              "offset": offset, "events": events,
              "source_identity": docs["shadow-report.json"]["checkpoint"]["original_source_identity"],
              "source_spec": docs["shadow-report.json"]["checkpoint"]["spec"],
              "shadow_executed_code_hashes": docs["shadow-report.json"]["code_hashes"],
              "current_saved_settings_sha256": sha(SETTINGS),
              "current_client": settings["source_patch_identifier_if_accepted"],
              "settings_observed_utc": settings["observed_utc"], "code": code,
              "report_hashes": {name: sha(path) for name, path in paths.items()},
              "limits": ["The empirical visual-offset envelope is not a guaranteed bound, confidence interval or physical input clock.",
                         "An LT API attempt/return is not a measured physical press. No media was decoded or inspected here.",
                         "Post-D persisted settings are not backdated to D and do not prove all active/default settings.",
                         "No new runtime/deployment identity, semantic review, inference, training or input is issued by this arithmetic."]}
    with OUTPUT.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(events, indent=2))
    print(json.dumps(code, indent=2))


if __name__ == "__main__":
    main()
