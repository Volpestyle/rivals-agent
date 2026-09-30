"""Live learned policy: native BGR frames in, semantic actions plus camera degrees out.

One call per decision. The model is recurrent and was trained at 30 Hz (one step = 1/30 s), so call `step` once per
captured frame at about that rate and `reset()` whenever the episode restarts. No capture, pad or game IO happens
here: the caller owns every live guard and turns `Step` into pad input (camera degrees through the camera map).

A bundle is a directory with `bundle.json` naming its files (see `write_bundle`). The first bundle is the confirmed
NitroGen-tower no-history policy (docs/lanes/policy.md): offline press F1 0.30, yaw worse than zero motion.
Decision latency on the RTX 4080 SUPER with torch preprocessing: p50 25 ms, p95 31 ms.

    from policy.live_policy import LivePolicy
    policy = LivePolicy("D:/rivals-policy/bundles/ng-nohist-s1", device="cuda")
    step = policy.step(frame_bgr)          # uint8 HxWx3 BGR, the desktop capture
    step.held["jump"], step.yaw_deg, step.pitch_deg, step.yaw_deg_s
"""
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import time

STEP_S = 1 / 30
TRAIN_SIZE = (2560, 1440)       # every admitted recording; the crop view is 256x256 native pixels at this size
MAX_GAP_S = .5                  # a longer gap between frames carries no usable motion for bc2


@dataclass
class Step:
    """One decision. Actions are semantic (policy.range_bc.vocab.NAMES); only `live` actions are ever set.

    held: the action should be held down during this step. press/release: edges this step (a tap is press and
    release in one step, with held False; hold it for one step). yaw_deg/pitch_deg: requested rotation over this
    step, yaw positive right, pitch positive DOWN; *_deg_s is the same as a rate. probs: raw (hold, press, release)
    probabilities. latency_ms: preprocessing + model on this call."""
    held: dict
    press: dict
    release: dict
    yaw_deg: float
    pitch_deg: float
    yaw_deg_s: float
    pitch_deg_s: float
    probs: dict
    latency_ms: float
    index: int

    def as_dict(self):
        return asdict(self)


def _sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_bundle(directory, *, checkpoint, vision, vision_config, evaluation, name, notes=""):
    """Record a bundle's files, hashes, TRAIN-chosen thresholds and live action mask in bundle.json."""
    from policy.range_bc import vocab
    directory = Path(directory)
    evaluation_data = json.loads((directory / evaluation).read_text())
    calibration = evaluation_data["threshold_calibration"]["actions"]
    bundle = {"format": "rivals-live-policy-bundle-v1", "name": name, "kind": "encoder_h1", "notes": notes,
              "step_s": STEP_S, "train_size": list(TRAIN_SIZE), "actions": list(vocab.NAMES),
              "files": {}, "thresholds": {n: calibration[n]["threshold"] for n in vocab.NAMES},
              "live": {n: bool(calibration[n]["live"]) for n in vocab.NAMES}}
    for key, file in (("checkpoint", checkpoint), ("vision", vision), ("vision_config", vision_config),
                      ("evaluation", evaluation)):
        bundle["files"][key] = {"path": file, "sha256": _sha256(directory / file)}
    (directory / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n")
    return bundle


def write_bc2_bundle(directory, *, checkpoint, report, tag="selected", name, notes="",
                     vision="vision.safetensors", vision_config="siglip2-large-config.json",
                     buttons=None, buttons_evaluation=None, camera_decode="mean"):
    """A policy.bc2 bundle: Policy2 checkpoint, the NitroGen tower, and report.json's TRAIN-calibrated thresholds.
    Hybrid: `buttons` (an encoder_h1 checkpoint on the same tower features) and its evaluation.json replace the
    action head and thresholds; the camera stays bc2's. camera_decode: "mean" (expectation; the better onset
    direction on val) or "median"."""
    from policy.range_bc import vocab
    directory = Path(directory)
    rep = json.loads((directory / report).read_text())
    live = vocab.live_mask([10 ** 6] * vocab.N)
    bundle = {"format": "rivals-live-policy-bundle-v1", "name": name, "kind": "bc2", "notes": notes,
              "step_s": STEP_S, "train_size": list(TRAIN_SIZE), "actions": list(vocab.NAMES), "files": {},
              "thresholds": rep[tag]["thresholds"], "live": dict(zip(vocab.NAMES, map(bool, live))),
              "camera_decode": camera_decode}
    entries = [("checkpoint", checkpoint), ("vision", vision), ("vision_config", vision_config), ("report", report)]
    if buttons:
        calibration = json.loads((directory / buttons_evaluation).read_text())["threshold_calibration"]["actions"]
        bundle["thresholds"] = {n: calibration[n]["threshold"] for n in vocab.NAMES}
        entries += [("buttons", buttons), ("buttons_evaluation", buttons_evaluation)]
    for key, file in entries:
        bundle["files"][key] = {"path": file, "sha256": _sha256(directory / file)}
    (directory / "bundle.json").write_text(json.dumps(bundle, indent=2) + "\n")
    return bundle


def load_encoder_checkpoint(path, sha256):
    """An H1 encoder-head checkpoint (EXPLORATORY or CONFIRM tag) from the chunk trainer."""
    import torch
    from policy.range_bc.explore_chunks_train import FORMAT
    from policy.range_bc.explore_encoder import EncoderPolicy
    from policy.range_bc.model import Config
    if _sha256(path) != sha256:
        raise ValueError(f"{path}: checkpoint hash differs from bundle.json")
    payload = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
    recipe = payload["recipe"]
    if payload["format"] != FORMAT or recipe["horizon"] != 1:
        raise ValueError("expected an H1 range-chunks checkpoint")
    model = EncoderPolicy(Config.from_dict(recipe["config"]), horizon=1)
    model.load_state_dict(payload["model"], strict=True)
    return model.eval(), recipe


class LivePolicy:
    def __init__(self, bundle_dir, *, device="cuda", thresholds="train", resize=True, preprocess="torch",
                 camera_decode=None):
        """thresholds: "train" (per-action, TRAIN-calibrated to human press counts) or a float for all actions.
        resize: scale frames that are not 2560x1440 to it (area) first, so the crop view keeps its training field
        of view. Otherwise a different size is refused.
        preprocess: "torch" computes the cache views on the model's device (area scaling is exact average pooling
        at 2560x1440, so it stays off the CPU the game needs); "ffmpeg" runs the exact cache graph on the CPU."""
        from policy.range_bc import vocab
        from policy.range_bc.live_inference import EncoderPredictor, InProcessCachePreprocessor
        root = Path(bundle_dir)
        self.bundle = json.loads((root / "bundle.json").read_text())
        files = {k: (root / v["path"], v["sha256"]) for k, v in self.bundle["files"].items()}
        if preprocess not in ("torch", "ffmpeg"):
            raise ValueError("preprocess is torch or ffmpeg")
        self.kind, self.preprocess = self.bundle.get("kind", "encoder_h1"), preprocess
        if self.kind == "bc2":
            import torch
            from policy.bc2.features import load_tower
            from policy.bc2.model import Config, Policy2
            if preprocess != "torch":
                raise ValueError("bc2 bundles run with preprocess='torch'")
            for key in ("checkpoint", "vision", "vision_config"):
                if _sha256(files[key][0]) != files[key][1]:
                    raise ValueError(f"{files[key][0]}: hash differs from bundle.json")
            payload = torch.load(files["checkpoint"][0], map_location="cpu", weights_only=True)
            self.model = Policy2(Config(**payload["config"]))
            self.model.load_state_dict(payload["model"], strict=True)
            self.model.to(device).eval()
            self.tower = load_tower(files["vision"][0], files["vision_config"][0], device)
            self.predict = None
            self.buttons = None
            if "buttons" in files:
                self.buttons = load_encoder_checkpoint(*files["buttons"])[0].to(device).eval()
        else:
            model, self.recipe = load_encoder_checkpoint(*files["checkpoint"])
            # Training cache frames were full-range RGB decoded from YUV; the capture is already full-range BGR.
            self.predict = EncoderPredictor(model, InProcessCachePreprocessor(compact_bgr=True)
                                            if preprocess == "ffmpeg" else None, vision_path=files["vision"][0],
                                            vision_sha256=files["vision"][1], config_path=files["vision_config"][0],
                                            config_sha256=files["vision_config"][1], device=device)
        self.names = vocab.NAMES
        self.mask = tuple(bool(self.bundle["live"][n]) for n in self.names)
        self.levels = tuple(float(self.bundle["thresholds"][n]) if thresholds == "train" else float(thresholds)
                            for n in self.names)
        self.resize, self.device = resize, device
        self.camera_decode = camera_decode or self.bundle.get("camera_decode", "median")
        if self.camera_decode not in ("median", "mean"):
            raise ValueError("camera_decode is median or mean")
        self.reset()

    def reset(self):
        """Start a new episode: clear the recurrent state and the held-action memory."""
        from policy.range_bc import vocab
        if self.predict is not None:
            self.predict.state = None
        self.state, self.gray_prev, self.buttons_state, self.t_prev = None, None, None, None
        self.prev = {"held": [0] * vocab.N, "press": [0] * vocab.N, "release": [0] * vocab.N,
                     "known": [True] * vocab.N, "cy": vocab.ZERO_CLASS, "cp": vocab.ZERO_CLASS}
        self.index = 0

    @staticmethod
    def _check(frame):
        import numpy as np
        if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("uint8 HxWx3 BGR frame required")
        return frame if frame.flags.c_contiguous else np.ascontiguousarray(frame)

    def _frame(self, frame):
        frame = self._check(frame)
        h, w = frame.shape[:2]
        if (w, h) == TRAIN_SIZE:
            return frame
        if not self.resize:
            raise ValueError(f"frame {w}x{h} differs from training {TRAIN_SIZE}; pass resize=True")
        import cv2
        return cv2.resize(frame, TRAIN_SIZE, interpolation=cv2.INTER_AREA if w > TRAIN_SIZE[0] else cv2.INTER_LINEAR)

    def _views(self, frame):
        """The cache's global (144x256) and crop (128x128) views: RGB float [1, 3, H, W] holding uint8 values."""
        import torch
        from policy.bc2.features import views_from_bgr
        if frame.shape[:2] != TRAIN_SIZE[::-1] and not self.resize:
            raise ValueError(f"frame {frame.shape[:2]} differs from training {TRAIN_SIZE[::-1]}")
        return views_from_bgr(torch.from_numpy(frame).to(self.device, non_blocking=True))

    def _bc2_predict(self, frame, t=None):
        """policy.bc2: tower features of both views plus motion observed since the previous step's frame."""
        import torch
        from policy.bc2.features import tower_features
        from policy.bc2.model import gray_small
        with torch.inference_mode():
            rgb = [v.permute(0, 2, 3, 1).to(torch.uint8) for v in self._views(frame)]
            feats = tower_features(self.tower, rgb)[None, None]      # both views in one tower batch
            gray = [gray_small(v) for v in rgb]
            if self.model.config.hires:
                from policy.bc2.model import gray_full
                gray[0] = gray_full(rgb[0])
            now = time.perf_counter() if t is None else t
            gap = None if self.t_prev is None else now - self.t_prev
            if gap is None or gap > MAX_GAP_S:        # no usable previous frame: no motion this step
                prev = gray
            else:
                prev = self.gray_prev
            dt = torch.full((1, 1), min(3., max(1., (gap or STEP_S) / STEP_S)), device=feats.device)
            self.t_prev = now
            green = None
            if self.model.config.use_green:
                from policy.bc2.model import green_profile
                green = green_profile(rgb[0]).to(torch.float16)[None]
            with torch.autocast("cuda", dtype=torch.bfloat16):
                acts, cams, self.state = self.model(feats, prev[0][None], gray[0][None], prev[1][None],
                                                    gray[1][None], self.state, green, dt)
            self.gray_prev = gray
            acts, cams = acts.float(), cams.float()
            if self.buttons is not None:          # hybrid: incumbent action head on the same tower features
                from policy.range_bc import steps
                zero = torch.zeros(1, 1, steps.PREV_DIM, device=feats.device)
                acts, _, self.buttons_state = self.buttons(feats[:, :, 0], feats[:, :, 1], None, zero,
                                                           self.buttons_state)
            if not (bool(torch.isfinite(acts).all()) and bool(torch.isfinite(cams).all())):
                raise ValueError("nonfinite model outputs")
            return torch.sigmoid(acts[0, 0]).tolist(), torch.softmax(cams[0, 0], -1).tolist()

    def _torch_predict(self, frame):
        """EncoderPredictor.__call__ with the cache views computed on the device."""
        import torch
        from torch.nn import functional as F
        from policy.range_bc import steps
        from policy.range_bc.explore_encoder import pool_tokens
        p = self.predict
        with torch.inference_mode():
            pixels = []
            for v in self._views(frame):
                v = F.interpolate(v, (256, 256), mode="bilinear", align_corners=False, antialias=True)
                pixels.append((v / 127.5 - 1).to(p.tower_dtype))
            tokens = p.tower(pixel_values=torch.cat(pixels)).last_hidden_state
            features = pool_tokens(tokens).to(torch.float16)
            feats = features[0:1, None], features[1:2, None], torch.zeros(1, 1, 1, device=p.device)
            prev = torch.tensor(steps.prev_vector(self.prev), dtype=torch.float32, device=p.device)[None, None]
            acts, cams, p.state = p.model(*feats, prev, p.state, regime=p.regime)
            if not (bool(torch.isfinite(acts).all()) and bool(torch.isfinite(cams).all())):
                raise ValueError("nonfinite model outputs")
            return torch.sigmoid(acts[0, 0]).tolist(), torch.softmax(cams[0, 0], -1).tolist()

    def step(self, frame_bgr, t=None):
        """t: the frame's capture time in seconds (any monotonic clock); default the call time. bc2 models use the
        interval between consecutive frames (clamped to 1-3 steps of 33 ms); after MAX_GAP_S they see no motion."""
        from policy.range_bc import executor, vocab
        started = time.perf_counter()
        if self.kind == "bc2":
            probs, cameras = self._bc2_predict(self._check(frame_bgr), t)
        elif self.preprocess == "torch":
            probs, cameras = self._torch_predict(self._check(frame_bgr))
        else:
            probs, cameras = self.predict(self._frame(frame_bgr), self.prev)
        held_p, press_p, release_p = (probs[i * vocab.N:(i + 1) * vocab.N] for i in range(3)) \
            if len(probs) == 3 * vocab.N else probs
        held, press, release = [], [], []
        for i, level in enumerate(self.levels):
            h, p, r = executor.decode_step(held_p, press_p, release_p, self.prev["held"], self.mask, threshold=level)
            held.append(h[i]), press.append(p[i]), release.append(r[i])
        yaw_p, pitch_p = cameras if len(cameras) == 2 else (cameras[:vocab.CAMERA_CLASSES], cameras[vocab.CAMERA_CLASSES:])
        cy, cp = vocab.median_class(yaw_p), vocab.median_class(pitch_p)
        if self.camera_decode == "mean":      # expectation: commits to the likelier side at turn onsets
            reps = [vocab.class_degrees(k) for k in range(vocab.CAMERA_CLASSES)]
            yaw, pitch = (sum(p * r for p, r in zip(axis, reps)) for axis in (yaw_p, pitch_p))
            cy, cp = vocab.camera_class(yaw), vocab.camera_class(pitch)
        else:
            yaw, pitch = vocab.class_degrees(cy), vocab.class_degrees(cp)
        self.prev = {"held": held, "press": press, "release": release, "known": [True] * vocab.N, "cy": cy, "cp": cp}
        self.index += 1
        named = lambda bits: {n: bool(b) for n, b in zip(self.names, bits)}
        return Step(held=named(held), press=named(press), release=named(release), yaw_deg=yaw, pitch_deg=pitch,
                    yaw_deg_s=yaw / STEP_S, pitch_deg_s=pitch / STEP_S,
                    probs={n: (held_p[i], press_p[i], release_p[i]) for i, n in enumerate(self.names)},
                    latency_ms=(time.perf_counter() - started) * 1000, index=self.index - 1)

    def close(self):
        if self.predict is not None and self.predict.preprocess is not None:
            self.predict.close()


def main(argv=None):
    """Bundle writing and a latency benchmark on recorded or synthetic frames."""
    import argparse
    p = argparse.ArgumentParser(description=main.__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("bundle")
    w.add_argument("dir")
    w.add_argument("--name", required=True)
    w.add_argument("--notes", default="")
    b = sub.add_parser("bench")
    b.add_argument("dir")
    b.add_argument("--device", default="cuda")
    b.add_argument("--frames", nargs="*", help="image files; default synthetic noise")
    b.add_argument("--n", type=int, default=100)
    b.add_argument("--out")
    a = p.parse_args(argv)
    if a.cmd == "bundle":
        print(json.dumps(write_bundle(a.dir, checkpoint="epoch-26.pt", vision="vision.safetensors",
                                      vision_config="siglip2-large-config.json", evaluation="evaluation.json",
                                      name=a.name, notes=a.notes), indent=2))
        return 0
    import numpy as np
    policy = LivePolicy(a.dir, device=a.device)
    if a.frames:
        import cv2
        frames = [cv2.imread(f) for f in a.frames]
    else:
        rng = np.random.default_rng(0)
        frames = [rng.integers(0, 256, (1440, 2560, 3), dtype=np.uint8) for _ in range(4)]
    for i in range(5):
        policy.step(frames[i % len(frames)])
    policy.reset()
    times, steps = [], []
    for i in range(a.n):
        s = policy.step(frames[i % len(frames)])
        times.append(s.latency_ms)
        steps.append(s)
    q = lambda x: float(np.percentile(times, x))
    result = {"device": a.device, "n": a.n, "p50_ms": q(50), "p95_ms": q(95), "max_ms": max(times),
              "gpu": __import__("torch").cuda.get_device_name() if a.device == "cuda" else None,
              "last": steps[-1].as_dict()}
    print(json.dumps(result, indent=2))
    if a.out:
        Path(a.out).write_text(json.dumps(result, indent=2) + "\n")
    policy.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
