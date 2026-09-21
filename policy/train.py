"""Step 2: a temporal head over cached embeddings, and the first held-out number.

The head reads about 5 s of history at 10 Hz and names the intent the recorder logged next.
Trained first on the one label source that is exact today — our own range runs, where every
tick carries the scripted brain's intent. **Distilling the scripted brain teaches nothing
new.** Its purpose is to prove the path end to end (loader, no future leakage, whole-session
splits, class imbalance, metrics) and to produce a number against a majority baseline.

  uv run --group policy python -m policy.train                 # leave-one-session-out, regime off
  uv run --group policy python -m policy.train --regime normal
  uv run --group policy pytest tests/test_policy.py

Windows come from `agent/demos.py`: it owns segments, whole-recording splits and the leakage
guards, and an `Observation` refuses to hold anything later than its own `t`. This module adds
no schema — it resolves each `FrameRef` against the embedding cache by (clip, decoded time).

Three input channels per timestep, each with its own present bit, **missing never filled**:

  embedding   384 from the frozen encoder; absent when a frame has no cache row
  state       the loop's own `State` where the row carried one: hp, ammo, ability readiness,
              detections, crosshair. Every unknown reads as a zero **with its known-bit clear**,
              never as a value. L4's trial runs carry no `State`, so the channel is absent there
  events      the HUD event stream where a run has one. No run has one today, so this channel
              is absent on every window; it is wired so it fills the day one does

`cooldowns` regime is picked before any window is cut, and the two regimes are never mixed.
The loader reads a run's regime from its `meta.json`, which our recorders do not write yet, so
the sources are selected by `policy.corpus` (which holds the lead's statement) and the loader is
then told `mix_regimes=True` — the selection above has already pinned one regime, and a test
pins that the selection is what does it.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np

from agent.demos import Demos
from . import corpus as corpus_mod
from .encode import DEFAULT, HZ, cache_dir, load
from .frames import NORM

HISTORY_S = 5.0
FRAME_HZ = 10.0          # the cache's rate: one embedding per step
DECISION_HZ = 5.0        # windows per second of recording
MATCH_S = 0.06           # a FrameRef resolves to a cache row within this many seconds
STATE_F, EVENT_F = 13, 4
EVENT_KINDS = ("hp_lost", "web_cluster_fired", "slot_unavailable", "slot_available")
ROOT = Path(__file__).resolve().parent.parent


def vocab_of(note):
    """The recorders' notes brought to one vocabulary: 'engage:enemy' and 'Engage' are both engage.

    `stand` (L4's trials) and `idle` (the loop) are kept apart on purpose: one is a scripted pause,
    the other is the loop standing the controller down. Merging them would invent an equivalence.
    """
    return (note or "none").split(":")[0].strip().lower()


def _state_features(state):
    """The compact State summary. Every unknown is a zero whose known-bit is clear, never a value."""
    out = np.zeros(STATE_F, np.float32)
    if not state:
        return out, False
    hp, max_hp = state.get("hp"), state.get("max_hp")
    if hp is not None and max_hp:
        out[0], out[1] = hp / max_hp, 1.0
    if state.get("webs") is not None:
        out[2], out[3] = state["webs"] / 5.0, 1.0
    for slot, at in (("swing", 4), ("pull", 6), ("uppercut", 8)):
        ability = (state.get("abilities") or {}).get(slot)
        if ability:
            ready = ability.get("ready")
            if ready is None and ability.get("charges") is not None:
                ready = ability["charges"] > 0
            if ready is not None:
                out[at], out[at + 1] = float(ready), 1.0
    dets = state.get("detections")
    if dets is not None:
        out[10] = min(len(dets), 5) / 5.0
    if state.get("on_target") is not None:
        out[11], out[12] = float(state["on_target"]), 1.0
    return out, True


def _event_features(events, t):
    """Counts of the kinds confirmed in the last second. Absent when the clip has no event stream."""
    out = np.zeros(EVENT_F, np.float32)
    if events is None:
        return out, False
    for e in events:
        if e.t_to > t - 1.0 and e.kind in EVENT_KINDS:
            out[EVENT_KINDS.index(e.kind)] += 1.0
    return out, True


class Cache:
    """The embedding cache as (clip, time) -> vector, plus the dim every window is built at."""

    def __init__(self, out_dir):
        self.by_clip, self.dim = {}, None
        for meta, emb, t in load(out_dir):
            self.by_clip[meta["id"]] = (np.asarray(t), emb.astype(np.float32))
            self.dim = meta["dim"]
        if self.dim is None:
            raise FileNotFoundError(f"{out_dir}: nothing cached; run policy.encode --all first")

    def at(self, clip, t):
        """The embedding for a frame, or None when the cache does not hold that frame."""
        found = self.by_clip.get(clip)
        if found is None:
            return None
        times, emb = found
        i = int(np.argmin(np.abs(times - t)))
        return emb[i] if abs(times[i] - t) <= MATCH_S else None


def windows(regime="off", encoder=DEFAULT, hz=HZ, decision_hz=DECISION_HZ, data=corpus_mod.DATA):
    """(X [n, T, F], y [n], sessions [n], classes) for one regime, split-ready by session.

    Sources are picked by regime here, before any window is cut, so no window can mix regimes.
    """
    # `splittable` keeps a source out of every split until something establishes it is not a
    # duplicate of another: the full YouTube uploads may overlap the retained Twitch sections.
    sources = [s for s in corpus_mod.corpus(data, kinds=("run",)) if s.cooldowns == regime and s.splittable]
    if not sources:
        raise ValueError(f"no splittable run is recorded as cooldowns={regime!r}")
    cache = Cache(cache_dir(_Tag(encoder), hz))
    demos = Demos.load(*[str(s.path) for s in sources])
    steps = int(round(HISTORY_S * FRAME_HZ)) + 1
    width = cache.dim + 1 + STATE_F + 1 + EVENT_F + 1
    rows, labels, sessions = [], [], []
    # Every split, because the fold is leave-one-session-out below: the loader's own train/val/test
    # assignment would throw away sessions we have too few of to spare.
    for split in sorted(set(demos.splits.values())):
        for sample in demos.samples(split, history_s=HISTORY_S, frame_hz=FRAME_HZ, hz=decision_hz,
                                    label_s=0.5, mix_regimes=True):   # regime already pinned by `sources`
            note = next((i.note for label in sample.labels for i in (label.inputs or ()) if i.note), None)
            if note is None:
                continue
            obs = sample.observation
            block = np.zeros((steps, width), np.float32)
            for k, frame in enumerate(obs.frames[-steps:]):
                at = steps - min(len(obs.frames), steps) + k
                vec = cache.at(obs.clip, frame.t)
                if vec is not None and not frame.masked:
                    block[at, :cache.dim], block[at, cache.dim] = vec, 1.0
                state = next((i.extra.get("state") for i in (obs.inputs or ()) if abs(i.t - frame.t) <= MATCH_S
                              and i.extra.get("state")), None)
                s_feat, s_ok = _state_features(state)
                o = cache.dim + 1
                block[at, o:o + STATE_F], block[at, o + STATE_F] = s_feat, float(s_ok)
                e_feat, e_ok = _event_features(obs.events, frame.t)
                o += STATE_F + 1
                block[at, o:o + EVENT_F], block[at, o + EVENT_F] = e_feat, float(e_ok)
            rows.append(block)
            labels.append(vocab_of(note))
            sessions.append(obs.clip)
    classes = sorted(set(labels))
    y = np.array([classes.index(v) for v in labels], np.int32)
    return np.stack(rows), y, np.array(sessions), classes


class _Tag:
    """cache_dir wants an Encoder; only its tag is read, and loading MLX weights here is waste."""

    def __init__(self, name):
        self.tag = name.replace(".", "-")


class Head(nn.Module):
    """A small causal sequence model: project, two GRU layers, classify from the last step."""

    def __init__(self, width, classes, d=128):
        super().__init__()
        self.proj = nn.Linear(width, d)
        self.gru1, self.gru2 = nn.GRU(d, d), nn.GRU(d, d)
        self.out = nn.Linear(d, classes)

    def __call__(self, x):
        h = nn.relu(self.proj(x))
        h = self.gru2(nn.tanh(self.gru1(h)))
        return self.out(h[:, -1])


def fit(xtr, ytr, xte, n_classes, epochs=40, batch=64, lr=1e-3, seed=0):
    """Train with a class-weighted loss (rare intents must not be swamped); predict xte and xtr.

    The training-set prediction is the diagnostic that tells a thin dataset apart from a broken
    pipeline: a head that cannot even fit what it was shown has a wiring fault, while one that
    fits and then fails held out is being asked to generalize from too little.
    """
    mx.random.seed(seed)
    model = Head(xtr.shape[-1], n_classes)
    counts = np.bincount(ytr, minlength=n_classes).astype(np.float32)
    weights = mx.array(np.where(counts > 0, len(ytr) / (n_classes * np.maximum(counts, 1)), 0.0))
    opt = optim.Adam(learning_rate=lr)

    def loss_fn(m, xb, yb):
        logits = m(xb)
        return (nn.losses.cross_entropy(logits, yb, reduction="none") * weights[yb]).mean()

    step = nn.value_and_grad(model, loss_fn)
    order = np.arange(len(xtr))
    for epoch in range(epochs):
        np.random.default_rng(seed + epoch).shuffle(order)
        for start in range(0, len(order), batch):
            idx = order[start:start + batch]
            loss, grads = step(model, mx.array(xtr[idx]), mx.array(ytr[idx]))
            opt.update(model, grads)
            mx.eval(model.parameters(), opt.state)
    model.eval()

    def predict(x):
        out = []
        for start in range(0, len(x), 256):
            logits = model(mx.array(x[start:start + 256]))
            mx.eval(logits)
            out.append(np.asarray(logits).argmax(1))
        return np.concatenate(out) if out else np.zeros(0, np.int64)

    return predict(xte), predict(xtr)


def folds(sessions, y, mode):
    """(name, train mask, test mask) per fold.

    `session` is the honest split the lane always uses: whole recordings, never frames. `tail`
    trains on the first 70% of every session and tests on the last 30% of each — neighbouring
    windows overlap by design, so it is NOT a generalization claim. It is the control that says
    whether the features and labels carry any signal at all, which a failing session split alone
    cannot tell apart from a broken pipeline.
    """
    if mode == "session":
        for held in sorted(set(sessions)):
            yield held, sessions != held, sessions == held
        return
    train = np.zeros(len(y), bool)
    for name in sorted(set(sessions)):
        where = np.flatnonzero(sessions == name)
        train[where[: int(len(where) * 0.7)]] = True
    for name in sorted(set(sessions)):
        yield name, train, (~train) & (sessions == name)


def leave_one_session_out(regime="off", mode="session", **kw):
    x, y, sessions, classes = windows(regime=regime, **kw)
    print(f"regime {regime}: {len(x)} windows, {x.shape[1]} steps x {x.shape[2]} features, "
          f"{len(set(sessions))} sessions, classes {classes}, split by {mode}")
    print(f"  {'session':<16}" + "".join(f"{c:>9}" for c in classes))
    for name in sorted(set(sessions)):
        counts = np.bincount(y[sessions == name], minlength=len(classes))
        print(f"  {name:<16}" + "".join(f"{n:>9}" for n in counts))
    report = {}
    for held, tr, te in folds(sessions, y, mode):
        if not tr.any() or not te.any():
            continue
        pred, pred_tr = fit(x[tr], y[tr], x[te], len(classes))
        truth, fit_acc = y[te], float((pred_tr == y[tr]).mean())
        majority = np.bincount(y[tr], minlength=len(classes)).argmax()
        acc, base = float((pred == truth).mean()), float((truth == majority).mean())
        seen = float(max(np.bincount(truth, minlength=len(classes))) / len(truth))
        report[held] = {"windows": int(te.sum()), "accuracy": round(acc, 3), "train_fit": round(fit_acc, 3),
                        "train_majority_baseline": round(base, 3), "held_out_majority": round(seen, 3),
                        "macro_f1": round(_macro_f1(truth, pred, len(classes)), 3),
                        "confusion": _confusion(truth, pred, classes)}
        print(f"\nheld out {held}: {int(te.sum())} windows  accuracy {acc:.3f}  "
              f"(train-majority {base:.3f}, held-out majority {seen:.3f})  macro F1 {report[held]['macro_f1']:.3f}  "
              f"[fits its own training set {fit_acc:.3f}]")
        _print_confusion(truth, pred, classes)
    return report, classes


def _macro_f1(truth, pred, n):
    scores = []
    for c in range(n):
        tp = int(((pred == c) & (truth == c)).sum())
        fp, fn = int(((pred == c) & (truth != c)).sum()), int(((pred != c) & (truth == c)).sum())
        if tp + fn:
            scores.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0)
    return float(np.mean(scores)) if scores else 0.0


def _confusion(truth, pred, classes):
    return {classes[t]: {classes[p]: int(((truth == t) & (pred == p)).sum()) for p in range(len(classes))}
            for t in range(len(classes))}


def _print_confusion(truth, pred, classes):
    print("    truth \\ pred  " + "".join(f"{c:>9}" for c in classes))
    for t, name in enumerate(classes):
        if (truth == t).any():
            print(f"    {name:<13} " + "".join(f"{int(((truth == t) & (pred == p)).sum()):>9}" for p in range(len(classes))))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regime", default="off", choices=("off", "normal", "unknown"))
    ap.add_argument("--encoder", default=DEFAULT)
    ap.add_argument("--hz", type=float, default=HZ)
    ap.add_argument("--decision-hz", type=float, default=DECISION_HZ)
    ap.add_argument("--split", default="session", choices=("session", "tail"),
                    help="session: the honest whole-recording split. tail: the control (see folds())")
    ap.add_argument("--out", help="write the report as JSON here")
    a = ap.parse_args(argv)
    started = time.perf_counter()
    report, classes = leave_one_session_out(a.regime, a.split, encoder=a.encoder, hz=a.hz, decision_hz=a.decision_hz)
    if a.out:
        Path(a.out).write_text(json.dumps({"regime": a.regime, "split": a.split, "encoder": a.encoder,
                                           "norm": NORM, "classes": classes, "folds": report}, indent=1))
    print(f"\n{time.perf_counter() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
