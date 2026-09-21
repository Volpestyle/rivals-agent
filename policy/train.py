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

Three input channels per timestep, **missing never filled**:

  embedding   384 from the frozen encoder, with TWO bits: `present` (a cache row was found at or
              before this step) and `scene_masked` (the segmenter proved something hides the scene
              here, such as a scoreboard). A frame that is neither is a cache MISS, which fails the
              run rather than passing as blank video
  state       the loop's own `State` where the row carried one: hp, ammo, ability readiness,
              detections, crosshair. Every unknown reads as a zero **with its known-bit clear**,
              never as a value. L4's trial runs carry no `State`, so the channel is absent there
  events      the HUD event stream where a run has one, counted over (t - 1 s, t] at each step.
              The loader validates current format-4 streams. This range-intent trainer can count
              their past events; frames-only B0 passes events=None and uses only columns 0-385.
              Event-input prefix causality is unproven, so B0 uses events only for targets and
              explicitly separate offline diagnostic baselines.

Clocks, regimes, splits and patches are each pinned by one authority:

  clock    the cache records whether its `t` is media PTS or the recorder's, and where it starts;
           lookups convert once and take the latest frame AT OR BEFORE the step, never the nearest
  regime   the run's own metadata. `corpus.RUNS` is a legacy fallback for inventory, and a run it
           cannot qualify is excluded from training by name. The loader's own guard stays on
  split    an allow-list (`TRAINABLE`), so `inspection_only` can never yield a training row
  patch    a balance patch is a regime of its own; two of them raise unless asked to mix
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
MATCH_S = 0.12           # how stale the at-or-before row may be: one 10 Hz step (0.1 s) plus 20 ms of PTS jitter
STATE_F, EVENT_F = 13, 4
EVENT_KINDS = ("hp_lost", "web_cluster_fired", "slot_unavailable", "slot_available")
ROOT = Path(__file__).resolve().parent.parent


TRAINABLE = ("train", "val", "test")   # allow-list: inspection_only and anything new never train


def layout(emb_dim):
    """Where each channel sits in one step's feature vector. **The only place this is written.**

    policy/live.py builds windows for the runtime and must agree exactly; deriving the offsets
    twice is how the live path silently fed the head a vector one column out of step.
    """
    state = emb_dim + 2                       # after the embedding, its present bit and scene-masked bit
    events = state + STATE_F + 1
    return {"emb": 0, "emb_present": emb_dim, "scene_masked": emb_dim + 1,
            "state": state, "state_present": state + STATE_F,
            "events": events, "events_present": events + EVENT_F,
            "width": events + EVENT_F + 1}


def emb_dim_of(width):
    """The embedding dimension a window of this width was built with."""
    return width - (2 + STATE_F + 1 + EVENT_F + 1)


# What each field a Mask can hide owns in the state channel (value and known-bit columns), per
# agent/demos.py's Mask: "hud" (all of it), "scene", "player", or one HUD field ("hp", "ammo", a
# slot). A hidden field is zeroed WITH its known-bit, so the head reads "not available", never a value.
STATE_COLS = {"hp": (0, 1), "ammo": (2, 3), "swing": (4, 5), "get_over_here": (6, 7), "pull": (6, 7),
              "uppercut": (8, 9)}
HUD_FIELDS = ("hp", "ammo", "swing", "get_over_here", "uppercut")
SCENE_DERIVED = (10, 11, 12)   # detection count and crosshair-on-target come from the scene's pixels


def step_row(emb_dim, vec, mask, state, events, t):
    """One timestep's features, masking exactly what `mask.hidden` says and nothing more.

    `vec` is the cache lookup (None: the cache has no row here); `mask` is the loader's Mask or None.
      scene            the embedding is dropped and `scene_masked` is set; scene-derived state too
      hud              every HUD field's state columns are dropped; the scene is left alone
      hp, ammo, slot   only that field's columns are dropped
      player           nothing here is player-specific, so nothing more is dropped
    Returns (row, has_embedding, scene_hidden). A step with neither an embedding nor a hidden scene
    is a cache MISS, which the caller must not let pass as blank video.
    """
    at = layout(emb_dim)
    row = np.zeros(at["width"], np.float32)
    hidden = set(mask.hidden) if mask else set()
    if "hud" in hidden:
        hidden |= set(HUD_FIELDS)
    scene_hidden = "scene" in hidden
    if scene_hidden:
        row[at["scene_masked"]] = 1.0
    elif vec is not None:
        row[:emb_dim], row[at["emb_present"]] = vec, 1.0
    s_feat, s_ok = _state_features(state)
    for field in hidden:
        s_feat[list(STATE_COLS.get(field, ()))] = 0.0
    if scene_hidden:
        s_feat[list(SCENE_DERIVED)] = 0.0
    row[at["state"]:at["state"] + STATE_F], row[at["state_present"]] = s_feat, float(s_ok)
    e_feat, e_ok = _event_features(events, t)
    row[at["events"]:at["events"] + EVENT_F], row[at["events_present"]] = e_feat, float(e_ok)
    return row, (vec is not None and not scene_hidden), scene_hidden


class CacheMiss(ValueError):
    """A source has no embeddings, or none that line up with the loader's clock."""


class PatchError(ValueError):
    """Training would mix balance patches and the caller did not ask for that."""


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


def _event_features(events, t, window_s=1.0):
    """Counts of the kinds confirmed in (t - window_s, t], for the step at time `t`.

    Bounded at BOTH ends. Without the upper bound an early step in a window counts events that were
    only confirmed seconds later, which is future knowledge at that step even though the window as a
    whole respects the decision time. Absent when the clip has no event stream.
    """
    out = np.zeros(EVENT_F, np.float32)
    if events is None:
        return out, False
    for e in events:
        if t - window_s < e.t_to <= t and e.kind in EVENT_KINDS:
            out[EVENT_KINDS.index(e.kind)] += 1.0
    return out, True


class Cache:
    """The embedding cache as (clip, clip time) -> vector, on ONE clock.

    A video's rows carry absolute decoded PTS, whose origin need not be 0 (one DayMR section starts
    at 1.616 s), while `agent/demos.py` speaks clip time measured from the first frame. The sidecar
    records which clock it is on and where it starts, and every lookup converts with that, so a
    source with an offset origin cannot silently miss on every frame.
    """

    def __init__(self, out_dir, *, ids):
        self.by_clip, self.dim = {}, None
        ids = frozenset(ids)
        for meta, emb, t in load(out_dir, want=lambda m: m["id"] in ids):
            self.by_clip[meta["id"]] = (np.asarray(t) - float(meta.get("t_origin") or 0.0), emb.astype(np.float32))
            self.dim = meta["dim"]
        if self.dim is None:
            # The same failure as one missing run, and the same type: training has nothing to read.
            raise CacheMiss(f"{out_dir}: nothing cached; run policy.encode --all first")

    def has(self, clip):
        return clip in self.by_clip

    def index_at(self, clip, t, tolerance=MATCH_S):
        """The row of the latest frame AT OR BEFORE clip time `t`, else None.

        Never the nearest: the nearest frame to a decision can be after it, which would put a
        future frame inside the observation. `tolerance` bounds how stale an at-or-before frame
        may be before the cache is treated as not holding that moment, so a time past the end of
        the clip, or before its first frame, misses.
        """
        found = self.by_clip.get(clip)
        if found is None:
            return None
        times = found[0]
        i = int(np.searchsorted(times, t + 1e-9, side="right")) - 1
        if i < 0 or t - times[i] > tolerance:
            return None
        return i

    def at(self, clip, t, tolerance=MATCH_S):
        """The embedding at `index_at`, else None."""
        i = self.index_at(clip, t, tolerance)
        return None if i is None else self.by_clip[clip][1][i]


def windows(regime="off", encoder=DEFAULT, hz=HZ, decision_hz=DECISION_HZ, data=corpus_mod.DATA, recorder="loop",
            patch=None, mix_patches=False):
    """(X [n, T, F], y [n], sessions [n], prev [n], classes) for one regime, split-ready by session.

    Sources are picked by regime here, before any window is cut, so no window can mix regimes, and
    by `recorder`: the default is the live loop's runs alone, because L4's trial logs are a
    different recorder with a four-symbol vocabulary of their own. `prev` is the intent already in
    force at the decision (the last note at or before t), which is the sticky baseline's guess.
    """
    # `splittable` keeps a source out of every split until something establishes it is not a
    # duplicate of another: the full YouTube uploads may overlap the retained Twitch sections.
    sources = [s for s in corpus_mod.corpus(data, kinds=("run",))
               if s.cooldowns == regime and s.splittable and (recorder is None or s.recorder == recorder)]
    if patch is not None:
        sources = [s for s in sources if s.patch == patch]
    if not sources:
        raise ValueError(f"no splittable {recorder or 'any'}-recorder run is recorded as cooldowns={regime!r}"
                         + (f" on patch {patch!r}" if patch else ""))
    # Balance patches change cooldowns, damage and mechanics, so a patch is a regime of its own
    # (VUH-1324). Training across two of them silently would learn the average of two games.
    seen = sorted({s.patch for s in sources})
    if len(seen) > 1 and not mix_patches:
        raise PatchError(f"these runs span balance patches {seen}: pass patch=<one of them> to pick, or "
                         f"mix_patches=True to train across them on purpose")
    # Training takes only runs whose OWN metadata states the regime. The legacy name table is a
    # documented fallback for inventory, never a reason to feed a model a run nobody labelled.
    unstated = [s.id for s in sources if s.cooldowns_source != "metadata"]
    if unstated:
        print(f"excluded, regime not stated by the run itself: {', '.join(unstated)}", flush=True)
        sources = [s for s in sources if s.cooldowns_source == "metadata"]
    if not sources:
        raise ValueError(f"no run states cooldowns={regime!r} in its own metadata "
                         f"(the corpus.RUNS fallback does not qualify a run for training)")

    cache = Cache(cache_dir(_Tag(encoder), hz), ids={s.id for s in sources})
    # A source with no cached embeddings would contribute windows of blank video that look exactly
    # like a fully masked scene. Refuse the run and name it, rather than train on nothing.
    missing = [s.id for s in sources if not cache.has(s.id)]
    if missing:
        raise CacheMiss(f"not in the embedding cache: {', '.join(missing)}. Run "
                        f"`python -m policy.encode --all --kinds run` first, or drop those runs.")

    demos = Demos.load(*[str(s.path) for s in sources])
    steps = int(round(HISTORY_S * FRAME_HZ)) + 1
    width = layout(cache.dim)["width"]
    rows, labels, sessions, at_t = [], [], [], []
    blank = 0
    for split in TRAINABLE:                  # an allow-list: inspection_only never yields a row
        if split not in set(demos.splits.values()):
            continue
        for sample in demos.samples(split, history_s=HISTORY_S, frame_hz=FRAME_HZ, hz=decision_hz,
                                    label_s=0.5, cooldowns=regime):   # the loader's own regime guard, on
            note = next((i.note for label in sample.labels for i in (label.inputs or ()) if i.note), None)
            if note is None:
                continue
            obs = sample.observation
            block = np.zeros((steps, width), np.float32)
            accounted = 0      # steps that hold an embedding, or whose scene a mask proves hidden
            for k, frame in enumerate(obs.frames[-steps:]):
                at = steps - min(len(obs.frames), steps) + k
                state = next((i.extra.get("state") for i in (obs.inputs or ()) if abs(i.t - frame.t) <= MATCH_S
                              and i.extra.get("state")), None)
                block[at], has_emb, scene_hidden = step_row(cache.dim, cache.at(obs.clip, frame.t),
                                                            frame.masked, state, obs.events, frame.t)
                accounted += has_emb or scene_hidden
            blank += not accounted
            rows.append(block)
            labels.append(vocab_of(note))
            sessions.append(obs.clip)
            at_t.append(obs.t)
    if not rows:
        raise CacheMiss(f"no window survived: {len(sources)} source(s), splits {TRAINABLE}")
    if blank:
        raise CacheMiss(f"{blank} of {len(rows)} windows hold no embedding at all (every frame a cache miss, "
                        "not a mask): the cache and the loader disagree about this source's clock")
    classes = sorted(set(labels))
    y = np.array([classes.index(v) for v in labels], np.int32)
    sessions, at_t = np.array(sessions), np.array(at_t)
    # The sticky guess is the label of the PREVIOUS DECISION in the same session, not the intent a
    # control tick earlier: consecutive rows of frames.jsonl are ~33 ms apart and agree by
    # construction, which would make the baseline 0.99 and measure nothing. The first decision of a
    # session has no predecessor and is marked -1, which never equals a class.
    prev = np.full(len(y), -1, np.int32)
    for name in set(sessions.tolist()):
        where = np.flatnonzero(sessions == name)
        where = where[np.argsort(at_t[where])]
        prev[where[1:]] = y[where[:-1]]
    return np.stack(rows), y, sessions, prev, classes


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


def _fit_model(xtr, ytr, n_classes, epochs=40, batch=64, lr=1e-3, seed=0, extra=None):
    """Train and return the model itself (what `save` keeps); `fit` wraps this to predict."""
    mx.random.seed(seed)
    model = Head(xtr.shape[-1], n_classes)
    counts = np.bincount(ytr, minlength=n_classes).astype(np.float32)
    weights = np.where(counts > 0, len(ytr) / (n_classes * np.maximum(counts, 1)), 0.0).astype(np.float32)
    # `extra` multiplies the per-window weight (the transition curriculum); ones by default.
    per_window = mx.array(weights[ytr] * (np.ones(len(ytr), np.float32) if extra is None else extra))
    opt = optim.Adam(learning_rate=lr)

    def loss_fn(m, xb, yb, wb):
        logits = m(xb)
        return (nn.losses.cross_entropy(logits, yb, reduction="none") * wb).mean()

    step = nn.value_and_grad(model, loss_fn)
    order = np.arange(len(xtr))
    for epoch in range(epochs):
        np.random.default_rng(seed + epoch).shuffle(order)
        for start in range(0, len(order), batch):
            idx = order[start:start + batch]
            loss, grads = step(model, mx.array(xtr[idx]), mx.array(ytr[idx]), per_window[mx.array(idx)])
            opt.update(model, grads)
            mx.eval(model.parameters(), opt.state)
    model.eval()
    return model


def fit(xtr, ytr, xte, n_classes, epochs=40, batch=64, lr=1e-3, seed=0, extra=None):
    """Train with a class-weighted loss (rare intents must not be swamped); predict xte and xtr.

    The training-set prediction is the diagnostic that tells a thin dataset apart from a broken
    pipeline: a head that cannot even fit what it was shown has a wiring fault, while one that
    fits and then fails held out is being asked to generalize from too little.
    """
    model = _fit_model(xtr, ytr, n_classes, epochs, batch, lr, seed, extra)

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


def save(path, regime="off", **kw):
    """Train on every window of one regime (no holdout) and write the head for step 3.

    The sidecar records what the head was trained on and the exact feature layout, because a head
    fed a window built any other way is not the head that was measured.
    """
    x, y, sessions, _prev, classes = windows(regime=regime, **kw)
    model = _fit_model(x, y, len(classes))
    trained = {s.id: s for s in corpus_mod.corpus(kinds=("run",))}
    patches = sorted({trained[i].patch for i in set(sessions.tolist()) if i in trained})
    path = Path(path)
    model.save_weights(str(path.with_suffix(".safetensors")))
    path.with_suffix(".json").write_text(json.dumps({
        "classes": classes, "width": int(x.shape[-1]), "emb_dim": emb_dim_of(int(x.shape[-1])),
        "steps": int(x.shape[1]), "history_s": HISTORY_S,
        "frame_hz": FRAME_HZ, "state_f": STATE_F, "event_f": EVENT_F, "event_kinds": list(EVENT_KINDS),
        "regime": regime, "patch": patches[0] if len(patches) == 1 else patches,
        "norm": NORM, "encoder": kw.get("encoder", DEFAULT),
        "trained_on": sorted(set(sessions.tolist())), "windows": int(len(x)),
        "written": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, indent=1))
    print(f"head: {path.with_suffix('.safetensors')} ({len(x)} windows, {len(classes)} classes {classes}, "
          f"cooldowns {regime}, patch {patches})")
    return path


def leave_one_session_out(regime="off", mode="session", transition_weight=1.0, k=3, **kw):
    x, y, sessions, prev, classes = windows(regime=regime, **kw)
    upcoming = near_change(y, sessions, k)
    print(f"regime {regime}: {len(x)} windows, {x.shape[1]} steps x {x.shape[2]} features, "
          f"{len(set(sessions))} sessions, classes {classes}, split by {mode}")
    print(f"  {'session':<16}" + "".join(f"{c:>10}" for c in classes))
    for name in sorted(set(sessions)):
        counts = np.bincount(y[sessions == name], minlength=len(classes))
        print(f"  {name:<16}" + "".join(f"{n:>10}" for n in counts))
    report = {}
    for held, tr, te in folds(sessions, y, mode):
        if not tr.any() or not te.any():
            continue
        extra = None if transition_weight == 1.0 else np.where(upcoming[tr], transition_weight, 1.0).astype(np.float32)
        pred, pred_tr = fit(x[tr], y[tr], x[te], len(classes), extra=extra)
        truth, fit_acc = y[te], float((pred_tr == y[tr]).mean())
        majority = np.bincount(y[tr], minlength=len(classes)).argmax()
        acc, base = float((pred == truth).mean()), float((truth == majority).mean())
        seen = float(max(np.bincount(truth, minlength=len(classes))) / len(truth))
        # The baseline a temporal model actually has to beat: intents are sticky, so guessing that
        # nothing changed since the last tick is strong and costs nothing.
        sticky = float((prev[te] == truth).mean())
        # Where the sticky guess is right almost always, per-window accuracy cannot tell two models
        # apart: what a temporal model is for is the moment the intent CHANGES. Sticky scores 0 there
        # by definition, so this is the only column where beating it means anything.
        changed = prev[te] != truth
        changed_acc = float((pred[changed] == truth[changed]).mean()) if changed.any() else None
        report[held] = {"windows": int(te.sum()), "accuracy": round(acc, 3), "train_fit": round(fit_acc, 3),
                        "train_majority_baseline": round(base, 3), "held_out_majority": round(seen, 3),
                        "sticky_baseline": round(sticky, 3), "changes": int(changed.sum()),
                        "accuracy_on_changes": None if changed_acc is None else round(changed_acc, 3),
                        "recall_on_changes": _recall(truth[changed], pred[changed], classes),
                        "transition_weight": transition_weight, "k": k,
                        "macro_f1": round(_macro_f1(truth, pred, len(classes)), 3),
                        "confusion": _confusion(truth, pred, classes)}
        print(f"\nheld out {held}: {int(te.sum())} windows  accuracy {acc:.3f}  "
              f"(train-majority {base:.3f}, held-out majority {seen:.3f}, STICKY {sticky:.3f})  "
              f"macro F1 {report[held]['macro_f1']:.3f}  [fits its own training set {fit_acc:.3f}]")
        print(f"    on the {int(changed.sum())} windows where the intent CHANGES: "
              + ("no change in this session" if changed_acc is None else f"{changed_acc:.3f} (sticky scores 0 there)"))
        if changed.any():
            print("    per-class recall there: " + ", ".join(
                f"{n} {v:.2f} (n={c})" for n, (v, c) in sorted(_recall(truth[changed], pred[changed], classes).items())))
        _print_confusion(truth, pred, classes)
    return report, classes


def near_change(y, sessions, k):
    """Windows whose label changes within the next `k` decisions of the same session.

    A training-time curriculum over the LABELS, which are targets: nothing here enters an
    observation, and evaluation is untouched. Within a session the rows are already in time order.
    """
    flag = np.zeros(len(y), bool)
    for name in set(sessions.tolist()):
        where = np.flatnonzero(sessions == name)
        for j, i in enumerate(where):
            ahead = where[j + 1: j + 1 + k]
            if len(ahead) and (y[ahead] != y[i]).any():
                flag[i] = True
    return flag


def _recall(truth, pred, classes):
    """Per-class recall, only for classes actually present."""
    out = {}
    for c, name in enumerate(classes):
        n = int((truth == c).sum())
        if n:
            out[name] = (round(float(((pred == c) & (truth == c)).sum() / n), 3), n)
    return out


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
    print("    truth \\ pred  " + "".join(f"{c:>10}" for c in classes))
    for t, name in enumerate(classes):
        if (truth == t).any():
            print(f"    {name:<13} " + "".join(f"{int(((truth == t) & (pred == p)).sum()):>10}" for p in range(len(classes))))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regime", default="normal", choices=("off", "normal", "unknown"))
    ap.add_argument("--patch", help="only runs on this balance patch (default: refuse to mix two)")
    ap.add_argument("--transition-weight", type=float, default=1.0,
                    help="multiply the training weight of windows whose label changes within --k decisions")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--recorder", default="loop", choices=("loop", "trial", "any"),
                    help="loop: agent/loop.py's runs (the default). trial: L4's own four-symbol logs")
    ap.add_argument("--encoder", default=DEFAULT)
    ap.add_argument("--hz", type=float, default=HZ)
    ap.add_argument("--decision-hz", type=float, default=DECISION_HZ)
    ap.add_argument("--split", default="session", choices=("session", "tail"),
                    help="session: the honest whole-recording split. tail: the control (see folds())")
    ap.add_argument("--save", metavar="PATH", help="train on every window of the regime (no holdout) and write the head there")
    ap.add_argument("--out", help="write the report as JSON here")
    a = ap.parse_args(argv)
    started = time.perf_counter()
    if a.save:
        save(a.save, a.regime, encoder=a.encoder, hz=a.hz, decision_hz=a.decision_hz,
             recorder=None if a.recorder == 'any' else a.recorder, patch=a.patch)
        print(f"\n{time.perf_counter() - started:.0f}s")
        return 0
    report, classes = leave_one_session_out(a.regime, a.split, a.transition_weight, a.k,
                                            encoder=a.encoder, hz=a.hz, decision_hz=a.decision_hz,
                                            recorder=None if a.recorder == 'any' else a.recorder, patch=a.patch)
    if a.out:
        Path(a.out).write_text(json.dumps({"regime": a.regime, "split": a.split, "recorder": a.recorder,
                                           "encoder": a.encoder,
                                           "norm": NORM, "classes": classes, "folds": report}, indent=1))
    print(f"\n{time.perf_counter() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
