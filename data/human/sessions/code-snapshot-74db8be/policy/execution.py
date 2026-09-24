"""Offline keyboard/mouse imitation. No executor or game-control imports."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import random
import subprocess
import tempfile

from agent.human_demos import DemoError, load_datasets

DOMAIN = "keyboard_mouse"
FORMAT = "rivals-execution-v1"
CHANNELS = ("held", "press", "release")


def torch_module():
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Install the execution dependency group to use this baseline") from exc
    return torch


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise DemoError(message)


def key_id(key):
    if not isinstance(key, dict):
        key = asdict(key)
    require(key["scan"] > 0, "zero scan code has no supported physical key identity")
    return "key:{scan}:{flags}".format(**key)


def snapshot_vk(key):
    if not isinstance(key, dict):
        key = asdict(key)
    vk = key["vk"]
    if vk == 16:
        return {42: 160, 54: 161}.get(key["scan"], vk)
    if vk in (17, 18):
        return (162 if vk == 17 else 164) + bool(key["flags"] & 2)
    return vk


def event_key(row):
    return key_id({**row, "flags": row["flags"] & 6})


@dataclass(frozen=True)
class ActionSpec:
    controls: tuple[str, ...]
    bins: int
    bin_ns: int
    domain: str = DOMAIN
    key_vks: tuple = ()

    def validate(self, domain=DOMAIN):
        require(domain == DOMAIN and self.domain == DOMAIN,
                "keyboard_mouse checkpoint is incompatible with pad/gamepad execution")
        require(self.bins > 0 and self.bin_ns > 0, "invalid action horizon")
        require(len(set(self.controls)) == len(self.controls), "duplicate controls")


def fit_spec(samples, bins, bin_ns):
    """Vocabulary uses training labels only, never held-session labels."""
    require(samples and all(s.split == "train" for s in samples), "spec requires train samples")
    keys = {}
    for sample in samples:
        for action in sample.future:
            rows = [asdict(k) for state in (action.held_start, action.held_end) for k in state.keys]
            rows += [{**e.payload, "flags": e.payload["flags"] & 6} for e in action.events if e.type == "key"]
            for row in rows:
                keys.setdefault(key_id(row), set()).add(snapshot_vk(row))
    return ActionSpec(tuple(sorted(keys)) + tuple(f"mouse:{i}" for i in range(1, 6)), bins, bin_ns,
                      key_vks=tuple((k, tuple(sorted(v))) for k, v in sorted(keys.items())))


def encode_state(state, spec):
    if not isinstance(state, dict):
        state = asdict(state)
    active = {key_id(k) for k in state["keys"]} | {f"mouse:{b}" for b in state["mouse_buttons"]}
    unknown = set(state["unknown_physical_vk"])
    aliases = dict(spec.key_vks)
    values, known = [], []
    for control in spec.controls:
        values.append(float(control in active))
        known.append(float(state["observed"] and
                           (control.startswith("mouse:") or not unknown.intersection(aliases.get(control, unknown)))))
    return values, known


def observation_input(observation, spec):
    """Accept only Sample.observation(), with no future field."""
    require("future" not in observation, "future labels must not enter model inputs")
    require(observation["control_type"] == DOMAIN, "wrong observation domain")
    require(all(f["composition_ns"] <= observation["anchor_ns"] for f in observation["frames"]),
            "future frame in observation")
    require(all(e["t_ns"] <= observation["anchor_ns"] for e in observation["past_events"]),
            "future input in observation")
    values, known = encode_state(observation["state"], spec)
    return [v * k for v, k in zip(values, known)] + known


def targets(future, spec):
    """Held state plus transition existence retain taps, not exact event timing.

    Repeated make/break events are not edges. Unknown-start key edge masks stay
    false for the whole bin. More than one real press or release is unsupported
    and masks both edge channels (held-end remains supervised).
    """
    torch = torch_module()
    require(len(future) == spec.bins, "action chunk shape differs from spec")
    y = torch.zeros(spec.bins, len(spec.controls), 3)
    mask = torch.zeros_like(y)
    motion = torch.zeros(spec.bins, 4)
    motion_mask = torch.zeros_like(motion)
    unseen, unsupported = set(), []
    lookup = {c: i for i, c in enumerate(spec.controls)}
    for b, action in enumerate(future):
        require(action.end_ns - action.start_ns == spec.bin_ns, "action bin duration mismatch")
        end, end_known = encode_state(action.held_end, spec)
        _, start_known = encode_state(action.held_start, spec)
        y[b, :, 0] = torch.tensor(end)
        mask[b, :, 0] = torch.tensor(end_known)
        mask[b, :, 1:] = torch.tensor(start_known)[:, None]
        active = {key_id(k) for k in action.held_start.keys}
        active.update(f"mouse:{i}" for i in action.held_start.mouse_buttons)
        unseen.update(key_id(k) for k in action.held_end.keys if key_id(k) not in lookup)
        counts = {}
        for event in action.events:
            require(action.start_ns < event.t_ns <= action.end_ns, "event outside action bin")
            row = event.payload
            changes = []
            if event.type == "key":
                changes = [(event_key(row), row["down"])]
            elif event.type == "mouse":
                changes = [(f"mouse:{i}", True) for i in row["buttons_down"]]
                changes += [(f"mouse:{i}", False) for i in row["buttons_up"]]
            elif event.type in ("focus", "pause"):
                raise DemoError("action bin crosses focus/pause boundary")
            for control, down in changes:
                if control not in lookup:
                    unseen.add(control)
                elif down != (control in active):
                    channel = 1 if down else 2
                    y[b, lookup[control], channel] = 1
                    counts[control, channel] = counts.get((control, channel), 0) + 1
                if down:
                    active.add(control)
                else:
                    active.discard(control)
        for control in {c for (c, _), count in counts.items() if count > 1}:
            mask[b, lookup[control], 1:] = 0
            unsupported.append((b, control))
        observed = action.held_start.observed and action.held_end.observed
        if action.relative_motion_known and observed:
            motion[b, :2] = torch.tensor([action.mouse_dx, action.mouse_dy])
            motion_mask[b, :2] = 1
        motion[b, 2:] = torch.tensor([action.wheel_vertical, action.wheel_horizontal])
        motion_mask[b, 2:] = float(observed)
    return y, mask, motion, motion_mask, unseen, unsupported


def decode_frames(refs, *, image_size=96, ffmpeg="ffmpeg", max_frames=20000):
    """One process/video selects exact decoded ordinals, with strict byte counts."""
    torch = torch_module()
    grouped = {}
    for ref in refs:
        grouped.setdefault(ref["video_path"], set()).add(ref["frame_index"])
    require(sum(map(len, grouped.values())) <= max_frames,
            "selected frames exceed RAM safety cap; reduce samples or increase --max-frames")
    decoded = {}
    for path, ordinals in grouped.items():
        indices = sorted(ordinals)
        require(indices and indices[0] >= 0, "invalid decoded frame ordinal")
        expression = "+".join(f"eq(n\\,{i})" for i in indices)
        with tempfile.TemporaryDirectory(prefix="rivals-frames-") as directory:
            script, raw = Path(directory) / "filter.txt", Path(directory) / "frames.rgb"
            script.write_text(f"select={expression},scale={image_size}:{image_size}:flags=bilinear", encoding="ascii")
            result = subprocess.run([str(ffmpeg), "-v", "error", "-nostdin", "-i", path,
                "-map", "0:v:0", "-filter_script:v", str(script), "-fps_mode", "passthrough",
                "-an", "-sn", "-pix_fmt", "rgb24", "-f", "rawvideo", str(raw)],
                capture_output=True, check=False)
            require(result.returncode == 0 and not result.stderr.strip(),
                    f"ffmpeg decode failed: {result.stderr.decode(errors='replace')}")
            size = image_size * image_size * 3
            require(raw.stat().st_size == len(indices) * size, "decoded ordinal count mismatch")
            with raw.open("rb") as stream:
                for index in indices:
                    frame = torch.frombuffer(bytearray(stream.read(size)), dtype=torch.uint8)
                    decoded[path, index] = frame.reshape(image_size, image_size, 3).permute(2, 0, 1).contiguous()
    return decoded


class Examples:
    def __init__(self, samples, spec, frames):
        self.samples, self.spec, self.frames = samples, spec, frames
        self.observations = [s.observation() for s in samples]
        self.previous = [observation_input(o, spec) for o in self.observations]
        self.labels = [targets(s.future, spec) for s in samples]

    def __len__(self):
        return len(self.samples)

    def batch(self, indices, device="cpu"):
        torch = torch_module()
        rgb = torch.stack([torch.stack([self.frames[f["video_path"], f["frame_index"]]
            for f in self.observations[i]["frames"]]) for i in indices]).to(device).float() / 255
        previous = torch.tensor([self.previous[i] for i in indices], device=device)
        labels = tuple(torch.stack([self.labels[i][j] for i in indices]).to(device) for j in range(4))
        return rgb, previous, labels


def make_model(spec, *, encoder="small", hidden=96, weights=None, download_weights=False):
    torch = torch_module()
    nn = torch.nn
    spec.validate()
    if encoder == "small":
        visual = nn.Sequential(nn.Conv2d(3, 16, 5, stride=2, padding=2), nn.ReLU(),
            nn.Conv2d(16, 32, 3, stride=2, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1), nn.Flatten())
        width = 32
    elif encoder == "resnet18":
        from torchvision.models import ResNet18_Weights, resnet18
        visual = resnet18(weights=ResNet18_Weights.DEFAULT if download_weights else None)
        if weights:
            visual.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
        visual.fc = nn.Identity()
        visual.requires_grad_(False)
        width = 512
    else:
        raise DemoError("unknown encoder")

    class ExecutionModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.visual = visual
            self.temporal = nn.GRU(width, hidden, batch_first=True)
            self.head = nn.Sequential(nn.Linear(hidden + 2 * len(spec.controls), hidden), nn.ReLU(),
                nn.Linear(hidden, spec.bins * (len(spec.controls) * 3 + 4)))
            self.register_buffer("rgb_mean", torch.tensor([.485, .456, .406]).view(1, 3, 1, 1))
            self.register_buffer("rgb_std", torch.tensor([.229, .224, .225]).view(1, 3, 1, 1))

        def forward(self, rgb, previous):
            n, t, c, h, w = rgb.shape
            x = rgb.reshape(n * t, c, h, w)
            if encoder == "resnet18":
                self.visual.eval()
                x = (x - self.rgb_mean) / self.rgb_std
            encoded = self.visual(x).reshape(n, t, width)
            _, state = self.temporal(encoded)
            output = self.head(torch.cat((state[-1], previous), dim=-1)).reshape(n, spec.bins, -1)
            return output[:, :, :-4].reshape(n, spec.bins, len(spec.controls), 3), output[:, :, -4:]

    return ExecutionModel()


def fit_statistics(examples):
    torch = torch_module()
    require(examples.samples and all(s.split == "train" for s in examples.samples), "statistics require train only")
    y, mask, motion, mm = [torch.stack([row[i] for row in examples.labels]) for i in range(4)]
    prior = (y * mask).sum(0) / mask.sum(0).clamp_min(1)
    mean = (motion * mm).sum((0, 1)) / mm.sum((0, 1)).clamp_min(1)
    scale = (((motion - mean).square() * mm).sum((0, 1)) / mm.sum((0, 1)).clamp_min(1)).sqrt().clamp_min(1)
    return {"prior": prior, "motion_mean": mean, "motion_scale": scale,
            "control_support": mask.sum((0, 1)), "control_positive": (y * mask).sum((0, 1)),
            "motion_support": mm.sum((0, 1))}


def masked_loss(logits, prediction, labels, stats):
    torch = torch_module()
    y, mask, motion, mm = labels
    mean, scale = (stats[k].to(prediction.device) for k in ("motion_mean", "motion_scale"))
    binary = torch.nn.functional.binary_cross_entropy_with_logits(logits, y, reduction="none")
    continuous = torch.nn.functional.smooth_l1_loss(prediction, (motion - mean) / scale, reduction="none")
    return (binary * mask).sum() / mask.sum().clamp_min(1) + (continuous * mm).sum() / mm.sum().clamp_min(1)


def train_model(model, examples, stats, *, epochs=5, batch_size=16, lr=.001, device="cpu", seed=0):
    torch = torch_module()
    require(epochs > 0 and batch_size > 0 and lr > 0, "invalid training settings")
    require(examples.samples and all(s.split == "train" for s in examples.samples), "training accepts only train sessions")
    model.to(device)
    optimizer = torch.optim.Adam((p for p in model.parameters() if p.requires_grad), lr=lr)
    rng, losses = random.Random(seed), []
    for _ in range(epochs):
        model.train()
        indices = list(range(len(examples)))
        rng.shuffle(indices)
        total = 0.
        for start in range(0, len(indices), batch_size):
            ids = indices[start:start + batch_size]
            rgb, previous, labels = examples.batch(ids, device)
            optimizer.zero_grad()
            logits, motion = model(rgb, previous)
            loss = masked_loss(logits, motion, labels, stats)
            require(bool(torch.isfinite(loss)), "nonfinite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.)
            optimizer.step()
            total += float(loss.detach()) * len(ids)
        losses.append(total / len(examples))
    return losses


def evaluate(model, examples, stats, *, batch_size=16, device="cpu"):
    """Fixed 0.5 threshold; metrics include support, never fit on val."""
    torch = torch_module()
    require(examples.samples and all(s.split == "val" for s in examples.samples), "evaluate requires val, never test")
    require(batch_size > 0, "batch size must be positive")
    model.to(device).eval()
    totals = {name: {**{key: torch.zeros(len(examples.spec.controls), 3) for key in
        ("support", "positive", "correct", "tp", "fp", "fn")},
        "motion_abs": torch.zeros(4), "motion_sq": torch.zeros(4), "motion_n": torch.zeros(4)}
        for name in ("model", "persistence", "train_prior")}
    with torch.no_grad():
        for start in range(0, len(examples), batch_size):
            rgb, previous, labels = examples.batch(list(range(start, min(start + batch_size, len(examples)))), device)
            logits, motion = model(rgb, previous)
            y, mask, target_motion, mm = [x.cpu() for x in labels]
            previous = previous.cpu()
            persistence = torch.zeros_like(y)
            persistence[..., 0] = previous[:, None, :len(examples.spec.controls)]
            persistence_mask = mask.clone()
            persistence_mask[..., 0] *= previous[:, None, len(examples.spec.controls):]
            predictions = {
                "model": (logits.cpu().sigmoid(), motion.cpu() * stats["motion_scale"] + stats["motion_mean"], mask),
                "persistence": (persistence, torch.zeros_like(target_motion), persistence_mask),
                "train_prior": (stats["prior"].expand_as(y), stats["motion_mean"].expand_as(target_motion), mask)}
            for name, (prob, counts, valid) in predictions.items():
                pred, truth = prob >= .5, y.bool()
                accum = totals[name]
                for key, value in {"support": valid, "positive": y * valid,
                        "correct": (pred == truth) * valid, "tp": (pred & truth) * valid,
                        "fp": (pred & ~truth) * valid, "fn": (~pred & truth) * valid}.items():
                    accum[key] += value.sum((0, 1))
                error = counts - target_motion
                accum["motion_abs"] += (error.abs() * mm).sum((0, 1))
                accum["motion_sq"] += (error.square() * mm).sum((0, 1))
                accum["motion_n"] += mm.sum((0, 1))
    reports = {}
    for name, accum in totals.items():
        controls = {}
        for i, control in enumerate(examples.spec.controls):
            controls[control] = {}
            for j, channel in enumerate(CHANNELS):
                n, pos, correct, tp, fp, fn = (float(accum[k][i, j]) for k in
                    ("support", "positive", "correct", "tp", "fp", "fn"))
                controls[control][channel] = {"support": int(n), "positive": int(pos),
                    "accuracy": correct / n if n else None,
                    "precision": tp / (tp + fp) if tp + fp else None,
                    "recall": tp / (tp + fn) if tp + fn else None,
                    "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}
        motion_report = {}
        for j, axis in enumerate(("dx", "dy", "wheel_vertical", "wheel_horizontal")):
            n = int(accum["motion_n"][j])
            motion_report[axis] = {"support": n,
                "mae_counts_per_bin": float(accum["motion_abs"][j]) / n if n else None,
                "rmse_counts_per_bin": (float(accum["motion_sq"][j]) / n) ** .5 if n else None}
        reports[name] = {"controls": controls, "motion": motion_report}
    reports["unseen_controls"] = sorted(set().union(*(row[4] for row in examples.labels)))
    reports["unseen_control_chunk_support"] = {control: sum(control in row[4] for row in examples.labels)
        for control in reports["unseen_controls"]}
    reports["unsupported_multi_edge_bins"] = sum(len(row[5]) for row in examples.labels)
    reports["samples"] = len(examples)
    reports["sessions"] = sorted({s.session_id for s in examples.samples})
    return reports


def settings_identity(dataset):
    review = json.loads(dataset.review_json)
    return {k: review["provenance"][k]["value"] for k in
            ("settings", "bindings", "game_patch", "cooldown_regime")}


def load_cohort(paths, splits):
    # Importer refuses sealed headers before reading payload. No unseal option.
    datasets = load_datasets(paths, splits=splits)
    require(datasets, "no sessions supplied")
    require(all(json.loads(d.review_json).get("device_scope", {}).get("kind") == "single_keyboard_mouse"
                for d in datasets), "device-handle normalization requires single_keyboard_mouse admission")
    identity = settings_identity(datasets[0])
    require(all(settings_identity(d) == identity for d in datasets),
            "settings/bindings/patch/cooldown mismatch; no mixed-context handling")
    artifacts = []
    for path, dataset in zip(paths, datasets):
        require(dataset.placement.split in ("train", "val"), "test access forbidden")
        # load_datasets rehashes original media before building any samples.
        artifacts.append({**asdict(dataset.placement), "artifact_sha256": fingerprint(path),
                          "media_sha256": dataset.media_sha256})
    return datasets, identity, artifacts


def save_checkpoint(path, model, spec, stats, config, provenance):
    torch = torch_module()
    payload = {"format": FORMAT, "action_spec": asdict(spec), "config": config,
        "provenance": provenance, "statistics": {k: v.cpu() for k, v in stats.items()},
        "model": {k: v.detach().cpu() for k, v in model.state_dict().items()}}
    with Path(path).open("xb") as stream:
        torch.save(payload, stream)


def load_checkpoint(path, *, domain=DOMAIN, device="cpu"):
    require(domain == DOMAIN, "keyboard_mouse checkpoint is incompatible with pad/gamepad execution")
    torch = torch_module()
    payload = torch.load(path, map_location="cpu", weights_only=True)
    require(payload.get("format") == FORMAT, "unsupported checkpoint")
    spec = ActionSpec(**{**payload["action_spec"], "controls": tuple(payload["action_spec"]["controls"])})
    spec.validate(domain)
    model = make_model(spec, encoder=payload["config"]["encoder"], hidden=payload["config"]["hidden"])
    model.load_state_dict(payload["model"], strict=True)
    return model.to(device).eval(), spec, payload


def gather_samples(datasets, options, limit):
    require(limit > 0, "max samples must be positive")
    result = []
    for dataset in datasets:
        count = 0
        for sample in dataset.samples(**options):
            result.append(sample)
            count += 1
            if count >= limit:
                break
        require(count > 0, f"no eligible samples in {dataset.placement.session_id}")
    return result


def cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fit = sub.add_parser("fit", help="fit on train and report held-session validation")
    fit.add_argument("--train", nargs="+", required=True)
    fit.add_argument("--val", nargs="+", required=True)
    fit.add_argument("--checkpoint", required=True)
    fit.add_argument("--encoder", choices=("small", "resnet18"), default="small")
    fit.add_argument("--weights", help="local torchvision ResNet18 state_dict")
    fit.add_argument("--download-weights", action="store_true")
    for flag, default in (("hidden", 96), ("epochs", 5), ("seed", 0), ("history-ms", 500),
                          ("frame-step-ms", 100), ("bin-ms", 20), ("bins", 10), ("stride-ms", 100),
                          ("image-size", 96), ("max-samples-per-session", 1000)):
        fit.add_argument("--" + flag, type=int, default=default)
    fit.add_argument("--lr", type=float, default=.001)
    ev = sub.add_parser("evaluate", help="repeat saved-checkpoint validation; test forbidden")
    ev.add_argument("--val", nargs="+", required=True)
    ev.add_argument("--checkpoint", required=True)
    for command in (fit, ev):
        command.add_argument("--splits", required=True)
        command.add_argument("--report", required=True)
        command.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
        command.add_argument("--batch-size", type=int, default=16)
        command.add_argument("--max-frames", type=int, default=20000)
        command.add_argument("--ffmpeg", default="ffmpeg")
        command.add_argument("--threads", type=int, default=2)
    args = parser.parse_args(argv)
    require(args.threads > 0, "threads must be positive")
    require(not Path(args.report).exists(), "report exists; choose a new output")
    torch = torch_module()
    torch.set_num_threads(args.threads)
    if args.command == "fit":
        require(not Path(args.checkpoint).exists(), "checkpoint exists; choose a new output")
        require(Path(args.report).resolve() != Path(args.checkpoint).resolve(), "report and checkpoint paths collide")
        require(args.image_size >= 16 and args.hidden > 0, "invalid model dimensions")
        require(not (args.weights and args.download_weights), "choose local weights or explicit download")
        require(args.encoder != "resnet18" or args.weights or args.download_weights,
                "frozen ResNet18 requires --weights or --download-weights")
        require(args.encoder == "resnet18" or not (args.weights or args.download_weights), "weights require resnet18")
        torch.manual_seed(args.seed)
        datasets, identity, artifacts = load_cohort(args.train + args.val, args.splits)
        train_sets, val_sets = datasets[:len(args.train)], datasets[len(args.train):]
        require(all(d.placement.split == "train" for d in train_sets) and
                all(d.placement.split == "val" for d in val_sets), "artifact split differs from requested role")
        options = {"history_ns": args.history_ms * 1_000_000, "frame_step_ns": args.frame_step_ms * 1_000_000,
            "bin_ns": args.bin_ms * 1_000_000, "bins": args.bins, "stride_ns": args.stride_ms * 1_000_000}
        config = {"encoder": args.encoder, "hidden": args.hidden, "image_size": args.image_size,
            "sample_options": options, "max_samples_per_session": args.max_samples_per_session,
            "epochs": args.epochs, "lr": args.lr, "seed": args.seed,
            "batch_size": args.batch_size, "device": args.device, "threads": args.threads,
            "weights_source": "torchvision.ResNet18_Weights.DEFAULT" if args.download_weights else args.weights,
            "weights_sha256": fingerprint(args.weights) if args.weights else None}
        training = gather_samples(train_sets, options, args.max_samples_per_session)
        validation = gather_samples(val_sets, options, args.max_samples_per_session)
        spec = fit_spec(training, args.bins, options["bin_ns"])
        model = make_model(spec, encoder=args.encoder, hidden=args.hidden,
                           weights=args.weights, download_weights=args.download_weights)
        provenance = {"registry_sha256": fingerprint(args.splits), "settings": identity,
            "settings_sha256": hashlib.sha256(canonical(identity).encode()).hexdigest(), "artifacts": artifacts,
            "torch_version": str(torch.__version__), "source_sha256": fingerprint(__file__),
            "alignment": {d.placement.session_id: json.loads(d.review_json)["alignment"] for d in datasets}}
    else:
        model, spec, payload = load_checkpoint(args.checkpoint, device=args.device)
        config, provenance = payload["config"], payload["provenance"]
        require(fingerprint(args.splits) == provenance["registry_sha256"], "split registry differs from checkpoint")
        datasets, identity, artifacts = load_cohort(args.val, args.splits)
        require(all(d.placement.split == "val" for d in datasets), "evaluate only accepts val")
        expected = [a for a in provenance["artifacts"] if a["split"] == "val"]
        require(sorted(artifacts, key=lambda a: a["session_id"]) == sorted(expected, key=lambda a: a["session_id"]),
                "validation artifacts differ from checkpoint; no test or new tuning cohort permitted")
        require(identity == provenance["settings"], "settings differ from checkpoint")
        validation = gather_samples(datasets, config["sample_options"], config["max_samples_per_session"])
        training = []
    refs = [f for s in training + validation for f in s.observation()["frames"]]
    frames = decode_frames(refs, image_size=config["image_size"], ffmpeg=args.ffmpeg, max_frames=args.max_frames)
    held = Examples(validation, spec, frames)
    if args.command == "fit":
        train = Examples(training, spec, frames)
        stats = fit_statistics(train)
        losses = train_model(model, train, stats, epochs=args.epochs, batch_size=args.batch_size,
                             lr=args.lr, device=args.device, seed=args.seed)
        save_checkpoint(args.checkpoint, model, spec, stats, config, provenance)
    else:
        stats, losses = payload["statistics"], None
    report = {"format": FORMAT, "domain": DOMAIN, "config": config, "provenance": provenance,
        "action_spec": asdict(spec), "training_loss": losses,
        "training_support": {control: {channel: {
            "known": int(stats["control_support"][i, j]),
            "positive": int(stats["control_positive"][i, j])} for j, channel in enumerate(CHANNELS)}
            for i, control in enumerate(spec.controls)},
        "validation": evaluate(model, held, stats, batch_size=args.batch_size, device=args.device),
        "checkpoint_sha256": fingerprint(args.checkpoint),
        "claim": "Offline validation only; no gameplay competence or pad compatibility demonstrated."}
    with Path(args.report).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"Wrote {args.report}; validation samples={len(held)}; domain={DOMAIN}")


if __name__ == "__main__":
    cli()
