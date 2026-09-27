"""Fixed median yaw evaluation on recorded frozen-dev pixels; no threshold search."""
import torch

from . import metrics, steps, train, vocab
from .explore_camera import sent_prediction
from .spatial_yaw_metrics import retention, yaw_slices


@torch.no_grad()
def evaluate_model(model, arrays, live_mask, thresholds, *, device="cpu", chunk=steps.WINDOW):
    model.eval()
    train.require(not model.config.history, "evaluation requires the frozen no-history candidate")
    # Same chunk execution and recurrent carry for both predictions. No extra
    # teacher/self-fed sweep: with no history their inputs are identical.
    runs = {name: [] for name in ("base", "candidate", "base_fixed05", "candidate_fixed05")}
    nll = {name: {"n": 0, "nll_sum": 0.} for name in ("real", "zero_spatial")}
    logit_rows = 0
    for arr in arrays:
        pitch_known = train._pitch_known(arr.session)
        for start, end in arr.runs:
            records = steps.step_records(arr.session, start, end, lag=0)
            state = None
            held = {name: [0]*vocab.N for name in runs}
            outputs = {name: [] for name in runs}
            for offset in range(start, end, chunk):
                rows = torch.arange(offset, min(end, offset+chunk))
                frames = [x[None].to(device) for x in arr.frames(rows)]
                prev = arr.prev[rows][None].to(device)
                actions, camera, state, base_camera, zero_camera = model.forward_pair(*frames, prev, state,
                                                                                     include_zero=True)
                train.require(torch.equal(camera[:, :, 1], base_camera[:, :, 1]), "pitch logits changed")
                train.require(bool(torch.isfinite(actions).all()) and bool(torch.isfinite(camera).all()),
                              "nonfinite evaluation logits")
                p = actions[0].sigmoid().cpu().tolist()
                cameras = {"base": base_camera[0].softmax(-1).cpu().tolist(),
                           "candidate": camera[0].softmax(-1).cpu().tolist()}
                mask = arr.valid[rows] & arr.camera_known[rows, 0]
                target = arr.camera[rows, 0]
                for name, logits in (("real", camera), ("zero_spatial", zero_camera)):
                    values = -logits[0, :, 0].cpu().double().log_softmax(-1).gather(1, target[:, None])[:, 0]
                    nll[name]["n"] += int(mask.sum())
                    nll[name]["nll_sum"] += float(values[mask].sum())
                logit_rows += len(rows)
                for name in runs:
                    for i in range(len(rows)):
                        used = [.5]*vocab.N if name.endswith("_fixed05") else thresholds
                        prediction, _ = sent_prediction(p[i], cameras[name.removesuffix("_fixed05")][i],
                                                        held[name], live_mask, used, "median", pitch_known)
                        held[name] = prediction["held"]
                        outputs[name].append(prediction)
            for name in runs:
                train.require(len(records) == len(outputs[name]), "evaluation row alignment differs")
                runs[name].append(list(zip(records, outputs[name])))
    kept = retention(runs["base"], runs["candidate"])
    retention(runs["base_fixed05"], runs["candidate_fixed05"])
    kept.update(exact_pitch_logits=True, shared_frozen_action_logits=True, logit_rows=logit_rows)
    result = {"tag": "EXPLORATORY", "decoder": "median, pad-saturated, original CUDA TRAIN cutoffs",
              "mode": "offline recorded pixels; no previous-action input; recurrent state carried within each run",
              "limitation": "not a live rollout; no claim from teacher/self-fed gap closure",
              "retention": kept,
              "spatial_token_ablation": {"label": "out-of-distribution inference ablation, not a trained control",
                  "conditioning": "same real base 4x4 inputs and recurrent memory; only yaw readout tokens zeroed",
                  "yaw_nll": {k: {**v, "nll": v["nll_sum"]/v["n"] if v["n"] else None} for k,v in nll.items()}}}
    for name in runs:
        scored = metrics.evaluate(runs[name], self_fed=True)
        live = [scored["actions"][action] for c, action in enumerate(vocab.NAMES) if live_mask[c]]
        human, predicted = sum(r["true_presses"] for r in live), sum(r["pred_presses"] for r in live)
        n = scored["valid_steps"]
        result[name] = {"yaw": yaw_slices(runs[name]), "metrics": scored,
                        "press_rates": {"human_events": human, "predicted_events": predicted, "valid_frames": n,
                            "human_events_per_frame": human/n if n else None,
                            "predicted_events_per_frame": predicted/n if n else None,
                            "predicted_human_ratio": predicted/human if human else None}}
    return result
