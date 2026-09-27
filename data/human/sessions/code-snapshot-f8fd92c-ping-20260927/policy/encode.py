"""The embedding cache: every frame of every source, through one encoder, once.

This is the expensive label-independent step, and it is the only place in the lane that
touches pixels. A frozen pretrained encoder turns a normalized frame into one vector; the
temporal head that learns from those vectors is trained separately and can be retrained in
seconds without decoding anything again.

  uv run --group policy python -m policy.encode --bench            # what the encoder choice rests on
  uv run --group policy python -m policy.encode --probe            # which encoder's features separate our intents
  uv run --group policy python -m policy.encode --all [--hz 10]    # fill the cache, niced, resumable
  uv run --group policy python -m policy.encode --list

One `.npz` per source under `data/embeddings/<encoder>-<norm>-<hz>hz/`, holding `emb`
(float16 [n, dim]) and `t` (the decoded timestamps, float64 [n]), beside a `.json` sidecar
with the source's provenance: its kind, creator, split group, **cooldown regime**, the
normalization version and the mask rectangles the pixels actually went through. A trainer
reads the sidecar and refuses to mix regimes; nothing downstream has to remember which run
was cooldown-free.

Resume is per source: a source with both files already written is skipped, and each source
is written to a temporary name and renamed, so an interrupted run never leaves a half file
that looks complete. Re-encoding one source means deleting its two files.

Embeddings are derived from third-party media, so `data/embeddings/` stays under `data/`:
gitignored, never in docs/evidence, never on Linear.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np
from mlxim.model import create_model

from . import corpus as corpus_mod
from .frames import NORM, SIZE, Decoded, DecodedJpegs, DecodedProxy, rects, thin, visible_fraction

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "embeddings"
HZ = 10.0
SIDECAR_VERSION = 3      # bumped whenever a provenance field is added; `fill` rewrites older ones
DEFAULT = "vit_small_patch16_224.dino"
CANDIDATES = ("mobilenet_v3_small", "resnet18", "vit_base_patch32_224", "vit_small_patch16_224.dino")
MEAN = mx.array([0.485, 0.456, 0.406])
STD = mx.array([0.229, 0.224, 0.225])
HEADS = ("fc", "heads", "classifier")   # the classifier mlx-image gives each family; replaced by Identity


class Encoder:
    """A frozen pretrained encoder with its classifier removed: frames in, one vector each."""

    def __init__(self, name=DEFAULT, batch=64):
        self.name, self.batch = name, batch
        self.model = create_model(name)
        for attr in HEADS:
            if hasattr(self.model, attr):
                setattr(self.model, attr, nn.Identity())
                break
        else:
            raise ValueError(f"{name}: no classifier head to strip")
        self.model.eval()
        self.dim = int(self(np.zeros((1, SIZE, SIZE, 3), np.uint8)).shape[-1])

    def __call__(self, batch_u8):
        """[n, SIZE, SIZE, 3] uint8 -> [n, dim] float16."""
        x = (mx.array(batch_u8).astype(mx.float32) / 255.0 - MEAN) / STD
        out = self.model(x)
        mx.eval(out)
        return np.asarray(out.astype(mx.float16))

    @property
    def tag(self):
        return self.name.replace(".", "-")


def cache_dir(encoder, hz):
    return CACHE / f"{encoder.tag}-{NORM}-{hz:g}hz"


def run_frames(source):
    """A run's saved jpgs, their recorded times and the intent logged on each, in index order."""
    files, times, notes = [], [], []
    for line in source.index.read_text().splitlines():
        row = json.loads(line)
        if row.get("file"):
            files.append(row["file"])
            times.append(float(row["t"]))
            notes.append(row.get("note") or "none")
    return files, np.asarray(times, np.float64), notes


def encode_source(source, encoder, hz, out_dir):
    """Encode one source into out_dir. Returns (n, seconds) or None when it was already done."""
    npz, side = out_dir / f"{source.id.replace(':', '-')}.npz", out_dir / f"{source.id.replace(':', '-')}.json"
    if npz.exists() and side.exists():
        # The pixels are done, but provenance keeps gaining fields and a regime can be corrected:
        # rewrite the sidecar from what the corpus says NOW, without decoding anything.
        with np.load(npz) as z:
            side.write_text(json.dumps(sidecar(source, encoder.name, encoder.dim, hz, z["emb"], z["t"]), indent=1))
        return None
    started = time.perf_counter()
    chunks = []
    if source.is_video:
        decoded = Decoded(source.path, source.creator, hz, source.fps, batch=encoder.batch)
        for batch in decoded:
            chunks.append(encoder(batch))
        times = decoded.check()
    else:
        files, times, _ = run_frames(source)
        # A run's frames are either its saved jpgs or, on newer runs, a proxy video with one frame
        # per logged frame. Either way the clock is frames.jsonl's, never the media's.
        decoded = (DecodedProxy(source.proxy, source.creator, len(files), batch=encoder.batch)
                   if source.proxy and source.proxy.exists()
                   else DecodedJpegs(source.path, files, source.creator, batch=encoder.batch))
        for batch in decoded:
            chunks.append(encoder(batch))
        decoded.check()
        keep = thin(times, hz)                   # a run saves at its own rate; take it down to ours
        chunks, times = [np.concatenate(chunks)[keep]], times[keep]
    emb = np.concatenate(chunks) if chunks else np.zeros((0, encoder.dim), np.float16)
    if len(emb) != len(times):
        raise ValueError(f"{source.id}: {len(emb)} embeddings against {len(times)} timestamps")
    tmp_npz, tmp_side = npz.with_name(npz.name + ".tmp"), side.with_name(side.name + ".tmp")
    with tmp_npz.open("wb") as fh:                # a file object, so savez cannot append its own suffix
        np.savez(fh, emb=emb, t=times)
    tmp_side.write_text(json.dumps(sidecar(source, encoder.name, encoder.dim, hz, emb, times), indent=1))
    tmp_npz.rename(npz)                           # both files land only when both are complete
    tmp_side.rename(side)
    return len(emb), time.perf_counter() - started


def sidecar(source, encoder_name, dim, hz, emb, times):
    """Everything about a cached source except its vectors: provenance, regime, patch, masks."""
    return {
        "id": source.id, "kind": source.kind, "creator": source.creator, "group": source.group,
        "cooldowns": source.cooldowns, "cooldowns_evidence": source.cooldowns_evidence,
        "patch": source.patch, "patch_evidence": source.patch_evidence, "recorder": source.recorder,
        "media": str(source.path.relative_to(ROOT)), "source_fps": source.fps,
        "upload_date": source.upload_date, "edited_upload": source.edited, "splittable": source.splittable,
        "encoder": encoder_name, "dim": dim, "norm": NORM, "size": SIZE, "hz": hz,
        "masks": [list(r) for r in rects(source.creator)], "visible_fraction": round(visible_fraction(source.creator), 4),
        "frames": len(emb), "t_first": float(times[0]) if len(times) else None,
        "t_last": float(times[-1]) if len(times) else None,
        # Which clock `t` is on, and where it starts. A video's rows carry ABSOLUTE decoded PTS,
        # whose origin is not 0 (one DayMR section starts at 1.616 s), while agent/demos.py speaks
        # clip time from the first frame. Whoever reads the cache converts with this, once.
        "clock": "media_pts" if source.is_video else "recorder",
        "t_origin": float(times[0]) if (source.is_video and len(times)) else 0.0,
        "sidecar_version": SIDECAR_VERSION,
        "written": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def refresh(encoder_name=DEFAULT, hz=HZ, data=corpus_mod.DATA):
    """Rewrite every cached sidecar from current provenance, without decoding a frame.

    Provenance keeps gaining fields (the regime, then the patch, then splittable) while the vectors
    are unchanged; re-encoding the corpus to add a key would cost fifteen minutes for nothing.
    """
    out_dir = cache_dir(_Tag(encoder_name), hz)
    by_id = {s.id: s for s in corpus_mod.corpus(data)}
    n = 0
    for side in sorted(out_dir.glob("*.json")):
        old = json.loads(side.read_text())
        source = by_id.get(old["id"])
        if source is None:
            print(f"{old['id']:<34} cached but no longer in the corpus: left alone")
            continue
        with np.load(side.with_suffix(".npz")) as z:
            fresh = sidecar(source, old["encoder"], old["dim"], old["hz"], z["emb"], z["t"])
        side.write_text(json.dumps(fresh, indent=1))
        n += 1
    print(f"{n} sidecars rewritten in {out_dir}")
    return out_dir


class _Tag:
    """cache_dir wants an Encoder; only its tag is read, and loading weights to rewrite JSON is waste."""

    def __init__(self, name):
        self.tag = name.replace(".", "-")


def fill(encoder, hz=HZ, kinds=None, data=corpus_mod.DATA):
    out_dir = cache_dir(encoder, hz)
    out_dir.mkdir(parents=True, exist_ok=True)
    for source in corpus_mod.corpus(data, kinds):
        done = encode_source(source, encoder, hz, out_dir)
        if done is None:
            print(f"{source.id:<34} cached", flush=True)
        else:
            n, seconds = done
            print(f"{source.id:<34} {n:6} frames in {seconds:6.1f}s "
                  f"({n/max(seconds, 1e-9):6.1f}/s, cooldowns={source.cooldowns})", flush=True)
    return out_dir


def load(out_dir, want=None):
    """Every cached source in out_dir as (sidecar dict, emb, t), optionally filtered by a predicate."""
    for side in sorted(Path(out_dir).glob("*.json")):
        meta = json.loads(side.read_text())
        if want and not want(meta):
            continue
        with np.load(side.with_suffix(".npz")) as z:
            yield meta, z["emb"], z["t"]


# --- the measurements the encoder choice rests on --------------------------------------

def bench(hz=HZ):
    """Decode throughput on a real VOD, and each candidate's forward throughput and latency."""
    source = next(s for s in corpus_mod.corpus(kinds=("vod",)))
    for batch_size in (64,):
        decoded = Decoded(source.path, source.creator, hz, source.fps, batch=batch_size)
        started, frames = time.perf_counter(), 0
        for batch in decoded:
            frames += len(batch)
            if frames >= 600:
                break
        seconds = time.perf_counter() - started
        print(f"decode+mask {source.path.name} @ {hz:g} Hz: {frames} frames in {seconds:.2f}s "
              f"= {frames/seconds:.0f}/s, {frames/seconds/hz:.0f}x realtime")
    for name in CANDIDATES:
        encoder = Encoder(name)
        for n in (1, 64):
            x = np.random.randint(0, 255, (n, SIZE, SIZE, 3), dtype=np.uint8)
            encoder(x)
            started = time.perf_counter()
            for _ in range(10):
                encoder(x)
            seconds = (time.perf_counter() - started) / 10
            print(f"encode {name:<30} batch {n:>3}: {n/seconds:8.1f} img/s, {seconds*1000:6.1f} ms/call, dim {encoder.dim}")


def probe(hz=HZ, data=corpus_mod.DATA):
    """Which candidate's features carry the intent our own runs are labelled with.

    A ridge probe on ONE frame's embedding, reported two ways, because they answer different
    questions and only one of them is a policy claim:

      session   trained on the other sessions, tested on this one. This is the honest split
                (the lane never splits within a recording) and it is what step 2 must beat.
      tail      trained on the first 70% of a session, tested on its last 30%. Neighbouring
                frames are near duplicates, so this is optimistic and is NOT evidence of
                generalization: it is a like-for-like comparison of the four encoders.

    Single-frame and frozen on purpose: it measures the features, not the temporal head, and
    it is the cheapest tie-break available when every candidate is far faster than the data.
    """
    labels = {}
    for source in corpus_mod.corpus(data, kinds=("run",)):
        _, times, notes = run_frames(source)
        keep = thin(times, hz)
        labels[source.id] = np.array([notes[i].split(":")[0] for i in keep])
    for name in CANDIDATES:
        encoder = Encoder(name)
        out_dir = fill(encoder, hz, kinds=("run",), data=data)
        sessions = {m["id"]: e.astype(np.float32) for m, e, _ in load(out_dir, lambda m: m["kind"] == "run")}
        by_session = [_score(np.concatenate([sessions[s] for s in sessions if s != held]),
                             np.concatenate([labels[s] for s in sessions if s != held]),
                             sessions[held], labels[held], held.split(":")[-1]) for held in sorted(sessions)]
        by_tail = []
        for s in sorted(sessions):
            cut = int(len(sessions[s]) * 0.7)
            by_tail.append(_score(sessions[s][:cut], labels[s][:cut], sessions[s][cut:], labels[s][cut:], s.split(":")[-1]))
        print(f"{name:<30} session  " + "  ".join(by_session), flush=True)
        print(f"{'':<30} tail     " + "  ".join(by_tail), flush=True)


def _score(x, y, xt, yt, tag):
    """Ridge probe accuracy against the held-out majority class."""
    classes = sorted(set(y) | set(yt))
    onehot = np.stack([(y == c).astype(np.float32) for c in classes], 1)
    x1 = np.concatenate([x, np.ones((len(x), 1), np.float32)], 1)
    w = np.linalg.solve(x1.T @ x1 + 1e2 * np.eye(x1.shape[1], dtype=np.float32), x1.T @ onehot)
    xt1 = np.concatenate([xt, np.ones((len(xt), 1), np.float32)], 1)
    pred = np.array(classes)[(xt1 @ w).argmax(1)]
    return f"{tag} {(pred == yt).mean():.2f} (maj {max((yt == c).mean() for c in classes):.2f})"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="fill the cache for every source on this machine")
    ap.add_argument("--kinds", help="only these source kinds, comma separated: run,sample,vod,guide")
    ap.add_argument("--bench", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--list", action="store_true", help="what is cached already")
    ap.add_argument("--refresh", action="store_true", help="rewrite every sidecar from current provenance; decodes nothing")
    ap.add_argument("--encoder", default=DEFAULT)
    ap.add_argument("--hz", type=float, default=HZ)
    a = ap.parse_args(argv)

    os.nice(10)   # the game is not running here, but a full corpus pass should not own the machine
    if a.bench:
        return bench(a.hz)
    if a.probe:
        return probe(a.hz)
    if a.refresh:
        refresh(a.encoder, a.hz)
        return 0
    if a.list:
        for side in sorted(CACHE.glob("*/*.json")):
            m = json.loads(side.read_text())
            print(f"{side.parent.name:<34} {m['id']:<34} {m['frames']:>6} x {m['dim']:<4} cooldowns={m['cooldowns']}")
        return 0
    if a.all:
        out = fill(Encoder(a.encoder), a.hz, tuple(a.kinds.split(",")) if a.kinds else None)
        print(f"cache: {out}")
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
