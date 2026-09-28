"""Summarize frozen exploratory annotations and validate the exact frame receipts."""
from collections import Counter
from decimal import Decimal, ROUND_CEILING
import json
from pathlib import Path
import runpy
import time
import zipfile

HERE = Path(__file__).resolve().parent
audit = runpy.run_path(str(HERE / "audit.py"))
sha, save = audit["digest"], audit["save"]
peak = audit["PRIOR"]["limits"]()
selection = json.loads((HERE / "selection.json").read_text())
causal = json.loads((HERE / "causal-annotations.json").read_text())
oracle = json.loads((HERE / "oracle-annotations.json").read_text())
freeze = json.loads((HERE / "causal-freeze.json").read_text())
assert sha(HERE / "causal-annotations.json") == freeze["sha256"]
assert not freeze["future_panels_exist"]
events = {e["id"]: (s, e) for s in selection["sessions"] for e in s["events"]}
c = {e["id"]: e for e in causal["events"]}
o = {e["id"]: e for e in oracle["events"]}
assert set(events) == set(c) == set(o) and len(events) == 12
receipts = {}
for phase in ("causal", "oracle"):
    rec = json.loads((HERE / phase / "receipt.json").read_text())
    assert rec["selection_sha256"] == sha(HERE / "selection.json")
    assert len(rec["frames"]) == 36
    for f in rec["frames"]:
        assert f["pts"] == f["decoded_pts"] and f["composition_ns"] <= f["anchor_ns"]
        assert (f["offset_s"] <= 0) == (phase == "causal")
        assert sha(HERE / f["path"]) == f["sha256"]
    receipts[phase] = rec
    peak()
archive = audit["ROOT"] / "data/research/intent-target-audit-20260928-native.zip"
archive.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_STORED) as z:
    for phase, rec in receipts.items():
        for f in rec["frames"]:
            z.write(HERE / f["path"], f["path"])
        z.write(HERE / phase / "receipt.json", phase + "/receipt.json")
save(HERE / "native-archive.json", {"path": str(archive), "bytes": archive.stat().st_size,
    "sha256": sha(archive), "note": "72 native JPEGs retained locally; 24 contact sheets committed. Original native JPEGs also remain at receipt paths."})
counts = Counter(label for e in o.values() for label in e["classes"])
resolved = [k for k in events if o[k]["bot_focus_resolved"]]
unique = [k for k in events if c[k]["unique_plausible_target"]]
summary = {"tag": "EXPLORATORY_DIAGNOSTIC_NOT_HUMAN_GROUND_TRUTH", "n": len(events),
    "causal_plausible_single_focus": unique, "oracle_apparent_bot_focus": resolved,
    "newly_resolved_in_hindsight": sorted(set(resolved)-set(unique)),
    "causal_hypothesis_but_future_exit": sorted(set(unique)-set(resolved)),
    "overlapping_intent_counts": dict(counts), "cloud_usd": 0,
    "frame_count": 72, "decode_seconds": sum(r["seconds"] for r in receipts.values()),
    "peak_decoder_working_set_bytes": max(r["peak_working_set_bytes"] for r in receipts.values()),
    "source_sha256": {p: sha(HERE / p) for p in ("plan.md", "selection.json", "audit.py", "test_audit.py",
        "causal-annotations.json", "causal-freeze.json", "oracle-annotations.json",
        "causal/receipt.json", "oracle/receipt.json", "native-archive.json")}, "reported_unix": time.time()}
save(HERE / "summary.json", summary)
table = ["| Event | Session / row | Turn in next 0.5 s | Causal single-focus hypothesis | Oracle context | Apparent bot focus |",
         "|---|---|---:|---|---|---|"]
for k, (session, event) in events.items():
    table.append(f"| [{k} causal]({k and 'causal'}/{k}-contact.jpg) / [oracle](oracle/{k}-contact.jpg) | "
        f"{session['session'][:15]} / {event['center']} | {event['yaw_next_half_s']:+.2f} deg | "
        f"{'Yes' if c[k]['unique_plausible_target'] else 'Unresolved'} | {', '.join(o[k]['classes'])} | "
        f"{o[k]['target'] or 'Unresolved / no definite bot destination'} |")
body = '''# What is James turning toward? — bounded EXPLORATORY audit

In this 12-event sample, **six turns have an apparent bot focus in hindsight**;
the other six show traversal or leave the next target unresolved. The causal
pass identified a single plausible bot focus in four events. Hindsight resolved
three additional events (E01/E03/E11), while E12 went the other way: its clearly
visible current target was defeated and James turned out of the doorway.
These are assistant-authored interpretations of sparse frames, **not James's
intent labels, human-adjudicated truth, a learned planner score or a yaw result**.

The practical distinction is between continuing an engagement, acquiring the
next target and traversing/repositioning. A visible nearby bot is not always the
destination of the next turn. E09 contains engagement, a KO and departure in the
same two-second interval. E07 looks back toward the ongoing opponent after
passing beside it. E06/E10 primarily navigate a pillar/cover panel. E08 faces the
prominent bot briefly, then leaves; looking toward it does not prove an attack.
No event establishes deliberate defensive disengagement, so that class is not
forced onto post-KO traversal.

## Frozen selection and separate evidence passes

Plan committed in `42fce44`; selector/tests/metadata selection in `f17edb2`.
Causal annotations were committed in `44aa5d4` before future panels were decoded.
Only three explicitly admitted TRAIN sources were opened, with existing split,
admission and current sealed-denylist checks. No frozen-dev/sealed pixels, model
inference, fit, cloud app, desktop input or new data admission occurred.

There are two left and two right event windows per session, selected first/last
in each direction with >=10s separation. A qualifying 0.5s future window has
>=10deg net requested yaw, >=80% directional consistency and <=2deg absolute
yaw in the preceding 0.5s. The anchor is the start of a qualifying window;
it can precede the first nonzero yaw packet by up to 0.5s. It is not an exact
motor-onset timestamp. Candidates overlap before selection. The 30Hz step
period is read from each header, not assumed from the encoder's sampling rate.

We inspected causal t=-1,-0.5,0 first, then oracle t=+0.5,+1,+2. Source identities,
row indices, PTS, dimensions and timebase were pinned/checked; all 72 decoded
frames match exact PTS and composition<=their own row anchor. Future frames and
human yaw labels are oracle/selection evidence only. Causal contact sheets
contain no future controls. The annotator knew the balanced turn-selection
design, so this is not a formal blinded human experiment.

'''
body += "\n".join(table) + "\n\n"
body += f"Overlapping context labels: {dict(counts)}. Counts need not sum to 12. "
body += '''Five of the six apparent bot focuses can be linked to a causal visible
candidate; E03 linkage is only possible, not proven. Only three of the four
causal single-focus hypotheses remain an apparent future bot focus. These
descriptive fractions are not accuracy estimates: there was no forced predictor,
independent adjudicator or representative sample.

## What this supports, and what it does not

The audit gives examples of mixed contexts and target ambiguity worth preserving
in diagnostics. It **does not prove** that intent conditioning explains the
model's yaw error: no checkpoint predictions were read here, and no oracle-versus-
causal controlled experiment ran. Sparse frames can miss brief switches or
attacks. First/last balanced sampling over-represents session edges; still-then-
turn selection excludes sustained turning and makes no population claim.
Three sessions in the practice range do not cover live self-fed behavior.

If target/intent conditioning is later tested, keep an explicit unknown/no-target
state and distinguish goal selection from target bearing. A causal input may use
past/current visible candidates, occlusion and visible engagement phase; it
cannot use the eventual attacked bot, future image, KO outcome or James's next
command. Even past visible attack animation would become the model's own action
feedback live. These observations must not be admitted as training targets
without the appropriate independent data review and label validation.

The currently requested next paid sizing remains one 4x4 regularization test
against the completed control, not a new intent-conditioned architecture. The
overfitting curves independently motivate that test; this audit does not license
more grids or encoders.

## Validation and cost

Five synthetic selection tests passed (direction, exact offsets, gaps/unknown or
unaccepted rows, quiet/mixed-sign controls and separation/shortfalls). All 72
native image hashes and exact-PTS receipts revalidated. Decode was CPU-only,
BelowNormal, two threads, streamed; no paid compute. Native JPEGs are retained in
the local archive identified by `native-archive.json`; contact sheets, receipts,
annotations and selection metadata are in this evidence packet.
'''
body += f"\nDecode wall time: {summary['decode_seconds']:.3f}s across two passes; peak decoder working set "
body += f"{summary['peak_decoder_working_set_bytes']/1024**2:.2f} MiB; cloud cost $0.\n"
(HERE / "report.md").open("x", encoding="utf-8", newline="\n").write(body)
rate = Decimal("0.0007178888888888888888888888889")
hold = (rate * 2220 + Decimal("0.05")).quantize(Decimal("0.000001"), rounding=ROUND_CEILING)
print(json.dumps({"summary": summary, "proposed_fit_hold": str(hold), "three_fit_holds": str(hold*3)}, indent=2))
