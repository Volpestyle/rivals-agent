"""EXPLORATORY camera decoders and an inference-only conditioning diagnostic.

Shared recorded features, independent recurrent states and executed histories for
each decoder. No future frame is an input. The zero-feature ablation is a
distribution-shift sensitivity test, not a separately trained history-only model.
"""

import time

import torch
import torch.nn.functional as F

from . import executor, steps, train, vocab

DECODERS = ("median", "mode", "expectation")


def decode_camera(probabilities, decoder):
    """CPU probability lists -> exact requested degrees before pad saturation."""
    if decoder == "median":
        return vocab.class_degrees(vocab.median_class(probabilities))
    if decoder == "mode":
        return vocab.class_degrees(max(range(len(probabilities)), key=probabilities.__getitem__))
    if decoder == "expectation":
        return sum(p * vocab.class_degrees(c) for c, p in enumerate(probabilities))
    raise ValueError(f"unknown camera decoder {decoder}")


def decode_buttons(probabilities, previous, live_mask, thresholds):
    """Per-action cutoffs with the existing executor's exact Python-float rule."""
    result = [[0] * vocab.N for _ in range(3)]
    # Usually only a few unique cutoffs: reuse each scalar decode across actions.
    for threshold in sorted(set(thresholds)):
        decoded = executor.decode_step(*probabilities, previous, live_mask, threshold=threshold)
        for c, value in enumerate(thresholds):
            if value == threshold:
                for channel in range(3):
                    result[channel][c] = decoded[channel][c]
    return tuple(result)


def sent_prediction(probabilities, camera, previous, live_mask, thresholds, decoder, pitch_known):
    held, press, release = decode_buttons(probabilities, previous, live_mask, thresholds)
    yaw, pitch = executor.saturate(*(decode_camera(axis, decoder) for axis in camera))
    pitch = pitch if pitch_known else None
    prediction = {"held": list(map(float, held)), "press": list(map(float, press)),
                  "release": list(map(float, release)), "yaw": yaw, "pitch": pitch}
    feedback = {"held": held, "press": press, "release": release, "known": [True] * vocab.N,
                "camera_known": True, "cy": vocab.camera_class(yaw),
                "cp": vocab.camera_class(pitch) if pitch is not None else None}
    return prediction, feedback


@torch.no_grad()
def predict_suite(model, arrays, live_mask, conditions, *, device="mps", chunk=steps.WINDOW, progress=None):
    """TF and self-fed runs for {(threshold-name, camera-decoder): thresholds}.

    Visual encoders run once. The self-fed core uses a batch of independent
    recurrent states, each driven by its own executed camera and button history.
    Each TF condition still uses the human previous input, as in round 2.
    """
    model.eval()
    names = list(conditions)
    count = len(names)
    reported = time.perf_counter()
    results = {name: {"teacher": [], "teacher_camera": [], "self": []} for name in names}
    for arr in arrays:
        pk = train._pitch_known(arr.session)
        for a, b in arr.runs:
            records = steps.step_records(arr.session, a, b, lag=arr.lag)
            tf_state = sf_state = None
            feedback = [None] * count
            tf_held = [[0] * vocab.N for _ in names]
            sf_held = [[0] * vocab.N for _ in names]
            outputs = {name: {"teacher": [], "teacher_camera": [], "self": []} for name in names}
            for start in range(a, b, chunk):
                if progress and time.perf_counter() - reported >= 30:
                    progress(f"Six decode rollouts: {arr.session.session_id}, row {start}, run end {b}")
                    reported = time.perf_counter()
                rows = torch.arange(start, min(b, start + chunk))
                frames = (x[None].to(device) for x in train._frames(model, arr, rows))
                prev = arr.prev[rows][None].to(device)
                feats = model.features(*frames, 1, len(rows), prev)
                regime = arr.regime[rows][None].to(device)
                ta, tc, tf_state = model.step(feats, prev, tf_state, regime=regime)
                tp, tm = ta[0].sigmoid().cpu().tolist(), tc[0].softmax(-1).cpu().tolist()
                for i in range(len(rows)):
                    own_prev = torch.tensor([steps.prev_vector(p) for p in feedback], device=device)[:, None]
                    sa, sc, sf_state = model.step(feats[:, i:i + 1].expand(count, -1, -1), own_prev, sf_state,
                                                  regime=regime[:, i:i + 1].expand(count, -1))
                    sp = sa[:, 0].sigmoid().cpu().tolist()
                    sm = sc[:, 0].softmax(-1).cpu().tolist()
                    for j, name in enumerate(names):
                        decoder, thresholds = name[1], conditions[name]
                        teacher, _ = sent_prediction(tp[i], tm[i], tf_held[j], live_mask, thresholds, decoder, pk)
                        tf_held[j] = teacher["held"]
                        self_fed, feedback[j] = sent_prediction(sp[j], sm[j], sf_held[j], live_mask,
                                                               thresholds, decoder, pk)
                        sf_held[j] = self_fed["held"]
                        raw_camera = {**teacher, "yaw": decode_camera(tm[i][0], decoder),
                                      "pitch": decode_camera(tm[i][1], decoder) if pk else None}
                        outputs[name]["teacher"].append(teacher)
                        outputs[name]["teacher_camera"].append(raw_camera)
                        outputs[name]["self"].append(self_fed)
            for name in names:
                for mode in outputs[name]:
                    results[name][mode].append(list(zip(records, outputs[name][mode])))
    return results


@torch.no_grad()
def conditioning_nll(model, arrays, *, device="mps", chunk=steps.WINDOW):
    """H=1 checkpoint camera NLL: true history held fixed, real vs zero features.

    Both recurrent states reset at each eligible run and carry across chunks.
    Labels are masked per axis. Moving-sign NLL conditions on a nonzero target
    and a nonzero predicted class; it measures direction separately from motion.
    """
    train.require(model.horizon == 1, "conditioning pre-step is the H=1 control")
    model.eval()
    sums = {mode: {axis: {"n": 0, "nll_sum": 0., "moving_n": 0, "moving_sign_nll_sum": 0.}
                   for axis in ("yaw", "pitch")} for mode in ("visual", "zero_features")}
    presses = {mode: {name: {"n": 0, "nll_sum": 0., "positive_n": 0, "positive_nll_sum": 0.}
                      for name in vocab.NAMES} for mode in sums}
    for arr in arrays:
        for a, b in arr.runs:
            states = {mode: None for mode in sums}
            for start in range(a, b, chunk):
                rows = torch.arange(start, min(b, start + chunk))
                frames = (x[None].to(device) for x in train._frames(model, arr, rows))
                prev = arr.prev[rows][None].to(device)
                feats = model.features(*frames, 1, len(rows), prev)
                for mode in sums:
                    used = feats if mode == "visual" else torch.zeros_like(feats)
                    actions, camera, states[mode] = model.step(used, prev, states[mode],
                                                        regime=arr.regime[rows][None].to(device))
                    target_press = arr.act[rows, 1].double()
                    press_mask = arr.act_known[rows, 1] & arr.valid[rows, None]
                    press_nll = F.binary_cross_entropy_with_logits(
                        actions[0, :, 1].cpu().double(), target_press, reduction="none")
                    for c, name in enumerate(vocab.NAMES):
                        mask = press_mask[:, c]
                        positive = mask & (target_press[:, c] > .5)
                        item = presses[mode][name]
                        item["n"] += int(mask.sum())
                        item["nll_sum"] += float(press_nll[:, c][mask].sum())
                        item["positive_n"] += int(positive.sum())
                        item["positive_nll_sum"] += float(press_nll[:, c][positive].sum())
                    logp = F.log_softmax(camera[0].cpu().double(), dim=-1)
                    target = arr.camera[rows]
                    known = arr.camera_known[rows] & arr.valid[rows, None]
                    nll = -logp.gather(-1, target[..., None]).squeeze(-1)
                    # Stable conditional sign probabilities, excluding zero.
                    negative = torch.logsumexp(logp[..., :vocab.ZERO_CLASS], dim=-1)
                    positive = torch.logsumexp(logp[..., vocab.ZERO_CLASS + 1:], dim=-1)
                    nonzero = torch.logaddexp(negative, positive)
                    sign_nll = nonzero - torch.where(target < vocab.ZERO_CLASS, negative, positive)
                    for axis, name in enumerate(("yaw", "pitch")):
                        mask = known[:, axis]
                        moving = mask & (target[:, axis] != vocab.ZERO_CLASS)
                        item = sums[mode][name]
                        item["n"] += int(mask.sum())
                        item["nll_sum"] += float(nll[:, axis][mask].sum())
                        item["moving_n"] += int(moving.sum())
                        item["moving_sign_nll_sum"] += float(sign_nll[:, axis][moving].sum())
    for axes in sums.values():
        for item in axes.values():
            item["nll"] = item["nll_sum"] / item["n"] if item["n"] else None
            item["moving_sign_nll"] = (item["moving_sign_nll_sum"] / item["moving_n"]
                                        if item["moving_n"] else None)
    for actions in presses.values():
        for item in actions.values():
            item["nll"] = item["nll_sum"] / item["n"] if item["n"] else None
            item["positive_nll"] = (item["positive_nll_sum"] / item["positive_n"]
                                     if item["positive_n"] else None)
    return {"tag": "EXPLORATORY", "conditioning": "same teacher action history, real versus zero visual features",
            "limitation": "zero-feature inference ablation is out of distribution; not a trained history-only control",
            "axes": sums, "press": presses}
