"""Full-scale imitation test (lead, 2026-09-30; VUH-1346): bc2 features for every IDM v2-cd expert row that the
existing expert shards do not already cover, extracted on the PC GPU and shipped to the Modal volume shard by shard.

  plan     For each v2-cd table, drop rows whose source frame (video, pts) an existing shard already holds; split
           what is left into ~30k-row shards of whole pieces (a v2-cd run split by covered rows becomes pieces
           "<run>~k", so motion and recurrent state never bridge a gap). -> <out>/expert-<video>-c<i>.steps.jsonl
  extract  Per shard: expert.decode_rows (software decode, on a thread) and expert.views_of, then expert.features'
           GPU stage (tower, gray, green) and targets, in one pass. Software decode, not NVDEC: NVDEC frames differ
           by ~0.1 grey level and the frozen tower turns that into a ~12% mean feature change (measured on
           expert-2873352801-s0's first 512 rows; the software path reproduces the stored features exactly), so
           new shards would not match the existing ones.
  run      extract planned shards (--part i/N splits them across processes); pauses while the game runs, below a
           free-RAM floor, or while more than --pending-gb of extracted shards wait for the upload.
  ship     ship each finished shard (scp to the Mac, `modal volume put` into /expert-features/<shard>, then delete
           the .npy files on both sides; targets.npz and meta.json stay for r1 overlays) until all are shipped.

    python -m policy.bc2.fullscale plan D:/rivals-agent-local/idm-labels/v2-cd --have D:/rivals-policy/expert-labels \
        D:/rivals-policy/expert-labels-mac --out D:/rivals-policy/fullscale/labels
    python -m policy.bc2.fullscale run D:/rivals-policy/fullscale/labels --out D:/rivals-policy/fullscale/features \
        --part 0/2      (and 1/2 in a second process)
    python -m policy.bc2.fullscale ship D:/rivals-policy/fullscale/labels --out D:/rivals-policy/fullscale/features
"""
import argparse
import json
from pathlib import Path
import subprocess
import threading
import time

import numpy as np

MAC_SHIP = "~/dev/policy-bc2/fs-ship"
VOLUME = "rivals-policy-bc2-20260930"
MODAL = "export PATH=$HOME/.local/bin:$PATH; MODAL_PROFILE=rivals nice -n 10 taskpolicy -b modal"   # Mac caps
NPY = ("feats.npy", "gray_g.npy", "gray_c.npy", "green.npy")


def _video(header):
    return header.get("source_video_group", header["session_id"])


def covered(shard_dirs):
    """{(video, pts)} of every row in the existing shard label files."""
    have = set()
    for d in shard_dirs:
        for path in sorted(Path(d).glob("expert-*.steps.jsonl")):
            with path.open(encoding="utf-8") as stream:
                video = _video(json.loads(stream.readline()))
                for line in stream:
                    if line.strip():
                        have.add((video, json.loads(line)["frame"]["pts"]))
    return have


def plan(tables, have, out_dir, rows_per_shard=30000, log=print):
    """Write shards of the uncovered rows; returns {shard path: rows}."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for table in tables:
        with Path(table).open(encoding="utf-8") as stream:
            header = json.loads(stream.readline())
            video = _video(header)
            pieces, piece, prev_run, prev_kept, splits = [], [], None, False, {}
            total = 0
            for line in stream:
                if not line.strip():
                    continue
                total += 1
                r = json.loads(line)
                keep = (video, r["frame"]["pts"]) not in have
                if piece and (r["run"] != prev_run or not keep):
                    pieces.append(piece)
                    piece = []
                if keep:
                    if not piece:
                        k = splits.get(r["run"], -1) + 1
                        splits[r["run"]] = k
                    r["_piece"] = k
                    piece.append(r)
                prev_run = r["run"]
            if piece:
                pieces.append(piece)
        # a run that came out in more than one piece gets "~k" names; whole runs keep theirs
        multi = {run for run, k in splits.items() if k > 0}
        n = max(1, round(sum(map(len, pieces)) / rows_per_shard))
        shards, sizes = [[] for _ in range(n)], [0] * n
        for p in pieces:                                    # whole pieces, in order, to the emptiest shard
            j = sizes.index(min(sizes))
            shards[j].append(p)
            sizes[j] += len(p)
        for i, ps in enumerate(shards):
            rows = [dict({k: v for k, v in r.items() if k != "_piece"},
                         run=f"{r['run']}~{r['_piece']}" if r["run"] in multi else r["run"]) for p in ps for r in p]
            if not rows:
                continue
            sid = f"{header['session_id']}-c{i}"
            h = dict(header, session_id=sid, session_group=sid, source_video_group=video)
            path = out_dir / f"{sid}.steps.jsonl"
            with path.open("w", encoding="utf-8") as f:
                f.write(json.dumps(h) + "\n")
                for k, r in enumerate(rows):
                    f.write(json.dumps(dict(r, i=k)) + "\n")
            written[str(path)] = len(rows)
        log(f"{Path(table).name}: {total} rows, {sum(map(len, pieces))} new in {len(pieces)} pieces "
            f"({len(multi)} runs split) -> {len([s for s in shards if s])} shards")
    return written


def extract(labels, out_root, tower, *, device="cuda", batch=256, log=print, decode=None):
    """One shard's feature directory, as expert.views + expert.features would write it."""
    import torch
    from policy.bc2 import data
    import queue
    from policy.bc2.expert import NpyRows, decode_rows, load_labels, views_of
    from policy.bc2.features import tower_features
    from policy.bc2.model import FEAT, GREEN_DIM, gray_small, green_profile
    session = load_labels(labels)
    rows, n = session.rows, len(session.rows)
    out = Path(out_root) / session.session_id
    out.mkdir(parents=True, exist_ok=True)
    outs = {"feats": NpyRows(out / "feats.npy", np.float16, (n, 2, FEAT)),
            "gray_g": NpyRows(out / "gray_g.npy", np.uint8, (n, 72, 128)),
            "gray_c": NpyRows(out / "gray_c.npy", np.uint8, (n, 64, 64)),
            "green": NpyRows(out / "green.npy", np.float16, (n, GREEN_DIM))}
    pending, done, started = [], 0, time.monotonic()

    def flush():
        s = pending[0][0]
        g = torch.from_numpy(np.stack([v[0] for _, v in pending])).to(device)
        c = torch.from_numpy(np.stack([v[1] for _, v in pending])).to(device)
        f = tower_features(tower, [g, c])
        m = len(g)
        outs["feats"].write(s, torch.stack((f[:m], f[m:]), 1).cpu().numpy())
        outs["gray_g"].write(s, gray_small(g).cpu().numpy())
        outs["gray_c"].write(s, gray_small(c).cpu().numpy())
        outs["green"].write(s, green_profile(g).cpu().numpy().astype(np.float16))
        pending.clear()
    q = queue.Queue(1024)

    def produce():                       # decode and resize release the GIL: overlap them with the GPU stage
        try:
            for k, bgr in (decode or decode_rows)(rows[0]["frame"]["video_path"], rows):
                g, c = views_of(bgr)
                q.put((k, (np.ascontiguousarray(g), np.ascontiguousarray(c))))
            q.put(None)
        except BaseException as e:
            q.put(e)
    threading.Thread(target=produce, daemon=True).start()
    try:
        with torch.no_grad():
            while True:
                item = q.get()
                if item is None:
                    break
                if isinstance(item, BaseException):
                    raise item
                k, views = item
                if pending and k != pending[-1][0] + 1:
                    flush()
                pending.append((k, views))
                done += 1
                if len(pending) == batch:
                    flush()
            if pending:
                flush()
    finally:
        for a in outs.values():
            a.close()
    if done != n:
        raise ValueError(f"{session.session_id}: decoded {done} of {n} rows")
    np.savez(out / "targets.npz", **data.session_arrays(session, list(range(n))))
    meta = {"session": session.session_id, "split": session.split, "source_kind": "replay",
            "steps_sha256": session.sha256, "steps": n, "runs": len({r["run"] for r in rows}),
            "seconds": time.monotonic() - started, "labels": str(labels), "calibration": session.header["calibration"],
            "expert_context": session.header.get("expert_context"), "extractor": "fullscale (software decode, fused)"}
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    log(json.dumps({k: meta[k] for k in ("session", "steps", "seconds")}))
    return meta


GIT_SSH = "C:/Program Files/Git/usr/bin"
SSH_OPTS = ("-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=4")
LAN_MBPS, UPLINK_MBPS = 10., 11.5        # measured 2026-09-30: scp PC->Mac ~12 MB/s, Mac->Modal ~9.5-11.5 MB/s


def _ssh(cmd, timeout=60):
    """One short remote command (Git Bash ssh, -n -T, BatchMode). No long-lived session: Windows ssh has hung on
    teardown after a successful command (2026-09-30, the first shard's upload). Returns stdout."""
    return subprocess.run([f"{GIT_SSH}/ssh.exe", "-n", "-T", *SSH_OPTS, "mac", cmd], check=True,
                          capture_output=True, text=True, timeout=timeout).stdout


def _gib(text):
    v, unit = text.split()
    return float(v) * {"B": 2 ** -30, "KiB": 2 ** -20, "MiB": 2 ** -10, "GiB": 1., "TiB": 2 ** 10}[unit]


class Unknown(RuntimeError):
    """A status query failed in transport (ssh exit 255 or timeout): nothing is known, so nothing is cleaned up."""


def _query(cmd, timeout=120):
    try:
        return _ssh(cmd, timeout)
    except subprocess.TimeoutExpired as e:
        raise Unknown(f"timeout: {cmd[:60]}") from e
    except subprocess.CalledProcessError as e:
        if e.returncode == 255:
            raise Unknown(f"ssh transport: {e.stderr[-200:]}") from e
        raise


def on_volume(d):
    """True when every file of shard dir d is on the volume at its local size (modal's listing rounds sizes), False
    when a successful listing shows it absent or short. Raises Unknown when the listing itself failed."""
    shards = json.loads(_query(f"{MODAL} volume ls --json {VOLUME} /expert-features"))
    if not any(Path(e["filename"]).name == d.name for e in shards):
        return False
    listing = json.loads(_query(f"{MODAL} volume ls --json {VOLUME} /expert-features/{d.name}"))
    remote = {Path(e["filename"]).name: _gib(e["size"]) for e in listing if e.get("type") == "file"}
    for f in d.iterdir():
        if f.name in ("shipped", "ship-failed"):
            continue
        want = f.stat().st_size / 2 ** 30
        if f.name not in remote or abs(remote[f.name] - want) > max(.06 * want, 1e-3):
            return False
    return True


def mac_attempt(remote):
    """The Mac side of a shard's upload: (done marker text, an upload process is live, staging dir exists)."""
    name = remote.rsplit("/", 1)[1]
    out = _query(f"cat {remote}.done 2>/dev/null; echo; pgrep -f 'volume put.*fs-ship/{name} ' >/dev/null "
                 f"&& echo live || echo idle; [ -d {remote} ] && echo dir || echo nodir", 60).split("\n")
    return out[0].strip(), "live" in out, "dir" in out


def ship(feature_dir, log=print, lan=None):
    """scp to the Mac, upload into the volume's /expert-features/<shard> as a detached Mac job, poll it with short
    ssh calls, check the volume, then free the .npy bytes on both sides. Timeouts are ~2x the expected time.
    lan: a lock held only around the PC->Mac copy, so the next shard's copy overlaps this shard's upload.
    A failed status query (Unknown) never leads to cleanup; a live detached upload is reattached, not restarted;
    a shard whose state cannot be reconciled gets a ship-failed marker for the owner."""
    d = Path(feature_dir)
    remote = f"{MAC_SHIP}/{d.name}"
    gb = sum(f.stat().st_size for f in d.iterdir() if f.is_file()) / 1e9
    limit = max(600, 2 * gb * 1e3 / UPLINK_MBPS)
    if on_volume(d):
        log(f"{d.name}: already on the volume")
    else:
        done, live, _ = mac_attempt(remote)
        if live:
            log(f"{d.name}: reattaching to a live upload on the Mac")
        elif done == "ok":           # a finished upload the listing does not confirm: do not loop on it
            (d / "ship-failed").write_text("upload reported ok but the volume listing does not match\n")
            raise RuntimeError(f"{d.name}: marked ship-failed (ok marker, listing mismatch)")
        else:                        # no attempt is live: safe to clean the staging copy and start over
            _query(f"mkdir -p {MAC_SHIP} && rm -rf {remote} {remote}.done {remote}.log")
            with (lan or threading.Lock()):
                t = time.monotonic()
                subprocess.run([f"{GIT_SSH}/scp.exe", "-q", "-r", *SSH_OPTS, str(d), f"mac:{MAC_SHIP}/"], check=True,
                               capture_output=True, text=True, timeout=max(300, 2 * gb * 1e3 / LAN_MBPS))
                log(f"{d.name}: {gb:.2f} GB on the Mac in {time.monotonic() - t:.0f} s")
            _query(f"nohup sh -c '{MODAL} volume put --force {VOLUME} {remote} /expert-features/{d.name} "
                   f"&& rm -rf {remote} && echo ok > {remote}.done || echo fail > {remote}.done' "
                   f"> {remote}.log 2>&1 < /dev/null &")
        t = time.monotonic()
        while True:
            time.sleep(30)
            try:
                done, live, _ = mac_attempt(remote)
            except Unknown as e:               # one failed probe is not a failed upload
                log(f"{d.name}: status unavailable ({e}); polling again")
                continue
            if done == "ok":
                break
            if done == "fail" and not live:
                raise RuntimeError(f"{d.name}: modal volume put failed (see {remote}.log on the Mac)")
            if time.monotonic() - t > limit:
                if live:                       # still running: never clean up under it; the owner decides
                    (d / "ship-failed").write_text(f"upload still live after {limit:.0f} s\n")
                raise TimeoutError(f"{d.name}: upload not done after {limit:.0f} s (live={live})")
            log(f"{d.name}: uploading {time.monotonic() - t:.0f}/{limit:.0f} s")
        log(f"{d.name}: uploaded in {time.monotonic() - t:.0f} s ({gb * 1e3 / (time.monotonic() - t):.1f} MB/s)")
        if not on_volume(d):
            (d / "ship-failed").write_text("upload reported ok but the volume listing does not match\n")
            raise RuntimeError(f"{d.name}: marked ship-failed (listing mismatch after upload)")
    for name in NPY:
        (d / name).unlink(missing_ok=True)
    (d / "shipped").write_text(time.strftime("%Y-%m-%dT%H:%M:%S%z") + "\n")
    log(f"shipped {d.name}")


def overlays(shard_labels, aligned_dir, plain_dir, meta_root, out_root, log=print):
    """Target-only r1 overlays (cloud.fit expert_targets) for each shard: copy the shard's feature meta.json from
    meta_root/<shard>/ and expert.relabel it against expert-<video>.steps.jsonl. Old "-s" shards hold v2-a frames
    and take idm's aligned-to-v2-a r1 table; new "-c" shards hold v2-cd frames and take the plain r1 table (a
    video can have both). Returns {shard: (matched, missing)}."""
    from policy.bc2.expert import relabel
    out = {}
    for labels in shard_labels:
        labels = Path(labels)
        shard = labels.name.replace(".steps.jsonl", "")
        video, part = shard.rsplit("-", 1)
        table = Path(aligned_dir if part.startswith("s") else plain_dir) / f"{video}.steps.jsonl"
        if not table.exists():
            raise FileNotFoundError(f"no r1 table for {shard}: {table}")
        dst = Path(out_root) / shard
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "meta.json").write_bytes((Path(meta_root) / shard / "meta.json").read_bytes())
        out[shard] = relabel(labels, table, dst)
        log(f"{shard}: {table.parent.name}/{table.name} matched {out[shard][0]}, missing {out[shard][1]}")
    return out


def _status(progress, stage="running", part=""):
    try:
        from scripts.job_status import write
        write("policy-fullscale-extract" + part, owner="policy (VUH-1346)", stage=stage, host="pc",
              evidence="D:/rivals-policy/fullscale", progress=progress)
    except Exception as exc:
        print(f"status write failed: {exc}", flush=True)


def _shards(label_dir, out_root):
    return [(p, Path(out_root) / p.name.replace(".steps.jsonl", ""))
            for p in sorted(Path(label_dir).glob("expert-*-c*.steps.jsonl"))]


def pending_gb(out_root):
    """Extracted, not yet shipped .npy bytes on disk."""
    return sum(f.stat().st_size for f in Path(out_root).glob("*/*.npy")) / 2 ** 30


def extract_loop(label_dir, out_root, *, part=0, parts=1, cap_gb=40., floor_gb=6., poll=60, log=print):
    """Extract this part's shards (resumable: a shard with meta.json is done; a partial one is redone)."""
    import torch
    from policy.bc2.expert import free_ram_gb, game_running
    from policy.bc2.features import load_tower
    tag = f"-p{part}"
    mine = [(p, d) for i, (p, d) in enumerate(_shards(label_dir, out_root)) if i % parts == part]
    todo = [(p, d) for p, d in mine if not (d / "meta.json").exists()]
    log(f"part {part}/{parts}: {len(mine)} shards, {len(todo)} to extract")
    tower = None
    try:
        for i, (p, d) in enumerate(todo):
            while game_running() or free_ram_gb() < floor_gb or pending_gb(out_root) > cap_gb:
                if tower is not None and game_running():          # give the GPU back to the game
                    tower = None
                    torch.cuda.empty_cache()
                _status(f"waiting (game, RAM or upload backlog) before {p.name} ({i + 1}/{len(todo)})", part=tag)
                time.sleep(poll)
            if tower is None:
                tower = load_tower("D:/rivals-policy/bundles/ng-nohist-s1/vision.safetensors",
                                   "D:/rivals-policy/bundles/ng-nohist-s1/siglip2-large-config.json", "cuda")
            _status(f"extracting {p.name} ({i + 1}/{len(todo)})", part=tag)
            extract(p, out_root, tower, log=log)
        _status(f"{len(todo)} shards extracted", stage="done", part=tag)
    except BaseException as e:
        _status(str(e)[:200], stage="failed", part=tag)
        raise


def ship_loop(label_dir, out_root, *, poll=60, inflight=2, log=print):
    """Ship finished shards in plan order until every planned shard is shipped: up to `inflight` shards at once,
    one PC->Mac copy at a time (the next copy overlaps the previous upload); a failed shard backs off up to 15 min
    and is retried."""
    lan, busy, retry_at, lock = threading.Lock(), {}, {}, threading.Lock()

    def one(d):
        try:
            ship(d, log, lan)
            retry_at.pop(d.name, None)
        except Exception as e:
            wait = min(2 * retry_at.get(d.name, (0, poll / 2))[1], 900)
            retry_at[d.name] = (time.monotonic() + wait, wait)
            log(f"ship failed {d.name}: {e}; retrying in {wait:.0f} s")
        finally:
            with lock:
                busy.pop(d.name, None)
    while True:
        shards = _shards(label_dir, out_root)
        failed = [d.name for _, d in shards if (d / "ship-failed").exists()]
        left = [d for _, d in shards if not (d / "shipped").exists() and d.name not in failed]
        if not left and not busy:
            _status(f"{len(shards) - len(failed)}/{len(shards)} shards shipped; ship-failed (owner): {failed}",
                    stage="done" if not failed else "failed", part="-ship")
            return
        now = time.monotonic()
        ready = [d for d in left if (d / "meta.json").exists() and d.name not in busy
                 and retry_at.get(d.name, (0, 0))[0] <= now]
        with lock:
            while ready and len(busy) < inflight:
                d = ready.pop(0)
                busy[d.name] = threading.Thread(target=one, args=(d,), daemon=True)
                busy[d.name].start()
        _status(f"{len(shards) - len(left) - len(failed)}/{len(shards)} shipped; in flight: {', '.join(busy) or 'none'}; "
                f"{pending_gb(out_root):.0f} GB waiting" + (f"; ship-failed: {failed}" if failed else ""), part="-ship")
        time.sleep(10)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("stage", choices=("plan", "extract", "run", "ship", "overlays"))
    p.add_argument("paths", nargs="+")
    p.add_argument("--have", nargs="*", default=[])
    p.add_argument("--out", required=True)
    p.add_argument("--rows", type=int, default=30000)
    p.add_argument("--pending-gb", type=float, default=40.)
    p.add_argument("--part", default="0/1", help="run: this process's share i/N of the planned shards")
    p.add_argument("--aligned", help="overlays: idm's aligned-to-v2-a r1 tables (for -s shards)")
    p.add_argument("--plain", help="overlays: idm's plain r1 tables (for -c shards)")
    p.add_argument("--meta", nargs="+", help="overlays: directories holding <shard>/meta.json")
    a = p.parse_args(argv)
    if a.stage == "plan":
        tables = [t for d in a.paths for t in (sorted(Path(d).glob("expert-*.steps.jsonl")) if Path(d).is_dir()
                                                 else [Path(d)])]
        written = plan(tables, covered(a.have), a.out, a.rows, log=lambda m: print(m, flush=True))
        print(json.dumps({"shards": len(written), "rows": sum(written.values())}))
        return 0
    if a.stage == "extract":
        import torch
        from policy.bc2.features import load_tower
        torch.set_num_threads(2)
        tower = load_tower("D:/rivals-policy/bundles/ng-nohist-s1/vision.safetensors",
                           "D:/rivals-policy/bundles/ng-nohist-s1/siglip2-large-config.json", "cuda")
        for path in a.paths:
            extract(path, a.out, tower, log=lambda m: print(m, flush=True))
        return 0
    log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)
    if a.stage == "overlays":            # paths: shard label files or directories of them
        labels = [f for d in a.paths for f in (sorted(Path(d).glob("expert-*.steps.jsonl")) if Path(d).is_dir()
                                                else [Path(d)])]
        result = {}
        for f in labels:
            shard = f.name.replace(".steps.jsonl", "")
            meta_root = next(m for m in a.meta if (Path(m) / shard / "meta.json").exists())
            result.update(overlays([f], a.aligned, a.plain, meta_root, a.out, log=log))
        print(json.dumps({"shards": len(result), "matched": sum(m for m, _ in result.values()),
                          "missing": sum(x for _, x in result.values())}))
        return 0
    if a.stage == "ship":
        ship_loop(a.paths[0], a.out, log=log)
        return 0
    import torch
    torch.set_num_threads(2)
    part, parts = map(int, a.part.split("/"))
    extract_loop(a.paths[0], a.out, part=part, parts=parts, cap_gb=a.pending_gb, log=log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
