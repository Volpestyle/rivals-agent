"""EXPLORATORY live-match target admission; never interpret replay viewer inputs.

An external, hash-pinned admission receipt is required in addition to the registry
role. Registration alone is insufficient. This module does not grant admission.
The receipt and this selection boundary need independent review before real use.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from policy.idm import receipt_current

FORMAT = "rivals-idm-match-admission-v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def identity(header):
    return {k: header[k] for k in ("bindings", "swing_mode", "accel_on", "patch", "settings_hash", "calibration")}


@dataclass(frozen=True)
class Admission:
    sessions: dict
    registry: dict
    sha256: str
    receipt_pins: dict | None = None

    def check(self, session_id, media=None):
        from policy import idm_targets as T

        if self.receipt_pins is not None:
            receipt_current.require_current({session_id: self.receipt_pins.get(session_id)})

        row = self.registry.get(session_id)
        T._require(row is not None and row.get("split") == "idm_train", "match is not registered idm_train")
        T._require(not row.get("sealed") and not row.get("training_pending"), "match admission/motor identity pending")
        # A replay's viewer log must never enter the human-input target builder.
        T._require(not row.get("pair"), "replay needs a separately reviewed live-target alignment path")
        entry = self.sessions.get(session_id)
        T._require(entry is not None and entry.get("source_kind") == "live", "no reviewed live-match admission")
        T._require(entry.get("media_sha256") == row.get("expected_media_sha256"), "match media identity mismatch")
        T._require(entry.get("session_group") == row.get("session_group"), "match family mismatch")
        T._require(media is None or media == entry["media_sha256"], "match target media mismatch")
        for key in ("steps_sha256", "imported_demo_sha256", "identity_sha256", "motor_statement_sha256"):
            pin = entry.get(key)
            T._require(isinstance(pin, str) and len(pin) == 64 and all(c in "0123456789abcdef" for c in pin),
                       f"match admission lacks {key}")
        return entry

    def header(self, header):
        from policy import idm_targets as T

        e = self.check(header["session_id"], header["media_sha256"])
        T._require(header["session_group"] == e["session_group"], "target family differs from admission")
        T._require(digest(identity(header)) == e["identity_sha256"], "match motor/calibration identity differs")
        for key in ("steps", "imported_demo"):
            T._require(header["source"][key]["sha256"] == e[key + "_sha256"], "match source differs from admission")


def load(path, sha256_pin, *, registry, denylist):
    from policy import idm_targets as T
    from agent import human_intake as hi

    raw = Path(path).read_bytes()
    T._require(hashlib.sha256(raw).hexdigest() == sha256_pin, "match admission hash mismatch")
    doc = json.loads(raw)
    T._require(doc.get("format") == FORMAT and doc.get("scope") == "EXPLORATORY", "match admission format/scope")
    T._require(doc.get("decision") == "accepted" and doc.get("reviewer"), "match admission not independently accepted")
    receipt_pins = {sid: sha256_pin for sid in doc["sessions"]}
    T._require(receipt_pins, "match admission has no sessions")
    receipt_current.require_current(receipt_pins)
    hi.check_registry(registry, denylist=denylist)  # includes role/family/denylist validation
    reg = json.loads(Path(registry).read_text(encoding="utf-8"))
    rows = {r["session_id"]: r for r in reg["sessions"]}
    result = Admission(doc["sessions"], rows, sha256_pin, receipt_pins)
    for sid in doc["sessions"]:
        entry = result.check(sid)
        T.refuse_sealed(sid, entry["media_sha256"], denylist)
    return result


def references(manifest):
    """One legacy receipt or an explicit list; never silently prefer one spelling."""
    from policy import idm_targets as T

    T._require(not ("match_admission" in manifest and "match_admissions" in manifest),
               "choose match_admission or match_admissions, not both")
    if "match_admissions" in manifest:
        refs = manifest["match_admissions"]
    else:
        ref = manifest.get("match_admission")
        refs = [] if ref is None else [ref]
    T._require(isinstance(refs, list), "match_admissions must be a list")
    for ref in refs:
        T._require(isinstance(ref, dict) and set(ref) == {"path", "sha256"}, "receipt needs path and sha256")
        T._require(isinstance(ref["path"], str) and ref["path"], "receipt path required")
        T._require(isinstance(ref["sha256"], str) and len(ref["sha256"]) == 64
                   and all(c in "0123456789abcdef" for c in ref["sha256"]), "receipt sha256 required")
    return refs


def load_references(refs, *, registry, denylist):
    """Authenticate every receipt before combining disjoint session entries.

    No target rows are read here. Each member keeps the existing accepted/reviewer,
    registry, motor and sealed checks. For multiple receipts `sha256` identifies
    the ordered pinned-reference set, not a fictional merged admission document.
    """
    from policy import idm_targets as T

    receipts = [load(ref["path"], ref["sha256"], registry=registry, denylist=denylist) for ref in refs]
    if not receipts:
        return None
    if len(receipts) == 1:
        return receipts[0]
    sessions = {}
    for receipt in receipts:
        T._require(receipt.registry == receipts[0].registry, "registry changed between admission receipts")
        T._require(receipt.sessions, "empty member of admission receipt set")
        T._require(not sessions.keys() & receipt.sessions.keys(), "duplicate session across admission receipts")
        sessions.update(receipt.sessions)
    pins = {sid: pin for receipt in receipts for sid, pin in receipt.receipt_pins.items()}
    return Admission(sessions, receipts[0].registry, digest(refs), pins)


def load_steps(path, targets, admission, denylist):
    """Validate an admitted match table without broadening the policy loader.

    The range schema's human split enum predates idm_train. After authenticating
    the original match role, apply its remaining schema checks to a temporary
    header view. The returned Session retains idm_train, as do all source bytes.
    """
    from policy import idm_targets as T
    from policy.range_bc import steps

    T._require(admission is not None, "match admission required before step payload")
    admission.header(targets.header)
    entry = admission.check(targets.session_id, targets.header["media_sha256"])
    pin = T.sha256(path)
    T._require(pin == entry["steps_sha256"], "step table differs from admission")
    with Path(path).open(encoding="utf-8") as stream:
        header = json.loads(stream.readline())
        T.refuse_sealed(header.get("session_id"), header.get("media_sha256"), denylist)
        T._require(header.get("split") == "idm_train" and header.get("session_id") == targets.session_id,
                   "match step role/identity mismatch")
        T._require(header.get("media_sha256") == entry["media_sha256"]
                   and header.get("session_group") == entry["session_group"], "match step media/family mismatch")
        T._require(digest(identity(header)) == entry["identity_sha256"], "match step motor identity mismatch")
        # Only split-dependent policy guard is the test-split refusal. Original
        # idm_train is authenticated above; sealed checks remain unconditional.
        steps.check_header({**header, "split": "train"}, denylist=denylist)
        rows = [json.loads(line) for line in stream if line.strip()]
    T._require(rows and T.sha256(path) == pin, "empty/changed match step table")
    for i, row in enumerate(rows):
        steps.check_row(row, header, i)
    steps.check_sequence(rows, header)
    return steps.Session(str(path), pin, header, rows)
