"""Authenticated current admission heads, including revocations across relocation.

The complete canonical metadata bundle is source-pinned. A deployment must carry
its index and every listed receipt/marker. Adjacent files beside a copied receipt
are never a fallback authority. A new admission requires an explicit bundle refresh.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "policy/idm/receipt-current.json"
INDEX_SHA256 = "2e2b286342befc7e8c08bb9be6a9624bebc41bcf0c806a87a937fa8e02ab453d"  # LF
FORMAT = "rivals-idm-current-receipts-v1"
ACCEPTED = re.compile(r"(.+)\.accepted(?:-a([1-9][0-9]*))?\.json\Z")


def need(condition, message):
    from policy import idm_targets as T
    T._require(condition, "current receipt authority: " + message)


def raw(path):
    need(path.is_file() and not path.is_symlink(), f"missing/linked metadata {path}")
    return path.read_bytes()


def heads():
    """Return {session: current receipt hash}; all reads are receipt metadata only."""
    from policy.idm.match_targets import FORMAT as RECEIPT_FORMAT

    index_raw = raw(INDEX).replace(b"\r\n", b"\n")
    need(hashlib.sha256(index_raw).hexdigest() == INDEX_SHA256, "index hash mismatch")
    index = json.loads(index_raw)
    need(index.get("format") == FORMAT and index.get("scope") == "EXPLORATORY", "index format/scope")
    files = index.get("files")
    need(isinstance(files, dict) and files, "empty metadata bundle")
    # New local canonical metadata must trigger an explicit authority refresh.
    # On cloud the pin authenticates completeness even if a partial upload omits files.
    found = {p.relative_to(ROOT).as_posix() for p in (ROOT / "docs/evidence").glob("idm-match*/receipt/*.json")
             if ".accepted" in p.name or ".superseded" in p.name}
    need(found == set(files), "incomplete or changed canonical metadata inventory")
    receipts, markers = {}, []
    for name, pin in files.items():
        relative = Path(name)
        need(not relative.is_absolute() and ".." not in relative.parts, "unsafe canonical path")
        p = ROOT / relative
        need(p.resolve().is_relative_to(ROOT.resolve()), "canonical path escapes bundle")
        content = raw(p)
        need(hashlib.sha256(content).hexdigest() == pin, f"metadata hash mismatch: {name}")
        doc = json.loads(content)
        if doc.get("status") == "superseded":
            markers.append(doc)
            continue
        match = ACCEPTED.fullmatch(p.name)
        need(match is not None and doc.get("format") == RECEIPT_FORMAT
             and doc.get("scope") == "EXPLORATORY" and doc.get("decision") == "accepted"
             and doc.get("reviewer"), f"not independently accepted metadata: {name}")
        need(isinstance(doc.get("sessions"), dict) and doc["sessions"], "receipt has no sessions")
        need(pin not in receipts, "duplicate receipt hash")
        receipts[pin] = dict(path=relative, doc=doc, revision=int(match[2] or 0),
                             family=(relative.parent.as_posix(), match[1]))
    revoked = set()
    for marker in markers:
        old = marker.get("historical_receipt", {})
        pin = old.get("sha256")
        need(pin in receipts and old.get("path") == receipts[pin]["path"].as_posix(),
             "revocation lacks its exact historical receipt")
        revoked.add(pin)
    by_session = {}
    for pin, receipt in receipts.items():
        doc, revision = receipt["doc"], receipt["revision"]
        if revision:
            supersedes = doc.get("supersedes", {})
            old = receipts.get(supersedes.get("sha256"))
            need(old is not None, "incomplete supersession chain")
            parent_path = Path(supersedes.get("path", ""))
            need(not parent_path.is_absolute() and ".." not in parent_path.parts,
                 "unsafe supersession path")
            need(receipt["path"].parent.parent / parent_path == old["path"]
                 and old["family"] == receipt["family"] and old["revision"] + 1 == revision
                 and set(old["doc"]["sessions"]) == set(doc["sessions"]), "invalid supersession chain")
            for sid in doc["sessions"]:
                for key in ("media_sha256", "session_group"):
                    need(doc["sessions"][sid].get(key) == old["doc"]["sessions"][sid].get(key),
                         "supersession changes session identity")
            revoked.add(supersedes["sha256"])
        else:
            need(not doc.get("supersedes"), "base receipt cannot supersede another revision")
        for sid in doc["sessions"]:
            by_session.setdefault(sid, []).append((revision, pin, receipt["family"]))
    current = {}
    for sid, versions in by_session.items():
        need(len({v[2] for v in versions}) == 1, "conflicting receipt families for " + sid)
        need(len({v[0] for v in versions}) == len(versions), "conflicting revisions for " + sid)
        _, latest, _ = max(versions)
        if latest not in revoked:
            current[sid] = latest
        # A revoked latest head never falls back to an older accepted receipt.
    return current


def require_current(session_pins):
    current = heads()
    for sid, pin in session_pins.items():
        need(sid in current and current[sid] == pin, f"superseded or non-current receipt for {sid}")
