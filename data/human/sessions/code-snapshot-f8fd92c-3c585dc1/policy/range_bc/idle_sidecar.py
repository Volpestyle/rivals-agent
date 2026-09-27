"""Streaming, train-only physical-idle proof for countermeasures round 3.

No images, training, or game input. The immutable manifest requires independent
review before use. Scored-window mass auditing belongs to the training consumer.
"""
import argparse
from array import array
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile

from agent import human_demos as raw

BASE_COMMIT = "9d61d593ac7adf2aac2abd63e5fe0d764509344f"
TABLE_HASHES = {
    "20260923T051828-422Z-33696-1": "d49224e3c4382a62ebb4c4252bcc5800138782688e1d0f60e03e46ce4b6e7edb",
    "20260923T200129-346Z-33696-6": "fcc9b0443e720648b899453ea3f04f82c0a6dd1735f30a420a36b3675549ba8e",
    "20260924T232304-170Z-12024-1": "8a6c63d4024b13d5b73ab0154f434782e6cfc853d6eaa8291bd9fa8ca8f3b1b1",
    "20260925T021320-371Z-7804-1": "841fe6953cf473e55c6becfe24143259fa48dca639bb9387bc04615edf6ea537",
    "20260925T025230-605Z-7804-2": "84cef39b81ce8a40637bb5cf9766cdfc6f4054b32cda5d94ac1082329434c288",
}
K, IDLE_WEIGHT = 30, 0.1
FORMAT = "rivals-range-idle-sidecar-v1"
MANIFEST_FORMAT = "rivals-range-idle-manifest-v1"
ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATHS = ("policy/range_bc/idle_sidecar.py", "agent/human_demos.py")
RAW_NAMES = ("inputs.jsonl", "frames.csv", "metadata.json")
HEADS = ("held", "press", "release", "yaw", "pitch")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def small_json(path):
    """Bounded metadata only; payloads always use line/record iterators."""
    require(Path(path).stat().st_size <= 4 * 1024 * 1024, "metadata exceeds 4 MiB limit")
    with Path(path).open(encoding="utf-8-sig") as f:
        return json.load(f)


def json_lines(path):
    with Path(path).open(encoding="utf-8") as f:
        while line := f.readline(1024 * 1024 + 1):
            require(len(line) <= 1024 * 1024, "JSONL record exceeds 1 MiB")
            yield json.loads(line)


def write_line(f, value):
    f.write(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def authorize(registry_path, denylist_path):
    """Validate the entire fixed cohort before opening any logger or step table."""
    deny = small_json(denylist_path)
    registry = small_json(registry_path)
    selected = {}
    for sid in TABLE_HASHES:
        matches = [s for s in registry["sessions"] if s["session_id"] == sid]
        require(len(matches) == 1, f"missing/duplicate registered session: {sid}")
        s = matches[0]
        require(s["split"] == "train" and s["session_group"] == sid, f"not independent train: {sid}")
        for entry in deny["sessions"]:
            paths = {str(s.get(k, "")).replace("\\", "/").casefold()
                     for k in ("video_path", "recorded_video_path")}
            require(entry["session_id"] != sid
                    and entry.get("media_sha256") != s.get("expected_media_sha256")
                    and str(entry.get("media_path", "!")).replace("\\", "/").casefold() not in paths,
                    f"denylisted source: {sid}")
        selected[sid] = s
    return selected


class RawCursor:
    """One lookahead event and the importer's physical state; no whole-log load."""

    def __init__(self, events):
        self.events = iter(events)
        self.next = None
        self.state = raw.HeldState()
        self.registered = self.paused = False
        self.relative = True
        self.generation = 0
        self.count = 0
        self.last_time = self.last_seq = -1
        self.types = Counter()
        self.devices = {"key": set(), "mouse": set()}
        self._read()

    def _read(self):
        self.next = next(self.events, None)
        if self.next is not None:
            e = self.next
            require(type(e.get("t_ns")) is int and e["t_ns"] >= self.last_time,
                    "raw events are not time ordered")
            require(type(e.get("seq")) is int and e["seq"] > self.last_seq,
                    "raw event sequence is not increasing")
            self.last_time, self.last_seq = e["t_ns"], e["seq"]

    def state_unknown(self):
        return (not self.registered or self.paused or not self.state.observed
                or bool(self.state.unknown_physical_vk) or not self.relative)

    def held(self):
        return bool(self.state.keys or self.state.mouse_buttons)

    def apply(self):
        e = self.next
        kind = e["type"]
        self.count += 1
        self.types[kind] += 1
        boundary = kind in ("gap", "focus", "pause", "raw_input_status")
        if boundary:
            self.generation += 1
        if kind == "gap" or (kind == "raw_input_status" and e.get("ok") is not True):
            self.state = raw.HeldState()
            if kind == "raw_input_status":
                self.registered = False
            self._read()
            return False, True
        event = raw._event(e)  # rejects malformed/unsupported records, never guesses
        if kind == "raw_input_status":
            self.registered = True
            self.state = raw.HeldState()  # registration cannot recover an earlier invalid snapshot
        if kind == "pause":
            self.paused = e["paused"]
        if kind == "focus":
            self.relative = True
        self.state = raw._advance(self.state, event)
        if kind == "mouse":
            self.relative = e["relative"]
        active = raw._control_affecting(event)
        if kind in self.devices and active:
            require(e["device"] != 0, "injected control-affecting packet")
            self.devices[kind].add(e["device"])
            require(len(self.devices[kind]) == 1, "multiple control-affecting devices")
        unknown = boundary or self.state_unknown()
        # Absolute/virtual-desktop/attributes-changed/unknown flag bits cannot
        # establish relative-input validity. MOVE_NOCOALESCE (8) is inert here.
        if kind == "mouse" and e["motion_flags"] & ~0x08:
            self.relative = False
            unknown = True
        self._read()
        return active, unknown

    def classify(self, anchor, step_ns):
        while self.next is not None and self.next["t_ns"] <= anchor:
            self.apply()
        unknown, active = self.state_unknown(), self.held()
        generation = self.generation
        while self.next is not None and self.next["t_ns"] <= anchor + step_ns:
            a, u = self.apply()
            active |= a or self.held()
            unknown |= u
        return (None if unknown else not active), generation

    def finish(self):
        while self.next is not None:
            self.apply()


class FrameContinuity:
    """Disk-sorted frame timestamps: encoder packet order includes B frames.

    Only compact gap/ambiguity intervals survive the index. Duplicated CTS and
    backwards presentation CTS are conservatively excluded, never repaired.
    """

    def __init__(self, path, db_path, metadata):
        con = sqlite3.connect(db_path)
        try:
            con.execute("PRAGMA cache_size=-8192")
            con.execute("PRAGMA temp_store=FILE")
            con.execute("CREATE TABLE frames (cts INTEGER, pts INTEGER, seq INTEGER UNIQUE)")
            count = 0
            with Path(path).open(newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    require(int(r["timebase_num"]) > 0 and int(r["timebase_den"]) > 0, "bad timebase")
                    require(int(r["composition_ns"]) > 0, "missing frame composition timestamp")
                    con.execute("INSERT INTO frames VALUES (?, ?, ?)",
                                (int(r["composition_ns"]), int(r["pts"]), int(r["event_seq"])))
                    count += 1
            con.commit()
            require(count == metadata["video_packets"] and count > 1, "frame count mismatch")
            period = (10**9 * metadata["fps_den"] + metadata["fps_num"] - 1) // metadata["fps_num"]
            gap_limit = (2 * 10**9 * metadata["fps_den"] + metadata["fps_num"] - 1) // metadata["fps_num"]
            gaps, previous = [], None
            for (cts,) in con.execute("SELECT cts FROM frames ORDER BY cts"):
                if previous is None:
                    self.start = cts
                elif cts - previous > gap_limit:
                    gaps.append((previous, cts))
                elif cts == previous:
                    gaps.append((cts - period, cts + period))
                previous = cts
            self.end = previous
            previous = None
            for (cts,) in con.execute("SELECT cts FROM frames ORDER BY pts"):
                if previous is not None and cts < previous:
                    gaps.append((cts - period, previous + period))
                previous = cts
            self.gaps = sorted(gaps)
            self.position = 0
            self.count = count
        finally:
            con.close()

    def valid(self, a, b):
        while self.position < len(self.gaps) and self.gaps[self.position][1] <= a:
            self.position += 1
        return (self.start <= a and b <= self.end
                and not (self.position < len(self.gaps) and self.gaps[self.position][0] < b))


def eligible(row):
    return row["suitability"] == "accepted" and row["regime"] == "normal"


def run_lengths(rows, nulls, generations, step_ns):
    """Compact derived integers only. True runs cannot bridge any boundary."""
    lengths = array("q", [0]) * len(nulls)
    runs, start, previous = [], None, None
    for i, row in enumerate(rows):
        ok = nulls[i] == 1 and eligible(row) and row["gap_free"]
        continuous = (previous is not None and row["run"] == previous["run"]
                      and row["segment"] == previous["segment"]
                      and row["anchor_ns"] == previous["anchor_ns"] + step_ns
                      and generations[i] == generations[i - 1])
        if start is not None and (not ok or not continuous):
            runs.append((start, i - start))
            start = None
        if ok and start is None:
            start = i
        previous = row
    if start is not None:
        runs.append((start, len(nulls) - start))
    for start, length in runs:
        for i in range(start, start + length):
            lengths[i] = length
    return lengths, runs


def table_rows(path):
    it = json_lines(path)
    next(it)
    yield from it


def head_counts(row, header):
    """Original eligible/gap-free known mass, once per row; NOT scored windows."""
    if not eligible(row) or not row["gap_free"]:
        return dict.fromkeys(HEADS, 0)
    n = sum(row["held_known"])
    return {"held": n, "press": n, "release": n, "yaw": int(row["relative_known"]),
            "pitch": int(row["relative_known"] and header["calibration"]["pitch_deg_per_count"] is not None)}


def export_session(sid, table, logger, output, registration, producer_hashes):
    require(sid in TABLE_HASHES, "session outside fixed train allowlist")
    require(sha256(table) == TABLE_HASHES[sid], "frozen table hash mismatch")
    header = next(json_lines(table))
    require(header["session_id"] == sid and header["split"] == "train", "table identity/role mismatch")
    require(header["media_sha256"] == registration["expected_media_sha256"], "table media identity mismatch")
    hashes = {name: sha256(logger / name) for name in RAW_NAMES}
    meta = small_json(logger / "metadata.json")
    require(meta["session_id"] == sid and meta["video_path"] == registration["recorded_video_path"],
            "raw metadata identity mismatch")
    require(meta["schema_version"] == 1 and meta["control_type"] == "keyboard_mouse", "unsupported logger")
    require(meta["complete"] is True and meta["clean_stop"] is True and meta["status"] == "complete",
            "recording incomplete")
    require(all(meta[k] == 0 for k in ("queue_dropped_events", "raw_input_errors",
                                      "frames_without_composition_timestamp")) and meta["writer_failed"] is False,
            "recording integrity failure")
    step_ns = header["step_ns"]
    nulls, generations = array("b"), array("q")
    with tempfile.TemporaryDirectory(prefix="frame-index-", dir=output) as tmp:
        frames = FrameContinuity(logger / "frames.csv", Path(tmp) / "frames.sqlite", meta)
        cursor = RawCursor(json_lines(logger / "inputs.jsonl"))
        previous = None
        for i, row in enumerate(table_rows(table)):
            a = row["anchor_ns"]
            require(row["i"] == i and (previous is None or a >= previous + step_ns),
                    "table indices/intervals not ordered")
            null, generation = cursor.classify(a, step_ns)
            if (not row["gap_free"] or not frames.valid(a, a + step_ns)
                    or not meta["start_ns"] <= a < a + step_ns <= meta["end_ns"]):
                null = None
            nulls.append(-1 if null is None else int(null))
            generations.append(generation)
            previous = a
        cursor.finish()
        require(cursor.types["key"] + cursor.types["mouse"] == meta["input_events"], "input count mismatch")
        require(cursor.count + frames.count == meta["events_attempted"], "total logger event count mismatch")
    lengths, runs = run_lengths(table_rows(table), nulls, generations, step_ns)
    out_header = {"format": FORMAT, "role": "train", "session_id": sid, "table_sha256": TABLE_HASHES[sid],
                  "step_ns": step_ns, "k": K, "idle_weight": IDLE_WEIGHT,
                  "raw_sha256": hashes, "producer_sha256": producer_hashes}
    path = output / f"{sid}.idle.jsonl"
    unweighted, treated = Counter(), Counter()
    positives = {h: [0] * len(header["actions"]) for h in ("press", "release")}
    known = [0] * len(header["actions"])
    weighted_rows = 0
    with path.open("x", encoding="utf-8", newline="\n") as f:
        write_line(f, out_header)
        for i, row in enumerate(table_rows(table)):
            weight = IDLE_WEIGHT if lengths[i] >= K else 1.0
            weighted_rows += weight == IDLE_WEIGHT
            write_line(f, {"i": i, "anchor_ns": row["anchor_ns"],
                           "null": None if nulls[i] == -1 else bool(nulls[i]),
                           "idle_run_length": lengths[i], "weight": weight})
            counts = head_counts(row, header)
            unweighted.update(counts)
            if weight == IDLE_WEIGHT:
                treated.update(counts)
            if eligible(row) and row["gap_free"]:
                for c, k in enumerate(row["held_known"]):
                    known[c] += k
                    for h in positives:
                        positives[h][c] += int(k and row[h][c] > 0)
    require(hashes == {name: sha256(logger / name) for name in RAW_NAMES}, "raw files changed during export")
    require(sha256(table) == TABLE_HASHES[sid], "table changed during export")
    stats = {
        "null_rows": {"true": nulls.count(1), "false": nulls.count(0), "unknown": nulls.count(-1)},
        "maximal_idle_runs": [{"start_i": a, "length": n} for a, n in runs],
        "idle_run_length_histogram": dict(sorted(Counter(n for _, n in runs).items())),
        "weighted_rows": weighted_rows, "weighted_row_share": weighted_rows / len(nulls),
        "total_effective_row_weight": (10 * len(nulls) - 9 * weighted_rows) / 10,
        "row_head_mass": {h: {"U": unweighted[h], "C": treated[h],
                              "E": (10 * unweighted[h] - 9 * treated[h]) / 10} for h in HEADS},
        "row_head_mass_scope": "eligible normal gap-free rows once each; excludes no burn-in or short runs; not scored-window audit",
        "unweighted_bce": {"actions": header["actions"], "known": known, "positive": positives},
        "raw_event_types": dict(cursor.types), "frame_packets": frames.count,
        "frame_gap_or_ambiguity_intervals": len(frames.gaps),
    }
    return {"sidecar": path.name, "sidecar_sha256": sha256(path), "table_sha256": TABLE_HASHES[sid],
            "raw_sha256": hashes, "rows": len(nulls), "step_ns": step_ns, "statistics": stats}


def export(*, logger_root, table_root, output, registry_path, denylist_path):
    registrations = authorize(registry_path, denylist_path)
    pins = {"registry_sha256": sha256(registry_path), "denylist_sha256": sha256(denylist_path)}
    producer = {p: sha256(ROOT / p) for p in SOURCE_PATHS}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)  # immutable candidate: never overwrite a prior attempt
    sessions = {}
    for sid in TABLE_HASHES:
        print(f"Exporting authorized train {sid}", flush=True)
        sessions[sid] = export_session(sid, Path(table_root) / sid / f"{sid}.steps.jsonl",
                                       Path(logger_root) / sid, output, registrations[sid], producer)
        s = sessions[sid]["statistics"]
        print(f"  rows={sessions[sid]['rows']} null={s['null_rows']} weighted={s['weighted_rows']}", flush=True)
    require(producer == {p: sha256(ROOT / p) for p in SOURCE_PATHS}, "producer source changed during export")
    require(pins == {"registry_sha256": sha256(registry_path), "denylist_sha256": sha256(denylist_path)},
            "access controls changed during export")
    manifest = {"format": MANIFEST_FORMAT, "role": "train", "k": K, "idle_weight": IDLE_WEIGHT,
                "base_commit": BASE_COMMIT, **pins, "producer_sha256": producer, "sessions": sessions,
                "scored_mass_audit": "r3-impl owns exact Batches.windows audit; row masses here are not scored masses",
                "review_status": "candidate; binds-review independent acceptance required before training"}
    with (output / "manifest.json").open("x", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")
    return manifest


def load_weights(table_path, sidecar_path, *, manifest_path, manifest_sha256, registry_path, denylist_path):
    """Validate all provenance and rows before returning array('d'); never open raw sources."""
    require(sha256(manifest_path) == manifest_sha256, "manifest hash mismatch")
    manifest = small_json(manifest_path)
    require(manifest["format"] == MANIFEST_FORMAT and manifest["role"] == "train"
            and manifest["k"] == K and manifest["idle_weight"] == IDLE_WEIGHT, "manifest contract mismatch")
    require(set(manifest["sessions"]) == set(TABLE_HASHES), "manifest must contain exactly the five train sessions")
    require(sha256(registry_path) == manifest["registry_sha256"]
            and sha256(denylist_path) == manifest["denylist_sha256"], "access-control hash mismatch")
    registrations = authorize(registry_path, denylist_path)
    named_sid = Path(sidecar_path).name.removesuffix(".idle.jsonl")
    require(named_sid in TABLE_HASHES, "sidecar outside train allowlist")
    require(Path(table_path).name in (f"{named_sid}.steps.jsonl", f"{named_sid}.jsonl"),
            "table filename outside selected train session")
    tables = json_lines(table_path)
    table_header = next(tables)
    sid = table_header["session_id"]
    require(sid in TABLE_HASHES and table_header["split"] == "train", "table is not authorized train")
    require(table_header["media_sha256"] == registrations[sid]["expected_media_sha256"], "media identity mismatch")
    entry = manifest["sessions"][sid]
    require(sha256(table_path) == entry["table_sha256"] == TABLE_HASHES[sid], "table hash mismatch")
    require(Path(sidecar_path).name == entry["sidecar"] == f"{sid}.idle.jsonl", "sidecar path/session mismatch")
    require(sha256(sidecar_path) == entry["sidecar_sha256"], "sidecar hash mismatch")
    sidecars = json_lines(sidecar_path)
    header = next(sidecars)
    expected = {"format": FORMAT, "role": "train", "session_id": sid, "table_sha256": entry["table_sha256"],
                "step_ns": table_header["step_ns"], "k": K, "idle_weight": IDLE_WEIGHT,
                "raw_sha256": entry["raw_sha256"], "producer_sha256": manifest["producer_sha256"]}
    require(header == expected and entry["step_ns"] == table_header["step_ns"], "header provenance mismatch")
    require(set(header["raw_sha256"]) == set(RAW_NAMES) and set(header["producer_sha256"]) == set(SOURCE_PATHS),
            "missing provenance hashes")
    for hashes in (header["raw_sha256"], header["producer_sha256"]):
        require(all(isinstance(h, str) and len(h) == 64 and all(c in "0123456789abcdef" for c in h)
                    for h in hashes.values()), "invalid provenance digest")
    weights = array("d")
    for i, row in enumerate(tables):
        proof = next(sidecars, None)
        require(proof is not None, "short sidecar")
        require(type(proof["i"]) is int and proof["i"] == row["i"] == i
                and type(proof["anchor_ns"]) is int and proof["anchor_ns"] == row["anchor_ns"],
                "sidecar row alignment mismatch")
        null, length, weight = proof["null"], proof["idle_run_length"], proof["weight"]
        require(null is None or type(null) is bool, "invalid null tri-state")
        require(type(length) is int and length >= 0 and (length == 0 or null is True), "invalid idle run length")
        require(not length or (eligible(row) and row["gap_free"]), "idle run in ineligible row")
        require(type(weight) in (float, int) and weight == (IDLE_WEIGHT if length >= K else 1.0),
                "weight disagrees with null/run classification")
        weights.append(weight)
    require(next(sidecars, None) is None and len(weights) == entry["rows"], "sidecar row count mismatch")
    return weights


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--logger-root", type=Path, default=Path("C:/Users/volpe/Videos/RivalsInput"))
    ap.add_argument("--table-root", type=Path, default=Path("data/human/sessions"))
    ap.add_argument("--output", type=Path, default=Path("data/human/round3-idle-sidecars-20260926"))
    ap.add_argument("--registry-path", type=Path, default=Path("data/human/session-splits.corpus.json"))
    ap.add_argument("--denylist-path", type=Path, default=Path("data/human/sealed-denylist.v2.json"))
    a = ap.parse_args()
    export(**vars(a))
    print(f"Manifest SHA256 {sha256(a.output / 'manifest.json')}", flush=True)


if __name__ == "__main__":
    main()
