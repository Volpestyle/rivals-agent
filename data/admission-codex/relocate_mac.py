"""Immutable relocation of an accepted match session to the Mac (docs/machines.md, "Record on Windows, import on
the Mac"): hash on Windows first, copy only the named files at below-normal priority, verify with shasum on the Mac,
and write a receipt. Refuses on any mismatch with the pinned hashes. Nothing on either side is edited or deleted.

    python relocate_mac.py SESSION_ID RECEIPT_OUT
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BELOW = 0x4000
ROOT = Path("C:/Users/volpe/repos/rivals-agent")
RAW = Path("C:/Users/volpe/Videos/RivalsInput")
MAC_ROOT = "/Users/james/dev/idm-match-data"
SSH_EXE = "C:/Program Files/Git/usr/bin/ssh.exe"
SCP_EXE = "C:/Program Files/Git/usr/bin/scp.exe"
SSH = ["-F", "C:/Users/volpe/.ssh/config", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
       "-o", "StrictHostKeyChecking=yes", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def need(cond, msg):
    if not cond:
        raise SystemExit(f"REFUSED: {msg}")


def main():
    sid, out = sys.argv[1], Path(sys.argv[2])
    need(sid == "20260927T052001-827Z-150600-5", "this retry is only authorized for accepted match -5")
    need(not out.exists(), f"{out} exists")
    reg = {r["session_id"]: r for r in json.loads((ROOT / "data/human/session-splits.corpus.json").read_text(encoding="utf-8"))["sessions"]}
    row = reg[sid]
    need(row["split"] == "idm_train" and not row.get("training_pending") and not row.get("pair"), "not an admissible live match")
    d = ROOT / "data/human/sessions" / sid
    steps_header = json.loads((d / f"{sid}.steps.jsonl").open(encoding="utf-8").readline())
    video = Path(row["video_path"])
    files = [  # (local path, mac path, pinned sha256 or None)
        (video, f"{MAC_ROOT}/originals/{video.name}", row["expected_media_sha256"]),
        *[(RAW / sid / n, f"{MAC_ROOT}/originals/{sid}/{n}", None) for n in ("metadata.json", "inputs.jsonl", "frames.csv")],
        (d / f"{sid}.steps.jsonl", f"{MAC_ROOT}/sessions/{sid}/{sid}.steps.jsonl", None),
        (d / "imported-demo.jsonl", f"{MAC_ROOT}/sessions/{sid}/imported-demo.jsonl",
         steps_header["source"]["imported_demo_sha256"]),
    ]
    rows = []
    for local, remote, pin in files:
        h = sha(local)
        need(pin is None or h == pin, f"{local.name}: Windows sha256 {h} differs from its pin {pin}")
        rows.append(dict(windows_path=local.as_posix(), mac_path=remote, bytes=local.stat().st_size, windows_sha256=h))
        print("hashed", local.name, h, flush=True)
    dirs = sorted({r["mac_path"].rsplit("/", 1)[0] for r in rows})
    subprocess.run([SSH_EXE, "-n", "-T", *SSH, "mac", "mkdir -p " + " ".join(f"'{x}'" for x in dirs)], check=True)
    exists = subprocess.run([SSH_EXE, "-n", "-T", *SSH, "mac", " ; ".join(f"test -e '{r['mac_path']}' && echo EXISTS '{r['mac_path']}'" for r in rows) + " ; true"],
                            capture_output=True, text=True, check=True).stdout
    need("EXISTS" not in exists, f"destination files already exist, never overwritten:\n{exists}")
    for r in rows:
        # Git's MSYS scp accepts /c/... without interpreting the drive colon as a remote host.
        local = r["windows_path"]
        msys_local = "/" + local[0].lower() + local[2:]
        subprocess.run([SCP_EXE, "-q", *SSH, msys_local, f"mac:{r['mac_path']}"], check=True, creationflags=BELOW)
        print("copied", r["mac_path"], flush=True)
    got = subprocess.run([SSH_EXE, "-n", "-T", *SSH, "mac", "shasum -a 256 " + " ".join(f"'{r['mac_path']}'" for r in rows)],
                         capture_output=True, text=True, check=True).stdout.splitlines()
    mac = {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in got}
    for r in rows:
        r["mac_sha256"] = mac[r["mac_path"]]
        need(r["mac_sha256"] == r["windows_sha256"], f"{r['mac_path']}: Mac sha256 differs")
    doc = dict(kind="immutable_relocation", session=sid, contract="docs/machines.md, Record on Windows, import on the Mac",
               at=datetime.now(timezone.utc).isoformat(timespec="seconds"), mac_root=MAC_ROOT,
               note=("recorder metadata copied byte-identical (its literal Windows video_path unchanged); a Mac registry "
                     "sets video_path to the Mac original with recorded_video_path and expected_media_sha256 from the "
                     "PC registry row"),
               registry_row=dict(recorded_video_path=row["recorded_video_path"], expected_media_sha256=row["expected_media_sha256"],
                                 session_group=row["session_group"], split=row["split"]),
               files=rows)
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("receipt", out, sha(out))


if __name__ == "__main__":
    main()
