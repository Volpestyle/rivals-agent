"""Train-only web-cluster request fit from an admitted cohort manifest (2026-09-23). No source media or live controller IO.

    uv run --offline --locked --group execution python -B data/diagnostics/<RUN>/fit_cohort_20260923.py \
        --manifest <cohort-manifest.json> --manifest-sha256 <sha256> --out data/diagnostics/<RUN>/run-1 [--dry-run <session>]
    uv run --offline --no-project python -B data/diagnostics/<RUN>/fit_cohort_20260923.py --manifest ... \
        --manifest-sha256 ... --check [--dry-run <session>] [--transfer-manifest <path>]   # stops before the fit; no torch

Every gate is an explicit raise, and the driver refuses to run under -O or PYTHONOPTIMIZE.

Stage 1 uses the standard library only and runs before any repo code is imported:
  1. The manifest's bytes must equal --manifest-sha256. Every file a selected member names, every pin and every
     {path, sha256} reference in each member's examples packet is then hash-checked before it is read.
  2. Admission is read from the frozen artifacts themselves, not only from the manifest (see admission()).
  3. Every repo module the policy import runs (CLOSURE) must equal the pinned code snapshot's git blob, as source bytes.
Stage 2 imports the policy code with bytecode caches bypassed and re-checks every repo module it loaded. It builds rows
with the accepted constructor recipe, runs the real validate()/cohort(), and requires the manifest's identity and counts
and each member's frozen evidence digest. The fit is the 2026-09-22 request fit, unchanged. Without --dry-run the
manifest and every member must be admitted; --dry-run <session> reads only that one accepted member.
The operator sequence is "Next fit" in docs/evidence/fit-readiness-20260923/README.md.
"""
import sys

if sys.flags.optimize:
    raise SystemExit("refused: run without -O or PYTHONOPTIMIZE")

import argparse
from collections import defaultdict
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
DRIVER = Path(__file__).resolve()
MANIFEST_FORMAT = "rivals-request-cohort-manifest-v1"
REQUEST = ("rivals-range-skill-requests-v1", "web_cluster_request", "web-cluster-request-v1", "masked-state-grid-causal-v1")
CLOSURE = ("agent/__init__.py", "agent/state.py", "agent/human_demos.py", "policy/__init__.py",
           "policy/execution.py", "policy/range_policy.py", "policy/range_skill_policy.py")
CODE = ("policy/range_skill_policy.py", "policy/range_policy.py", "agent/state.py")  # recorded as on 2026-09-22
PERCEPTION = ("perception/hud.py", "perception/outline.py", "agent/loop.py")
SELECTOR = ("agent/brain.py", "agent/tracker.py")
SEALED = "053616"
NOT_ADMITTED = ("candidate", "pending", "reject")
PLACEHOLDER = "0" * 64
REVIEW_PROVENANCE = frozenset({"origin", "review_sha256"})
REMEASURED = frozenset({"source", "history", "anchor_target_track"})  # the only row fields a re-measurement may change
CONFIG = dict(epochs=100, batch_size=2, lr=.01, device="mps", seed=7)
HIDDEN = 8
P = State = Detection = None  # bound by import_policy() once stage 1 has passed


def gate(ok, message):
    if not ok:
        raise SystemExit(f"refused: {message}")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    full = (ROOT / path).resolve()
    gate(full.is_relative_to(ROOT), f"{path} is outside the checkout")
    return full.relative_to(ROOT).as_posix()


def git_blob(raw):
    raw = raw.replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def refs(value):
    """Every {path, sha256} reference in artifact metadata; example rows are not searched."""
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            yield value["path"], value["sha256"]
        for key, item in value.items():
            if key != "rows":
                yield from refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from refs(item)


def admitted_status(status):
    text = str(status or "").lower()
    return text.startswith(("accepted", "admitted")) and not any(word in text for word in NOT_ADMITTED)


class Inputs(dict):
    """Repo-relative path -> sha256 of every file checked; a file is read only after it is here."""

    def verify(self, name, expected):
        gate(isinstance(name, str) and isinstance(expected, str), f"malformed reference {name!r}")
        name = rel(name)
        gate((ROOT / name).is_file() and sha(ROOT / name) == expected, f"hash mismatch or missing: {name}")
        gate(self.setdefault(name, expected) == expected, f"conflicting pins: {name}")

    def json(self, name):
        gate(name in self, f"{name} would be read before its hash is checked")
        return json.loads((ROOT / name).read_text())


def by_grid(session, rows):
    table = {r.get("grid_index"): r for r in rows}
    gate(len(table) == len(rows), f"{session}: duplicate grid rows")
    return table


def lead_rows_bound(session, rows, candidate, coverage):
    """The packet is the lead-admitted artifact plus review provenance, row for row.

    Each admitted candidate row equals the packet row at its grid index on every request_example_fields value, on
    history, and on the label mapped through request_example_mapping. The packet row adds only history, review
    provenance and the candidate's source identity. Every other packet row is an unknown with empty history. The
    packet's grid, labels and unknown reasons are the admitted coverage.json's."""
    mapping, admitted, table = candidate.get("request_example_mapping") or {}, by_grid(session, candidate.get("rows") or []), by_grid(session, rows)
    grid = coverage.get("grid") or []
    gate([r.get("grid_index") for r in rows] == [g.get("grid_index") for g in grid], f"{session}: packet grid is not the admitted coverage grid")
    for n, a in admitted.items():
        p, fields = table.get(n), a.get("request_example_fields") or {}
        label = None if a.get("label") is None else mapping.get(a["label"], "unmapped")
        gate(p is not None and set(p) == set(fields) | {"history", "source"} | REVIEW_PROVENANCE
             and all(p[k] == v for k, v in fields.items() if k not in REVIEW_PROVENANCE)
             and p["history"] == a.get("history") and p["label"] == label and p["source"] == candidate.get("source_identity"),
             f"{session}: grid {n} differs from the lead-admitted row")
    for g in grid:
        p = table[g["grid_index"]]
        gate((p.get("label_known"), p.get("label")) == (g.get("label_known"), g.get("label")), f"{session}: grid {g['grid_index']} label differs from the admitted coverage")
        if g["grid_index"] not in admitted:
            gate(p.get("label_known") is False and p.get("label") is None and p.get("history") == [] and p.get("reason") == g.get("reason"),
                 f"{session}: grid {g['grid_index']} is not an unknown row of the admitted coverage")


def admission(member, packet, inputs):
    """Admission read from the frozen packet and its hash-pinned review receipt, never from the manifest alone.

    The packet's own status must begin "accepted"/"admitted" and name no candidate, pending or rejection. A packet that
    re-measures accepted labels ("remeasured_accepted...") carries admission from the artifact it re-measured, which
    must itself be accepted, be hash-pinned by the packet and keep the same receipt. The receipt must be real (not the
    placeholder), be the review hash of every row, and have every file it names hash-checked before its content is
    trusted. It must admit this packet, belong to this session and bind its labels, in one of two schemas:
      decision receipt (2026-09-22): `decision` begins accept/admit; its `frozen_candidate` is in `input_artifacts`;
        its `known_labels` equal the packet's.
      lead admission decision (2026-09-23): train-only for this session/group/split; its `admitted_artifact` is the
        packet's `source_artifact`; the packet equals that artifact and its coverage row for row (lead_rows_bound).
    Either way the bound candidate's rows are all this session's.
    """
    session = member["session"]
    gate((packet.get("format"), packet.get("head"), packet.get("semantic_revision"), packet.get("feature_revision")) == REQUEST,
         f"{session}: not a {REQUEST[0]} examples packet")
    status, chain, rows = str(packet.get("status", "")), None, packet.get("rows") or []
    gate(not any(word in status.lower() for word in NOT_ADMITTED), f"{session}: packet status {status!r}")
    if not admitted_status(status):
        original = (packet.get("remeasurement") or {}).get("of_artifact") or {}
        gate(status.lower().startswith("remeasured_accepted") and original.get("path") in inputs,
             f"{session}: packet status {status!r} is not an admission")
        remeasured = inputs.json(original["path"])
        gate(admitted_status(remeasured.get("status")), f"{session}: re-measured artifact status {remeasured.get('status')!r}")
        gate(remeasured.get("review_receipt") == packet.get("review_receipt"), f"{session}: re-measurement changed the review receipt")
        # Re-measurement changes features by design (history, source, anchor track), so labels and every other row
        # field are bound to the accepted artifact, row for row, and the features to the pinned re-measurement report:
        # its new_history for each re-measured row, the original's history for the rest, its identity for every
        # source. The anchor track has no counterpart in the report and is not a model feature.
        gate(set(packet["remeasurement"].get("changed_fields") or []) <= REMEASURED, f"{session}: re-measurement declares changes beyond features")
        theirs, mine = by_grid(session, remeasured.get("rows") or []), by_grid(session, rows)
        gate(mine.keys() == theirs.keys() and all({k: v for k, v in mine[n].items() if k not in REMEASURED} ==
                                                  {k: v for k, v in theirs[n].items() if k not in REMEASURED} for n in mine),
             f"{session}: re-measured rows differ from the accepted artifact beyond the re-measured features")
        pinned = packet["remeasurement"].get("report") or {}
        gate(pinned.get("path") in inputs and inputs[pinned["path"]] == pinned.get("sha256"), f"{session}: re-measurement report is not hash-pinned")
        report = inputs.json(pinned["path"])
        gate(report.get("commit") == packet["remeasurement"].get("commit"), f"{session}: re-measurement report is from another commit")
        remeasured_history = {r.get("grid_index"): r.get("new_history") for r in report.get("rows") or []}
        gate(len(remeasured_history) == len(report.get("rows") or []) and remeasured_history.keys() <= mine.keys(),
             f"{session}: re-measurement report rows are not this packet's")
        gate(all(mine[n].get("history") == remeasured_history.get(n, theirs[n].get("history")) for n in mine),
             f"{session}: re-measured histories differ from the pinned re-measurement report")
        gate(all(mine[n].get("source") == report.get("source_identity") for n in mine),
             f"{session}: re-measured source differs from the pinned re-measurement report's identity")
        chain = dict(path=original["path"], sha256=original["sha256"], status=remeasured["status"])
    ref = packet.get("review_receipt") or {}
    gate(ref.get("path") in inputs and inputs[ref["path"]] == ref.get("sha256"), f"{session}: review receipt is not hash-pinned")
    gate(ref["sha256"] != PLACEHOLDER, f"{session}: placeholder review hash")
    gate(rows and all((r.get("review_sha256"), r.get("origin"), r.get("session"), r.get("group"), r.get("split")) ==
                      (ref["sha256"], "reviewed_human", session, member["group"], member["split"]) for r in rows),
         f"{session}: rows do not carry this receipt, origin, session, group and split")
    receipt = inputs.json(ref["path"])
    for name, expected in refs(receipt):
        inputs.verify(name, expected)
    known = {r["grid_index"]: r["label"] for r in rows if r.get("label_known")}
    if "decision" in receipt:
        schema, bound = "decision_receipt", receipt.get("frozen_candidate") or {}
        gate(str(receipt["decision"]).lower().startswith(("accept", "admit")), f"{session}: receipt decision {receipt['decision']!r}")
        gate(bound in packet.get("input_artifacts", []), f"{session}: receipt's frozen_candidate is not among the packet's input_artifacts")
        gate(isinstance(receipt.get("known_labels"), dict) and {int(k): v for k, v in receipt["known_labels"].items()} == known,
             f"{session}: labels differ from the receipt's known_labels")
    else:
        schema, bound = "lead_admission_decision", receipt.get("admitted_artifact") or {}
        gate(receipt.get("kind") == "lead_admission_decision" and receipt.get("train_only") is True
             and (receipt.get("session"), receipt.get("group"), receipt.get("split")) == (session, member["group"], member["split"]),
             f"{session}: receipt is not a train-only admission of this session")
        source = packet.get("source_artifact") or {}
        gate((bound.get("path"), bound.get("sha256")) == (source.get("path"), source.get("sha256")),
             f"{session}: receipt's admitted_artifact is not the packet's source_artifact")
        coverage = bound.get("coverage") or {}
        gate(coverage.get("path") in inputs and inputs[coverage["path"]] == coverage.get("sha256"), f"{session}: admitted coverage is not hash-pinned")
    gate(bound.get("path") in inputs and inputs[bound["path"]] == bound.get("sha256"), f"{session}: receipt's bound artifact is not hash-pinned")
    candidate = inputs.json(bound["path"])
    gate({r.get("session") for r in candidate.get("rows") or [{}]} == {session}, f"{session}: receipt's bound artifact belongs to another session")
    if schema == "lead_admission_decision":
        lead_rows_bound(session, rows, candidate, inputs.json(coverage["path"]))
    if "counts" in receipt:
        counts = receipt["counts"]
        gate((counts.get("starts"), counts.get("controls"), counts.get("coordinates")) ==
             (sum(v == "start" for v in known.values()), sum(v == "no_new_start" for v in known.values()), len(rows)),
             f"{session}: counts differ from the receipt's")
    return dict(packet_status=status, remeasured_from=chain, receipt=dict(path=ref["path"], sha256=ref["sha256"], schema=schema),
                bound_artifact=dict(path=bound["path"], sha256=bound["sha256"]))


def preflight(manifest_path, manifest_sha256, dry_run=None):
    """Stage 1, standard library only. Returns what stage 2 needs; raises SystemExit on any refusal."""
    manifest_path = rel(manifest_path)
    gate((ROOT / manifest_path).is_file() and sha(ROOT / manifest_path) == manifest_sha256, "cohort manifest differs from --manifest-sha256")
    inputs = Inputs({manifest_path: manifest_sha256})
    manifest = inputs.json(manifest_path)
    gate((manifest.get("format"), manifest.get("head"), manifest.get("semantic_revision"), manifest.get("feature_revision")) ==
         (MANIFEST_FORMAT, *REQUEST[1:]), "not a request cohort manifest")
    members = list(enumerate(manifest.get("members") or []))
    if dry_run is None:
        gate(admitted_status(manifest.get("status")), f"manifest status {manifest.get('status')!r}: not admitted")
        selected = members
    else:
        selected = [(i, m) for i, m in members if m.get("session") == dry_run]
        gate(len(selected) == 1, f"--dry-run must name exactly one member session: {dry_run}")
    gate(bool(selected), "no members")
    for _, m in selected:
        gate(admitted_status(m.get("status")) and "examples" in m and "candidate_rows" not in m,
             f"member {m.get('session')} is not admitted: {m.get('status')!r}")
        gate(m.get("split") == "train" and SEALED not in str(m.get("session")), f"member {m.get('session')}: not a train session")
        for name, expected in refs(m):
            inputs.verify(name, expected)
    for name, expected in (manifest.get("pins") or {}).items():
        inputs.verify(name, expected)

    snapshots = [name for name in manifest.get("pins") or {} if "/code-snapshot/manifest-" in name]
    gate(len(snapshots) == 1, "exactly one pinned code-snapshot manifest required")
    snapshot = inputs.json(snapshots[0])
    gate(snapshot.get("commit") == manifest.get("perception_commit"), "code snapshot is not the perception commit")
    blobs = {f["path"]: f["git_blob"] for f in snapshot.get("files", [])}
    for name in CLOSURE:
        gate(name in blobs and git_blob((ROOT / name).read_bytes()) == blobs[name], f"{name} differs from the cohort's code snapshot")

    chosen = []
    for i, m in selected:
        path = rel(m["examples"]["path"])
        hashes = inputs.json(rel(m["artifact_hashes"]["path"]))
        gate(isinstance(hashes.get("files"), dict) and hashes["files"].get(path) == m["examples"]["sha256"],
             f"{m['artifact_hashes']['path']} does not pin {path}")
        packet = inputs.json(path)
        for name, expected in refs(packet):
            inputs.verify(name, expected)
        gate(packet.get("policy_schema_sha256") in (next((f["sha256"] for f in snapshot["files"] if f["path"] == "policy/range_skill_policy.py"), None),
                                                    sha(ROOT / "policy/range_skill_policy.py")), f"{path}: policy schema is not the snapshot's")
        chosen.append(dict(index=i, member=m, path=path, packet=packet, hashes=hashes, admission=admission(m, packet, inputs)))
    return dict(manifest=manifest, members=chosen, inputs=inputs, blobs=blobs, dry_run=dry_run,
                skipped=[m.get("session") for i, m in members if i not in {c["index"] for c in chosen}])


def check_loaded(blobs):
    """Every module loaded from the checkout must be in the verified closure and still equal its snapshot blob.

    Only a module whose __file__ is an absolute path to a real file was loaded from disk; torch.ops, for one, is a
    synthetic module whose __file__ is the bare string "_ops.py". The running script is skipped by identity, since
    multiprocessing also registers it as __mp_main__."""
    outside = [Path(p).resolve() for p in {sys.prefix, sys.base_prefix, sys.exec_prefix}]
    main = sys.modules.get("__main__")
    for name, module in list(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if module is main or not isinstance(path, str) or not Path(path).is_absolute() or not Path(path).is_file():
            continue
        path = Path(path).resolve()
        if path == DRIVER or not path.is_relative_to(ROOT) or any(path.is_relative_to(o) for o in outside):
            continue
        name = path.relative_to(ROOT).as_posix()
        gate(name in CLOSURE and git_blob(path.read_bytes()) == blobs[name], f"loaded module {name} is outside the verified code closure")


def import_policy(blobs):
    global P, State, Detection
    sys.dont_write_bytecode = True
    sys.pycache_prefix = tempfile.mkdtemp(prefix="fit-cohort-pycache-")  # compile the verified source; never a cached .pyc
    sys.path.insert(0, str(ROOT))
    from agent.state import State, Detection
    from policy import range_skill_policy as P
    check_loaded(blobs)
    gate((P.REQUEST_FORMAT, P.REQUEST_HEAD, P.REQUEST_SEMANTIC_REVISION, P.FEATURE_REVISION) == REQUEST,
         "policy request constants differ from the driver's")


def example(row):
    history = tuple(P.Snapshot(State.from_dict(s["state"]),
        Detection(**{**s["target"], "bbox": tuple(s["target"]["bbox"])}) if s["target"] else None,
        s["available_t"]) for s in row["history"])
    return P.RequestExample(**{**row, "source": P.SourceIdentity(**row["source"]), "history": history})


def build(bundle):
    """Stage 2: import the verified policy code, build the rows and require the manifest's frozen records."""
    import_policy(bundle["blobs"])
    check = bundle["manifest"]["check"]
    for c in bundle["members"]:
        examples = [example(row) for row in c["packet"]["rows"]]
        digest = P.evidence_digest(examples)
        records = [c["packet"].get("evidence_digest"), c["hashes"].get("evidence_digest")]
        if "evidence_digest" in check["per_member"][c["index"]]:
            records.append(check["per_member"][c["index"]]["evidence_digest"])
        gate(all(r == digest for r in records), f"{c['member']['session']}: evidence digest {digest} differs from its frozen records")
        known = [e for e in examples if e.label_known]
        c["counts"] = dict(rows=len(examples), known=len(known), bin_support=[sum(e.label == o for e in known) for o in P.OUTCOMES])
        gate(c["counts"] == {k: check["per_member"][c["index"]][k] for k in ("rows", "known", "bin_support")},
             f"{c['member']['session']}: counts {c['counts']} differ from the manifest's")
        c["examples"], c["evidence_digest"] = examples, digest
    examples = [e for c in bundle["members"] for e in c["examples"]]
    source, origin = P.cohort(examples)
    gate(asdict(source) == check["source_identity"], "cohort identity differs from the manifest's")
    gate(origin == check.get("origin", "reviewed_human") == "reviewed_human" and all(e.split == "train" for e in examples)
         and not any(SEALED in e.session for e in examples), "cohort is not reviewed-human train rows")
    coverage = P.coverage_report(examples)
    if bundle["dry_run"] is None:
        joint = dict(rows=len(examples), bin_support=coverage["bin_support"], unique_events=coverage["unique_events"])
        gate(joint == check["joint"], f"joint {joint} differs from the manifest's")
        if "joint_evidence_digest" in check:
            gate(check["joint_evidence_digest"] == P.evidence_digest(examples), "joint evidence digest differs from the manifest's")
    return examples, source


def predictions(model, examples):
    probs = [model.probabilities(e.history, e.anchor_t) if e.label_known else None for e in examples]
    names = [P.OUTCOMES[max(range(len(p)), key=p.__getitem__)] if p else None for p in probs]
    return probs, names


def identity_code_check(source):
    """Perception/selector digests of this commit's files in both byte forms; the runtime must use the matching one."""
    def form(names, crlf):
        blobs = {n: subprocess.check_output(["git", "show", f"HEAD:{n}"], cwd=ROOT).replace(b"\r\n", b"\n") for n in names}
        return P.digest({n: hashlib.sha256(b.replace(b"\n", b"\r\n") if crlf else b).hexdigest() for n, b in blobs.items()})
    out = {name: dict(perception_sha256=form(PERCEPTION, name == "crlf"), selector_sha256=form(SELECTOR, name == "crlf"))
           for name in ("lf", "crlf")}
    want = dict(perception_sha256=source.perception_sha256, selector_sha256=source.selector_sha256)
    out["source_identity_matches"] = [name for name in ("lf", "crlf") if out[name] == want]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--manifest-sha256", required=True)
    ap.add_argument("--out", help="new run directory, created exclusively (fit only)")
    ap.add_argument("--dry-run", metavar="SESSION", help="read and fit only this accepted member")
    ap.add_argument("--check", action="store_true", help="verify and build the cohort, then stop; imports no torch")
    ap.add_argument("--transfer-manifest", help="with --check: write every verified input and this driver as {path: sha256}, exclusively")
    args = ap.parse_args()
    bundle = preflight(args.manifest, args.manifest_sha256, args.dry_run)
    examples, source = build(bundle)
    members = [dict(session=c["member"]["session"], group=c["member"]["group"], status=c["member"]["status"],
                    examples=c["member"]["examples"], evidence_digest=c["evidence_digest"], admission=c["admission"], **c["counts"])
               for c in bundle["members"]]
    if args.check:
        gate(args.out is None, "--check does not fit")
        if args.transfer_manifest:  # this driver travels with its inputs, at the path it ran from
            with open(args.transfer_manifest, "x") as f:
                json.dump({**bundle["inputs"], rel(DRIVER): sha(DRIVER)}, f, indent=1)
                f.write("\n")
        print(json.dumps(dict(manifest=rel(args.manifest), status=bundle["manifest"]["status"], dry_run_member=args.dry_run,
                              members=members, skipped_members=bundle["skipped"], coverage=P.coverage_report(examples),
                              source_identity=asdict(source), evidence_digest=P.evidence_digest(examples),
                              verified_inputs=len(bundle["inputs"])), indent=2))
        return
    gate(bool(args.out) and not args.transfer_manifest, "--out is required to fit")
    gate("agent.controller" not in sys.modules and "agent.loop" not in sys.modules, "live IO modules imported")

    torch = P.torch_module()
    gate(torch.backends.mps.is_available(), "MPS required; no silent CPU fallback")
    torch.set_num_threads(4)
    spec = P.Spec(hidden=HIDDEN)
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=False)
    t0 = time.perf_counter()
    policy = P.train(examples, spec=spec, **CONFIG)
    torch.mps.synchronize()
    seconds = time.perf_counter() - t0
    gate(str(next(policy.model.parameters()).device).startswith("mps"), "model is not on MPS")

    probs, names = predictions(policy, examples)
    code = {name: sha(ROOT / name) for name in CODE}
    driver = dict(path=rel(DRIVER), sha256=sha(DRIVER))
    checkpoint = out / "model.pt"
    checkpoint_sha = P.save_checkpoint(checkpoint, policy, examples, code_sha256=code["policy/range_skill_policy.py"],
        training_config={**CONFIG, "spec": asdict(spec), "train_only": True, "cohort_manifest_sha256": args.manifest_sha256,
                         "driver_sha256": driver["sha256"], "dry_run_member": args.dry_run})
    loaded = P.load_checkpoint(checkpoint, expected_sha256=checkpoint_sha, expected_identity=source, device="cpu", offline=True)
    cpu_probs, cpu_names = predictions(loaded, examples)
    delta = max(abs(a - b) for p, q in zip(probs, cpu_probs) if p for a, b in zip(p, q))
    gate(names == cpu_names and delta < 1e-5, f"CPU reload differs from MPS (max delta {delta})")
    check_loaded(bundle["blobs"])

    ammo = [None if not e.history or e.history[-1].state.webs is None else
            ("start" if e.history[-1].state.webs > 0 else "no_new_start") for e in examples]
    never = ["no_new_start"] * len(examples)
    confident = [n if p and max(p) >= spec.confidence else None for n, p in zip(names, probs)]

    def metrics(values, session=None):
        pairs = [(e, v) for e, v in zip(examples, values) if session in (None, e.session)]
        return P.event_metrics([e for e, _ in pairs], [v for _, v in pairs], spec, semantic_revision=source.semantic_revision)

    known_rows = [dict(session=e.session, grid_index=e.grid_index, label=e.label, request_id=e.request_id,
                       ammo=e.history[-1].state.webs, probabilities=p, cpu_probabilities=q, prediction=n, reproduced=n == e.label)
                  for e, p, q, n in zip(examples, probs, cpu_probs, names) if e.label_known]
    contrast = defaultdict(lambda: {o: [] for o in P.OUTCOMES})
    for e in examples:
        if e.label_known:
            contrast[tuple(s.state.webs for s in e.history)][e.label].append([e.session, e.grid_index])
    limits = [line for c in bundle["members"] for line in c["packet"].get("limitations", [])] + [
        "Train-only reproduction of admitted labels; this is not validation or generalization.",
        "Window-reset tracking is not proven equivalent to continuous live selection.",
        "No native media opened by this training job."]
    if args.dry_run:
        limits.insert(0, f"Dry run on the accepted member {args.dry_run} only; not a new candidate or admission.")
    report = {
        "scope": ("dry_run_accepted_member_train_only_numerical_fit_reload_not_a_candidate" if args.dry_run
                  else "admitted_human_received_request_train_only_numerical_fit_reload"),
        "not_generalization_or_live_clearance": True, "dry_run_member": args.dry_run,
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "torch": torch.__version__, "training_device": str(next(policy.model.parameters()).device),
        "fit_seconds": seconds, "config": CONFIG, "spec": asdict(spec), "code_sha256": code,
        "code_closure_git_blobs": {name: bundle["blobs"][name] for name in CLOSURE}, "driver": driver,
        "cohort_manifest": dict(path=rel(args.manifest), sha256=args.manifest_sha256, status=bundle["manifest"]["status"]),
        "members": members, "skipped_members": bundle["skipped"], "input_artifacts": dict(bundle["inputs"]),
        "source_identity": asdict(source), "identity_code_check": identity_code_check(source),
        "evidence_digest": policy.data_sha256, "checkpoint_sha256": checkpoint_sha, "coverage": P.coverage_report(examples),
        "label_reproduction": dict(known=len(known_rows), reproduced=sum(r["reproduced"] for r in known_rows)),
        "model_train_metrics": metrics(names), "cpu_reload_train_metrics": metrics(cpu_names),
        "cpu_reload_max_probability_delta": delta,
        "confidence_filtered_train_metrics": dict(threshold=spec.confidence, **metrics(confident)),
        "ammo_baseline_train_metrics": metrics(ammo), "never_start_train_metrics": metrics(never),
        "per_session_train_metrics": {s: dict(model=metrics(names, s), ammo_baseline=metrics(ammo, s),
                                              never_start=metrics(never, s))
                                      for s in sorted({e.session for e in examples})},
        "known_rows": known_rows,
        "same_ammo_contrast_groups": [dict(ammo_history=list(k), **v) for k, v in contrast.items() if all(v.values())],
        "validation": None, "deployment_binding": None, "live_io_imported": False, "limits": limits,
    }
    (out / "mac-report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"checkpoint_sha256": checkpoint_sha, "device": report["training_device"], "fit_seconds": seconds,
                      "coverage": report["coverage"], "label_reproduction": report["label_reproduction"],
                      "model_train_metrics": report["model_train_metrics"],
                      "cpu_reload_max_probability_delta": delta}, indent=2))


if __name__ == "__main__":
    main()
