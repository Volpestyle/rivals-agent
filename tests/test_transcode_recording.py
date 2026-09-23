"""scripts/transcode_recording.py end to end on a 1 s copy of the 7 s HEVC encoder test take (docs/recording-log.md).

Needs ffmpeg/ffprobe on PATH and the take plus its logger folder on this PC; absent, the media tests skip with that
reason. The take is never modified: each test works on a stream-copied 1 s prefix in tmp_path (the logger's
frames.csv still matches a prefix: intake's matcher accepts unwritten tail packets), with a copied logger folder whose
metadata.json names the copy. libx265 ultrafast throughout; NVENC is never started (its process guard is tested with
fakes, and the encode monitor on a sleeping child process).
"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import transcode_recording as T  # noqa: E402

TAKE = Path("C:/Users/volpe/Videos/2026-09-23 15-37-16.mkv")
SESSION = Path("C:/Users/volpe/Videos/RivalsInput/20260923T203716-726Z-45572-1")
SEALED_ID, SEALED_MEDIA = "20260923T053616-779Z-33696-2", "C:/Users/volpe/Videos/2026-09-23 00-36-16.mkv"
FFMPEG, FFPROBE = shutil.which("ffmpeg"), shutil.which("ffprobe")

media = pytest.mark.skipif(not (FFMPEG and FFPROBE and TAKE.is_file() and SESSION.is_dir()),
                           reason="ffmpeg/ffprobe or the 15-37-16 test take and its logger folder are absent")
CLEAR = lambda: {"explorer.exe", "python.exe"}                              # noqa: E731  a process list without them


@pytest.fixture(scope="module")
def cut(tmp_path_factory):
    d = tmp_path_factory.mktemp("take")
    clip = d / "clip.mkv"
    subprocess.run([FFMPEG, "-hide_banner", "-v", "error", "-i", str(TAKE), "-map", "0", "-c", "copy", "-t", "1",
                    str(clip)], check=True)
    return clip


@pytest.fixture
def take(cut, tmp_path):
    """A fresh (clip, session folder) pair per test; the folder keeps the logger's session id as its name."""
    clip = tmp_path / "rec" / "clip.mkv"
    clip.parent.mkdir()
    shutil.copy2(cut, clip)
    session = tmp_path / SESSION.name
    shutil.copytree(SESSION, session)
    meta = json.loads((session / "metadata.json").read_text(encoding="utf-8"))
    meta["video_path"] = str(clip).replace("\\", "/")
    (session / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return clip, session


@pytest.fixture(autouse=True)
def no_priority_change(monkeypatch):
    """transcode() lowers its own process's priority; in tests it is recorded, not applied (see the child test)."""
    calls = []
    monkeypatch.setattr(T, "lower_priority", lambda: calls.append(1) or True)
    return calls


def _run(clip, session, out, **kw):
    kw.setdefault("encoder", "libx265")
    kw.setdefault("preset", "ultrafast")
    kw.setdefault("processes", CLEAR)
    return T.transcode(clip, session, out, ffmpeg=FFMPEG, ffprobe=FFPROBE, log=lambda s: None, **kw)


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _left(tmp_path):
    return sorted(p.name for p in tmp_path.iterdir())


# --- the verified path ------------------------------------------------------------------------------------------

@media
def test_end_to_end_preserves_every_timestamp_and_writes_the_receipt(take, tmp_path):
    clip, session = take
    before = _sha(clip)
    out = tmp_path / "out" / "clip.mkv"
    out.parent.mkdir()
    doc = _run(clip, session, out)
    v = doc["verification"]
    assert v["ok"] and v["decoded_frames"] == v["frames_csv"]["matched_frames"] > 100
    assert v["packets"]["0"]["type"] == "video" and v["packets"]["1"]["type"] == "audio"
    assert [s["codec_name"] for s in v["streams"]["output"]] == ["hevc", "aac"]
    video = [s for s in v["streams"]["output"] if s["codec_type"] == "video"][0]
    assert video["pix_fmt"] == "yuv420p" and video["color_range"] == "tv"
    receipt = json.loads((out.parent / "clip.transcode.json").read_text(encoding="utf-8"))
    assert receipt["original"]["sha256"] == before == _sha(clip)             # the original is untouched
    assert receipt["output"]["sha256"] == _sha(out) and receipt["ffmpeg_version"].startswith("ffmpeg version")
    assert "-enc_time_base:v" in receipt["command"] and "-n" in receipt["command"]
    assert _left(out.parent) == ["clip.mkv", "clip.transcode.json"]          # no partials


def test_lower_priority_is_inherited_by_ffmpeg_and_ffprobe():
    """Review D3: the class is set on the tool's own process, in a child here so pytest keeps its own."""
    probe = ("import ctypes; from ctypes import wintypes; k = ctypes.WinDLL('kernel32'); "
             "k.GetCurrentProcess.restype = wintypes.HANDLE; k.GetPriorityClass.argtypes = (wintypes.HANDLE,); "
             "print(hex(k.GetPriorityClass(k.GetCurrentProcess())))")
    code = ("import sys, subprocess; sys.path.insert(0, 'scripts'); import transcode_recording as T; "
            f"assert T.lower_priority(); exec({probe!r}); "
            f"print(subprocess.run([sys.executable, '-c', {probe!r}], capture_output=True, text=True).stdout.strip())")
    run = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    assert run.stdout.split() == ["0x4000", "0x4000"], run.stderr


@media
def test_the_run_lowers_its_priority_first(take, tmp_path, no_priority_change, monkeypatch):
    clip, session = take
    _run(clip, session, tmp_path / "o.mkv", plan_only=True)
    assert no_priority_change == [1]
    monkeypatch.setattr(T, "lower_priority", lambda: False)                  # fail closed: nothing at normal priority
    with pytest.raises(T.Refused, match="below-normal"):
        _run(clip, session, tmp_path / "o.mkv", plan_only=True)


@media
def test_an_interrupt_between_the_renames_still_leaves_a_receipt(take, tmp_path, monkeypatch):
    """Review D5: the output is in place, so the finally completes its receipt rather than deleting it."""
    clip, session = take
    real, calls = T.os.replace, []

    def replace(a, b):
        calls.append(Path(b).name)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return real(a, b)

    monkeypatch.setattr(T.os, "replace", replace)
    out = tmp_path / "out" / "clip.mkv"
    out.parent.mkdir()
    with pytest.raises(KeyboardInterrupt):
        _run(clip, session, out)
    monkeypatch.setattr(T.os, "replace", real)
    assert _left(out.parent) == ["clip.mkv", "clip.transcode.json"]
    assert json.loads((out.parent / "clip.transcode.json").read_text(encoding="utf-8"))["verification"]["ok"]


@media
def test_plan_only_checks_everything_and_writes_nothing(take, tmp_path):
    clip, session = take
    lines = []
    doc = T.transcode(clip, session, tmp_path / "o.mkv", encoder="libx265", preset="ultrafast", plan_only=True,
                      ffmpeg=FFMPEG, ffprobe=FFPROBE, processes=CLEAR, log=lines.append)
    p = doc["plan"]
    assert p["original"]["sha256"] == _sha(clip) and p["original"]["video"]["codec_name"] == "hevc"
    assert p["session_id"] == SESSION.name and "-n" in p["command"]
    assert any(l.startswith("PLAN ") for l in lines) and not (tmp_path / "o.mkv").exists()
    assert _left(tmp_path) == sorted(["rec", SESSION.name])


@media
def test_rounded_timestamps_fail_verification_and_leave_nothing(take, tmp_path, monkeypatch):
    """Without -enc_time_base:v demux the encoder rounds 1 ms PTS to 1/120 s: the check must catch it."""
    clip, session = take
    real = T.command
    monkeypatch.setattr(T, "command", lambda *a: [x for x in real(*a) if x not in ("-enc_time_base:v", "demux")])
    with pytest.raises(T.VerifyFailed, match="PTS"):
        _run(clip, session, tmp_path / "clip.mkv")
    assert _left(tmp_path) == sorted(["rec", SESSION.name])


@media
def test_a_pixel_format_change_fails_verification(take, tmp_path, monkeypatch):
    """Review T4: the fit's cache takes only yuv420p/nv12, tv, BT.709; a changed format or tag must not pass."""
    clip, session = take
    real = T.command
    monkeypatch.setattr(T, "command", lambda *a: real(*a)[:-1] + ["-pix_fmt", "yuv444p", real(*a)[-1]])
    with pytest.raises(T.VerifyFailed, match="pixel format or colour"):
        _run(clip, session, tmp_path / "clip.mkv")
    assert _left(tmp_path) == sorted(["rec", SESSION.name])


@media
def test_an_interrupted_encode_leaves_no_partial(take, tmp_path, monkeypatch):
    """Review T2: any exit that is not a verified success removes the partial, interrupts included."""
    clip, session = take

    def interrupted(cmd, **kw):
        Path(cmd[-1]).write_bytes(b"half an encode")
        raise KeyboardInterrupt

    monkeypatch.setattr(T, "encode", interrupted)
    with pytest.raises(KeyboardInterrupt):
        _run(clip, session, tmp_path / "clip.mkv")
    assert _left(tmp_path) == sorted(["rec", SESSION.name])


# --- the sealed denylist and pairing ----------------------------------------------------------------------------

def test_the_sealed_session_is_refused_by_id_before_anything_is_opened(tmp_path):
    with pytest.raises(T.Refused, match="session id"):
        _run(tmp_path / "nothing.mkv", tmp_path / SEALED_ID, tmp_path / "o.mkv")    # neither exists


@pytest.mark.parametrize("spelling", [SEALED_MEDIA, SEALED_MEDIA.upper(), SEALED_MEDIA.replace("/", "\\")])
def test_the_sealed_media_is_refused_by_path_as_a_string(tmp_path, spelling):
    with pytest.raises(T.Refused, match="media path"):
        _run(Path(spelling), tmp_path / "x", tmp_path / "o.mkv")


@media
def test_the_sealed_media_is_refused_by_hash(take, tmp_path):
    clip, session = take
    deny = tmp_path / "deny.json"
    deny.write_text(json.dumps({"schema_version": 1, "sessions": [
        {"session_id": "some-other-id", "media_path": "C:/elsewhere.mkv", "media_sha256": _sha(clip)}]}),
        encoding="utf-8")
    with pytest.raises(T.Refused, match="sealed"):
        _run(clip, session, tmp_path / "o.mkv", denylist_path=deny, denylist_pin=_sha(deny))
    assert not (tmp_path / "o.mkv").exists()


@media
def test_a_renamed_sealed_folder_is_refused_on_metadata_before_frames_are_read(take, tmp_path):
    """Review T7: metadata.json is read and checked before frames.csv is opened."""
    clip, session = take
    renamed = tmp_path / "renamed"
    session.rename(renamed)
    meta = json.loads((renamed / "metadata.json").read_text(encoding="utf-8"))
    (renamed / "metadata.json").write_text(json.dumps({**meta, "session_id": SEALED_ID}), encoding="utf-8")
    (renamed / "frames.csv").unlink()                                      # opening it would raise, not refuse
    with pytest.raises(T.Refused, match="sealed"):
        _run(clip, renamed, tmp_path / "o.mkv")


def test_a_changed_denylist_fails_closed(tmp_path):
    with pytest.raises(T.Refused, match="denylist unusable"):
        _run(tmp_path / "a.mkv", tmp_path / "s", tmp_path / "o.mkv", denylist_pin="0" * 64)


@media
def test_intakes_media_hash_check_must_hold(take, tmp_path):
    """Pairing is metadata.json's video_path AND the registry's expected_media_sha256, never a name pattern."""
    clip, session = take
    reg = tmp_path / "session-splits.test.json"
    reg.write_text(json.dumps({"schema_version": 1, "sessions": [
        {"session_id": SESSION.name, "expected_media_sha256": "0" * 64}]}), encoding="utf-8")
    with pytest.raises(T.Refused, match="media-hash check fails"):
        _run(clip, session, tmp_path / "o.mkv", registries=[reg])
    reg.write_text(json.dumps({"schema_version": 1, "sessions": [
        {"session_id": SESSION.name, "expected_media_sha256": _sha(clip)}]}), encoding="utf-8")
    doc = _run(clip, session, tmp_path / "o.mkv", registries=[reg], plan_only=True)
    assert doc["plan"]["registered_in"] == [str(reg)]


@media
@pytest.mark.parametrize("problem", ["exists", "container", "wrong video", "no disk"])
def test_refusals_before_encoding(take, tmp_path, monkeypatch, problem):
    clip, session = take
    out = tmp_path / "o.mkv"
    if problem == "exists":
        out.write_bytes(b"")
    elif problem == "container":
        out = tmp_path / "o.mp4"
    elif problem == "wrong video":
        other = tmp_path / "other.mkv"
        shutil.copy2(clip, other)
        clip = other
    else:
        monkeypatch.setattr(T.shutil, "disk_usage", lambda p: SimpleNamespace(free=10))
    with pytest.raises(T.Refused):
        _run(clip, session, out)
    assert not out.with_name("o.transcode.json").exists()


# --- the game and OBS absent for any encoder, fail closed -------------------------------------------------------

@media
@pytest.mark.parametrize("encoder", ["hevc_nvenc", "libx265"])
@pytest.mark.parametrize("running, match", [
    ({"marvel-win64-shipping.exe"}, "marvel-win64-shipping.exe running"),
    ({"obs64.exe"}, "obs64.exe running"),
    ({"obs-ffmpeg-mux.exe", "explorer.exe"}, "obs-ffmpeg-mux.exe running"),
])
def test_any_transcode_is_refused_while_the_game_or_obs_runs(take, tmp_path, running, match, encoder):
    clip, session = take
    with pytest.raises(T.Refused, match=match):
        _run(clip, session, tmp_path / "o.mkv", encoder=encoder, processes=lambda: running)


@media
def test_the_game_starting_mid_encode_kills_a_cpu_encode(take, tmp_path):
    clip, session = take
    calls = {"n": 0}

    def processes():
        calls["n"] += 1
        return {"explorer.exe"} if calls["n"] <= 2 else {"explorer.exe", "marvel-win64-shipping.exe"}

    real = T.encode
    T.encode = lambda cmd, guard=None, **k: real(cmd, guard=guard, every=0.05)
    try:
        with pytest.raises(T.Refused, match="marvel-win64-shipping.exe running"):
            _run(clip, session, tmp_path / "o.mkv", processes=processes)
    finally:
        T.encode = real
    assert _left(tmp_path) == sorted(["rec", SESSION.name])


@pytest.mark.parametrize("run", [SimpleNamespace(returncode=1, stdout=""),
                                 SimpleNamespace(returncode=0, stdout=""),
                                 OSError("no tasklist")])
def test_a_failing_tasklist_counts_as_running(monkeypatch, run):
    def fake(*a, **k):
        if isinstance(run, Exception):
            raise run
        return run

    monkeypatch.setattr(T.subprocess, "run", fake)
    with pytest.raises(T.Refused, match="treated as the game and OBS running"):
        T.processes_clear()


def test_the_real_tasklist_reads():
    names = T.running_images()
    assert len(names) > 5 and all(n == n.lower() and n.endswith(".exe") or " " in n or n for n in names)


def test_the_encode_monitor_kills_the_encoder_when_the_game_appears():
    calls = {"n": 0}

    def guard():
        calls["n"] += 1
        if calls["n"] >= 3:
            raise T.Refused("marvel-win64-shipping.exe running")

    t0 = time.monotonic()
    with pytest.raises(T.Refused, match="running"):
        T.encode([sys.executable, "-c", "import time; time.sleep(60)"], guard=guard, every=0.2)
    assert time.monotonic() - t0 < 15 and calls["n"] == 3


def test_the_encode_monitor_checks_before_starting():
    def guard():
        raise T.Refused("obs64.exe running")

    with pytest.raises(T.Refused):
        T.encode([sys.executable, "-c", "raise SystemExit('must not start')"], guard=guard)


# --- --delete-original RECEIPT: only through intake's media relocation ------------------------------------------

from agent import human_intake as hi  # noqa: E402


@pytest.fixture
def transcoded(take, tmp_path):
    """A verified transcode of the clip, its receipt, and an empty repo root for sessions and registries."""
    clip, session = take
    out = tmp_path / "out" / "clip.mkv"
    out.parent.mkdir()
    _run(clip, session, out)
    root = tmp_path / "repo"
    (root / "data" / "human" / "sessions").mkdir(parents=True)
    return clip, session, out, out.with_name("clip.transcode.json"), root


def _relocate(root, session_id, receipt, digest):
    """What data/human/sessions/relocate_session.py leaves: intake's relocation record, pinned by a fresh freeze."""
    folder = root / "data" / "human" / "sessions" / session_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "imported-demo.jsonl").write_text(json.dumps({"media_sha256": digest}) + "\n", encoding="utf-8")
    record = hi.relocation_record(receipt, session_id=session_id, identity_sha256=digest)
    (folder / hi.RELOCATION_FILE).write_text(json.dumps(record), encoding="utf-8")
    hi.freeze(folder, root=root)
    return folder


@pytest.fixture
def approved(monkeypatch):
    """The rule behind the switch: tests exercise it with DELETION_APPROVED set, as the lead would."""
    monkeypatch.setattr(T, "DELETION_APPROVED", True)


def _roots(root):
    return tuple(root / p for p in ("data/human/sessions", "data/human/skill-event-candidates",
                                    "data/human/calibration", "docs/evidence"))


def _delete(receipt, root):
    return T.delete_original(receipt, roots=_roots(root), data_root=root / "data",
                             sessions_root=root / "data" / "human" / "sessions", root=root, log=lambda s: None)


def test_deletion_is_refused_unconditionally_as_committed(tmp_path):
    assert T.DELETION_APPROVED is False
    with pytest.raises(T.Refused, match=r"^deletion not approved: pending D1/D2 \(see docs/evidence\)$"):
        T.delete_original(tmp_path / "anything.transcode.json")
    assert T.main(["--delete-original", str(tmp_path / "x.transcode.json")]) == 2


@media
def test_the_receipt_loads_through_intakes_contract(transcoded):
    clip, session, out, receipt, root = transcoded
    doc = hi.load_transcode_receipt(receipt, session_id=SESSION.name, identity_sha256=_sha(clip))
    assert doc["original_deleted"] is False and doc["output"]["sha256"] == _sha(out)


@media
def test_delete_is_refused_while_the_takes_own_session_holds_no_relocation(transcoded, approved):
    clip, session, out, receipt, root = transcoded
    with pytest.raises(T.Refused, match=f"{SESSION.name}: no media-relocation.json"):
        _delete(receipt, root)
    assert clip.is_file() and not receipt.with_name("clip.deleted.json").exists()


@media
def test_delete_after_the_relocation_is_recorded(transcoded, approved):
    clip, session, out, receipt, root = transcoded
    digest = _sha(clip)
    folder = _relocate(root, SESSION.name, receipt, digest)
    rec = _delete(receipt, root)
    assert not clip.exists() and out.is_file() and rec["relocated_sessions"] == [SESSION.name]
    deleted = json.loads(receipt.with_name("clip.deleted.json").read_text(encoding="utf-8"))
    assert deleted["state"] == "deleted" and deleted["sha256"] == digest
    assert hi.check_freeze(folder, root=root) == []                     # the session still checks without the original
    assert json.loads(receipt.read_text(encoding="utf-8"))["original_deleted"] is False   # the pinned receipt is intact


@media
def test_every_binder_must_resolve_to_a_relocated_session(transcoded, approved):
    """Review D1: a registry anywhere under data/ (here a calibration registry, outside the session-splits glob)
    and an assembled folder naming the original each need their own relocation."""
    clip, session, out, receipt, root = transcoded
    digest = _sha(clip)
    _relocate(root, SESSION.name, receipt, digest)
    reg = root / "data" / "human" / "calibration" / "20990101T000000-000Z-7-7" / "registry.01bc1e00335f.json"
    reg.parent.mkdir(parents=True)
    reg.write_text(json.dumps({"schema_version": 1, "sessions": [
        {"session_id": "20990101T000000-000Z-9-9", "expected_media_sha256": digest}]}), encoding="utf-8")
    with pytest.raises(T.Refused, match="20990101T000000-000Z-9-9: no media-relocation.json"):
        _delete(receipt, root)
    reg.unlink()
    other = root / "data" / "human" / "sessions" / "20990101T000000-000Z-8-8"      # an assembled folder naming it
    other.mkdir()
    (other / "provenance.json").write_text(json.dumps({"media": digest}), encoding="utf-8")
    with pytest.raises(T.Refused, match="20990101T000000-000Z-8-8"):
        _delete(receipt, root)
    assert clip.is_file()


@media
@pytest.mark.parametrize("where, how", [
    ("data/human/skill-event-candidates/051828-request-timing-v1/artifact-hashes.json", "sha256"),
    ("docs/evidence/range-request-human-fit-20260922/README.md", "path"),
    ("data/human/calibration/x/notes.md", "sha256"),
])
def test_a_binder_outside_any_session_blocks_deletion_and_is_named(transcoded, approved, where, how):
    """The review's missed binders: request cohorts, accepted evidence, calibration notes. None can hold a
    relocation record, so the original is kept and the file is named."""
    clip, session, out, receipt, root = transcoded
    _relocate(root, SESSION.name, receipt, _sha(clip))
    f = root / where
    f.parent.mkdir(parents=True, exist_ok=True)
    name = _sha(clip) if how == "sha256" else str(clip).replace("\\", "/")
    f.write_text(f"binds {name}", encoding="utf-8")
    with pytest.raises(T.Refused, match="resolves to no session") as e:
        _delete(receipt, root)
    assert str(f) in str(e.value) and clip.is_file()
    found = T.binders(clip, _sha(clip), roots=_roots(root), data_root=root / "data",
                      sessions_root=root / "data" / "human" / "sessions")
    assert {"path": str(f), "by": how, "session": None} in found


@media
@pytest.mark.parametrize("damage, match", [
    ("unpinned", "not pinned by the session's freeze"),
    ("other receipt", "another receipt"),
    ("tampered output", "no longer matches its receipt"),
    ("changed receipt", "load_transcode_receipt|another receipt|changed"),
])
def test_delete_refuses_a_relocation_that_does_not_hold(transcoded, approved, damage, match):
    clip, session, out, receipt, root = transcoded
    digest = _sha(clip)
    folder = _relocate(root, SESSION.name, receipt, digest)
    if damage == "unpinned":
        (folder / "artifact-hashes.json").unlink()
        hi.freeze(folder, root=root)
        doc = json.loads((folder / "artifact-hashes.json").read_text(encoding="utf-8"))
        doc["files"].pop(hi._rel(folder / hi.RELOCATION_FILE, root))
        (folder / "artifact-hashes.json").write_text(json.dumps(doc), encoding="utf-8")
    elif damage == "other receipt":
        rec = json.loads((folder / hi.RELOCATION_FILE).read_text(encoding="utf-8"))
        rec["receipt"]["sha256"] = "0" * 64
        (folder / hi.RELOCATION_FILE).write_text(json.dumps(rec), encoding="utf-8")
        (folder / "artifact-hashes.json").unlink()
        hi.freeze(folder, root=root)
    elif damage == "tampered output":
        out.write_bytes(out.read_bytes() + b"x")
    else:
        doc = json.loads(receipt.read_text(encoding="utf-8"))
        doc["cq"] = 99
        receipt.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(T.Refused, match=match):
        _delete(receipt, root)
    assert clip.is_file()


@media
def test_delete_refuses_a_receipt_intake_would_refuse(transcoded, approved):
    clip, session, out, receipt, root = transcoded
    doc = json.loads(receipt.read_text(encoding="utf-8"))
    doc["verification"]["ok"] = False
    receipt.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(T.Refused, match="load_transcode_receipt"):
        _delete(receipt, root)
    assert clip.is_file()


# --- plan-all ---------------------------------------------------------------------------------------------------

@media
def test_plan_all_pairs_by_metadata_and_never_opens_the_sealed_folder(take, tmp_path):
    clip, session = take
    root = tmp_path / "RivalsInput"
    root.mkdir()
    shutil.move(str(session), root / SESSION.name)
    (root / SEALED_ID).mkdir()                                  # no metadata.json: opening it would fail differently
    absent = root / "20990101T000000-000Z-1-1"
    absent.mkdir()
    (absent / "metadata.json").write_text(json.dumps({"session_id": absent.name,
                                                      "video_path": str(tmp_path / "gone.mkv")}), encoding="utf-8")
    (tmp_path / "rec" / "2026-09-23 15-37-16.mkv").write_bytes(b"a name-pattern decoy")
    rows = {r["session_id"]: r for r in T.plan_all(root, ffprobe=FFPROBE, log=lambda s: None)}
    assert rows[SEALED_ID]["status"] == "sealed: not opened"
    assert rows[SESSION.name]["status"] == "pairable" and T._norm(rows[SESSION.name]["original"]) == T._norm(clip)
    assert rows[SESSION.name]["sha256"] == _sha(clip) and rows[SESSION.name]["deletion"] == T.DELETION_REFUSAL
    assert rows[absent.name]["status"].startswith("not pairable") and "absent" in rows[absent.name]["status"]


def test_main_reports_refusal_with_exit_2(tmp_path, capsys):
    rc = T.main([str(tmp_path / "a.mkv"), str(tmp_path / SEALED_ID), "--out", str(tmp_path / "b.mkv"),
                 "--encoder", "libx265"])
    assert rc == 2 and "REFUSED" in capsys.readouterr().out
