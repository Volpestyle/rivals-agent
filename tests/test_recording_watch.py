"""scripts/recording_watch.py only prepares: one log row, the video's hash, and the admission lane's sequence as text."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import recording_watch as W  # noqa: E402

SID = "20260923T230000-000Z-1-7"
LOG = ("# Recording log\r\n\r\n| Video (Videos/) | Logger session | Length | Content | Cooldowns | Intake status |\r\n"
       "|---|---|---|---|---|---|\r\n| a.mkv | 20260922T000000-000Z-1-1 | 1 min | x | normal | admitted |\r\n"
       "\r\nTotal logged range play: see above.\r\n")


def test_next_steps_is_register_then_intake_steps_then_review_then_assemble():
    text = W.next_steps(SID)
    marks = [f"1. register {SID} in data/human/session-splits.corpus.json"]
    marks += [f"python intake_session.py {step} {SID} --scratch <DIR> --snapshot <code-snapshot-XXXXXXX>"
              for step in ("provenance", "verify", "profile", "vote", "scan", "regime", "motor", "propose", "evidence")]
    marks += [f"3. the independent per-session review of {SID}/segments-evidence.json",
              f"4. python assemble_session.py {SID} --independent-verdicts <PATH> --snapshot <code-snapshot-XXXXXXX>"]
    at = [text.index(m) for m in marks]
    assert at == sorted(at)
    assert "sealed-denylist.json" in text and "registered, reviewed and imported nothing" in text


def test_nothing_printed_imports_by_itself():
    text = W.next_steps(SID)
    assert "import_human_demo" not in text and "--unseal" not in text and "import --session" not in text


def _session(tmp_path, complete=True):
    video = tmp_path / "Videos" / "2026-09-23 18-00-00.mkv"
    video.parent.mkdir()
    video.write_bytes(b"not a real video")
    folder = tmp_path / "RivalsInput" / "s1"
    folder.mkdir(parents=True)
    (folder / "metadata.json").write_text(json.dumps(dict(
        session_id=SID, status="complete", complete=complete, clean_stop=True, queue_dropped_events=0,
        raw_input_errors=0, start_ns=0, end_ns=90 * 10**9, video_path=str(video))), encoding="utf-8")
    return tmp_path / "RivalsInput"


def test_scan_adds_one_row_after_the_table_prints_the_sequence_and_is_idempotent(tmp_path, monkeypatch, capsys):
    log = tmp_path / "recording-log.md"
    log.write_bytes(LOG.encode())
    monkeypatch.setattr(W, "LOG", log)
    root = _session(tmp_path)
    W.scan(root, settle_s=0, dry_run=False)
    out = capsys.readouterr().out
    lines = log.read_bytes().decode().split("\r\n")
    assert lines[5].startswith(f"| 2026-09-23 18-00-00.mkv | {SID} | 1.5 min |") and lines[6] == ""
    assert W.sha256(Path(json.loads((root / "s1/metadata.json").read_text())["video_path"])) in lines[5]
    assert W.next_steps(SID) in out
    before = log.read_bytes()
    W.scan(root, settle_s=0, dry_run=False)
    assert log.read_bytes() == before and SID not in capsys.readouterr().out
    written = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    assert written == {"recording-log.md", "Videos/2026-09-23 18-00-00.mkv", "RivalsInput/s1/metadata.json"}


def test_dry_run_and_incomplete_sessions_write_nothing(tmp_path, monkeypatch, capsys):
    log = tmp_path / "recording-log.md"
    log.write_bytes(LOG.encode())
    monkeypatch.setattr(W, "LOG", log)
    W.scan(_session(tmp_path), settle_s=0, dry_run=True)
    assert log.read_bytes() == LOG.encode() and W.next_steps(SID) in capsys.readouterr().out
    (tmp_path / "RivalsInput/s1/metadata.json").write_text(json.dumps(dict(session_id=SID, complete=False)))
    W.scan(tmp_path / "RivalsInput", settle_s=0, dry_run=False)
    assert log.read_bytes() == LOG.encode() and capsys.readouterr().out == ""
