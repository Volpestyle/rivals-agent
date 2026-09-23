"""Re-encode one existing OBS recording to HEVC, prove nothing but the picture coding changed, and keep the original.

  python scripts/transcode_recording.py ORIGINAL.mkv SESSION_DIR --out OUTPUT.mkv [--plan]
        [--encoder hevc_nvenc|libx265] [--preset P] [--cq N]
  python scripts/transcode_recording.py --plan-all [--sessions-root DIR]
  python scripts/transcode_recording.py --delete-original RECEIPT.transcode.json

SESSION_DIR is the Rivals Input Logger folder recorded with ORIGINAL (metadata.json, frames.csv, inputs.jsonl). It is
read, never written. Every run prints its plan first; --plan stops there. --plan-all lists every pairable original
under the logger root, read-only. Order, each step refusing before the next:

1. Sealed denylist (data/human/sealed-denylist.json, pinned by sha256 in DENYLIST_SHA256): the session folder's name
   and the original's path are compared as strings before either is opened, then the original's sha256, then
   metadata.json's session_id (read, checked, and only then frames.csv).
2. Pairing, never by name pattern: metadata.json's video_path names ORIGINAL and its session_id is the folder name,
   and intake's media-hash check holds: where a split registry (any registry*.json or session-splits*.json under data/)
   gives the session an expected_media_sha256, the original's sha256 must equal it. The output does not exist, is not
   the original, keeps the original's container, and the output's disk has room for it.
3. The original itself must verify: agent.human_demos.match_frames(frames.csv, decoded PTS) in inspection mode, the
   matcher intake uses. A mapping that does not hold on the original cannot be shown to survive.
4. Every encoder (review D3): the game (Marvel-Win64-Shipping.exe) and OBS (obs64.exe, obs32.exe, obs-ffmpeg-mux.exe)
   must both be absent before the run starts, immediately before the encode and every MONITOR_EVERY_S during it;
   tasklist failing counts as present (fail closed). If either appears, ffmpeg is killed and the partial removed. The
   tool lowers its own priority class to below normal first, so ffmpeg and every ffprobe (the verification decodes
   included) inherit it.
5. ffmpeg -n: every stream mapped, video re-encoded, every other stream copied, timestamps passed through
   (-fps_mode passthrough, -enc_time_base:v demux, -copyts, -avoid_negative_ts disabled; without the time-base flag
   the encoder rounds 1 ms PTS to 1/120 s ticks), into OUTPUT's ".partial" sibling. The partial is removed on every
   exit that is not a verified success, interrupts included.
6. Verification, original against output:
   - the same container, streams in order and type, time bases; the output video is HEVC; the video's pixel format,
     colour range, space, primaries and transfer are unchanged; every other stream's codec is unchanged;
   - identical decoded video frame count and PTS list (ffprobe -show_frames: what intake reads);
   - per stream, identical packet PTS lists (video sorted: B-frames reorder packets) and counts;
   - frames.csv still matches: match_frames on the output returns the same FrameRefs (bar the path) and audit;
   - the original's size and mtime did not change while it was read.
7. Success: "<stem>.transcode.json.partial" is written (mode x), the partial is renamed to OUTPUT, and the receipt is
   renamed into place last. An OUTPUT without its .transcode.json is not a verified output.
8. --delete-original RECEIPT is REFUSED unconditionally ("deletion not approved: pending D1/D2 (see docs/evidence)")
   while DELETION_APPROVED is False. Behind it, the rule the tests keep exercising: a separate later step (intake's
   media relocation needs the receipt first: data/human/sessions/relocate_session.py). The receipt must load through
   intake's load_transcode_receipt, the output and the original must still hash as the receipt says, and every BINDER
   of the original is listed (binders(): every text file under BINDER_ROOTS, and every registry*.json or
   session-splits*.json anywhere under data/, naming its sha256 or its path). Each binder must resolve to a session
   holding a pinned media-relocation.json for this receipt: a file inside an assembled session folder resolves to that
   session, a registry row to its session id, and the take's own session is always included. A binder that resolves
   to no session (a request cohort, an evidence note, a calibration registry row without an assembled session) cannot
   hold a record, so the original is kept and the binder is named. For each session: intake's check_freeze clean, the
   record pinned by it, naming this receipt and original, and check_media accepting the output as "transcode". Then
   "<stem>.deleted.json" is written as an intent record, the original is unlinked, and the record is finalised. The
   receipt itself is never rewritten (relocations pin its sha256): it keeps "original_deleted": false.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent import human_demos as hd      # noqa: E402
from agent import human_intake as hi     # noqa: E402

DENYLIST = ROOT / "data" / "human" / "sealed-denylist.json"
DENYLIST_SHA256 = "57cfe01f29f6e1a55293f968ec697aa293c268bd87d7cf247ef648279e2fba7c"
REGISTRIES = None                     # None: every registry*.json / session-splits*.json under data/ (registry_files)
SESSIONS_ROOT = Path("C:/Users/volpe/Videos/RivalsInput")
ADMITTED_SESSIONS = ROOT / "data" / "human" / "sessions"
DATA = ROOT / "data"
# Everything that can bind an original by hash or path (review-transcode-2 D1), searched recursively.
BINDER_ROOTS = tuple(ROOT / p for p in (
    "data/human/skill-event-candidates", "data/human/skill-events", "data/human/calibration", "data/human/reviews",
    "data/human/inspection", "data/human/sessions", "data/diagnostics", "docs/evidence"))
REGISTRY_GLOBS = ("registry*.json", "session-splits*.json")        # anywhere under data/
BINDER_SUFFIXES = (".json", ".jsonl", ".md", ".csv", ".txt", ".log", ".py", ".yaml", ".yml")
DELETION_APPROVED = False             # the lead's switch; until then --delete-original refuses outright
DELETION_REFUSAL = "deletion not approved: pending D1/D2 (see docs/evidence)"
BELOW_NORMAL_PRIORITY_CLASS = 0x4000
GAME_IMAGE = "marvel-win64-shipping.exe"
OBS_IMAGES = ("obs64.exe", "obs32.exe", "obs-ffmpeg-mux.exe")
ENCODERS = ("hevc_nvenc", "libx265")
DEFAULT_PRESET = {"hevc_nvenc": "p5", "libx265": "medium"}
DEFAULT_CQ = 21                       # NVENC -cq / x265 -crf: a quality target, not a bitrate (James's call)
MONITOR_EVERY_S = 5.0
DISK_MARGIN_BYTES = 1 << 30
COLOUR_KEYS = ("pix_fmt", "color_range", "color_space", "color_primaries", "color_transfer")
HASH_CHUNK = 1 << 22
SCAN_HEAD_BYTES = 1 << 20             # files over 64 MB: the first MB is scanned for names


class Refused(Exception):
    """A precondition failed; nothing was written."""


class VerifyFailed(Exception):
    """The output differs from the original in something other than the picture coding."""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(HASH_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _norm(path):
    """A path as a comparable string, without touching the filesystem (review T7)."""
    return os.path.normcase(os.path.abspath(str(path))).replace("\\", "/")


# --- processes (fail closed) -----------------------------------------------------------------------------------

def running_images():
    """Lower-cased image names of every running process. Refused if tasklist fails or its output is unreadable."""
    try:
        run = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        raise Refused(f"cannot list processes ({e}): treated as the game and OBS running") from None
    rows = [r for r in csv.reader(io.StringIO(run.stdout)) if r]
    if run.returncode != 0 or not rows:
        raise Refused(f"tasklist failed (exit {run.returncode}): treated as the game and OBS running")
    return {r[0].strip().lower() for r in rows}


def processes_clear(processes=running_images):
    """Refused unless the game and OBS are both absent right now (any encoder: review D3)."""
    running = processes()
    present = sorted(running & ({GAME_IMAGE} | set(OBS_IMAGES)))
    if present:
        raise Refused(f"{', '.join(present)} running: transcodes wait until the game and OBS are both closed")


def lower_priority():
    """This process to below-normal priority; ffmpeg and ffprobe children inherit the class. True if set."""
    if sys.platform != "win32":
        os.nice(10)
        return True
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = wintypes.HANDLE           # a pseudo-handle: truncated to 32 bits without this
    k32.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    k32.SetPriorityClass.restype = wintypes.BOOL
    return bool(k32.SetPriorityClass(k32.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS))


# --- 1-2. the sealed denylist and pairing ----------------------------------------------------------------------

def load_sealed(path=DENYLIST, pin=DENYLIST_SHA256):
    try:
        return hi.load_denylist(path, sha256_pin=pin)
    except Exception as e:                                    # noqa: BLE001 - fail closed on any denylist problem
        raise Refused(f"sealed denylist unusable ({e}): nothing is opened without it") from None


def refuse_sealed_by_name(original, session_dir, denylist):
    """Before opening either: the folder name (the logger's session id) and the media path, as strings."""
    for row in denylist["sessions"]:
        if Path(session_dir).name == row["session_id"]:
            raise Refused(f"{row['session_id']}: sealed by the denylist (session id); never transcoded")
        if row.get("media_path") and _norm(original) == _norm(row["media_path"]):
            raise Refused(f"{original}: sealed by the denylist (media path); never transcoded")


def refuse_sealed(session_id, media_sha256, denylist):
    for row in denylist["sessions"]:
        if session_id == row["session_id"] or media_sha256 == row["media_sha256"]:
            raise Refused(f"{session_id}: sealed by the denylist (id or media hash); never transcoded")


def registry_hashes(registries=REGISTRIES):
    """{session_id: [(registry, expected_media_sha256)]} from the split registries' rows that carry one."""
    out = {}
    for path in (registry_files() if registries is None else registries):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        for row in doc.get("sessions", []):
            if row.get("expected_media_sha256"):
                out.setdefault(row.get("session_id"), []).append((str(path), row["expected_media_sha256"]))
    return out


def pair(original, session_dir, denylist, registries=REGISTRIES, log=print):
    """Steps 1-2 after the name checks: hash, sealed hash, metadata (id, video_path), intake's hash check, then
    frames.csv. Returns (digest, meta, packets, registered)."""
    original, session_dir = Path(original), Path(session_dir)
    log(f"hashing {original.name} ({original.stat().st_size / 1e9:.2f} GB)")
    digest = sha256(original)
    refuse_sealed(session_dir.name, digest, denylist)
    meta = json.loads((session_dir / "metadata.json").read_text(encoding="utf-8"))
    refuse_sealed(meta.get("session_id"), digest, denylist)
    if meta.get("session_id") != session_dir.name:
        raise Refused("metadata.json's session_id is not the folder's name")
    if _norm(meta.get("video_path") or "") != _norm(original):
        raise Refused(f"metadata.json names {meta.get('video_path')}, not {original}")
    registered = registry_hashes(registries).get(meta["session_id"], [])
    for reg, expected in registered:
        if expected != digest:
            raise Refused(f"intake's media-hash check fails: {reg} expects {expected[:12]}…, the file is "
                          f"{digest[:12]}…")
    with (session_dir / "frames.csv").open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != hd.FRAME_COLUMNS:
            raise Refused("unsupported frames.csv columns")
        packets = [{k: int(v) for k, v in row.items()} for row in reader]
    return digest, meta, packets, [r for r, _ in registered]


# --- probes ----------------------------------------------------------------------------------------------------

def _run_json(cmd):
    run = subprocess.run(cmd, capture_output=True, text=True)
    if run.returncode != 0:
        raise VerifyFailed(f"{Path(cmd[0]).name} failed: {run.stderr.strip()[:400]}")
    return json.loads(run.stdout)


def probe_streams(path, ffprobe="ffprobe"):
    keys = ("index", "codec_type", "codec_name", "time_base") + COLOUR_KEYS
    data = _run_json([ffprobe, "-v", "error", "-show_entries", "stream=" + ",".join(keys) + ":format=format_name",
                      "-of", "json", str(path)])
    return [{k: s.get(k) for k in keys} for s in data["streams"]], data["format"]["format_name"]


def probe_packets(path, ffprobe="ffprobe"):
    """{stream index: [pts, ...]} in file order."""
    data = _run_json([ffprobe, "-v", "error", "-show_entries", "packet=stream_index,pts", "-of", "json", str(path)])
    out = {}
    for p in data.get("packets", []):
        out.setdefault(p["stream_index"], []).append(p.get("pts"))
    return out


def frame_match(packets, decoded, video):
    try:
        refs, audit = hd.match_frames(packets, decoded, video, inspection_only=True)
    except hd.DemoError as e:
        raise VerifyFailed(f"frames.csv does not match {Path(video).name}: {e}") from None
    return [r.__dict__ | {"video_path": None} for r in refs], audit


# --- 6. verification -------------------------------------------------------------------------------------------

def verify(original, output, packets, *, ffprobe="ffprobe", before=None):
    """Every check, original against output. Returns the result dict; raises VerifyFailed on the first failure."""
    res = {}
    so, fo = probe_streams(original, ffprobe)
    sn, fn = probe_streams(output, ffprobe)
    if fo != fn:
        raise VerifyFailed(f"container changed: {fo} -> {fn}")
    if [(s["index"], s["codec_type"]) for s in so] != [(s["index"], s["codec_type"]) for s in sn]:
        raise VerifyFailed(f"stream layout changed: {so} -> {sn}")
    for a, b in zip(so, sn):
        if a["time_base"] != b["time_base"]:
            raise VerifyFailed(f"stream {a['index']} time base changed: {a['time_base']} -> {b['time_base']}")
        if a["codec_type"] == "video":
            if b["codec_name"] != "hevc":
                raise VerifyFailed(f"stream {a['index']} is {b['codec_name']}, not hevc")
            changed = {k: (a[k], b[k]) for k in COLOUR_KEYS if a[k] != b[k]}
            if changed:
                raise VerifyFailed(f"stream {a['index']} pixel format or colour tags changed: {changed}")
        elif a["codec_name"] != b["codec_name"]:
            raise VerifyFailed(f"stream {a['index']} codec changed: {a['codec_name']} -> {b['codec_name']}")
    res["streams"] = {"original": so, "output": sn, "container": fo}

    try:
        do, dn = hd.probe_video(original, ffprobe=ffprobe), hd.probe_video(output, ffprobe=ffprobe)
    except hd.DemoError as e:
        raise VerifyFailed(f"cannot decode for verification: {e}") from None
    if len(do["pts"]) != len(dn["pts"]):
        raise VerifyFailed(f"decoded frame count {len(do['pts'])} -> {len(dn['pts'])}")
    if do["pts"] != dn["pts"] or (do["timebase_num"], do["timebase_den"]) != (dn["timebase_num"], dn["timebase_den"]):
        first = next((i for i, (a, b) in enumerate(zip(do["pts"], dn["pts"])) if a != b), None)
        raise VerifyFailed(f"decoded PTS list differs (first at frame {first})")
    if (do["width"], do["height"]) != (dn["width"], dn["height"]):
        raise VerifyFailed("frame size changed")
    res["decoded_frames"] = len(dn["pts"])
    res["decoded_pts_sha256"] = hashlib.sha256(json.dumps(dn["pts"]).encode()).hexdigest()

    po, pn = probe_packets(original, ffprobe), probe_packets(output, ffprobe)
    if sorted(po) != sorted(pn):
        raise VerifyFailed("packet streams differ")
    res["packets"] = {}
    for s in so:
        i = s["index"]
        a, b = po.get(i, []), pn.get(i, [])
        if s["codec_type"] == "video":
            a, b = sorted(a, key=lambda v: (v is None, v)), sorted(b, key=lambda v: (v is None, v))
        if len(a) != len(b):
            raise VerifyFailed(f"stream {i} ({s['codec_type']}) packet count {len(a)} -> {len(b)}")
        if a != b:
            raise VerifyFailed(f"stream {i} ({s['codec_type']}) packet PTS list differs")
        res["packets"][str(i)] = {"type": s["codec_type"], "count": len(b)}

    ro, ao = frame_match(packets, do, original)
    rn, an = frame_match(packets, dn, output)
    if ro != rn or ao != an:
        raise VerifyFailed("frames.csv maps to the output differently than to the original")
    res["frames_csv"] = {"matched_frames": len(rn), "audit": an}

    if before is not None:
        st = Path(original).stat()
        if (st.st_size, st.st_mtime_ns) != before:
            raise VerifyFailed("the original changed while it was being read")
    res["ok"] = True
    return res


# --- 5. the encode ---------------------------------------------------------------------------------------------

def command(ffmpeg, original, partial, encoder, preset, cq):
    quality = ["-rc", "vbr", "-cq", str(cq), "-b:v", "0"] if encoder == "hevc_nvenc" else \
        ["-crf", str(cq), "-x265-params", "log-level=error"]
    return [ffmpeg, "-hide_banner", "-nostdin", "-n", "-v", "error", "-i", str(original),
            "-map", "0", "-c", "copy", "-c:v", encoder, "-preset", preset, *quality,
            "-fps_mode", "passthrough", "-enc_time_base:v", "demux", "-copyts", "-avoid_negative_ts", "disabled",
            "-map_metadata", "0", "-map_chapters", "0", str(partial)]


def encode(cmd, *, guard=None, every=MONITOR_EVERY_S, clock=time.monotonic, sleep=time.sleep):
    """Run ffmpeg; `guard()` (raising Refused) is called before the start and every `every` seconds during it, and a
    refusal kills ffmpeg. The caller removes the partial."""
    if guard is not None:
        guard()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        next_check = clock() + every
        while proc.poll() is None:
            sleep(min(0.5, every))
            if guard is not None and clock() >= next_check:
                guard()
                next_check = clock() + every
        err = proc.stderr.read()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    if proc.returncode != 0:
        raise VerifyFailed(f"ffmpeg exited {proc.returncode}: {err.strip()[:400]}")


# --- 8. deletion (a separate step, after intake's relocation) -------------------------------------------------

def _needles(original, digest):
    return {digest, _norm(original).lower()}


def _text_names(path, needles):
    """Whether a text file names one of `needles` (the whole file up to 64 MB, else its first MB)."""
    with Path(path).open("rb") as fh:
        raw = fh.read() if Path(path).stat().st_size <= 64 << 20 else fh.read(SCAN_HEAD_BYTES)
    text = raw.decode("utf-8", "replace").replace("\\\\", "/").replace("\\", "/").lower()
    found = [n for n in needles if n in text]
    return found[0] if found else None


def registry_files(data_root=DATA):
    """Every split registry under data/: registry*.json and session-splits*.json, at any depth."""
    return sorted({p for g in REGISTRY_GLOBS for p in Path(data_root).rglob(g) if p.is_file()})


def binders(original, digest, *, roots=BINDER_ROOTS, data_root=DATA, sessions_root=ADMITTED_SESSIONS):
    """Every file that names the original by sha256 or path: [{"path", "by", "session"}], where "session" is the
    session a hit resolves to (an assembled session folder's name, or a registry row's session id), else None."""
    needles = _needles(original, digest)
    sessions_root = Path(sessions_root).resolve()
    out, seen = [], set()
    for root in roots:
        if not Path(root).is_dir():
            continue
        for p in sorted(Path(root).rglob("*")):
            if not p.is_file() or p.suffix.lower() not in BINDER_SUFFIXES or p in seen:
                continue
            seen.add(p)
            hit = _text_names(p, needles)
            if hit:
                try:
                    session = p.resolve().relative_to(sessions_root).parts[0]
                except ValueError:
                    session = None
                out.append({"path": str(p), "by": "sha256" if hit == digest else "path", "session": session})
    for reg in registry_files(data_root):
        try:
            rows = json.loads(reg.read_text(encoding="utf-8")).get("sessions", [])
        except (ValueError, AttributeError):
            rows = []
        named = False
        for row in rows if isinstance(rows, list) else []:
            paths = {_norm(row[k]) for k in ("video_path", "recorded_video_path") if isinstance(row.get(k), str)}
            by = "sha256" if digest in (row.get("expected_media_sha256"), row.get("media_sha256")) else \
                "path" if _norm(original) in paths else None
            if by:
                named = True
                out.append({"path": str(reg), "by": by, "session": row.get("session_id"), "registry_row": True})
        if not named and reg not in seen and _text_names(reg, needles):
            out.append({"path": str(reg), "by": "text", "session": None, "registry_row": True})
    return out


def relocation_problem(session_id, receipt_path, output, digest, *, sessions_root=ADMITTED_SESSIONS, root=ROOT):
    """None if `session_id` holds a pinned, clean media-relocation.json for this receipt; else why not."""
    folder = Path(sessions_root) / session_id
    reloc = folder / hi.RELOCATION_FILE
    if not reloc.is_file():
        return f"{session_id}: no {hi.RELOCATION_FILE} (run data/human/sessions/relocate_session.py, or the session " \
               "is not assembled, so its original is kept)"
    try:
        frozen = json.loads((folder / "artifact-hashes.json").read_text(encoding="utf-8"))
        key = hi._rel(reloc, root)
        if not hi.pin_matches(reloc, frozen["files"].get(key)):
            return f"{session_id}: {hi.RELOCATION_FILE} is not pinned by the session's freeze"
        bad = hi.check_freeze(folder, root=root)
        if bad:
            return f"{session_id}: the session's freeze does not check clean: {bad[:3]}"
        record = json.loads(reloc.read_text(encoding="utf-8"))
        if record.get("receipt", {}).get("sha256") != sha256(receipt_path):
            return f"{session_id}: its relocation records another receipt"
        if record.get("session_id") != session_id or record.get("identity_sha256") != digest:
            return f"{session_id}: its relocation names another session or original"
        if hi.check_media(output, identity_sha256=digest, relocation=record, session_id=session_id) != "transcode":
            return f"{session_id}: intake's check_media does not accept the output as this relocation's transcode"
    except (hd.DemoError, OSError, ValueError, KeyError, TypeError) as e:
        return f"{session_id}: relocation check failed: {e}"
    return None


def delete_original(receipt_path, *, denylist_path=DENYLIST, denylist_pin=DENYLIST_SHA256, roots=BINDER_ROOTS,
                    data_root=DATA, sessions_root=ADMITTED_SESSIONS, root=ROOT, log=print):
    """Delete a transcoded original once every binder resolves to a session holding intake's relocation for this
    receipt. Refused outright while DELETION_APPROVED is False."""
    if not DELETION_APPROVED:
        raise Refused(DELETION_REFUSAL)
    receipt_path = Path(receipt_path)
    denylist = load_sealed(denylist_path, denylist_pin)
    try:
        raw = json.loads(receipt_path.read_text(encoding="utf-8"))
        sid, digest = raw["session_id"], raw["original"]["sha256"]
        doc = hi.load_transcode_receipt(receipt_path, session_id=sid, identity_sha256=digest)
    except (hd.DemoError, OSError, ValueError, KeyError, TypeError) as e:
        raise Refused(f"the receipt does not load through intake's load_transcode_receipt: {e}") from None
    original, output = Path(doc["original"]["path"]), Path(doc["output"]["path"])
    refuse_sealed_by_name(original, Path(sid), denylist)
    refuse_sealed(sid, digest, denylist)
    deleted = receipt_path.with_name(receipt_path.name.replace(".transcode.json", ".deleted.json"))
    if deleted.exists():
        raise Refused(f"{deleted.name} already exists")
    if not output.is_file() or sha256(output) != doc["output"]["sha256"]:
        raise Refused("the transcoded output is missing or no longer matches its receipt")
    if not original.is_file() or sha256(original) != digest:
        raise Refused("the original is missing or no longer matches its receipt")
    found = binders(original, digest, roots=roots, data_root=data_root, sessions_root=sessions_root)
    unbound = [b["path"] for b in found if b["session"] is None]
    sessions = sorted({sid} | {b["session"] for b in found if b["session"]})
    problems = [f"binder resolves to no session, so it cannot hold a relocation: {u}" for u in unbound]
    problems += [p for p in (relocation_problem(s_, receipt_path, output, digest, sessions_root=sessions_root,
                                                root=root) for s_ in sessions) if p]
    if problems:
        raise Refused("not deleting the original: " + "; ".join(problems))
    intent = {"kind": "recording-transcode-deletion-v1", "receipt": {"path": str(receipt_path),
              "sha256": sha256(receipt_path)}, "original": str(original), "sha256": digest,
              "binders": found, "relocated_sessions": sessions, "state": "intent",
              "intent_utc": datetime.now(timezone.utc).isoformat()}
    with deleted.open("x", encoding="utf-8") as fh:
        fh.write(json.dumps(intent, indent=2) + "\n")
    original.unlink()
    deleted.write_text(json.dumps({**intent, "state": "deleted", "deleted_utc": datetime.now(timezone.utc).isoformat()},
                                  indent=2) + "\n", encoding="utf-8")
    log(f"deleted {original}; relocated sessions {sessions}")
    return {**intent, "state": "deleted"}


# --- plan ------------------------------------------------------------------------------------------------------

def plan(original, session_dir, out, *, encoder, preset, cq, ffmpeg, ffprobe, denylist,
         registries=REGISTRIES, processes=running_images, log=print):
    """Every precondition, checked; returns (plan dict, pairing). Nothing is written."""
    original, session_dir, out = Path(original), Path(session_dir), Path(out)
    refuse_sealed_by_name(original, session_dir, denylist)            # strings only: before opening either
    if encoder not in ENCODERS:
        raise Refused(f"encoder must be one of {ENCODERS}")
    if not original.is_file() or not session_dir.is_dir():
        raise Refused("the original file and the logger session folder must both exist")
    if out.exists() or _norm(out) == _norm(original):
        raise Refused(f"refusing to write {out}: it exists or is the original")
    if out.suffix.lower() != original.suffix.lower():
        raise Refused("the output must keep the original's container (same suffix)")
    receipt, partial, deleted = _siblings(out)
    for p in (receipt, receipt.with_name(receipt.name + ".partial"), partial, deleted):
        if p.exists():
            raise Refused(f"{p.name} already exists")
    size = original.stat().st_size
    free = shutil.disk_usage(out.parent).free
    if free < size + DISK_MARGIN_BYTES:
        raise Refused(f"{out.parent} has {free / 1e9:.1f} GB free; the output may need up to {size / 1e9:.1f} GB + 1 GB")
    digest, meta, packets, registered = pair(original, session_dir, denylist, registries, log)
    processes_clear(processes)
    streams, container = probe_streams(original, ffprobe)
    preset = preset or DEFAULT_PRESET[encoder]
    p = {"original": {"path": str(original), "sha256": digest, "bytes": size,
                      "video": next((s for s in streams if s["codec_type"] == "video"), None)},
         "session_id": meta["session_id"], "registered_in": registered, "output": str(out), "receipt": str(receipt),
         "encoder": encoder, "preset": preset, "cq": cq, "free_bytes": free,
         "command": command(ffmpeg, original, partial, encoder, preset, cq),
         "process_guard": "game and OBS absent before and every %.0f s during the encode" % MONITOR_EVERY_S,
         "priority": "below normal (inherited by ffmpeg and ffprobe)",
         "binders": binders(original, digest),
         "original_kept": "always; --delete-original RECEIPT is a separate step after intake's relocation"}
    return p, (digest, meta, packets)


def _siblings(out):
    out = Path(out)
    return (out.with_name(out.stem + ".transcode.json"), out.with_name(out.stem + ".partial" + out.suffix),
            out.with_name(out.stem + ".deleted.json"))


def plan_all(sessions_root=SESSIONS_ROOT, denylist=None, registries=REGISTRIES, ffprobe="ffprobe", log=print):
    """Every logger folder under `sessions_root`: its original by metadata.json's video_path (never a name pattern),
    the intake hash check and the codec. Sealed folders are listed by name only and never opened. Read-only."""
    denylist = denylist or load_sealed()
    sealed_ids = {r["session_id"] for r in denylist["sessions"]}
    hashes = registry_hashes(registries)
    rows = []
    for folder in sorted(p for p in Path(sessions_root).iterdir() if p.is_dir()):
        row = {"session_id": folder.name}
        if folder.name in sealed_ids:
            rows.append({**row, "status": "sealed: not opened"})
            log(json.dumps(rows[-1]))
            continue
        try:
            meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
            video = Path(meta.get("video_path") or "")
            row["original"] = str(video)
            refuse_sealed_by_name(video, folder, denylist)
            if meta.get("session_id") != folder.name:
                raise Refused("metadata.json's session_id is not the folder's name")
            if not video.is_file():
                raise Refused("the original named by metadata.json is absent")
            digest = sha256(video)
            refuse_sealed(folder.name, digest, denylist)
            bad = [r for r, h in hashes.get(folder.name, []) if h != digest]
            if bad:
                raise Refused(f"intake's media-hash check fails against {bad}")
            streams, _ = probe_streams(video, ffprobe)
            v = next(s for s in streams if s["codec_type"] == "video")
            row.update(status="pairable", sha256=digest, bytes=video.stat().st_size, codec=v["codec_name"],
                       registered=bool(hashes.get(folder.name)),
                       deletion=DELETION_REFUSAL if not DELETION_APPROVED else
                       "only via --delete-original after relocate_session.py records the receipt")
        except (Refused, VerifyFailed, OSError, ValueError) as e:
            row["status"] = f"not pairable: {e}"
        rows.append(row)
        log(json.dumps(row))
    return rows


# --- the run ---------------------------------------------------------------------------------------------------

def transcode(original, session_dir, out, *, encoder="hevc_nvenc", preset=None, cq=DEFAULT_CQ,
              plan_only=False, ffmpeg="ffmpeg", ffprobe="ffprobe", denylist_path=DENYLIST,
              denylist_pin=DENYLIST_SHA256, registries=REGISTRIES, processes=running_images,
              log=print):
    original, session_dir, out = Path(original), Path(session_dir), Path(out)
    denylist = load_sealed(denylist_path, denylist_pin)
    if not lower_priority():
        raise Refused("cannot lower this process to below-normal priority: nothing is started at normal priority")
    p, (digest, meta, packets) = plan(original, session_dir, out, encoder=encoder, preset=preset, cq=cq,
                                      ffmpeg=ffmpeg, ffprobe=ffprobe,
                                      denylist=denylist, registries=registries, processes=processes, log=log)
    log("PLAN " + json.dumps(p))
    if plan_only:
        return {"plan": p}
    receipt, partial, deleted = _siblings(out)
    receipt_tmp = receipt.with_name(receipt.name + ".partial")
    st = original.stat()
    before = (st.st_size, st.st_mtime_ns)

    log("checking frames.csv against the original")
    try:
        frame_match(packets, hd.probe_video(original, ffprobe=ffprobe), original)
    except (VerifyFailed, hd.DemoError) as e:
        raise Refused(f"the original does not verify, so preservation cannot be shown: {e}") from None

    cmd = p["command"]
    done = False
    try:
        log("encoding")
        encode(cmd, guard=lambda: processes_clear(processes))
        log("verifying")
        result = verify(original, partial, packets, ffprobe=ffprobe, before=before)
        version = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
        doc = {
            "kind": "recording-transcode-v1",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "session_id": meta["session_id"],
            "original": {"path": str(original), "sha256": digest, "bytes": before[0]},
            "output": {"path": str(out), "sha256": sha256(partial), "bytes": partial.stat().st_size},
            "session_files": {n: {"path": str(session_dir / n), "sha256": sha256(session_dir / n)}
                              for n in ("metadata.json", "frames.csv", "inputs.jsonl") if (session_dir / n).is_file()},
            "registered_in": p["registered_in"],
            "command": cmd, "ffmpeg_version": version, "encoder": encoder, "preset": p["preset"], "cq": cq,
            "tool": {"path": str(Path(__file__).resolve()), "sha256": sha256(__file__)},
            "denylist_sha256": denylist_pin,
            "verification": result,
            "original_deleted": False,        # never rewritten: relocations pin this receipt; see <stem>.deleted.json
        }
        with receipt_tmp.open("x", encoding="utf-8") as fh:            # receipt first, renamed into place last
            fh.write(json.dumps(doc, indent=2) + "\n")
        os.replace(partial, out)
        os.replace(receipt_tmp, receipt)
        done = True
    finally:
        if not done:
            if out.exists() and receipt_tmp.exists() and not partial.exists():
                os.replace(receipt_tmp, receipt)          # the output is already in place: finish its receipt (D5)
            else:
                partial.unlink(missing_ok=True)
                receipt_tmp.unlink(missing_ok=True)
    log(f"verified; wrote {out.name} and {receipt.name}")

    return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("original", nargs="?")
    ap.add_argument("session_dir", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--plan", action="store_true", help="print the plan and stop")
    ap.add_argument("--plan-all", action="store_true", help="list every pairable original under --sessions-root")
    ap.add_argument("--sessions-root", default=str(SESSIONS_ROOT))
    ap.add_argument("--encoder", choices=ENCODERS, default="hevc_nvenc")
    ap.add_argument("--preset")
    ap.add_argument("--cq", type=int, default=DEFAULT_CQ)
    ap.add_argument("--delete-original", metavar="RECEIPT", help="delete a transcoded original (separate step)")
    ap.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    ap.add_argument("--ffprobe", default=shutil.which("ffprobe") or "ffprobe")
    a = ap.parse_args(argv)
    try:
        if a.delete_original:
            delete_original(a.delete_original)
            return 0
        if a.plan_all:
            plan_all(a.sessions_root, ffprobe=a.ffprobe)
            return 0
        if not (a.original and a.session_dir and a.out):
            raise Refused("ORIGINAL, SESSION_DIR and --out are required (or --plan-all)")
        doc = transcode(a.original, a.session_dir, a.out, encoder=a.encoder, preset=a.preset, cq=a.cq,
                        plan_only=a.plan, ffmpeg=a.ffmpeg, ffprobe=a.ffprobe)
    except Refused as e:
        print(f"REFUSED: {e}")
        return 2
    except VerifyFailed as e:
        print(f"VERIFY FAILED (output removed, original untouched): {e}")
        return 1
    if a.plan:
        return 0
    v = doc["verification"]
    print(json.dumps({"ok": True, "output": doc["output"], "decoded_frames": v["decoded_frames"],
                      "packets": v["packets"], "matched_frames": v["frames_csv"]["matched_frames"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
