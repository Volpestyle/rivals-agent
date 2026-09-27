"""Parity test for the pad->M&K HUD transform (`hudmap.pad_to_mk`), on paired stills: pad-HUD frames from the pilot
archives (data/l1/galacta-pilot-*, live dxcam captures) against James's M&K frames (decoded from his recordings).

Pre-registered checks (thresholds fixed here before the first run; the lane doc records them):
    P1 slot identity   `perception.hud.slot_mapping` (the repo's icon templates) over the transformed pad frames, read
                       in the M&K layout, names the same ability at every position as over James's M&K frames, and
                       all three ability positions are identified in both
    P2 reader parity   for webs, and for each ability's ready flag, charges and cooldown: the pad reader on the
                       original frame against the M&K reader on the transformed frame (the ability looked up at its
                       M&K position). Per quantity with at least MIN_KNOWN pad-known reads: agreement >= AGREE of
                       pad-known reads, and contradictions (both known, different) <= CONTRADICT of pad-known reads
    P3 webs position   the transformed web digit's right edge lies within James's measured range +- EDGE_TOL px for
                       >= AGREE of the frames where it is found
Reported, not gated: the same readers on the untransformed pad frames in the M&K layout (the gap the transform closes).

Parity fails if any of P1-P3 fails; the pre-registered consequence is that the live arm drops the HUD stream
(a `hud=False` arm), not that thresholds move. Needs the perception group (cv2, numpy).

Run 1 (2026-09-23, `hud-parity-1.json`) FAILED P2 and stays failed on record. The lead withdrew a post-hoc amendment
(round-3 review) and pre-registered P2' instead, before any new data, exactly as the review worded it (`--rule p2prime`):
    P2' ready flags   scored only on frames where the M&K reader's occlusion guard is NOT firing at that slot of the
                      transformed frame; every other quantity as in P2
    P2' agreement     >= AGREE with >= MIN_KNOWN pad-known frames per quantity, and ZERO contradictions on every
                      quantity (gated or not)
    power check       the untransformed baseline, scored the same way, must FAIL P2'
    coverage floor    >= COVERAGE frames each (pad reads of the originals) with webs <= 2, a spent swing charge, a
                      spent combo charge, and a running cooldown on each of the three ability slots
    fresh data        no source that run 1 used (by sha256) and never 053616: new pad stills from placement or pilot
                      runs, M&K frames from campaign takes
P2' passing does not by itself make the HUD arm the candidate: it must also beat the no-HUD arm on validation by
+0.05 self-fed macro press-F1 (`policy.range_bc.train.choose_candidate`).
"""
import argparse
import glob
import hashlib
import json
from pathlib import Path
import statistics
import sys

AGREE = .95
CONTRADICT = .01
MIN_KNOWN = 20
EDGE_TOL = 2.
COVERAGE = 20
RULES = ("p2", "p2prime")
# The ability at each hud.py position key, per layout (measured; hudmap.MEASURED).
PAD_AT = {"swing": "swing", "get_over_here": "get_over_here", "uppercut": "uppercut"}
MK_AT = {"swing": "swing", "get_over_here": "uppercut", "uppercut": "get_over_here"}


def _hud():
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from perception import hud
    return hud


def digit_right(frame, layout):
    """Absolute x (px, frame scale) of the web count's right edge, or None."""
    hud = _hud()
    w = frame.shape[1]
    for mask in hud._masks(frame, layout.webs, hud.WEBS_FLOOR, contrasts=(55,)):
        for g in hud._groups(hud._glyphs(mask)):
            last = g[-1][0]
            r = last[0] + last[2]
            if layout.webs_right[0] <= r <= layout.webs_right[1] and hud._number(g) is not None:
                return layout.webs[0] * w + r * w / 2560
        break
    return None


def _reads(frame, layout, at):
    """{quantity: value} with abilities keyed by ability name via the layout's position map."""
    hud = _hud()
    r = hud.read(frame, layout)
    by_ability = {ability: pos for pos, ability in at.items()}
    out = {"webs": r.webs, "hp": r.hp, "ult_ready": r.ult_ready}
    for ability, pos in by_ability.items():
        ready, charges = r.abilities.get(pos, (None, None))
        out[f"{ability}.ready"], out[f"{ability}.charges"] = ready, charges
        out[f"{ability}.cooldown"] = r.cooldowns.get(pos)
    return out


def _agreement(pairs):
    known = [(a, b) for a, b in pairs if a is not None]
    equal = sum(a == b for a, b in known)
    contradict = sum(b is not None and a != b for a, b in known)
    return {"pad_known": len(known), "equal": equal, "contradict": contradict, "lost": sum(b is None for _, b in known),
            "agreement": equal / len(known) if known else None,
            "contradiction_rate": contradict / len(known) if known else None}


def _guarded(frame, pos):
    hud = _hud()
    return hud._slot_occluded(frame, hud.MK.slot_cx[pos], hud.MK.slot_spill)


def _p2prime_pairs(live, others, at_other):
    """Pairs (pad read, other read) per quantity, with ready flags dropped where the M&K guard fires on `other`."""
    hud = _hud()
    rows = {}
    for f, o in zip(live, others):
        a, b = _reads(f, hud.PAD, PAD_AT), _reads(o, hud.MK, at_other)
        for k in a:
            if k.endswith(".ready"):
                pos = {ability: p for p, ability in at_other.items()}[k.split(".")[0]]
                if _guarded(o, pos):
                    continue
            rows.setdefault(k, []).append((a[k], b[k]))
    return rows


def _p2prime_verdict(rows):
    q = {k: _agreement(v) for k, v in rows.items()}
    gated = {k: v for k, v in q.items() if v["pad_known"] >= MIN_KNOWN}
    ok = (bool(gated) and all(v["agreement"] >= AGREE for v in gated.values())
          and all(v["contradict"] == 0 for v in q.values()))
    return {"quantities": q, "gated": sorted(gated), "pass": ok}


def coverage(live):
    """Pad-read resource states of the originals: the P2' coverage floor."""
    hud = _hud()
    n = {"webs<=2": 0, "swing_spent": 0, "combo_spent": 0, "swing_cooldown": 0, "get_over_here_cooldown": 0,
         "uppercut_cooldown": 0}
    for f in live:
        r = _reads(f, hud.PAD, PAD_AT)
        n["webs<=2"] += r["webs"] is not None and r["webs"] <= 2
        n["swing_spent"] += r["swing.charges"] is not None and r["swing.charges"] < 3
        n["combo_spent"] += r["uppercut.charges"] is not None and r["uppercut.charges"] < 2
        for a in ("swing", "get_over_here", "uppercut"):
            n[f"{a}_cooldown"] += (r[f"{a}.cooldown"] or 0) > 0
    return {"counts": n, "floor": COVERAGE, "pass": all(v >= COVERAGE for v in n.values())}


def parity_prime(pad_frames, mk_frames):
    """P2' (pre-registered after run 1, before any new data). Returns the full verdict."""
    hud = _hud()
    from .hudmap import pad_to_mk
    live = [f for f in pad_frames if hud.read_hp(f)[0] is not None]
    transformed = [pad_to_mk(f) for f in live]
    base = parity(pad_frames, mk_frames)          # P1 and P3 as before
    p2 = _p2prime_verdict(_p2prime_pairs(live, transformed, MK_AT))
    power = _p2prime_verdict(_p2prime_pairs(live, live, MK_AT))      # untransformed, scored the same way
    cov = coverage(live)
    return {"rule": "p2prime", "thresholds": {"AGREE": AGREE, "MIN_KNOWN": MIN_KNOWN, "COVERAGE": COVERAGE,
                                              "EDGE_TOL": EDGE_TOL, "contradictions": 0},
            "pad_frames": len(pad_frames), "pad_with_hp": len(live), "mk_frames": len(mk_frames),
            "P1": base["P1"], "P3": base["P3"], "P2prime": p2, "power": {**power, "must_fail": True,
                                                                        "ok": not power["pass"]},
            "coverage": cov,
            "pass": base["P1"]["pass"] and base["P3"]["pass"] and p2["pass"] and not power["pass"] and cov["pass"]}


def parity(pad_frames, mk_frames):
    hud = _hud()
    from .hudmap import pad_to_mk
    live = [f for f in pad_frames if hud.read_hp(f)[0] is not None]
    transformed = [pad_to_mk(f) for f in live]
    mk_live = [f for f in mk_frames if hud.read_hp(f)[0] is not None]
    # P1
    t_map = hud.slot_mapping(transformed, hud.MK)
    mk_map = hud.slot_mapping(mk_live, hud.MK)
    positions = ("swing", "get_over_here", "uppercut")
    p1 = {"transformed": t_map, "mk": mk_map,
          "pass": all(p in t_map and p in mk_map and t_map[p] == mk_map[p] for p in positions)}
    # P2 (and the untransformed baseline)
    rows, base = {}, {}
    for f, t in zip(live, transformed):
        a, b, c = _reads(f, hud.PAD, PAD_AT), _reads(t, hud.MK, MK_AT), _reads(f, hud.MK, MK_AT)
        for k in a:
            rows.setdefault(k, []).append((a[k], b[k]))
            base.setdefault(k, []).append((a[k], c[k]))
    p2q = {k: _agreement(v) for k, v in rows.items()}
    gated = {k: v for k, v in p2q.items() if v["pad_known"] >= MIN_KNOWN}
    p2 = {"quantities": p2q, "gated": sorted(gated),
          "pass": bool(gated) and all(v["agreement"] >= AGREE and v["contradiction_rate"] <= CONTRADICT
                                      for v in gated.values()),
          "untransformed_baseline": {k: _agreement(v) for k, v in base.items()}}
    # P3
    mk_edges = [e for e in (digit_right(f, hud.MK) for f in mk_live) if e is not None]
    t_edges = [e for e in (digit_right(t, hud.MK) for t in transformed) if e is not None]
    lo, hi = (min(mk_edges) - EDGE_TOL, max(mk_edges) + EDGE_TOL) if mk_edges else (None, None)
    inside = sum(lo <= e <= hi for e in t_edges) if mk_edges else 0
    p3 = {"mk_range": [lo, hi], "mk_found": len(mk_edges), "transformed_found": len(t_edges),
          "transformed_median": statistics.median(t_edges) if t_edges else None,
          "inside": inside, "pass": bool(t_edges) and bool(mk_edges) and inside >= AGREE * len(t_edges)}
    return {"rule": "p2", "thresholds": {"AGREE": AGREE, "CONTRADICT": CONTRADICT, "MIN_KNOWN": MIN_KNOWN,
                                         "EDGE_TOL": EDGE_TOL},
            "pad_frames": len(pad_frames), "pad_with_hp": len(live), "mk_frames": len(mk_frames),
            "mk_with_hp": len(mk_live), "P1": p1, "P2": p2, "P3": p3,
            "pass": p1["pass"] and p2["pass"] and p3["pass"],
            "consequence_if_failed": "the live arm drops the HUD stream (hud=False), pre-registered"}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    import cv2
    p = argparse.ArgumentParser(description="Pad->M&K HUD transform parity on paired stills")
    p.add_argument("--pad", nargs="+", required=True, help="pad still globs (e.g. data/l1/galacta-pilot-*/*.jpg)")
    p.add_argument("--mk", nargs="+", required=True, help="James's M&K frame globs (never the sealed test take)")
    p.add_argument("--out", required=True)
    p.add_argument("--rule", default="p2prime", choices=RULES, help="p2 reproduces run 1; p2prime is the rule now")
    p.add_argument("--exclude-run", nargs="*", default=[],
                   help="earlier parity results whose sources may not be reused (p2prime: run 1 at least)")
    a = p.parse_args(argv)
    pad_paths = sorted({x for g in a.pad for x in glob.glob(g)})
    mk_paths = sorted({x for g in a.mk for x in glob.glob(g)})
    if any("053616" in x for x in mk_paths + pad_paths):
        raise SystemExit("the sealed 053616 take is never a parity source")
    if a.rule == "p2prime":
        if not a.exclude_run:
            raise SystemExit("p2prime runs on fresh frames only: pass --exclude-run with run 1's result")
        used = {d for r in a.exclude_run for side in json.load(open(r, encoding="utf-8"))["sources"].values()
                for d in side.values()}
        reused = [x for x in pad_paths + mk_paths if _sha(x) in used]
        if reused:
            raise SystemExit(f"{len(reused)} sources were used by an earlier parity run, e.g. {reused[0]}")
    check = parity if a.rule == "p2" else parity_prime
    result = check([cv2.imread(x) for x in pad_paths], [cv2.imread(x) for x in mk_paths])
    from . import hudmap
    result.update(sources={"pad": {x: _sha(x) for x in pad_paths}, "mk": {x: _sha(x) for x in mk_paths}},
                  measured=hudmap.MEASURED)
    with open(a.out, "x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=1, sort_keys=True, default=str)
    keys = ("P1", "P2", "P3") if a.rule == "p2" else ("P1", "P2prime", "P3", "coverage")
    print(json.dumps({k: result[k]["pass"] for k in keys} | {"pass": result["pass"]}))


if __name__ == "__main__":
    main()
